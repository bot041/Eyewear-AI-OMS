import os
import pickle
import warnings
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from app import models
from app.config import settings

warnings.filterwarnings("ignore", category=FutureWarning)

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

STORE_SPEED = {"Bangalore": 0.9, "Mumbai": 1.0, "Delhi": 1.0}

# Hyperparameter search grids for Gradient Boosting
GB_REGRESSOR_GRID = {
    "model__n_estimators": [100, 200],
    "model__max_depth": [3, 5],
    "model__learning_rate": [0.1],
    "model__min_samples_split": [2, 5],
}

GB_CLASSIFIER_GRID = {
    "model__n_estimators": [100, 200],
    "model__max_depth": [3, 5],
    "model__learning_rate": [0.1],
    "model__min_samples_split": [2, 5],
}


def _model_dir() -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "ai")
    os.makedirs(path, exist_ok=True)
    return path


def _tat_model_path() -> str:
    return os.path.join(_model_dir(), settings.tat_model_file)


def _breach_model_path() -> str:
    return os.path.join(_model_dir(), settings.breach_model_file)


def _compute_historical_breach_rate(db: Session, lens_type: str, coating: str, store_location: str) -> float:
    """Compute historical breach rate for similar orders."""
    total = (
        db.query(models.Order)
        .filter(
            models.Order.lens_type == lens_type,
            models.Order.coating == coating,
            models.Order.store_location == store_location,
            models.Order.delivered_at.isnot(None),
        )
        .count()
    )
    if total == 0:
        return 0.0
    breached = (
        db.query(models.Order)
        .filter(
            models.Order.lens_type == lens_type,
            models.Order.coating == coating,
            models.Order.store_location == store_location,
            models.Order.delivered_at.isnot(None),
            models.Order.breach_flag == True,
        )
        .count()
    )
    return breached / total


def _order_to_features(order: models.Order, db: Session, qc_failed: bool = False) -> pd.DataFrame:
    """Convert an Order ORM object into a one-row feature DataFrame."""
    store = order.store_location
    if store not in STORE_SPEED:
        store = "Mumbai"

    created = order.created_at or datetime.utcnow()
    hour = created.hour
    day_of_week = created.weekday()
    days_since_start = max(0, (created - datetime(2024, 1, 1)).days)

    historical_breach_rate = _compute_historical_breach_rate(
        db, order.lens_type or "Single Vision", order.coating or "Standard", store
    )

    return pd.DataFrame([{
        "store_location": store,
        "lens_type": order.lens_type or "Single Vision",
        "power": float(order.power) if order.power is not None else 0.0,
        "abs_power": abs(float(order.power)) if order.power is not None else 0.0,
        "lens_index": float(order.lens_index) if order.lens_index is not None else 1.5,
        "coating": order.coating or "Standard",
        "frame": order.frame or "Round",
        "source": order.source or "Website",
        "inventory_available": bool(order.inventory_available),
        "procurement_needed": bool(order.procurement_needed),
        "current_status": order.current_status if order.current_status in ORDER_STAGES else "Order Placed",
        "qc_failed": bool(qc_failed),
        "sla_hours": float(order.sla_hours) if order.sla_hours else 72.0,
        "hour_of_day": hour,
        "day_of_week": day_of_week,
        "days_since_start": days_since_start,
        "historical_breach_rate": round(historical_breach_rate, 3),
        "coating_index_interaction": f"{(order.coating or 'Standard')}_{float(order.lens_index) if order.lens_index else 1.5}",
    }])


def _build_historical_df(orders: List[models.Order], db: Session) -> pd.DataFrame:
    rows = []
    start_date = datetime(2024, 1, 1)

    # Pre-compute breach rates for all delivered orders
    breach_rates = {}
    for o in orders:
        key = (o.lens_type, o.coating, o.store_location)
        if key not in breach_rates:
            total = sum(1 for x in orders if (x.lens_type, x.coating, x.store_location) == key)
            breached = sum(1 for x in orders if (x.lens_type, x.coating, x.store_location) == key and x.breach_flag)
            breach_rates[key] = breached / total if total > 0 else 0.0

    for o in orders:
        if o.delivered_at is None or o.created_at is None:
            continue
        actual_hours = (o.delivered_at - o.created_at).total_seconds() / 3600.0
        qc_failed = any(h.status in {"QC Failed", "Rework"} for h in o.status_history)
        created = o.created_at
        key = (o.lens_type, o.coating, o.store_location)
        rows.append({
            "store_location": o.store_location if o.store_location in STORE_SPEED else "Mumbai",
            "lens_type": o.lens_type,
            "power": float(o.power),
            "abs_power": abs(float(o.power)),
            "lens_index": float(o.lens_index),
            "coating": o.coating,
            "frame": o.frame or "Round",
            "source": o.source or "Website",
            "inventory_available": bool(o.inventory_available),
            "procurement_needed": bool(o.procurement_needed),
            "current_status": "Delivered",
            "qc_failed": qc_failed,
            "sla_hours": float(o.sla_hours),
            "hour_of_day": created.hour,
            "day_of_week": created.weekday(),
            "days_since_start": max(0, (created - start_date).days),
            "historical_breach_rate": round(breach_rates.get(key, 0.0), 3),
            "coating_index_interaction": f"{o.coating}_{o.lens_index}",
            "actual_hours": actual_hours,
            "breached": int(actual_hours > o.sla_hours),
        })
    return pd.DataFrame(rows)


def _categorical_features() -> List[str]:
    return [
        "store_location", "lens_type", "coating", "current_status",
        "frame", "source", "coating_index_interaction",
    ]


def _numerical_features() -> List[str]:
    return [
        "power", "abs_power", "lens_index", "inventory_available",
        "procurement_needed", "qc_failed", "sla_hours", "hour_of_day",
        "day_of_week", "days_since_start", "historical_breach_rate",
    ]


def _make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), _categorical_features()),
            ("num", StandardScaler(), _numerical_features()),
        ]
    )


def _train_pipeline(df: pd.DataFrame, target_col: str, model, param_grid: dict) -> Tuple[Optional[Pipeline], Optional[float]]:
    if df.empty or len(df) < 30:
        return None, None

    X = df[_categorical_features() + _numerical_features()]
    y = df[target_col].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = Pipeline([
        ("prep", _make_preprocessor()),
        ("model", model(random_state=42)),
    ])

    # Limit grid search on smaller datasets to avoid overfitting and keep training fast
    cv_folds = min(5, len(X_train) // 10) or 2
    grid = GridSearchCV(
        pipeline,
        param_grid,
        cv=cv_folds,
        scoring="r2" if target_col == "actual_hours" else "accuracy",
        n_jobs=-1,
    )
    grid.fit(X_train, y_train)
    score = grid.score(X_test, y_test)
    return grid.best_estimator_, float(score)


def train_models(db: Session) -> dict:
    """Train TAT regressor and breach classifier on delivered historical orders."""
    orders = (
        db.query(models.Order)
        .filter(models.Order.delivered_at.isnot(None))
        .all()
    )
    df = _build_historical_df(orders, db)

    result = {"status": "no_data", "tat_model_score": None, "breach_model_score": None, "message": ""}

    if len(df) < 30:
        result["message"] = f"Not enough delivered orders to train: {len(df)} found (need >= 30)."
        return result

    tat_pipeline, tat_score = _train_pipeline(df, "actual_hours", GradientBoostingRegressor, GB_REGRESSOR_GRID)
    breach_pipeline, breach_score = _train_pipeline(df, "breached", GradientBoostingClassifier, GB_CLASSIFIER_GRID)

    if tat_pipeline:
        with open(_tat_model_path(), "wb") as f:
            pickle.dump(tat_pipeline, f)
    if breach_pipeline:
        with open(_breach_model_path(), "wb") as f:
            pickle.dump(breach_pipeline, f)

    result["status"] = "trained"
    result["tat_model_score"] = tat_score
    result["breach_model_score"] = breach_score
    result["message"] = f"Trained on {len(df)} orders."
    return result


def _load_model(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def predict_with_ml(order: models.Order, db: Session) -> Optional[dict]:
    """Return ML prediction or None if models are missing/unusable."""
    tat_pipeline = _load_model(_tat_model_path())
    breach_pipeline = _load_model(_breach_model_path())
    if tat_pipeline is None or breach_pipeline is None:
        return None

    qc_failed = any(h.status in {"QC Failed", "Rework"} for h in order.status_history)
    X = _order_to_features(order, db, qc_failed=qc_failed)

    try:
        predicted_hours = float(np.clip(tat_pipeline.predict(X)[0], a_min=1.0, a_max=None))
        breach_proba = float(breach_pipeline.predict_proba(X)[0][1])
    except Exception:
        return None

    risk_score = int(np.clip(breach_proba * 100, 0, 100))
    breach_flag = bool(breach_proba >= 0.5)

    return {
        "predicted_completion_hours": round(predicted_hours, 1),
        "risk_score": risk_score,
        "breach_flag": breach_flag,
        "breach_probability": round(breach_proba, 3),
    }


def models_exist() -> bool:
    return os.path.exists(_tat_model_path()) and os.path.exists(_breach_model_path())
