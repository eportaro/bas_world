"""
FastAPI backend for the BAS World Tractor Head Finder chatbot.
Exposes REST API endpoints for chat, inventory browsing, and health checks.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage

from app.agents.graph import get_compiled_graph
from app.schemas.schemas import ChatRequest, ChatResponse, VehicleCard
from app.services.data_loader import load_inventory, get_vehicle_by_id, get_dataframe, get_unique_values
from app.tools.search_inventory import search_inventory_direct
from app.schemas.schemas import SearchFilters
from app.utils.logging import (
    setup_logging,
    log_user_message,
    log_vehicle_cards,
    log_chat_complete,
    log_startup,
    log_error,
)

# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    setup_logging()
    load_inventory()
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    port = int(os.getenv("PORT", "8080"))
    log_startup(port, model)
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BAS World Tractor Head Finder",
    description="AI-powered chatbot for finding the perfect tractor head",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# ---------------------------------------------------------------------------
# Graph singleton
# ---------------------------------------------------------------------------

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = get_compiled_graph()
    return _graph


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bas-world-chatbot"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint."""
    t0 = time.time()
    log_user_message(request.session_id, request.message)

    graph = get_graph()
    config = {"configurable": {"thread_id": request.session_id}}

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=request.message)], "session_id": request.session_id},
            config=config,
        )
    except Exception as e:
        log_error(f"Agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Extract the last AI message
    ai_messages = [m for m in result["messages"] if m.type == "ai" and m.content]
    if not ai_messages:
        response_text = "I apologize, but I couldn't process your request. Could you please rephrase?"
    else:
        response_text = ai_messages[-1].content

    # Extract vehicle cards from tool call results
    vehicles = _extract_vehicle_cards(result["messages"])
    log_vehicle_cards(vehicles)

    elapsed_ms = (time.time() - t0) * 1000
    log_chat_complete(elapsed_ms, len(vehicles))

    return ChatResponse(
        session_id=request.session_id,
        message=response_text,
        vehicles=vehicles,
    )


@app.get("/inventory/{vehicle_id}")
async def get_inventory_item(vehicle_id: int):
    """Get a specific vehicle by ID."""
    vehicle = get_vehicle_by_id(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")
    return vehicle.model_dump()


@app.get("/inventory")
async def list_inventory(
    brand: str | None = None,
    configuration: str | None = None,
    euro: int | None = None,
    gearbox: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_power: int | None = None,
    limit: int = 20,
):
    """List/filter inventory with query parameters."""
    filters = SearchFilters(
        brand=brand,
        configuration=configuration,
        euro=euro,
        gearbox=gearbox,
        min_price=min_price,
        max_price=max_price,
        min_power=min_power,
        limit=limit,
    )
    results = search_inventory_direct(filters)
    return {
        "count": len(results),
        "vehicles": [v.model_dump() for v in results],
    }


@app.get("/meta.json")
async def get_meta():
    """Return filter metadata for the sidebar — unique values per dimension with counts."""
    df = get_dataframe()
    # Exclude damaged
    df_clean = df[df.get("is_damaged", pd.Series([False]*len(df))).apply(
        lambda x: str(x).strip().lower() not in ("true", "1", "yes") if pd.notna(x) else True
    )]

    def _count_by(col):
        """Return sorted list of {value, count} dicts for a column."""
        counts = df_clean[col].dropna().value_counts()
        return [{"value": str(v), "count": int(c)} for v, c in counts.items()]

    return {
        "total": len(df_clean),
        "brands": _count_by("brand"),
        "configurations": _count_by("configuration"),
        "euro_norms": sorted([int(x) for x in df_clean["euro"].dropna().unique() if int(x) > 0]),
        "gearboxes": _count_by("gearbox"),
        "fuels": _count_by("fuel"),
        "conditions": {
            "new": int(df_clean["is_new"].apply(lambda x: str(x).strip().lower() in ("true", "1", "yes") if pd.notna(x) else False).sum()),
            "used": int((~df_clean["is_new"].apply(lambda x: str(x).strip().lower() in ("true", "1", "yes") if pd.notna(x) else False)).sum()),
        },
        "price_range": {
            "min": float(df_clean["internet_price"].dropna().min()) if not df_clean["internet_price"].dropna().empty else 0,
            "max": float(df_clean["internet_price"].dropna().max()) if not df_clean["internet_price"].dropna().empty else 0,
        },
        "power_range": {
            "min": int(df_clean["power"].dropna().min()) if not df_clean["power"].dropna().empty else 0,
            "max": int(df_clean["power"].dropna().max()) if not df_clean["power"].dropna().empty else 0,
        },
    }


# Serve static files for frontend images
IMAGES_DIR = FRONTEND_DIR / "images"
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the chat frontend."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>BAS World Chatbot API</h1><p>Frontend not found. Use /docs for API documentation.</p>")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_vehicle_cards(messages) -> list[VehicleCard]:
    """Extract vehicle data from the LAST tool call — handles all tool types.

    Supports:
      - search_inventory  → vehicles[] array
      - compare_vehicles  → vehicles[] array (only compared ones)
      - get_vehicle_details → single vehicle object
    """
    # Find the LAST tool message (any tool)
    last_tool_msg = None
    for msg in reversed(messages):
        if msg.type == "tool" and msg.name in ("search_inventory", "compare_vehicles", "get_vehicle_details"):
            last_tool_msg = msg
            break

    if last_tool_msg is None:
        return []

    cards = []
    try:
        data = json.loads(last_tool_msg.content)

        # get_vehicle_details returns a single vehicle dict (no "vehicles" key)
        if last_tool_msg.name == "get_vehicle_details":
            if "vehicle_id" in data:
                cards.append(_dict_to_card(data))
        else:
            # search_inventory and compare_vehicles both return {"vehicles": [...]}
            for v in data.get("vehicles", []):
                if v.get("vehicle_id"):
                    cards.append(_dict_to_card(v))
    except (json.JSONDecodeError, KeyError):
        pass

    return cards


def _dict_to_card(v: dict) -> VehicleCard:
    """Convert a vehicle dict to a VehicleCard."""
    return VehicleCard(
        vehicle_id=v.get("vehicle_id"),
        brand=v.get("brand"),
        model_extended=v.get("model_extended"),
        configuration=v.get("configuration"),
        cabin=v.get("cabin"),
        power=v.get("power"),
        euro=v.get("euro"),
        gearbox=v.get("gearbox"),
        fuel=v.get("fuel"),
        mileage=v.get("mileage"),
        internet_price=v.get("internet_price"),
        is_new=v.get("is_new"),
        retarder=v.get("retarder"),
        has_airco=v.get("has_airco"),
        bed_amount=v.get("bed_amount"),
        suspension=v.get("suspension"),
        total_weight=v.get("total_weight"),
        wheelbase=v.get("wheelbase"),
        registered_at=v.get("registered_at"),
        production_at=v.get("production_at"),
        has_hydraulics=v.get("has_hydraulics"),
    )
