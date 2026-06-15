from typing import List
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.ml_model import predict_with_ml
from app.services.kimi_client import generate_llm_explanation, generate_llm_actions

ORDER_STAGES = [
    "Order Placed",
    "Inventory Check",
    "Lens Manufacturing",
    "Coating",
    "Frame Assembly",
    "Quality Check",
    "Packaging",
    "Dispatch",
    "Delivered",
]

STAGE_WEIGHTS = {
    "Order Placed": 1.0,
    "Inventory Check": 1.1,
    "Lens Manufacturing": 1.3,
    "Coating": 1.4,
    "Frame Assembly": 1.1,
    "Quality Check": 1.2,
    "Packaging": 1.0,
    "Dispatch": 1.1,
    "Delivered": 0.0,
}

# Explicit SLA mapping by lens type (hours) - constrained between 72 and 168 hours
SLA_HOURS_BY_LENS_TYPE = {
    "Single Vision": 72,
    "Bifocal": 96,
    "Progressive": 168,
    "Computer Vision": 96,
    "Blue Cut": 72,
    "Photochromic": 120,
    "Anti-Glare": 84,
    "High Index": 120,
}


def get_sla_hours(lens_type: str) -> int:
    """Return the configured SLA hours for a lens type, constrained to 72-168 hours."""
    hours = SLA_HOURS_BY_LENS_TYPE.get(lens_type, 72)
    return min(168, max(72, hours))


def _count_similar_breaches(db: Session, order: models.Order) -> int:
    return (
        db.query(models.Order)
        .filter(
            models.Order.lens_type == order.lens_type,
            models.Order.coating == order.coating,
            models.Order.breach_flag == True,
        )
        .count()
    )


def _rule_based_prediction(db: Session, order: models.Order) -> dict:
    """Deterministic fallback predictor."""
    base_hours = 48.0

    stage_idx = ORDER_STAGES.index(order.current_status) if order.current_status in ORDER_STAGES else 0
    progress_factor = 1.0 + (stage_idx * 0.05)

    coating_factor = 1.0
    if order.coating.lower() in ["anti-glare", "blue cut", "photochromic"]:
        coating_factor = 1.2

    index_factor = 1.0 + ((order.lens_index - 1.5) * 0.3)
    inventory_factor = 1.0 if order.inventory_available else 1.5

    high_demand_locations = {"Mumbai", "Delhi", "Bangalore"}
    location_factor = 1.15 if order.store_location in high_demand_locations else 1.0

    similar_breaches = _count_similar_breaches(db, order)
    historical_factor = 1.2 if similar_breaches > 5 else 1.0

    predicted_hours = round(
        base_hours * progress_factor * coating_factor * index_factor *
        inventory_factor * location_factor * historical_factor, 1
    )
    expected_delay = round(min(48.0, max(0.0, predicted_hours - order.sla_hours)), 1)
    risk_score = min(100, int((predicted_hours / order.sla_hours) * 60))
    if not order.inventory_available:
        risk_score = min(100, risk_score + 15)
    if similar_breaches > 10:
        risk_score = min(100, risk_score + 10)

    breach_flag = predicted_hours > order.sla_hours or risk_score >= 70

    return {
        "predicted_completion_hours": predicted_hours,
        "expected_delay_hours": expected_delay,
        "risk_score": risk_score,
        "breach_flag": breach_flag,
        "similar_breaches": similar_breaches,
    }


def _generate_explanation(order: models.Order, prediction: dict) -> str:
    bullets = []
    if not order.inventory_available:
        bullets.append("Inventory unavailable in-house; vendor procurement required.")
    if order.coating.lower() in ["anti-glare", "blue cut", "photochromic"]:
        bullets.append(f"{order.coating.title()} coating adds processing complexity and queue time.")
    if order.lens_index >= 1.67:
        bullets.append(f"High-index ({order.lens_index}) lenses require specialized manufacturing.")
    if order.current_status == "Coating":
        bullets.append("Coating stage currently has a backlog.")
    if order.store_location in {"Mumbai", "Delhi", "Bangalore"}:
        bullets.append(f"{order.store_location} hub is experiencing high order volume.")
    if prediction["similar_breaches"] > 5:
        bullets.append(f"Similar historical orders exceeded SLA ({prediction['similar_breaches']} breaches).")

    delay = prediction["expected_delay_hours"]
    if delay <= 0:
        bullets.append("Order is currently on track to meet SLA.")
    else:
        bullets.append(
            f"Predicted completion is {prediction['predicted_completion_hours']:.1f}h "
            f"vs {order.sla_hours}h SLA ({delay:.1f}h delay)."
        )

    return "\n".join(f"• {b}" for b in bullets)


def _generate_actions(order: models.Order, prediction: dict) -> str:
    bullets = []
    if prediction["risk_score"] < 40:
        bullets.append("No immediate action required; continue standard processing.")
        return "\n".join(f"• {b}" for b in bullets)

    if not order.inventory_available:
        bullets.append("Expedite vendor procurement or source from an alternate supplier.")
    if prediction["expected_delay_hours"] > 12:
        bullets.append("Prioritize order in the production queue to recover lost time.")
    if order.coating.lower() in ["anti-glare", "blue cut", "photochromic"]:
        bullets.append("Schedule coating stage early to avoid backlog accumulation.")
    if order.lens_index >= 1.67:
        bullets.append("Allocate specialized manufacturing cell for high-index lens.")
    if order.store_location in {"Mumbai", "Delhi", "Bangalore"}:
        bullets.append("Consider express dispatch from the high-volume hub.")
    if prediction["similar_breaches"] > 5:
        bullets.append("Apply lessons learned from similar past SLA breaches.")

    return "\n".join(f"• {b}" for b in bullets)


def predict_sla(db: Session, order: models.Order) -> schemas.PredictSLAResponse:
    """Synchronous prediction: ML if available, else rule-based fallback."""
    if order.current_status == "Delivered":
        return schemas.PredictSLAResponse(
            risk_score=0,
            predicted_completion_hours=0.0,
            expected_delay_hours=0.0,
            breach_flag=False,
            ai_explanation="• Order has been delivered successfully.\n• No SLA risk remains.",
            recommended_actions="• No action required.",
        )

    # Try ML models first
    ml_result = predict_with_ml(order, db)
    if ml_result:
        prediction = {
            "predicted_completion_hours": ml_result["predicted_completion_hours"],
            "expected_delay_hours": round(min(48.0, max(0.0, ml_result["predicted_completion_hours"] - order.sla_hours)), 1),
            "risk_score": ml_result["risk_score"],
            "breach_flag": ml_result["breach_flag"],
            "similar_breaches": _count_similar_breaches(db, order),
        }
    else:
        prediction = _rule_based_prediction(db, order)

    explanation = _generate_explanation(order, prediction)
    actions = _generate_actions(order, prediction)

    return schemas.PredictSLAResponse(
        risk_score=prediction["risk_score"],
        predicted_completion_hours=prediction["predicted_completion_hours"],
        expected_delay_hours=prediction["expected_delay_hours"],
        breach_flag=prediction["breach_flag"],
        ai_explanation=explanation,
        recommended_actions=actions,
    )


async def enrich_prediction_with_llm(
    db: Session, order: models.Order, prediction: schemas.PredictSLAResponse
) -> schemas.PredictSLAResponse:
    """Async enhancement of explanation/actions via Kimi API (best-effort)."""
    pred_dict = {
        "predicted_completion_hours": prediction.predicted_completion_hours,
        "expected_delay_hours": prediction.expected_delay_hours,
        "risk_score": prediction.risk_score,
    }
    similar_breaches = _count_similar_breaches(db, order)

    llm_explanation = await generate_llm_explanation(order, pred_dict, similar_breaches)
    if llm_explanation:
        prediction.ai_explanation = llm_explanation

    llm_actions = await generate_llm_actions(order, pred_dict)
    if llm_actions:
        prediction.recommended_actions = llm_actions

    return prediction


def update_inventory_recommendations(db: Session):
    """Legacy threshold-based recommendation (kept as fallback)."""
    from app.services.forecasting import forecast_inventory_demand
    # Prefer Prophet-driven forecasts when consumption data exists
    forecast_inventory_demand(db)
