import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional
from sqlalchemy.orm import Session

import resend

from app import models
from app.config import settings

logger = logging.getLogger(__name__)

RESEND_ENABLED = bool(settings.resend_api_key)
if RESEND_ENABLED:
    resend.api_key = settings.resend_api_key

SMTP_ENABLED = bool(settings.smtp_host and settings.smtp_username and settings.smtp_password)

logger.info(f"Email provider status: RESEND={RESEND_ENABLED}, SMTP={SMTP_ENABLED}")
if SMTP_ENABLED:
    logger.info(f"SMTP host={settings.smtp_host}, port={settings.smtp_port}, username={settings.smtp_username}")


def build_alert_email(order: models.Order) -> Dict[str, str]:
    """Build the subject and HTML/text body for a high-risk order alert email."""
    subject = f"High Risk Order Alert - {order.id}"

    order_info = f"""
    <h2>1. Order Information</h2>
    <ul>
      <li><strong>Order ID:</strong> {order.id}</li>
      <li><strong>Order Number:</strong> {order.order_number}</li>
      <li><strong>Customer:</strong> {order.customer_name}</li>
      <li><strong>Lens:</strong> {order.lens_type} (Index {order.lens_index})</li>
      <li><strong>Coating:</strong> {order.coating}</li>
      <li><strong>Power:</strong> {order.power}</li>
      <li><strong>Frame:</strong> {order.frame}</li>
      <li><strong>Store Location:</strong> {order.store_location}</li>
      <li><strong>Current Status:</strong> {order.current_status}</li>
    </ul>
    """

    risk_assessment = f"""
    <h2>2. AI Risk Assessment</h2>
    <ul>
      <li><strong>Risk Score:</strong> {order.risk_score}%</li>
      <li><strong>Predicted Completion:</strong> {order.predicted_completion_hours:.1f} hours</li>
      <li><strong>SLA Target:</strong> {order.sla_hours} hours</li>
      <li><strong>Expected Delay:</strong> +{order.expected_delay_hours:.1f} hours</li>
      <li><strong>Breach Flag:</strong> {"Yes" if order.breach_flag else "No"}</li>
    </ul>
    """

    explanation = order.ai_explanation or "No explanation available."
    recommended_actions = order.recommended_actions or "No recommended actions available."

    # Convert plain-text bullet lists to HTML line breaks for email readability
    explanation_html = explanation.replace("\n", "<br>")
    actions_html = recommended_actions.replace("\n", "<br>")

    html_body = f"""
    <html>
      <body>
        {order_info}
        {risk_assessment}
        <h2>3. AI Explanation</h2>
        <p>{explanation_html}</p>
        <h2>4. Recommended Actions</h2>
        <p>{actions_html}</p>
        <hr>
        <p style="font-size: 12px; color: #666;">
          This alert was generated automatically by the AI-Powered Eyewear OMS.
        </p>
      </body>
    </html>
    """

    text_body = f"""
High Risk Order Alert - {order.id}

1. Order Information
- Order ID: {order.id}
- Order Number: {order.order_number}
- Customer: {order.customer_name}
- Lens: {order.lens_type} (Index {order.lens_index})
- Coating: {order.coating}
- Power: {order.power}
- Frame: {order.frame}
- Store Location: {order.store_location}
- Current Status: {order.current_status}

2. AI Risk Assessment
- Risk Score: {order.risk_score}%
- Predicted Completion: {order.predicted_completion_hours:.1f} hours
- SLA Target: {order.sla_hours} hours
- Expected Delay: +{order.expected_delay_hours:.1f} hours
- Breach Flag: {"Yes" if order.breach_flag else "No"}

3. AI Explanation
{explanation}

4. Recommended Actions
{recommended_actions}

---
This alert was generated automatically by the AI-Powered Eyewear OMS.
"""

    return {
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }


def log_email_delivery(
    db: Session,
    order: models.Order,
    recipient: str,
    status: str,
    subject: Optional[str] = None,
    message: Optional[str] = None,
) -> models.Alert:
    """Persist an alert record to the database."""
    alert = models.Alert(
        order_id=order.id,
        channel="email",
        recipient=recipient,
        risk_score=order.risk_score,
        subject=subject,
        message=message or "",
        status=status,
    )
    db.add(alert)
    db.flush()
    return alert


def _send_smtp_email(recipient: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send email via configured SMTP server."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.alert_from_email or settings.smtp_username
        msg["To"] = recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Gmail app passwords may contain spaces; strip them for login
        smtp_password = settings.smtp_password.replace(" ", "") if settings.smtp_password else ""

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, smtp_password)
            server.sendmail(
                settings.alert_from_email or settings.smtp_username,
                [recipient],
                msg.as_string(),
            )
        logger.info(f"SMTP email sent successfully to {recipient}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed: {type(e).__name__}: {e}")
        return False


def send_high_risk_alert(db: Session, order: models.Order) -> bool:
    """
    Send a high-risk alert email via Resend.
    Falls back to SMTP if Resend is not configured but SMTP is.
    Falls back to a mock/pending log entry if neither provider is configured.
    """
    recipient = settings.operations_email
    email = build_alert_email(order)
    subject = email["subject"]
    html_body = email["html"]
    text_body = email["text"]

    if RESEND_ENABLED:
        try:
            params: resend.Emails.SendParams = {
                "from": settings.email_from,
                "to": [recipient],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }
            resend.Emails.send(params)

            alert = log_email_delivery(db, order, recipient, "sent", subject, text_body)
            alert.sent_at = datetime.utcnow()
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Resend failed: {type(e).__name__}: {e}")
            alert = log_email_delivery(db, order, recipient, "failed", subject, text_body)
            db.commit()
            return False

    if SMTP_ENABLED:
        sent = _send_smtp_email(recipient, subject, html_body, text_body)
        status = "sent" if sent else "failed"
        alert = log_email_delivery(db, order, recipient, status, subject, text_body)
        if sent:
            alert.sent_at = datetime.utcnow()
        db.commit()
        return sent

    # No provider configured: log as sent (mock) so the flow can still be demoed
    logger.warning("No email provider configured; using mock fallback")
    alert = log_email_delivery(db, order, recipient, "sent (mock)", subject, text_body)
    alert.sent_at = datetime.utcnow()
    db.commit()
    return True


def get_email_provider_status() -> dict:
    """Return non-sensitive email configuration status."""
    return {
        "resend_enabled": RESEND_ENABLED,
        "smtp_enabled": SMTP_ENABLED,
        "smtp_host": settings.smtp_host,
        "smtp_username": settings.smtp_username,
        "alert_from_email": settings.alert_from_email,
        "alert_to_email": settings.alert_to_email,
        "operations_email": settings.operations_email,
        "email_from": settings.email_from,
    }
