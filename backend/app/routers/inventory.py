from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, require_role
from app.services.prediction import update_inventory_recommendations

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/", response_model=List[schemas.InventoryOut])
def list_inventory(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Inventory).all()


@router.post("/", response_model=schemas.InventoryOut)
def create_inventory(
    payload: schemas.InventoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    existing = db.query(models.Inventory).filter(
        models.Inventory.power == payload.power,
        models.Inventory.lens_type == payload.lens_type,
        models.Inventory.lens_index == payload.lens_index,
        models.Inventory.coating == payload.coating,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Inventory SKU already exists")

    item = models.Inventory(
        power=payload.power,
        lens_type=payload.lens_type,
        lens_index=payload.lens_index,
        coating=payload.coating,
        quantity=payload.quantity,
        forecast_demand=payload.forecast_demand,
        recommendation="",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    update_inventory_recommendations(db)
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.InventoryOut)
def update_inventory(
    item_id: int,
    payload: schemas.InventoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(["admin", "operations_manager"])),
):
    item = db.query(models.Inventory).filter(models.Inventory.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.forecast_demand is not None:
        item.forecast_demand = payload.forecast_demand
    if payload.recommendation is not None:
        item.recommendation = payload.recommendation
    update_inventory_recommendations(db)
    db.refresh(item)
    return item


@router.get("/consumption", response_model=List[schemas.InventoryConsumptionPoint])
def consumption_chart(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return daily inventory consumption aggregated across all SKUs for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(models.InventoryConsumption.date).label("day"),
            func.sum(models.InventoryConsumption.quantity_used).label("qty"),
        )
        .filter(models.InventoryConsumption.date >= since)
        .group_by(func.date(models.InventoryConsumption.date))
        .order_by(func.date(models.InventoryConsumption.date))
        .all()
    )
    return [{"date": str(r.day), "quantity": int(r.qty or 0)} for r in rows]


@router.get("/recommendations", response_model=List[schemas.InventoryOut])
def recommendations(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Inventory).filter(
        models.Inventory.recommendation.in_(["Restock", "Overstocked"])
    ).all()
