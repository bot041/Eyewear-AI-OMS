import os
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app import models, auth
from app.services.prediction import predict_sla, update_inventory_recommendations, get_sla_hours
from app.services.forecasting import record_consumption
from app.services.ml_model import train_models

fake = Faker("en_IN")

ROLES = ["admin", "operations_manager", "qc_manager"]
USERS = [
    {"name": "Admin User", "email": "admin@eluno.com", "role": "admin", "password": "admin123"},
    {"name": "Operations Manager", "email": "ops@eluno.com", "role": "operations_manager", "password": "ops123"},
    {"name": "QC Manager", "email": "qc@eluno.com", "role": "qc_manager", "password": "qc123"},
]

# Lens powers covering common, medium, and rare prescriptions
POWERS = [round(x * 0.25, 2) for x in range(-24, 25)]  # -6.00 to +6.00 in 0.25 steps

LENS_TYPES = ["Single Vision", "Bifocal", "Progressive", "Computer Vision"]
COATINGS = ["Standard", "Anti-Glare", "Blue Cut", "Photochromic"]
FRAMES = ["Round", "Rectangle", "Cat-Eye", "Aviator", "Wayfarer"]
STORE_LOCATIONS = ["Bangalore", "Mumbai", "Delhi"]
SOURCES = ["Website", "Retail Stores", "Marketplaces", "Sales Representatives"]

# Availability by power tier (plan-aligned)
def _availability_for_power(power: float) -> float:
    abs_p = abs(power)
    if abs_p <= 2.0:
        return 0.95
    if abs_p <= 4.0:
        return 0.75
    return 0.35

# QC failure rates by lens type (plan-aligned)
QC_FAILURE_RATES = {
    "Single Vision": 0.02,
    "Bifocal": 0.04,
    "Progressive": 0.08,
    "Computer Vision": 0.04,
}

# Procurement delay distribution (hours) - plan-aligned
PROCUREMENT_DELAYS = [24] * 40 + [48] * 35 + [72] * 20 + [96] * 5

# Store speed multiplier (plan-aligned)
STORE_SPEED = {"Bangalore": 0.90, "Mumbai": 1.00, "Delhi": 1.00}

# Weighted distribution for realistic active order pipeline stages
ACTIVE_STATUS_WEIGHTS = {
    "Order Placed": 0.12,
    "Inventory Check": 0.12,
    "Lens Manufacturing": 0.18,
    "Coating": 0.14,
    "Frame Assembly": 0.10,
    "Quality Check": 0.10,
    "QC Failed": 0.05,
    "Rework": 0.05,
    "Packaging": 0.08,
    "Dispatch": 0.06,
}


def _random_active_status() -> str:
    statuses = list(ACTIVE_STATUS_WEIGHTS.keys())
    weights = list(ACTIVE_STATUS_WEIGHTS.values())
    return random.choices(statuses, weights=weights, k=1)[0]


def seed_users(db: Session):
    for u in USERS:
        if not db.query(models.User).filter(models.User.email == u["email"]).first():
            db.add(models.User(
                name=u["name"],
                email=u["email"],
                role=u["role"],
                password_hash=auth.get_password_hash(u["password"]),
            ))
    db.commit()


def seed_inventory(db: Session):
    if db.query(models.Inventory).first():
        return
    for power in POWERS:
        for lens_type in LENS_TYPES:
            for coating in COATINGS:
                base_demand = random.randint(5, 150)
                availability = _availability_for_power(power)
                # Varied stock factors create realistic Restock / Overstocked / Healthy mix
                stock_factor = random.choice([0.0, 0.1, 0.3, 0.6, 1.0, 1.5, 2.5, 4.0])
                qty = max(0, int(base_demand * availability * stock_factor + random.gauss(0, base_demand * 0.2)))
                lens_index = random.choice([1.5, 1.56, 1.61, 1.67, 1.74])
                db.add(models.Inventory(
                    power=power,
                    lens_type=lens_type,
                    lens_index=lens_index,
                    coating=coating,
                    quantity=qty,
                    forecast_demand=base_demand,
                    recommendation="",
                ))
    db.commit()
    update_inventory_recommendations(db)


def _inventory_match(db: Session, power: float, lens_type: str, coating: str):
    return db.query(models.Inventory).filter(
        models.Inventory.power == power,
        models.Inventory.lens_type == lens_type,
        models.Inventory.coating == coating,
    ).first()


def _simulate_actual_hours(order: models.Order) -> float:
    """Simulate realistic order completion hours for synthetic historical data."""
    base = 48.0

    coating_factor = 1.0
    if order.coating.lower() in ["anti-glare", "blue cut", "photochromic"]:
        coating_factor = 1.2

    index_factor = 1.0 + ((order.lens_index - 1.5) * 0.3)
    inventory_factor = 1.0 if order.inventory_available else 1.5

    store_factor = STORE_SPEED.get(order.store_location, 1.05)

    qc_fail_rate = QC_FAILURE_RATES.get(order.lens_type, 0.04)
    qc_delay = 12.0 if random.random() < qc_fail_rate else 0.0

    procurement_delay = 0.0
    if order.procurement_needed:
        procurement_delay = random.choice(PROCUREMENT_DELAYS)

    noise = random.uniform(0.9, 1.1)
    hours = (base * coating_factor * index_factor * inventory_factor * store_factor) + qc_delay + procurement_delay
    hours *= noise
    return max(1.0, hours)


def _create_order(db: Session, idx: int, delivered: bool) -> models.Order:
    inv = random.choice(db.query(models.Inventory).all())
    inv_match = _inventory_match(db, inv.power, inv.lens_type, inv.coating)
    available = inv_match.quantity > 0 if inv_match else False

    lens_type = inv.lens_type
    coating = inv.coating
    power = inv.power
    lens_index = inv.lens_index
    store = random.choice(STORE_LOCATIONS)
    sla = get_sla_hours(lens_type)

    created = datetime.utcnow() - timedelta(
        days=random.randint(1, 180),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    order = models.Order(
        order_number=f"ORD{str(idx).zfill(4)}",
        customer_name=fake.name(),
        power=power,
        lens_type=lens_type,
        lens_index=lens_index,
        coating=coating,
        frame=random.choice(FRAMES),
        store_location=store,
        source=random.choice(SOURCES),
        inventory_available=available,
        procurement_needed=not available,
        current_status="Delivered" if delivered else _random_active_status(),
        sla_hours=sla,
        created_at=created,
    )
    db.add(order)
    db.flush()

    if delivered:
        actual_hours = _simulate_actual_hours(order)
        order.delivered_at = created + timedelta(hours=actual_hours)
        order.breach_flag = actual_hours > sla

        # Record consumption for demand forecasting
        if inv_match:
            record_consumption(db, inv_match.id, 1, date=created)

        # Add status history including optional QC failure/rework
        statuses = ["Order Placed", "Inventory Check", "Lens Manufacturing", "Coating", "Frame Assembly", "Quality Check", "Packaging", "Dispatch", "Delivered"]
        qc_fail_rate = QC_FAILURE_RATES.get(lens_type, 0.04)
        if random.random() < qc_fail_rate:
            statuses.insert(statuses.index("Quality Check") + 1, "QC Failed")
            statuses.insert(statuses.index("QC Failed") + 1, "Rework")
        for s in statuses:
            db.add(models.OrderStatusHistory(order_id=order.id, status=s, changed_by="system"))

        # Random delay log
        if random.random() < 0.2:
            db.add(models.DelayLog(order_id=order.id, reason=random.choice([
                "Lens out of stock", "Coating machine maintenance", "QC rework required", "Courier delay", "High hub volume"
            ]), logged_by="ops@eluno.com"))

        # Log the actual completion so we can train models
        db.add(models.PredictionLog(
            order_id=order.id,
            predicted_completion=actual_hours * random.uniform(0.85, 1.15),  # simulate an earlier prediction
            actual_completion=actual_hours,
            prediction_date=created,
        ))
    else:
        # Build a realistic status history up to the current active stage
        pipeline = ["Order Placed", "Inventory Check", "Lens Manufacturing", "Coating", "Frame Assembly", "Quality Check", "Packaging", "Dispatch"]
        current = order.current_status
        if current in ["QC Failed", "Rework"]:
            # These loop back from Quality Check
            history_stages = pipeline[:pipeline.index("Quality Check") + 1] + ["QC Failed", "Rework"]
        elif current in pipeline:
            history_stages = pipeline[:pipeline.index(current) + 1]
        else:
            history_stages = [current]
        for s in history_stages:
            db.add(models.OrderStatusHistory(order_id=order.id, status=s, changed_by="system"))

    pred = predict_sla(db, order)
    order.predicted_completion_hours = pred.predicted_completion_hours
    order.risk_score = pred.risk_score
    order.breach_flag = pred.breach_flag if not delivered else order.breach_flag
    order.expected_delay_hours = pred.expected_delay_hours
    order.ai_explanation = pred.ai_explanation
    order.recommended_actions = pred.recommended_actions

    return order


def seed_orders(db: Session, historical: int = 250, active: int = 500):
    existing = db.query(models.Order).count()
    if existing >= (historical + active):
        return

    next_idx = existing + 1

    # Historical delivered orders for ML training
    for i in range(historical):
        _create_order(db, next_idx + i, delivered=True)
    next_idx += historical

    # Active orders in various pipeline stages
    for i in range(active):
        _create_order(db, next_idx + i, delivered=False)

    db.commit()


def seed_all():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_users(db)
        seed_inventory(db)
        seed_orders(db)
        # Train ML models once synthetic historical data is in place
        train_models(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
