import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import List
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.email_service import send_high_risk_alert as send_resend_email_alert

DEFAULT_ALERT_THRESHOLD = 80


def _build_alert_message(order: models.Order) -> str:
    return (
        f"High SLA risk detected for {order.order_number} ({order.customer_name}). "
        f"Risk score: {order.risk_score}%, predicted completion: {order.predicted_completion_hours:.1f}h, "
        f"expected delay: +{order.expected_delay_hours:.1f}h. "
        f"Current stage: {order.current_status}."
    )


def create_alert(db: Session, order: models.Order, channel: str, recipient: str) -> models.Alert:
    message = _build_alert_message(order)
    subject = f"SLA Risk Alert: {order.order_number}"
    alert = models.Alert(
        order_id=order.id,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message,
        status="pending",
    )
    db.add(alert)
    db.flush()
    return alert


def _send_email_alert(alert: models.Alert) -> bool:
    """Send email alert via SMTP if configured, otherwise return False."""
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        return False

    try:
        msg = MIMEText(alert.message)
        msg["Subject"] = alert.subject or "SLA Risk Alert"
        msg["From"] = settings.alert_from_email
        msg["To"] = alert.recipient or settings.alert_to_email

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.alert_from_email, [alert.recipient or settings.alert_to_email], msg.as_string())
        return True
    except Exception:
        return False


def _send_whatsapp_alert(alert: models.Alert) -> bool:
    """Send WhatsApp alert via Twilio if configured, otherwise return False."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_whatsapp_from:
        return False

    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        to_number = alert.recipient or settings.twilio_whatsapp_to
        if not to_number:
            return False
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        client.messages.create(
            body=alert.message,
            from_=f"whatsapp:{settings.twilio_whatsapp_from}",
            to=to_number,
        )
        return True
    except Exception:
        return False


def send_alert(db: Session, alert: models.Alert) -> bool:
    """Dispatch alert via configured channel. Falls back to mock dispatch if no provider is configured."""
    try:
        if alert.channel == "email":
            sent = _send_email_alert(alert)
        elif alert.channel == "whatsapp":
            sent = _send_whatsapp_alert(alert)
        else:
            sent = False

        if sent:
            alert.status = "sent"
        else:
            # Mock dispatch when no provider is configured
            alert.status = "sent (mock)"
        alert.sent_at = datetime.utcnow()
        db.commit()
        return True
    except Exception:
        alert.status = "failed"
        db.commit()
        return False


def trigger_high_risk_alerts(db: Session, threshold: int = DEFAULT_ALERT_THRESHOLD) -> int:
    """Create and send alerts for all high-risk open orders."""
    high_risk_orders = (
        db.query(models.Order)
        .filter(
            models.Order.risk_score >= threshold,
            models.Order.current_status != "Delivered",
        )
        .all()
    )

    created = 0
    for order in high_risk_orders:
        # Avoid duplicate email alerts for the same order
        existing_email = (
            db.query(models.Alert)
            .filter(
                models.Alert.order_id == order.id,
                models.Alert.channel == "email",
                models.Alert.status.in_(["pending", "sent", "sent (mock)"]),
            )
            .first()
        )
        if not existing_email:
            send_resend_email_alert(db, order)
            created += 1

        # Keep WhatsApp alert as a secondary channel
        existing_whatsapp = (
            db.query(models.Alert)
            .filter(
                models.Alert.order_id == order.id,
                models.Alert.channel == "whatsapp",
                models.Alert.status.in_(["pending", "sent", "sent (mock)"]),
            )
            .first()
        )
        if not existing_whatsapp:
            whatsapp_alert = create_alert(db, order, "whatsapp", settings.twilio_whatsapp_to or "+91-9876543210")
            send_alert(db, whatsapp_alert)
            created += 1

    db.commit()
    return created


def list_alerts(db: Session, limit: int = 50) -> List[models.Alert]:
    return db.query(models.Alert).order_by(models.Alert.created_at.desc()).limit(limit).all()
