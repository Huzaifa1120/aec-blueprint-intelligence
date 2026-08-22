"""Catalog API endpoints — price catalog CRUD and spreadsheet import.

Provides REST endpoints for catalog material price and labor rate management,
including spreadsheet import functionality for non-technical users to update
prices without code changes.

Constraints:
- All prices live in catalog DB or YAML — never hardcoded in source (AGENTS.md §3)
- Missing price → "unpriced", not $0 (AGENTS.md §17, trap.md §2)
- No blended confidence percentages — per-line discrete status only (AGENTS.md §7)
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.catalog import Material
from app.catalog.prices import (
    ingest_material_price,
    ingest_labor_rate,
)


router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _parse_csv_content(file_content: bytes) -> List[Dict[str, str]]:
    """Parse CSV content into list of dicts, using first row as header."""
    text = file_content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    # Strip whitespace from string values
    for row in rows:
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.strip()
    return rows


def _parse_xlsx_content(file_content: bytes) -> List[Dict[str, str]]:
    """Parse XLSX content into list of dicts using openpyxl.

    openpyxl is imported lazily to avoid hard dependency if not needed.
    """
    try:
        import openpyxl
    except ImportError:
        raise ValueError("openpyxl not installed — cannot parse .xlsx files")

    workbook = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    sheet = workbook.active

    # Use first row as header
    header = [cell.value if cell.value else "" for cell in sheet[1]]
    header = [h.strip() if isinstance(h, str) else h for h in header]

    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_dict = {}
        for i, value in enumerate(row):
            if i < len(header) and header[i]:
                row_dict[header[i]] = str(value).strip() if value else ""
        rows.append(row_dict)

    return rows


def _determine_row_type(row: Dict[str, str]) -> Optional[str]:
    """Determine if a row is a material price or labor rate.

    Heuristic: if 'rate_name' or 'productivity_rate' column present → labor rate
    if 'material_name' or 'unit_price' column present → material price
    """
    row_lower = {k.lower(): v for k, v in row.items()}
    if "rate_name" in row_lower or "productivity_rate" in row_lower:
        return "labor"
    if "material_name" in row_lower or "unit_price" in row_lower:
        return "material"
    return None


@router.post(
    "/import",
    summary="Import material prices and labor rates from CSV/Excel",
)
def import_catalog(
    file: UploadFile = File(
        ...,
        description="CSV or Excel file with material prices or labor rates.",
    ),
) -> Dict[str, Any]:
    """Import material prices and labor rates from CSV or Excel file.

    Supported formats:
    - CSV (.csv): Standard CSV with header row
    - Excel (.xlsx): Excel workbook with header row

    Expected column structures:

    **Materials CSV:**
    | Column | Required | Description |
    |---|---|---|
    | `material_name` | Yes | Name of the material |
    | `unit` | Yes | Unit of measure (ea, m, etc.) |
    | `unit_price` | Yes | Unit price in catalog currency |
    | `category` | No | Optional category (electrical, mechanical, etc.) |
    | `effective_from` | No | When this price takes effect (YYYY-MM-DD) |
    | `effective_to` | No | When this price expires (YYYY-MM-DD) |
    | `source` | No | Origin of price (e.g., "spreadsheet_import") |

    **Labor Rates CSV:**
    | Column | Required | Description |
    |---|---|---|
    | `rate_name` | Yes | Name of the labor rate |
    | `productivity_rate` | Yes | Units per labor-hour (e.g., m/hr, ea/hr) |
    | `hourly_rate` | Yes | Hourly rate in catalog currency |
    | `category` | No | Optional category |
    | `effective_from` | No | When this rate takes effect (YYYY-MM-DD) |
    | `effective_to` | No | When this rate expires (YYYY-MM-DD) |
    | `source` | No | Origin of rate (e.g., "spreadsheet_import") |

    Response:
    - `successful`: Number of rows successfully ingested
    - `failed`: Number of rows that failed validation
    - `errors`: Array of `{row, reason}` objects (1-indexed row numbers)

    Trap constraint compliance:
    - AGENTS.md §3: Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source
    - AGENTS.md §17: Missing price → "unpriced", not $0
    - Implementation uses existing `ingest_material_price()` and `ingest_labor_rate()` CRUD functions which mediate all catalog DB writes
    """
    # Read file content
    contents = file.file.read()

    # Determine file type
    filename = file.filename or ""
    file_lower = filename.lower()

    if file_lower.endswith(".xlsx"):
        try:
            rows = _parse_xlsx_content(contents)
        except ValueError as e:
            return {"successful": 0, "failed": 0, "errors": [{"row": 0, "reason": str(e)}]}
    else:
        # Assume CSV
        rows = _parse_csv_content(contents)

    if not rows:
        return {"successful": 0, "failed": 0, "errors": []}

    # Process rows using DB session
    successful = 0
    failed = 0
    errors: List[Dict[str, int | str]] = []

    # Use get_db() generator to get a session
    # Since this is a FastAPI endpoint, we need to manage the session lifecycle
    # For simplicity in this endpoint, we'll create our own session
    from app.db.session import create_engine

    engine = create_engine(get_settings().database_url)

    with Session(engine) as db_session:
        for idx, row in enumerate(rows, start=2):  # start=2 because row 1 is header
            row_type = _determine_row_type(row)

            if row_type is None:
                failed += 1
                errors.append({"row": idx, "reason": "could not determine row type — expected material_name or rate_name column"})
                continue

            try:
                if row_type == "material":
                    # Validate required fields for material
                    material_name = row.get("material_name")
                    unit = row.get("unit")
                    unit_price_str = row.get("unit_price")

                    if not material_name:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing material_name"})
                        continue
                    if not unit:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing unit"})
                        continue
                    if not unit_price_str:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing unit_price"})
                        continue

                    try:
                        unit_price = float(unit_price_str)
                    except (ValueError, TypeError):
                        failed += 1
                        errors.append({"row": idx, "reason": f"invalid unit_price format: '{unit_price_str}'"})
                        continue

                    effective_from = row.get("effective_from")
                    effective_to = row.get("effective_to")
                    source = row.get("source", "spreadsheet_import")

                    # Parse dates if provided
                    eff_from_date: Optional[date] = None
                    eff_to_date: Optional[date] = None
                    if effective_from:
                        try:
                            eff_from_date = date.fromisoformat(effective_from)
                        except (ValueError, TypeError):
                            pass  # ignore invalid date, proceed without effective_from
                    if effective_to:
                        try:
                            eff_to_date = date.fromisoformat(effective_to)
                        except (ValueError, TypeError):
                            pass  # ignore invalid date, proceed without effective_to

                    ingest_material_price(
                        db_session=db_session,
                        material_name=material_name,
                        unit_price=unit_price,
                        currency="USD",
                        effective_from=eff_from_date,
                        effective_to=eff_to_date,
                        source=source,
                    )
                    successful += 1

                elif row_type == "labor":
                    # Validate required fields for labor rate
                    rate_name = row.get("rate_name")
                    productivity_rate_str = row.get("productivity_rate")
                    hourly_rate_str = row.get("hourly_rate")

                    if not rate_name:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing rate_name"})
                        continue
                    if not productivity_rate_str:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing productivity_rate"})
                        continue
                    if not hourly_rate_str:
                        failed += 1
                        errors.append({"row": idx, "reason": "missing hourly_rate"})
                        continue

                    try:
                        productivity_rate = float(productivity_rate_str)
                    except (ValueError, TypeError):
                        failed += 1
                        errors.append({"row": idx, "reason": f"invalid productivity_rate format: '{productivity_rate_str}'"})
                        continue

                    try:
                        hourly_rate = float(hourly_rate_str)
                    except (ValueError, TypeError):
                        failed += 1
                        errors.append({"row": idx, "reason": f"invalid hourly_rate format: '{hourly_rate_str}'"})
                        continue

                    category = row.get("category")
                    effective_from = row.get("effective_from")
                    effective_to = row.get("effective_to")
                    source = row.get("source", "spreadsheet_import")

                    # Parse dates if provided
                    eff_from_date: Optional[date] = None
                    eff_to_date: Optional[date] = None
                    if effective_from:
                        try:
                            eff_from_date = date.fromisoformat(effective_from)
                        except (ValueError, TypeError):
                            pass
                    if effective_to:
                        try:
                            eff_to_date = date.fromisoformat(effective_to)
                        except (ValueError, TypeError):
                            pass

                    ingest_labor_rate(
                        db_session=db_session,
                        name=rate_name,
                        productivity_rate=productivity_rate,
                        hourly_rate=hourly_rate,
                        category=category,
                        effective_from=eff_from_date,
                        effective_to=eff_to_date,
                        source=source,
                    )
                    successful += 1

            except Exception as e:
                failed += 1
                errors.append({"row": idx, "reason": f" unexpected error: {str(e)[:100]}"})

        # Commit all ingested rows — without this, the Session context manager
        # rolls back every uncommitted change on exit and nothing persists.
        db_session.commit()

    return {"successful": successful, "failed": failed, "errors": errors}


@router.get(
    "/",
    summary="List catalog materials with latest prices",
)
def list_materials() -> List[Dict[str, Any]]:
    """List all materials with their latest unit prices."""
    from sqlalchemy import select

    from app.db.session import create_engine as _create_engine
    engine_obj = _create_engine(get_settings().database_url)

    with Session(engine_obj) as session:
        stmt = select(Material).order_by(Material.name)
        result = session.execute(stmt).scalars().all()
        materials = []
        for m in result:
            latest_price = None
            if m.prices:
                sorted_prices = sorted(m.prices, key=lambda p: p.effective_from or "", reverse=True)
                latest_price = sorted_prices[0].unit_price if sorted_prices else None
            materials.append({
                "id": str(m.id),
                "name": m.name,
                "unit": m.unit,
                "category": m.category,
                "latest_unit_price": float(latest_price) if latest_price is not None else None,
            })
    return materials