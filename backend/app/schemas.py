from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class InventoryBase(BaseModel):
    power: float
    lens_type: str
    lens_index: float
    coating: str
    quantity: int
    forecast_demand: int = 0
    recommendation: str = ""


class InventoryOut(InventoryBase):
    id: int
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class InventoryCreate(BaseModel):
    power: float
    lens_type: str
    lens_index: float
    coating: str
    quantity: int = 0
    forecast_demand: int = 0


class InventoryUpdate(BaseModel):
    quantity: Optional[int] = None
    forecast_demand: Optional[int] = None
    recommendation: Optional[str] = None


class OrderStatusHistoryOut(BaseModel):
    id: int
    status: str
    changed_by: str
    timestamp: datetime

    class Config:
        from_attributes = True


class DelayLogOut(BaseModel):
    id: int
    reason: str
    logged_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    customer_name: str
    power: float
    lens_type: str
    lens_index: float
    coating: str
    frame: str
    store_location: str
    source: Optional[str] = "Website"


class OrderCreate(OrderBase):
    pass


class OrderOut(OrderBase):
    id: int
    order_number: str
    inventory_available: bool
    procurement_needed: bool
    current_status: str
    sla_hours: int
    predicted_completion_hours: Optional[float]
    risk_score: int
    breach_flag: bool
    expected_delay_hours: float
    ai_explanation: str
    recommended_actions: str
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    status_history: List[OrderStatusHistoryOut] = []
    delay_logs: List[DelayLogOut] = []
    sla_time_remaining_hours: float

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


class OrderFilter(BaseModel):
    status: Optional[str] = None
    lens_type: Optional[str] = None
    store_location: Optional[str] = None


class DelayReasonCreate(BaseModel):
    reason: str


class PredictSLARequest(BaseModel):
    lens_type: str
    lens_index: float
    coating: str
    current_stage: str
    inventory_available: bool
    store_location: str


class PredictSLAResponse(BaseModel):
    risk_score: int
    predicted_completion_hours: float
    expected_delay_hours: float
    breach_flag: bool
    ai_explanation: str
    recommended_actions: str


class ExplainRiskRequest(BaseModel):
    order_id: int


class ExplainRiskResponse(BaseModel):
    order_id: int
    risk_score: int
    explanation: str


class ForecastResponse(BaseModel):
    power: float
    lens_type: str
    demand: int
    recommendation: str


class DashboardKPIs(BaseModel):
    total_orders: int
    orders_at_risk: int
    sla_breaches: int
    inventory_health_score: int
    forecast_accuracy: int
    procurement_requests: int
    email_alerts_sent_today: int


class RiskOrderOut(BaseModel):
    id: int
    order_number: str
    customer_name: str
    risk_score: int
    predicted_completion_hours: float
    expected_delay_hours: float
    sla_time_remaining_hours: float
    ai_explanation: str
    recommended_actions: str
    current_status: str

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    risk_orders: List[RiskOrderOut]
    inventory_summary: List[InventoryOut]
    status_distribution: dict
    order_source_distribution: dict
    recent_alerts: List[AlertOut]


class RecommendedActionsRequest(BaseModel):
    order_id: int


class RecommendedActionsResponse(BaseModel):
    order_id: int
    actions: str


class RetrainResponse(BaseModel):
    status: str
    tat_model_score: Optional[float]
    breach_model_score: Optional[float]
    message: str


class ForecastOut(BaseModel):
    inventory_id: int
    power: float
    lens_type: str
    coating: str
    current_quantity: int
    forecast_demand_7d: int
    forecast_demand_30d: int
    recommendation: str

    class Config:
        from_attributes = True


class InventoryConsumptionPoint(BaseModel):
    date: str
    quantity: int


class AlertOut(BaseModel):
    id: int
    order_id: int
    channel: str
    recipient: str
    risk_score: int
    subject: Optional[str]
    message: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class TriggerAlertsResponse(BaseModel):
    alerts_created: int
    message: str


class AlertTestRequest(BaseModel):
    order_id: int


class AlertTestResponse(BaseModel):
    order_id: int
    risk_score: int
    status: str
    message: str
