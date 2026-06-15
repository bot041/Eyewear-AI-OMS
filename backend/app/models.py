import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)  # admin, operations_manager, qc_manager
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    power = Column(Float, nullable=False)
    lens_type = Column(String, nullable=False)
    lens_index = Column(Float, nullable=False)
    coating = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    forecast_demand = Column(Integer, default=0)
    recommendation = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True, nullable=False)
    customer_name = Column(String, nullable=False)
    power = Column(Float, nullable=False)
    lens_type = Column(String, nullable=False)
    lens_index = Column(Float, nullable=False)
    coating = Column(String, nullable=False)
    frame = Column(String, nullable=False)
    store_location = Column(String, nullable=False)
    source = Column(String, default="Website")
    inventory_available = Column(Boolean, default=True)
    procurement_needed = Column(Boolean, default=False)
    current_status = Column(String, default="Order Placed")
    sla_hours = Column(Integer, default=72)
    predicted_completion_hours = Column(Float, nullable=True)
    risk_score = Column(Integer, default=0)
    breach_flag = Column(Boolean, default=False)
    expected_delay_hours = Column(Float, default=0)
    ai_explanation = Column(Text, default="")
    recommended_actions = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)

    @property
    def sla_time_remaining_hours(self) -> float:
        """Hours remaining until the SLA deadline (negative if overdue)."""
        if self.current_status == "Delivered" or self.delivered_at is not None:
            return 0.0
        deadline = self.created_at + datetime.timedelta(hours=self.sla_hours)
        remaining = (deadline - datetime.datetime.utcnow()).total_seconds() / 3600.0
        return round(remaining, 1)

    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    delay_logs = relationship("DelayLog", back_populates="order", cascade="all, delete-orphan")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    status = Column(String, nullable=False)
    changed_by = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("Order", back_populates="status_history")


class DelayLog(Base):
    __tablename__ = "delay_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    reason = Column(String, nullable=False)
    logged_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("Order", back_populates="delay_logs")


class InventoryConsumption(Base):
    __tablename__ = "inventory_consumption"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    quantity_used = Column(Integer, default=0)

    inventory = relationship("Inventory")


class PredictionLog(Base):
    __tablename__ = "predictions_log"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    predicted_completion = Column(Float, nullable=False)
    actual_completion = Column(Float, nullable=True)
    prediction_date = Column(DateTime, default=datetime.datetime.utcnow)

    order = relationship("Order")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    channel = Column(String, nullable=False)  # email, whatsapp
    recipient = Column(String, nullable=False)
    risk_score = Column(Integer, default=0)
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, sent, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    order = relationship("Order")
