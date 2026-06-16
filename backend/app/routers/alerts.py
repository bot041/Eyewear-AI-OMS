from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role
from app.services.prediction import predict_sla, enrich_prediction_with_llm
from app.services.email_service import (
    send_high_risk_alert,
    get_email_provider_status,
    RESEND_ENABLED,
    SMTP_ENABLED,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/test", response_model=schemas.AlertTestResponse)
async def test_alert(
    payload: schemas.AlertTestRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    """
    Test the high-risk email alert flow for a specific order.
    Re-runs prediction, refreshes the order's AI explanation and recommended actions,
    and sends a test alert email via Resend.
    """
    order = db.query(models.Order).filter(models.Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)

    order.predicted_completion_hours = pred.predicted_completion_hours
    order.risk_score = pred.risk_score
    order.breach_flag = pred.breach_flag
    order.expected_delay_hours = pred.expected_delay_hours
    order.ai_explanation = pred.ai_explanation
    order.recommended_actions = pred.recommended_actions
    db.commit()

    sent = send_high_risk_alert(db, order)
    provider = "resend" if RESEND_ENABLED else "smtp" if SMTP_ENABLED else "mock"
    return schemas.AlertTestResponse(
        order_id=order.id,
        risk_score=order.risk_score,
        status="sent" if sent else "failed",
        message="High-risk alert email dispatched." if sent else "Failed to dispatch alert email.",
        provider=provider,
    )


@router.post("/send-test", response_model=schemas.AlertTestResponse)
async def send_test_alert_to_operations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    """
    Send a test high-risk alert email to the configured operations email address.
    Picks the highest-risk non-delivered order, refreshes its prediction, and sends the email.
    """
    order = (
        db.query(models.Order)
        .filter(models.Order.current_status != "Delivered")
        .order_by(models.Order.risk_score.desc())
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="No eligible order found")

    pred = predict_sla(db, order)
    pred = await enrich_prediction_with_llm(db, order, pred)

    order.predicted_completion_hours = pred.predicted_completion_hours
    order.risk_score = pred.risk_score
    order.breach_flag = pred.breach_flag
    order.expected_delay_hours = pred.expected_delay_hours
    order.ai_explanation = pred.ai_explanation
    order.recommended_actions = pred.recommended_actions
    db.commit()

    sent = send_high_risk_alert(db, order)
    provider = "resend" if RESEND_ENABLED else "smtp" if SMTP_ENABLED else "mock"
    return schemas.AlertTestResponse(
        order_id=order.id,
        risk_score=order.risk_score,
        status="sent" if sent else "failed",
        message="Test alert email dispatched to samasur018@gmail.com." if sent else "Failed to dispatch test alert email.",
        provider=provider,
    )



@router.get("/email-config")
def email_config_status(
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    """Return the active email provider configuration (no secrets exposed)."""
    return get_email_provider_status()
