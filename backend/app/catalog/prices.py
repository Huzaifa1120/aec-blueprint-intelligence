"""Price catalog & cost engine — pure functions, zero AI.

CRUD operations for unit prices and productivity rates live in the catalog
DB or YAML configuration. Never hardcoded in source code.

Core principle: every arithmetic operation is a pure function, fully
deterministic, and unit-tested. Zero AI involvement in quantity/price
calculation.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.db.models.catalog import Price as PriceModel, LaborRate as LRModel


# ---------------------------------------------------------------------------
# Pure arithmetic functions (zero AI, fully deterministic)
# ---------------------------------------------------------------------------

def material_cost(quantity: float, unit_price: float) -> float:
    """Material cost = quantity * unit_price.

    Uses Decimal for precision, rounds to 2 decimal places.
    """
    result = Decimal(str(quantity)) * Decimal(str(unit_price))
    return float(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def labor_hours(measured_quantity: float, productivity_rate: float) -> float:
    """Labor hours = measured_quantity / productivity_rate.

    Productivity rate is units per labor-hour (e.g. m/hr, ea/hr).
    If productivity_rate = 3.0 m/hr and measured_quantity = 6.0 m,
    then labor_hours = 2.0 hr.
    """
    if productivity_rate <= 0:
        raise ValueError("Productivity rate must be positive")
    return round(measured_quantity / productivity_rate, 2)


def labor_cost(labor_hours: float, hourly_rate: float) -> float:
    """Labor cost = labor_hours * hourly_rate."""
    result = Decimal(str(labor_hours)) * Decimal(str(hourly_rate))
    return float(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def total_cost(
    material_cost: float,
    labor_cost: float,
    equipment_cost: float = 0.0,
    waste: float = 0.0,
    contingency: float = 0.0,
) -> float:
    """Total = material_cost + labor_cost + equipment_cost + waste + contingency."""
    total = Decimal(str(material_cost))
    total += Decimal(str(labor_cost))
    if equipment_cost:
        total += Decimal(str(equipment_cost))
    if waste:
        total += Decimal(str(waste))
    if contingency:
        total += Decimal(str(contingency))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Catalog CRUD — DB-backed, never hardcoded
# ---------------------------------------------------------------------------

def list_materials(db_session: Session) -> List[Dict[str, Any]]:
    """List all materials with their latest unit prices."""
    from sqlalchemy import select
    from app.db.models.catalog import Material as MatModel

    stmt = select(MatModel).order_by(MatModel.name)
    result = db_session.execute(stmt).scalars().all()
    materials = []
    for m in result:
        # Get latest price
        latest_price = None
        if m.prices:
            # Sort by effective_from descending, take first
            sorted_prices = sorted(m.prices, key=lambda p: p.effective_from or "", reverse=True)
            latest_price = sorted_prices[0].unit_price if sorted_prices else None
        materials.append({
            "id": str(m.id),
            "name": m.name,
            "unit": m.unit,
            "category": m.category,
            "latest_unit_price": latest_price,
        })
    return materials


def get_latest_price(db_session: Session, material_name: str) -> Optional[float]:
    """Get the latest unit price for a material by name."""
    from sqlalchemy import select
    from app.db.models.catalog import Material as MatModel

    stmt = select(MatModel).where(MatModel.name == material_name)
    mat = db_session.execute(stmt).scalar_one_or_none()
    if mat is None or not mat.prices:
        return None
    sorted_prices = sorted(mat.prices, key=lambda p: p.effective_from or "", reverse=True)
    return float(sorted_prices[0].unit_price)


def ingest_material_price(
    db_session: Session,
    material_name: str,
    unit_price: float,
    currency: str = "USD",
    effective_from: Optional[str] = None,
    effective_to: Optional[str] = None,
    source: Optional[str] = None,
) -> PriceModel:
    """Ingest/upgrade a unit price for a material.

    Creates the Material row if it does not exist.
    Returns the Price model record created/updated.
    """
    from sqlalchemy import select
    from app.db.models.catalog import Material as MatModel, Price as PriceModel

    # Find or create Material
    stmt = select(MatModel).where(MatModel.name == material_name)
    mat = db_session.execute(stmt).scalar_one_or_none()
    if mat is None:
        mat = MatModel(name=material_name, unit="ea")  # default unit
        db_session.add(mat)
        db_session.flush()

    # Create/overwrite Price record
    # Check if an effective_from already exists for this material
    existing_price = (
        db_session.query(PriceModel)
        .filter_by(material_id=mat.id, currency=currency)
        .first()
    )

    if existing_price:
        existing_price.unit_price = unit_price
        existing_price.effective_from = effective_from
        existing_price.effective_to = effective_to
        price_record = existing_price
    else:
        price_record = PriceModel(
            material_id=mat.id,
            unit_price=unit_price,
            currency=currency,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        db_session.add(price_record)

    db_session.flush()
    return price_record


def list_labor_rates(db_session: Session) -> List[Dict[str, Any]]:
    """List all labor rates with productivity rates and hourly rates."""
    from sqlalchemy import select
    from app.db.models.catalog import LaborRate as LRModel

    stmt = select(LRModel).order_by(LRModel.name)
    result = db_session.execute(stmt).scalars().all()
    rates = []
    for r in result:
        rates.append({
            "id": str(r.id),
            "name": r.name,
            "productivity_rate": float(r.productivity_rate) if r.productivity_rate else None,
            "hourly_rate": float(r.hourly_rate) if r.hourly_rate else None,
            "category": r.category,
            "effective_from": str(r.effective_from) if r.effective_from else None,
        })
    return rates


def ingest_labor_rate(
    db_session: Session,
    name: str,
    productivity_rate: float,
    hourly_rate: float,
    category: Optional[str] = None,
    effective_from: Optional[str] = None,
    effective_to: Optional[str] = None,
    source: Optional[str] = None,
) -> LRModel:
    """Ingest/upgrade a labor rate (productivity + hourly rate)."""
    from sqlalchemy import select

    # Find or create LaborRate
    stmt = select(LRModel).filter_by(name=name)
    lr = db_session.execute(stmt).scalar_one_or_none()
    if lr is None:
        lr = LRModel(name=name, productivity_rate=productivity_rate, hourly_rate=hourly_rate)
        db_session.add(lr)
        db_session.flush()

    # Update fields
    lr.productivity_rate = productivity_rate
    lr.hourly_rate = hourly_rate
    if category:
        lr.category = category
    if effective_from:
        lr.effective_from = effective_from
    if effective_to:
        lr.effective_to = effective_to

    db_session.flush()
    return lr


# ---------------------------------------------------------------------------
# Cost engine with "unpriced" flag (never $0)
# ---------------------------------------------------------------------------

def compute_boq_item(
    quantity: float,
    material_name: str,
    db_session: Session,
) -> Dict[str, Any]:
    """Compute a BOQ item cost with 'unpriced' flag if gap exists.

    Returns dict with:
    - quantity: float
    - unit_price: float | None (None means unpriced)
    - total_cost: float (0.0 if unpriced)
    - unpriced: bool (True if no price found in catalog)
    """
    unit_price = get_latest_price(db_session, material_name)

    unpriced = unit_price is None

    if unpriced:
        # Flag the gap, never substitute $0
        return {
            "quantity": quantity,
            "unit_price": None,
            "total_cost": 0.0,
            "unpriced": True,
            "material_name": material_name,
            "note": "Material price not found in catalog — flag for review",
        }
    else:
        mc = material_cost(quantity, unit_price)
        return {
            "quantity": quantity,
            "unit_price": unit_price,
            "total_cost": mc,
            "unpriced": False,
            "material_name": material_name,
        }