"""
Pydantic schemas for the BAS World Tractor Head Finder chatbot.
Defines data models for vehicles, search filters, and API contracts.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vehicle model
# ---------------------------------------------------------------------------

class TractorHead(BaseModel):
    """Represents a single tractor head from the inventory."""

    vehicle_id: int
    euro: Optional[int] = None
    model: Optional[str] = None
    model_extended: Optional[str] = None
    brand: Optional[str] = None
    configuration: Optional[str] = None  # e.g. 4X2, 6X4
    cabin: Optional[str] = None
    length: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    power: Optional[int] = None  # HP
    mega: Optional[int] = None
    mileage: Optional[int] = None  # km
    wheelbase: Optional[int] = None
    gearbox: Optional[str] = None  # automatic / manual / semi-automatic
    registered_at: Optional[str] = None
    retarder: Optional[bool] = None
    internet_price: Optional[float] = None  # EUR
    is_new: Optional[bool] = None
    production_at: Optional[str] = None
    fuel: Optional[str] = None  # diesel / electric / LNG / CNG
    has_crane: Optional[bool] = None
    bed_amount: Optional[int] = None
    tank_amount: Optional[int] = None
    has_hydraulics: Optional[bool] = None
    is_damaged: Optional[bool] = None
    suspension: Optional[str] = None
    driver_side: Optional[str] = None
    has_airco: Optional[bool] = None
    total_weight: Optional[int] = None
    net_weight: Optional[int] = None

    def to_summary(self) -> str:
        """Human-readable one-line summary for LLM context."""
        price_str = f"€{self.internet_price:,.0f}" if self.internet_price and self.internet_price > 0 else "Price on request"
        mileage_str = f"{self.mileage:,} km" if self.mileage else "N/A"
        return (
            f"[ID:{self.vehicle_id}] {self.brand} {self.model_extended or self.model} | "
            f"{self.configuration} | {self.cabin} | {self.power} HP | "
            f"Euro {self.euro} | {self.gearbox} | {self.fuel} | "
            f"{mileage_str} | {price_str}"
        )

    def to_detail(self) -> str:
        """Multi-line detailed view for comparisons."""
        lines = [
            f"🚛 {self.brand} {self.model_extended or self.model} (ID: {self.vehicle_id})",
            f"   Configuration: {self.configuration}",
            f"   Cabin: {self.cabin}",
            f"   Power: {self.power} HP",
            f"   Euro norm: {self.euro}",
            f"   Gearbox: {self.gearbox}",
            f"   Fuel: {self.fuel}",
            f"   Mileage: {self.mileage:,} km" if self.mileage else "   Mileage: N/A",
            f"   Price: €{self.internet_price:,.0f}" if self.internet_price and self.internet_price > 0 else "   Price: On request",
            f"   New: {'Yes' if self.is_new else 'No'}",
            f"   Retarder: {'Yes' if self.retarder else 'No'}",
            f"   Air conditioning: {'Yes' if self.has_airco else 'No'}",
            f"   Beds: {self.bed_amount}" if self.bed_amount else "",
            f"   Suspension: {self.suspension}" if self.suspension else "",
            f"   Total weight: {self.total_weight:,} kg" if self.total_weight else "",
        ]
        return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Search filters
# ---------------------------------------------------------------------------

class SearchFilters(BaseModel):
    """Structured filters extracted from user queries."""

    brand: Optional[str] = Field(None, description="Brand name: DAF, SCANIA, MERCEDES, VOLVO, MAN, RENAULT, IVECO, FORD, GINAF")
    model: Optional[str] = Field(None, description="Model name, e.g. XF, ACTROS, FH, S, R, TGX")
    configuration: Optional[str] = Field(None, description="Axle configuration: 4X2, 6X2, 6X4, 8X4, etc.")
    euro: Optional[int] = Field(None, description="Euro emission norm: 0, 2, 4, 5, 6")
    gearbox: Optional[str] = Field(None, description="Gearbox type: automatic, manual, semi-automatic")
    fuel: Optional[str] = Field(None, description="Fuel type: diesel, electric, LNG, CNG")
    cabin: Optional[str] = Field(None, description="Cabin type keyword, e.g. SLEEPER, HIGHLINE, GLOBETROTTER, GIGASPACE, SPACE")
    min_price: Optional[float] = Field(None, description="Minimum price in EUR")
    max_price: Optional[float] = Field(None, description="Maximum price in EUR")
    min_power: Optional[int] = Field(None, description="Minimum engine power in HP")
    max_power: Optional[int] = Field(None, description="Maximum engine power in HP")
    min_mileage: Optional[int] = Field(None, description="Minimum mileage in km")
    max_mileage: Optional[int] = Field(None, description="Maximum mileage in km")
    is_new: Optional[bool] = Field(None, description="Filter for new vehicles only")
    has_retarder: Optional[bool] = Field(None, description="Must have retarder")
    has_airco: Optional[bool] = Field(None, description="Must have air conditioning")
    min_beds: Optional[int] = Field(None, description="Minimum number of beds in cabin")
    is_damaged: Optional[bool] = Field(None, description="Include/exclude damaged vehicles (default: exclude)")
    sort_by: Optional[str] = Field("price_asc", description="Sort order: price_asc, price_desc, mileage_asc, power_desc")
    limit: int = Field(5, description="Maximum number of results to return")


# ---------------------------------------------------------------------------
# API contracts
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    session_id: str = Field(..., description="Unique session/thread identifier")
    message: str = Field(..., description="User's message text")


class VehicleCard(BaseModel):
    """Simplified vehicle data for the frontend."""
    vehicle_id: int
    brand: Optional[str] = None
    model_extended: Optional[str] = None
    configuration: Optional[str] = None
    cabin: Optional[str] = None
    power: Optional[int] = None
    euro: Optional[int] = None
    gearbox: Optional[str] = None
    fuel: Optional[str] = None
    mileage: Optional[int] = None
    internet_price: Optional[float] = None
    is_new: Optional[bool] = None
    retarder: Optional[bool] = None
    has_airco: Optional[bool] = None
    bed_amount: Optional[int] = None


class ChatResponse(BaseModel):
    """Response sent back to the user."""
    session_id: str
    message: str = Field(..., description="Agent's response text")
    vehicles: list[VehicleCard] = Field(default_factory=list, description="Vehicle cards to display")
