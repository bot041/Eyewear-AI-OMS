from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role
from app.services.prediction import predict_sla, enrich_prediction_with_llm, ORDER_STAGES, get_sla_hours
from app.services.forecasting import record_consumption
from app.services.alerts import trigger_high_risk_alerts

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/", response_model=List[schemas.OrderOut])
def list_orders(
    status: Optional[str] = Query(None),
    lens_type: Optional[str] = Query(None),
    store_location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Order)
    if status:
        query = query.filter(models.Order.current_status == status)
    if lens_type:
        query = query.filter(models.Order.lens_type == lens_type)
    if store_location:
        query = query.filter(models.Order.store_location == store_location)
    return query.order_by(models.Order.created_at.desc()).all()


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/", response_model=schemas.OrderOut)
async def create_order(
    payload: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    inv = db.query(models.Inventory).filter(
        models.Inventory.power == payload.power,
        models.Inventory.lens_type == payload.lens_type,
        models.Inventory.coating == payload.coating,
    ).first()
    available = inv.quantity > 0 if inv else False

    count = db.query(models.Order).count()
    order = models.Order(
        order_number=f"ORD{str(count + 1).zfill(4)}",
        customer_name=payload.customer_name,
        power=payload.power,
        lens_type=payload.lens_type,
        lens_index=payload.lens_index,
        coating=payload.coating,
        frame=payload.frame,
        store_location=payload.store_location,
        source=payload.source or "Website",
        inventory_available=available,
        procurement_needed=not available,
        current_status="Order Placed",
        sla_hours=get_sla_hours(payload.lens_type),
    )
    db.add(order)
    db.flush()

    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)

    order.predicted_completion_hours = pred.predicted_completion_hours
    order.risk_score = pred.risk_score
    order.breach_flag = pred.breach_flag
    order.expected_delay_hours = pred.expected_delay_hours
    order.ai_explanation = pred.ai_explanation
    order.recommended_actions = pred.recommended_actions

    # Log prediction for accuracy tracking
    db.add(models.PredictionLog(
        order_id=order.id,
        predicted_completion=pred.predicted_completion_hours,
        prediction_date=datetime.utcnow(),
    ))

    # Reserve inventory and record consumption for demand forecasting
    if inv and available:
        inv.quantity -= 1
        record_consumption(db, inv.id, 1)

    # Proactive alerts for high-risk orders
    if order.risk_score >= 80:
        trigger_high_risk_alerts(db, threshold=80)

    db.add(models.OrderStatusHistory(order_id=order.id, status="Order Placed", changed_by=current_user.email))
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/status", response_model=schemas.OrderOut)
async def update_status(
    order_id: int,
    payload: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager", "qc_manager"])),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if payload.status not in ORDER_STAGES + ["QC Failed", "Rework"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    order.current_status = payload.status
    # Re-sync SLA hours to the latest lens-type mapping on every status update
    order.sla_hours = get_sla_hours(order.lens_type)
    db.add(models.OrderStatusHistory(order_id=order.id, status=payload.status, changed_by=current_user.email))

    if payload.reason:
        db.add(models.DelayLog(order_id=order.id, reason=payload.reason, logged_by=current_user.email))

    # Mark delivery time and compute actual completion for accuracy metrics
    if payload.status == "Delivered" and order.delivered_at is None:
        order.delivered_at = datetime.utcnow()
        actual_hours = (order.delivered_at - order.created_at).total_seconds() / 3600.0
        db.query(models.PredictionLog).filter(
            models.PredictionLog.order_id == order.id
        ).update({models.PredictionLog.actual_completion: actual_hours})

    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)

    order.predicted_completion_hours = pred.predicted_completion_hours
    order.risk_score = pred.risk_score
    order.breach_flag = pred.breach_flag
    order.expected_delay_hours = pred.expected_delay_hours
    order.ai_explanation = pred.ai_explanation
    order.recommended_actions = pred.recommended_actions

    # Proactive alerts for high-risk orders
    if order.risk_score >= 80:
        trigger_high_risk_alerts(db, threshold=80)

    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/delay-reason", response_model=schemas.DelayLogOut)
def add_delay_reason(
    order_id: int,
    payload: schemas.DelayReasonCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager", "qc_manager"])),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    log = models.DelayLog(order_id=order_id, reason=payload.reason, logged_by=current_user.email)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
