"""
Search inventory tool - structured filtering of the tractor head inventory.
Includes structured logging for agent tracing.
"""

from __future__ import annotations

import json
from typing import Optional

import pandas as pd
from langchain_core.tools import tool

from app.utils.logging import (
    log_tool_call,
    log_search_results,
    log_compare_results,
    log_detail_result,
    log_success,
    log_warning,
    log_error,
)

from app.schemas.schemas import SearchFilters, TractorHead
from app.services.data_loader import get_dataframe, _row_to_tractor_head


def _apply_filters(df: pd.DataFrame, filters: SearchFilters) -> pd.DataFrame:
    """Apply structured filters to the inventory DataFrame."""
    mask = pd.Series(True, index=df.index)

    # Exclude damaged by default
    if filters.is_damaged is None or filters.is_damaged is False:
        mask &= (df["is_damaged"] != True) | df["is_damaged"].isna()

    # Exclude zero-price vehicles unless specifically looking for new
    if filters.min_price is not None or filters.max_price is not None:
        mask &= df["internet_price"] > 0

    # Brand (exact match, case-insensitive)
    if filters.brand:
        mask &= df["brand"].str.upper().fillna("") == filters.brand.upper()

    # Model (contains match for flexibility)
    if filters.model:
        mask &= df["model"].fillna("").str.upper().str.contains(filters.model.upper(), na=False)

    # Configuration (exact)
    if filters.configuration:
        mask &= df["configuration"].fillna("").str.upper() == filters.configuration.upper()

    # Euro norm
    if filters.euro is not None:
        mask &= df["euro"] == filters.euro

    # Gearbox
    if filters.gearbox:
        gearbox_val = filters.gearbox.lower()
        mask &= df["gearbox"].fillna("").str.lower() == gearbox_val

    # Fuel type
    if filters.fuel:
        mask &= df["fuel"].fillna("").str.lower() == filters.fuel.lower()

    # Cabin (Smart match for "SLEEPER" and other premium terms)
    if filters.cabin:
        val = filters.cabin.upper()
        if val == "SLEEPER":
            # "Sleeper" should match all premium cabins with beds
            sleeper_keywords = [
                "SLEEPER", "SPACE", "HIGHLINE", "GLOBETROTTER", "GIGASPACE", 
                "TOPLINE", "SUPER", "BIGSPACE", "STREAMSPACE", "LONG", "L-CAB", "R-SERIES", "S-SERIES"
            ]
            # Create regex pattern for any of these
            pattern = "|".join(sleeper_keywords)
            mask &= df["cabin"].fillna("").str.upper().str.contains(pattern, regex=True, na=False)
        else:
            mask &= df["cabin"].fillna("").str.upper().str.contains(val, na=False)

    # Price range
    if filters.min_price is not None:
        mask &= df["internet_price"] >= filters.min_price
    if filters.max_price is not None:
        mask &= df["internet_price"] <= filters.max_price

    # Power range (HP)
    if filters.min_power is not None:
        mask &= df["power"] >= filters.min_power
    if filters.max_power is not None:
        mask &= df["power"] <= filters.max_power

    # Mileage range
    if filters.min_mileage is not None:
        mask &= df["mileage"] >= filters.min_mileage
    if filters.max_mileage is not None:
        mask &= df["mileage"] <= filters.max_mileage

    # Boolean filters
    if filters.is_new is not None:
        if filters.is_new:
            mask &= df["is_new"] == True
        else:
            mask &= (df["is_new"] != True) | df["is_new"].isna()

    # has_retarder: disabled — 'retarder' column in CSV is unreliable (often empty/NaN)
    # if filters.has_retarder is not None and filters.has_retarder:
    #     mask &= df["retarder"] == True

    # has_airco: disabled — 'has_airco' column is empty for most records in the CSV
    # if filters.has_airco is not None and filters.has_airco:
    #     mask &= df["has_airco"] == True

    if filters.min_beds is not None:
        mask &= df["bed_amount"] >= filters.min_beds

    result = df[mask].copy()

    # Sorting
    sort_col, sort_asc = "internet_price", True
    if filters.sort_by:
        if filters.sort_by == "price_desc":
            sort_col, sort_asc = "internet_price", False
        elif filters.sort_by == "mileage_asc":
            sort_col, sort_asc = "mileage", True
        elif filters.sort_by == "power_desc":
            sort_col, sort_asc = "power", False

    if sort_col in result.columns:
        # Push zero/null prices to the end when sorting ascending
        if sort_col == "internet_price" and sort_asc:
            result = result.sort_values(
                by=sort_col, ascending=sort_asc,
                na_position="last",
                key=lambda s: s.replace(0, float("nan"))
            )
        else:
            result = result.sort_values(by=sort_col, ascending=sort_asc, na_position="last")

    return result.head(filters.limit)


@tool
def search_inventory(filters_json: str) -> str:
    """Search the tractor head inventory using structured filters.

    Args:
        filters_json: JSON string with filter fields. Supported fields:
            - brand: str (DAF, SCANIA, MERCEDES, VOLVO, MAN, RENAULT, IVECO, FORD)
            - model: str (XF, ACTROS, FH, S, R, TGX, etc.)
            - configuration: str (4X2, 6X2, 6X4, 8X4)
            - euro: int (emission norm: 2, 4, 5, 6)
            - gearbox: str (automatic, manual, semi-automatic)
            - fuel: str (diesel, electric, LNG, CNG)
            - cabin: str (keyword: SLEEPER, HIGHLINE, GLOBETROTTER, GIGASPACE, SPACE)
            - min_price / max_price: float (EUR)
            - min_power / max_power: int (HP)
            - min_mileage / max_mileage: int (km)
            - is_new: bool
            - has_retarder: bool
            - has_airco: bool
            - min_beds: int
            - sort_by: str (price_asc, price_desc, mileage_asc, power_desc)
            - limit: int (default 10)

    Returns:
        JSON string with matching vehicles and count.
    """
    try:
        filters_dict = json.loads(filters_json)
        filters = SearchFilters(**filters_dict)
    except Exception as e:
        log_error(f"Invalid filters: {str(e)}")
        return json.dumps({"error": f"Invalid filters: {str(e)}", "count": 0, "vehicles": []})

    # Log the tool call with filters
    log_tool_call("search_inventory", filters_dict)

    df = get_dataframe()
    results_df = _apply_filters(df, filters)

    vehicles = [_row_to_tractor_head(row) for _, row in results_df.iterrows()]
    total_matching = len(vehicles)

    # Log results
    vehicle_dicts = [v.model_dump() for v in vehicles]
    log_search_results(total_matching, vehicle_dicts)

    output = {
        "count": total_matching,
        "filters_applied": filters_dict,
        "vehicles": vehicle_dicts,
        "summaries": [v.to_summary() for v in vehicles],
    }
    return json.dumps(output, default=str)


@tool
def get_vehicle_details(vehicle_id: int) -> str:
    """Get detailed information about a specific vehicle by its ID.

    Args:
        vehicle_id: The unique vehicle identifier.

    Returns:
        JSON string with vehicle details or error message.
    """
    from app.services.data_loader import get_vehicle_by_id
    vehicle = get_vehicle_by_id(vehicle_id)
    if vehicle is None:
        return json.dumps({"error": f"Vehicle with ID {vehicle_id} not found."})
    return json.dumps(vehicle.model_dump(), default=str)


@tool
def compare_vehicles(vehicle_ids: list[int]) -> str:
    """Compare multiple vehicles side by side.

    Args:
        vehicle_ids: List of 2-5 vehicle IDs to compare.

    Returns:
        JSON string with comparison data.
    """
    from app.services.data_loader import get_vehicle_by_id

    if len(vehicle_ids) < 2:
        return json.dumps({"error": "Please provide at least 2 vehicle IDs to compare."})
    if len(vehicle_ids) > 5:
        return json.dumps({"error": "Please provide at most 5 vehicle IDs to compare."})

    vehicles = []
    not_found = []
    for vid in vehicle_ids:
        v = get_vehicle_by_id(vid)
        if v:
            vehicles.append(v)
        else:
            not_found.append(vid)

    if not_found:
        return json.dumps({"error": f"Vehicles not found: {not_found}"})

    # Build comparison table
    comparison = {
        "vehicle_count": len(vehicles),
        "vehicles": [v.model_dump() for v in vehicles],
        "comparison_text": _build_comparison_text(vehicles),
    }
    return json.dumps(comparison, default=str)


def _build_comparison_text(vehicles: list[TractorHead]) -> str:
    """Build a human-readable comparison text."""
    lines = ["COMPARISON TABLE", "=" * 60]

    fields = [
        ("Brand & Model", lambda v: f"{v.brand} {v.model_extended or v.model}"),
        ("Price", lambda v: f"€{v.internet_price:,.0f}" if v.internet_price and v.internet_price > 0 else "On request"),
        ("Power", lambda v: f"{v.power} HP" if v.power else "N/A"),
        ("Mileage", lambda v: f"{v.mileage:,} km" if v.mileage else "N/A"),
        ("Configuration", lambda v: v.configuration or "N/A"),
        ("Cabin", lambda v: v.cabin or "N/A"),
        ("Euro", lambda v: str(v.euro) if v.euro else "N/A"),
        ("Gearbox", lambda v: v.gearbox or "N/A"),
        ("Fuel", lambda v: v.fuel or "N/A"),
        ("New", lambda v: "Yes" if v.is_new else "No"),
        ("Retarder", lambda v: "Yes" if v.retarder else "No"),
        ("Air conditioning", lambda v: "Yes" if v.has_airco else "No"),
        ("Beds", lambda v: str(v.bed_amount) if v.bed_amount else "N/A"),
        ("Suspension", lambda v: v.suspension or "N/A"),
    ]

    for label, getter in fields:
        values = [getter(v) for v in vehicles]
        line = f"{label:<20} | " + " | ".join(f"{val:<25}" for val in values)
        lines.append(line)

    return "\n".join(lines)


def search_inventory_direct(filters: SearchFilters) -> list[TractorHead]:
    """Direct Python API for search (used internally, not as LLM tool)."""
    df = get_dataframe()
    results_df = _apply_filters(df, filters)
    return [_row_to_tractor_head(row) for _, row in results_df.iterrows()]
