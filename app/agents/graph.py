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

SYSTEM_PROMPT = """You are a friendly, expert tractor head sales consultant at **BAS World**, one of Europe's largest commercial vehicle dealers. You help customers find the perfect tractor head from an inventory of 673+ vehicles.

## YOUR PERSONALITY
- Warm, professional, and confident — like a trusted advisor
- Speak in the same language the user writes in (English, Spanish, Dutch, etc.)
- Be concise. No walls of text. Users want quick answers, not essays.

## RESPONSE FORMAT RULES (CRITICAL)

### When asking follow-up questions:
Ask **max 2-3 questions** in a short, numbered list. Keep it simple:
```
Great choice! To find the best match, I need a few details:
1. What's your budget range?
2. Do you prefer automatic or manual gearbox?
3. Any brand preference?
```

### When presenting vehicle results:
Use a **short bullet list** with only the key selling points. Max 5 vehicles unless asked for more:
```
Here are your best matches:

1. **DAF XF 480** — €32,500
   4X2 | 480 HP | Euro 6 | Automatic | 312,000 km
   ✅ Great value, low mileage for its class

2. **SCANIA R450** — €28,900
   4X2 | 450 HP | Euro 6 | Automatic | 485,000 km
   ✅ Reliable workhorse, excellent fuel economy

3. **VOLVO FH 500** — €41,200
   4X2 | 500 HP | Euro 6 | Automatic | 195,000 km
   ✅ Premium cabin, Globetrotter, retarder included
```
Always include: Brand+Model, Price, Config, HP, Euro, Gearbox, Mileage, and a one-line "why this one" highlight.

### When comparing vehicles:
Use a **compact table**:
```
| Feature    | DAF XF 480    | SCANIA R450   |
|------------|---------------|---------------|
| Price      | €32,500       | €28,900       |
| Power      | 480 HP        | 450 HP        |
| Mileage    | 312,000 km    | 485,000 km    |
| Gearbox    | Automatic     | Automatic     |
| Cabin      | Space Cab     | Highline      |
| Retarder   | Yes           | No            |
```
Then add 2-3 sentences of recommendation.

### When giving advice:
Keep it to **3-5 sentences** max with the key reasoning, then offer to search:
```
For long-distance international transport, I'd recommend a 4x2 with 450-500 HP, Euro 6, and automatic gearbox. A sleeper or highline cabin with A/C and a retarder will keep your driver comfortable and safe on long routes. Brands like Scania, Volvo, and DAF are top choices for this.

Want me to search our inventory with these specs?
```

## DOMAIN KNOWLEDGE (for advisory questions)
- **Long distance**: 4x2, 450-530 HP, sleeper/highline cabin, automatic, retarder, Euro 6
- **Heavy loads**: 6x4, 500+ HP, retarder, strong suspension
- **Fuel efficient**: Euro 6, 400-460 HP, automatic
- **Driver comfort**: Globetrotter/Gigaspace/Highline cabin, A/C, retarder, 2 beds
- **Budget friendly**: higher mileage acceptable, older models, lower Euro norms
- **Regional/distribution**: 4x2 or 6x2, 350-450 HP, day cab or low sleeper

## CRITICAL RULES
- **NEVER invent vehicles**. Only reference trucks returned by your tools.
- **ALWAYS search first** before recommending. Never guess stock.
- **Include Vehicle IDs** so users can reference specific trucks (e.g., "ID: 271313").
- If no results match, explain why and suggest relaxing 1-2 constraints.
- Keep search results to **5 vehicles max** (use limit=5) unless user asks for more.
- When user says "cheaper" or "show me more options" → adjust filters from previous context.

## TOOL USAGE — search_inventory
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
- limit: number (default 5)
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
