import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from prophet import Prophet
from sqlalchemy.orm import Session

from app import models

warnings.filterwarnings("ignore")


def _group_consumption(db: Session) -> Dict[int, pd.DataFrame]:
    """Return {inventory_id: DataFrame[ds, y]} of daily consumption."""
    rows = (
        db.query(
            models.InventoryConsumption.inventory_id,
            models.InventoryConsumption.date,
            models.InventoryConsumption.quantity_used,
        )
        .all()
    )

    df = pd.DataFrame(
        [(r.inventory_id, pd.to_datetime(r.date).date(), r.quantity_used) for r in rows],
        columns=["inventory_id", "date", "quantity_used"],
    )

    if df.empty:
        return {}

    grouped = {}
    for inv_id, g in df.groupby("inventory_id"):
        daily = g.groupby("date")["quantity_used"].sum().reset_index()
        daily.columns = ["ds", "y"]
        daily["ds"] = pd.to_datetime(daily["ds"])
        grouped[inv_id] = daily
    return grouped


def _fit_and_forecast(df: pd.DataFrame, periods: int) -> int:
    """Fit Prophet and return summed forecast for the next `periods` days."""
    if df.empty or len(df) < 5:
        return 0

    try:
        m = Prophet(daily_seasonality=False, yearly_seasonality=False, weekly_seasonality=True)
        m.fit(df)
        future = m.make_future_dataframe(periods=periods)
        forecast = m.predict(future)
        future_sum = forecast.tail(periods)["yhat"].clip(lower=0).sum()
        return max(0, int(round(future_sum)))
    except Exception:
        return 0


def forecast_inventory_demand(db: Session) -> List[dict]:
    """Return demand forecasts and recommendations for every inventory SKU."""
    consumption = _group_consumption(db)
    inventory_items = db.query(models.Inventory).all()
    results = []

    for item in inventory_items:
        df = consumption.get(item.id)
        if df is not None and not df.empty:
            forecast_7d = _fit_and_forecast(df, 7)
            forecast_30d = _fit_and_forecast(df, 30)
        else:
            # Fallback: use the existing static forecast_demand field
            forecast_7d = max(0, int(item.forecast_demand / 4))
            forecast_30d = max(0, int(item.forecast_demand))

        qty = item.quantity
        # More sensitive thresholds to produce a realistic mix of recommendations
        if qty == 0 or forecast_30d > qty * 1.2:
            recommendation = "Restock"
        elif qty > forecast_30d * 2.5 and qty > 20:
            recommendation = "Overstocked"
        else:
            recommendation = "Healthy"

        # Persist back to inventory row
        item.forecast_demand = forecast_30d
        item.recommendation = recommendation

        results.append({
            "inventory_id": item.id,
            "power": item.power,
            "lens_type": item.lens_type,
            "coating": item.coating,
            "current_quantity": qty,
            "forecast_demand_7d": forecast_7d,
            "forecast_demand_30d": forecast_30d,
            "recommendation": recommendation,
        })

    db.commit()
    return results


def record_consumption(db: Session, inventory_id: int, quantity: int, date: Optional[datetime] = None):
    """Log daily lens consumption for demand forecasting."""
    if date is None:
        date = datetime.utcnow()
    entry = models.InventoryConsumption(
        inventory_id=inventory_id,
        date=date,
        quantity_used=quantity,
    )
    db.add(entry)
