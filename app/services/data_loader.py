"""
Data loading and normalization service.
Loads the trekkers CSV inventory and provides access methods.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from app.schemas.schemas import TractorHead

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CSV_PATH = _DATA_DIR / "trekkers.csv"

# Gearbox translation map (Dutch → English)
GEARBOX_MAP = {
    "AUTOMAAT": "automatic",
    "HANDGESCHAKELD": "manual",
    "HALFAUTOMAAT": "semi-automatic",
}

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_df: Optional[pd.DataFrame] = None


def _parse_bool(val) -> Optional[bool]:
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("true", "1", "yes")


def _parse_int(val) -> Optional[int]:
    if pd.isna(val) or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_float(val) -> Optional[float]:
    if pd.isna(val) or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_inventory(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Load and normalize the trekkers CSV file."""
    global _df

    path = Path(csv_path) if csv_path else _CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Inventory CSV not found at {path}")

    df = pd.read_csv(path, sep=";", encoding="utf-8", low_memory=False)

    # Handle duplicate column names – the CSV has two 'cabin', 'brand', etc.
    # Keep only the first occurrence of each duplicate
    cols = list(df.columns)
    seen: dict[str, int] = {}
    new_cols = []
    for c in cols:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    # Normalize gearbox
    if "gearbox" in df.columns:
        df["gearbox"] = df["gearbox"].map(
            lambda x: GEARBOX_MAP.get(str(x).strip().upper(), str(x).strip().lower()) if pd.notna(x) else None
        )

    # Normalize fuel
    if "fuel" in df.columns:
        df["fuel"] = df["fuel"].map(
            lambda x: str(x).strip().lower() if pd.notna(x) else None
        )

    # Normalize brand to uppercase
    if "brand" in df.columns:
        df["brand"] = df["brand"].map(
            lambda x: str(x).strip().upper() if pd.notna(x) else None
        )

    # Normalize cabin to uppercase
    if "cabin" in df.columns:
        df["cabin"] = df["cabin"].map(
            lambda x: str(x).strip().upper() if pd.notna(x) else None
        )

    # Normalize configuration to uppercase
    if "configuration" in df.columns:
        df["configuration"] = df["configuration"].map(
            lambda x: str(x).strip().upper() if pd.notna(x) else None
        )

    # Normalize model to uppercase
    if "model" in df.columns:
        df["model"] = df["model"].map(
            lambda x: str(x).strip().upper() if pd.notna(x) else None
        )

    # Normalize all boolean columns from CSV strings ("true"/"false") to Python booleans
    BOOL_COLS = ["retarder", "is_new", "has_airco", "has_hydraulics", "has_crane", "is_damaged", "has_crane_hook"]
    for col in BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].map(_parse_bool)

    _df = df
    return df


def get_dataframe() -> pd.DataFrame:
    """Return the loaded DataFrame, loading it if necessary."""
    global _df
    if _df is None:
        load_inventory()
    return _df  # type: ignore


def get_vehicle_by_id(vehicle_id: int) -> Optional[TractorHead]:
    """Retrieve a single vehicle by its ID."""
    df = get_dataframe()
    match = df[df["vehicle_id"] == vehicle_id]
    if match.empty:
        return None
    row = match.iloc[0]
    return _row_to_tractor_head(row)


def get_all_vehicles() -> list[TractorHead]:
    """Return all vehicles as TractorHead objects."""
    df = get_dataframe()
    return [_row_to_tractor_head(row) for _, row in df.iterrows()]


def get_unique_values(column: str) -> list:
    """Get distinct values for a column (useful for enums)."""
    df = get_dataframe()
    if column not in df.columns:
        return []
    return sorted(df[column].dropna().unique().tolist())


def _row_to_tractor_head(row: pd.Series) -> TractorHead:
    """Convert a DataFrame row to a TractorHead model."""
    return TractorHead(
        vehicle_id=int(row.get("vehicle_id", 0)),
        euro=_parse_int(row.get("euro")),
        model=str(row.get("model", "")) if pd.notna(row.get("model")) else None,
        model_extended=str(row.get("model_extended", "")) if pd.notna(row.get("model_extended")) else None,
        brand=str(row.get("brand", "")) if pd.notna(row.get("brand")) else None,
        configuration=str(row.get("configuration", "")) if pd.notna(row.get("configuration")) else None,
        cabin=str(row.get("cabin", "")) if pd.notna(row.get("cabin")) else None,
        length=_parse_int(row.get("length")),
        width=_parse_int(row.get("width")),
        height=_parse_int(row.get("height")),
        power=_parse_int(row.get("power")),
        mega=_parse_int(row.get("mega")),
        mileage=_parse_int(row.get("mileage")),
        wheelbase=_parse_int(row.get("wheelbase")),
        gearbox=str(row.get("gearbox", "")) if pd.notna(row.get("gearbox")) else None,
        registered_at=str(row.get("registered_at", "")) if pd.notna(row.get("registered_at")) else None,
        retarder=_parse_bool(row.get("retarder")),
        internet_price=_parse_float(row.get("internet_price")),
        is_new=_parse_bool(row.get("is_new")),
        production_at=str(row.get("production_at", "")) if pd.notna(row.get("production_at")) else None,
        fuel=str(row.get("fuel", "")) if pd.notna(row.get("fuel")) else None,
        has_crane=_parse_bool(row.get("has_crane")),
        bed_amount=_parse_int(row.get("bed_amount")),
        tank_amount=_parse_int(row.get("tank_amount")),
        has_hydraulics=_parse_bool(row.get("has_hydraulics")),
        is_damaged=_parse_bool(row.get("is_damaged")),
        suspension=str(row.get("suspension", "")) if pd.notna(row.get("suspension")) else None,
        driver_side=str(row.get("driver_side", "")) if pd.notna(row.get("driver_side")) else None,
        has_airco=_parse_bool(row.get("has_airco")),
        total_weight=_parse_int(row.get("total_weight")),
        net_weight=_parse_int(row.get("net_weight")),
    )
