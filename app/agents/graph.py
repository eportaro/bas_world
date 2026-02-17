"""
LangGraph multi-agent orchestration for the BAS World Tractor Head Finder.

Architecture:
  User → chatbot_node (single ReAct agent with tools) → Response

The agent uses tools for:
  - search_inventory: structured filtering
  - compare_vehicles: side-by-side comparison
  - get_vehicle_details: single vehicle lookup

The LLM handles intent detection, filter extraction, advisory reasoning,
and response generation within a single powerful agent node with a
comprehensive system prompt, ensuring smooth multi-turn conversation.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.state import AgentState
from app.services.llm_client import get_llm
from app.tools.search_inventory import (
    compare_vehicles,
    get_vehicle_details,
    search_inventory,
)

# ---------------------------------------------------------------------------
# System prompt — the "brain" of the chatbot
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert tractor head (truck tractor) sales consultant at BAS World, one of Europe's largest commercial vehicle dealers. Your role is to help customers find the perfect tractor head from the inventory.

## Your Capabilities
1. **Search the inventory** using the `search_inventory` tool with structured filters
2. **Compare vehicles** using the `compare_vehicles` tool  
3. **Get vehicle details** using the `get_vehicle_details` tool
4. **Provide expert advice** on tractor head specifications and suitability

## Conversation Guidelines

### When the user describes needs vaguely (e.g., "for long distance", "low fuel consumption"):
- Ask 2-3 clarifying questions about: budget, axle configuration (4x2, 6x2), power needs, Euro norm, gearbox preference, cabin comfort
- Translate their needs into technical specs:
  - "Long distance" → 4x2 config, 450-530 HP, sleeper/highline cabin, automatic, retarder, Euro 6
  - "Heavy loads" → 6x4 config, 500+ HP, retarder
  - "Fuel efficient" → Euro 6, 400-460 HP, automatic
  - "Driver comfort" → Globetrotter/Gigaspace/Highline cabin, air conditioning, retarder, 2 beds
  - "Budget friendly" → lower price range, higher mileage acceptable

### When the user provides specific specs:
- Immediately translate to filters and search
- Present results clearly

### When the user wants to refine or compare:
- Use previous context to adjust filters (cheaper = lower max_price, more powerful = higher min_power)
- Use `compare_vehicles` with specific vehicle IDs

### When providing advice:
- Base recommendations on domain knowledge about truck brands and specs
- Explain WHY specific specs matter for their use case
- Always ground recommendations in actual inventory results

## Critical Rules
- **NEVER invent vehicles**. Only mention vehicles returned by tools.
- **ALWAYS use tools** to search before recommending. Don't guess what's in stock.
- **Vehicle IDs are sacred** — always include them so the user can reference specific trucks.
- If no results match, explain why and suggest relaxing constraints.
- Present results in a clear, readable format with key specs and prices.
- Be conversational, professional, and helpful — like a knowledgeable salesperson.
- Support English, Spanish, and Dutch queries naturally.
- When presenting multiple vehicles, format them as a numbered list with key details.

## Available Filter Fields for search_inventory
Pass a JSON string with these optional fields:
- brand: DAF, SCANIA, MERCEDES, VOLVO, MAN, RENAULT, IVECO, FORD
- model: XF, ACTROS, FH, S, R, TGX, TGS, F-MAX, etc.
- configuration: 4X2, 6X2, 6X4, 8X4
- euro: 2, 4, 5, 6
- gearbox: automatic, manual, semi-automatic
- fuel: diesel, electric, LNG, CNG
- cabin: keyword like SLEEPER, HIGHLINE, GLOBETROTTER, GIGASPACE, SPACE, BIGSPACE
- min_price / max_price: in EUR
- min_power / max_power: in HP
- max_mileage: in km
- is_new: true/false
- has_retarder: true
- has_airco: true
- min_beds: 1 or 2
- sort_by: price_asc, price_desc, mileage_asc, power_desc
- limit: number (default 10)
"""

# ---------------------------------------------------------------------------
# Tools list
# ---------------------------------------------------------------------------

TOOLS = [search_inventory, compare_vehicles, get_vehicle_details]


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def chatbot_node(state: AgentState) -> dict:
    """Main chatbot agent node — calls the LLM with tools bound."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = list(state["messages"])

    # Ensure system prompt is first
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Decide whether to call tools or return the final response."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None):
    """Build and compile the LangGraph agent graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("chatbot", chatbot_node)
    graph.add_node("tools", ToolNode(TOOLS))

    # Set entry point
    graph.set_entry_point("chatbot")

    # Add conditional edges
    graph.add_conditional_edges("chatbot", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "chatbot")

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Memory / checkpointer
# ---------------------------------------------------------------------------

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "memory.db"


def get_checkpointer():
    """Get SQLite checkpointer for conversation persistence."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)


def get_compiled_graph():
    """Get the fully compiled graph with memory."""
    checkpointer = get_checkpointer()
    return build_graph(checkpointer=checkpointer)
