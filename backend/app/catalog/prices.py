"""Price catalog & cost engine — pure functions, zero AI.

CRUD operations for unit prices and productivity rates live in the catalog
DB or YAML configuration. Never hardcoded in source code.

Core principle: every arithmetic operation is a pure function, fully
deterministic, and unit-tested. Zero AI involvement in quantity/price
calculation.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models.catalog import Price as PriceModel, LaborRate as LRModel


# ---------------------------------------------------------------------------
# Price cache (request-scoped, invalidated per session)
# ---------------------------------------------------------------------------

_price_cache: Dict[str, Optional[float]] = {}
_labor_rate_cache: Dict[str, Optional[float]] = {}


def invalidate_price_cache() -> None:
    """Clear the request-scoped price cache."""
    _price_cache.clear()
    _labor_rate_cache.clear()


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


# Process-level latch so the drift warning logs once, not per BOQ line.
_LACKS_LABOR_RATES_TABLE = False


def latest_labor_rate(db_session: Session, category: str) -> Optional[float]:
    """Latest catalog hourly rate for one labor category.

    Ordered by ``effective_from`` descending; None-tolerant so rates without
    a date still serve when they are the only row. A deployment whose
    migration chain predates the drifted ``labor_rates`` table (known gotcha)
    degrades to "no catalog rate" with a warning — resolution then falls to
    YAML/unpriced instead of failing the run. ONLY that exact condition
    degrades: SQLite surfaces it as ``OperationalError("no such table: …")``
    and any other failure (lock, connection loss, …) propagates loudly.

    Cached: rates don't change during a request.
    """
    cache_key = category
    if cache_key in _labor_rate_cache:
        return _labor_rate_cache[cache_key]

    from datetime import date as _date

    global _LACKS_LABOR_RATES_TABLE
    try:
        rates = db_session.query(LRModel).filter(LRModel.category == category).all()
    except OperationalError as exc:
        if "no such table" not in str(exc):
            raise  # transient/unknown DB fault — never misread as "no table"
        if not _LACKS_LABOR_RATES_TABLE:
            _LACKS_LABOR_RATES_TABLE = True
            logging.getLogger(__name__).warning(
                "labor_rates table is missing from this database "
                "(model/migration drift) -- falling back to YAML hourly rates"
            )
        _labor_rate_cache[cache_key] = None
        return None
    if not rates:
        _labor_rate_cache[cache_key] = None
        return None
    dated = sorted(rates, key=lambda r: r.effective_from or _date.min, reverse=True)
    hourly = dated[0].hourly_rate
    result = float(hourly) if hourly is not None else None
    _labor_rate_cache[cache_key] = result
    return result


def compute_labor_cost(
    db_session: Session,
    category: Optional[str],
    hours: float,
    yaml_hourly_rate: Optional[float],
) -> Dict[str, Any]:
    """Resolve a labor rate and price ``hours`` of it.

    Rate resolution order: catalog LaborRate(category, latest) > YAML
    ``hourly_rate`` > unpriced. Returns::

        {"unit_rate": float | None,
         "total_cost": float,        # 0.0 when unpriced — never a fake price
         "unpriced": bool,
         "rate_source": "catalog" | "yaml" | None}

    Rounding reuses the pure ``labor_cost`` Decimal rule.
    """
    rate: Optional[float] = None
    source: Optional[str] = None
    if category:
        rate = latest_labor_rate(db_session, category)
        if rate is not None:
            source = "catalog"
    if rate is None and yaml_hourly_rate is not None:
        rate = float(yaml_hourly_rate)
        source = "yaml"
    if rate is None:
        return {
            "unit_rate": None,
            "total_cost": 0.0,
            "unpriced": True,
            "rate_source": None,
        }
    return {
        "unit_rate": rate,
        "total_cost": labor_cost(hours, rate),
        "unpriced": False,
        "rate_source": source,
    }


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
        materials.append(
            {
                "id": str(m.id),
                "name": m.name,
                "unit": m.unit,
                "category": m.category,
                "latest_unit_price": latest_price,
            }
        )
    return materials


def get_latest_price(db_session: Session, material_name: str) -> Optional[float]:
    """Get the latest unit price for a material by name.

    Cached: prices don't change during a request.
    """
    cache_key = material_name
    if cache_key in _price_cache:
        return _price_cache[cache_key]

    from sqlalchemy import select
    from app.db.models.catalog import Material as MatModel

    stmt = select(MatModel).where(MatModel.name == material_name)
    mat = db_session.execute(stmt).scalar_one_or_none()
    if mat is None or not mat.prices:
        _price_cache[cache_key] = None
        return None
    sorted_prices = sorted(mat.prices, key=lambda p: p.effective_from or "", reverse=True)
    price = float(sorted_prices[0].unit_price)
    _price_cache[cache_key] = price
    return price


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
        db_session.query(PriceModel).filter_by(material_id=mat.id, currency=currency).first()
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
        rates.append(
            {
                "id": str(r.id),
                "name": r.name,
                "productivity_rate": float(r.productivity_rate) if r.productivity_rate else None,
                "hourly_rate": float(r.hourly_rate) if r.hourly_rate else None,
                "category": r.category,
                "effective_from": str(r.effective_from) if r.effective_from else None,
            }
        )
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
