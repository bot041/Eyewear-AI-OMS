from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models
from app.dependencies import get_current_user
from app.schemas import DashboardResponse, DashboardKPIs, RiskOrderOut, InventoryOut, AlertOut
from datetime import datetime, timedelta





def _compute_forecast_accuracy(db: Session) -> int:
    rows = (
        db.query(models.PredictionLog)
        .filter(
            models.PredictionLog.actual_completion.isnot(None),
            models.PredictionLog.actual_completion > 0,
        )
        .all()
    )
    if not rows:
        return 0
    # Cap each order's percentage error at 100% and floor actual hours at 1 to avoid demo insta-deliveries skewing the metric.
    errors = [
        min(1.0, abs(r.actual_completion - r.predicted_completion) / max(r.actual_completion, 1.0))
        for r in rows
    ]
    mape = sum(errors) / len(errors)
    return max(0, min(100, int(100 - mape * 100)))

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    total_orders = db.query(models.Order).count()
    orders_at_risk = db.query(models.Order).filter(models.Order.risk_score >= 70).count()
    sla_breaches = db.query(models.Order).filter(models.Order.breach_flag == True).count()
    procurement_requests = db.query(models.Order).filter(models.Order.procurement_needed == True).count()

    inv_items = db.query(models.Inventory).all()
    healthy = sum(1 for i in inv_items if i.recommendation == "Healthy")
    health_score = int((healthy / len(inv_items)) * 100) if inv_items else 0
    forecast_accuracy = _compute_forecast_accuracy(db)

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    email_alerts_sent_today = (
        db.query(models.Alert)
        .filter(
            models.Alert.channel == "email",
            models.Alert.status.in_(["sent", "sent (mock)"]),
            models.Alert.sent_at >= today_start,
        )
        .count()
    )
    recent_alerts = (
        db.query(models.Alert)
        .order_by(models.Alert.created_at.desc())
        .limit(10)
        .all()
    )

    risk_orders = db.query(models.Order).filter(models.Order.risk_score >= 60).order_by(models.Order.risk_score.desc()).limit(10).all()
    status_distribution = {}
    for status, count in db.query(models.Order.current_status, func.count(models.Order.id)).group_by(models.Order.current_status).all():
        status_distribution[status] = count

    order_source_distribution = {}
    for source, count in db.query(models.Order.source, func.count(models.Order.id)).group_by(models.Order.source).all():
        order_source_distribution[source] = count

    # Sample a varied set of inventory items so the dashboard preview isn't all the same power
    import random
    sample_size = min(8, len(inv_items))
    inventory_sample = random.sample(inv_items, sample_size) if inv_items else []

    return DashboardResponse(
        kpis=DashboardKPIs(
            total_orders=total_orders,
            orders_at_risk=orders_at_risk,
            sla_breaches=sla_breaches,
            inventory_health_score=health_score,
            forecast_accuracy=forecast_accuracy,
            procurement_requests=procurement_requests,
            email_alerts_sent_today=email_alerts_sent_today,
        ),
        risk_orders=[RiskOrderOut.model_validate(o) for o in risk_orders],
        inventory_summary=[InventoryOut.model_validate(i) for i in inventory_sample],
        status_distribution=status_distribution,
        order_source_distribution=order_source_distribution,
        recent_alerts=[AlertOut.model_validate(a) for a in recent_alerts],
    )


@router.get("/risk-orders", response_model=list[RiskOrderOut])
def risk_orders(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Order).filter(models.Order.risk_score >= 60).order_by(models.Order.risk_score.desc()).all()
