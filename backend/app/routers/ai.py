from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.prediction import predict_sla, enrich_prediction_with_llm, get_sla_hours
from app.services.ml_model import train_models
from app.services.forecasting import forecast_inventory_demand
from app.services.alerts import trigger_high_risk_alerts, list_alerts

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/predict-sla", response_model=schemas.PredictSLAResponse)
async def predict_sla_endpoint(
    payload: schemas.PredictSLARequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    temp_order = models.Order(
        lens_type=payload.lens_type,
        lens_index=payload.lens_index,
        coating=payload.coating,
        current_status=payload.current_stage,
        inventory_available=payload.inventory_available,
        store_location=payload.store_location,
        sla_hours=get_sla_hours(payload.lens_type),
    )
    pred = predict_sla(db, temp_order)
    pred = await enrich_prediction_with_llm(db, temp_order, pred)
    return pred


@router.post("/explain-risk", response_model=schemas.ExplainRiskResponse)
async def explain_risk(
    payload: schemas.ExplainRiskRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)
    return schemas.ExplainRiskResponse(
        order_id=order.id,
        risk_score=pred.risk_score,
        explanation=pred.ai_explanation,
    )


@router.post("/recommended-actions", response_model=schemas.RecommendedActionsResponse)
async def recommended_actions(
    payload: schemas.RecommendedActionsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)
    return schemas.RecommendedActionsResponse(
        order_id=order.id,
        actions=pred.recommended_actions,
    )


@router.get("/forecast", response_model=list[schemas.ForecastOut])
def forecast(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return forecast_inventory_demand(db)


@router.post("/retrain", response_model=schemas.RetrainResponse)
def retrain(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = train_models(db)
    return schemas.RetrainResponse(
        status=result["status"],
        tat_model_score=result["tat_model_score"],
        breach_model_score=result["breach_model_score"],
        message=result["message"],
    )


@router.post("/trigger-alerts", response_model=schemas.TriggerAlertsResponse)
def trigger_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = trigger_high_risk_alerts(db)
    return schemas.TriggerAlertsResponse(
        alerts_created=count,
        message=f"Created and dispatched {count} proactive alerts for high-risk orders.",
    )


@router.get("/alerts", response_model=list[schemas.AlertOut])
def get_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return list_alerts(db)
