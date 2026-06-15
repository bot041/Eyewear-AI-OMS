import json
from typing import Optional

import httpx

from app.config import settings
from app import models


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


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.kimi_api_base,
        headers={"Authorization": f"Bearer {settings.kimi_api_key}"},
        timeout=settings.llm_timeout_seconds,
    )


def _stage_progress(status: str) -> str:
    if status in ORDER_STAGES:
        idx = ORDER_STAGES.index(status)
        return f"{idx + 1}/{len(ORDER_STAGES)} ({status})"
    return status


async def _ask_kimi(prompt: str) -> Optional[str]:
    if not settings.kimi_api_key:
        return None

    try:
        async with _client() as client:
            payload = {
                "model": settings.kimi_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 300,
            }
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def build_explanation_prompt(order: models.Order, prediction: dict, similar_breaches: int) -> str:
    return f"""You are an expert AI operations assistant for an eyewear order management system.

Order details:
- Order number: {order.order_number}
- Customer: {order.customer_name}
- Lens: {order.lens_type}, power {order.power}, index {order.lens_index}, coating {order.coating}
- Store location: {order.store_location}
- Current stage: {_stage_progress(order.current_status)}
- Inventory available in-house: {order.inventory_available}
- Procurement required: {order.procurement_needed}

Prediction:
- Predicted completion: {prediction['predicted_completion_hours']:.1f} hours
- SLA target: {order.sla_hours} hours
- Expected delay: {prediction['expected_delay_hours']:.1f} hours
- Risk score: {prediction['risk_score']}%
- Similar historical SLA breaches: {similar_breaches}

Task: Explain in 4-6 short bullet points why this order has its predicted risk/delay and what the main operational drivers are. Be concise and actionable."""


def build_actions_prompt(order: models.Order, prediction: dict) -> str:
    return f"""You are an expert AI operations assistant for an eyewear order management system.

Order details:
- Order number: {order.order_number}
- Lens: {order.lens_type}, power {order.power}, index {order.lens_index}, coating {order.coating}
- Store location: {order.store_location}
- Current stage: {_stage_progress(order.current_status)}
- Inventory available in-house: {order.inventory_available}
- Procurement required: {order.procurement_needed}

Prediction:
- Predicted completion: {prediction['predicted_completion_hours']:.1f} hours
- SLA target: {order.sla_hours} hours
- Expected delay: {prediction['expected_delay_hours']:.1f} hours
- Risk score: {prediction['risk_score']}%

Task: Recommend 3-5 specific operational actions to reduce delay risk. Each action should be one short sentence. If risk is low, say 'No immediate action required.'"""


async def generate_llm_explanation(order: models.Order, prediction: dict, similar_breaches: int) -> Optional[str]:
    if not settings.enable_llm_explanations:
        return None
    prompt = build_explanation_prompt(order, prediction, similar_breaches)
    return await _ask_kimi(prompt)


async def generate_llm_actions(order: models.Order, prediction: dict) -> Optional[str]:
    if not settings.enable_recommended_actions:
        return None
    prompt = build_actions_prompt(order, prediction)
    return await _ask_kimi(prompt)
