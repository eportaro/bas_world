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
import time
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
from app.utils.logging import (
    log_agent_thinking,
    log_agent_response,
    log_step,
    setup_logging,
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
**Context Matters:**
- **If the request is VAGUE** (e.g., "I need a truck for long distance" with no other details): **DO NOT** recommend specific trucks yet. Instead, ask 2-3 clarifying questions (e.g., Payload? Terrain? Driver preferences?) to tailor your advice.
- **If the request is DETAILED** (e.g., "Heavy loads, mountains, 500km daily"): Give your expert recommendation in **3-5 sentences**, then offer to search.

**Example (Vague Request):**
User: "What do you advise for long distance?"
Bot:
```
To give you the best advice, I need to know a bit more about your operation:
1. What is your typical payload weight?
2. Will you be driving in flat terrain or mountains?
3. Do you have a brand preference for driver comfort?
```

**Example (Detailed Request):**
User: "I haul 40 tons in the Alps, need good comfort."
Bot:
```
For heavy hauling in mountainous terrain, I highly recommend a 6x4 configuration with at least 500 HP and a retarder for safety. A Scania R-series or Volvo FH with a high-torque engine would be ideal.
```

## DOMAIN KNOWLEDGE (for advisory questions)
- **Long distance**: 4x2, 450-530 HP, sleeper/highline/globetrotter cabin, automatic, Euro 6
- **Heavy loads**: 6x4, 500+ HP, strong suspension
- **Fuel efficient**: Euro 6, 400-460 HP, automatic
- **Driver comfort**: Globetrotter/Gigaspace/Highline/Space cabin, automatic gearbox, 2+ beds — use cabin keyword filter to find these
- **Budget friendly**: higher mileage acceptable, older models, lower Euro norms
- **Regional/distribution**: 4x2 or 6x2, 350-450 HP, day cab or low sleeper

## ⚠ PROGRESSIVE SEARCH STRATEGY (CRITICAL — READ CAREFULLY)
When translating advisory knowledge into a search, NEVER apply all recommended specs at once.
Too many filters combined = 0 results. Instead, use this 2‑step approach:

**Step 1 — Broad search (2-3 core filters only):**
Pick only the most important filters for the use case:
- Long distance → `{"configuration": "4X2", "euro": 6, "gearbox": "automatic", "min_power": 400, "limit": 5}`
- Heavy loads → `{"configuration": "6X4", "min_power": 450, "limit": 5}`
- Budget → `{"sort_by": "price_asc", "limit": 5}`
DO NOT include cabin, retarder, airco, or beds in the first search.

**Step 2 — Narrow down (only if user asks):**
Once you have results, THEN mention which ones have retarder, sleeper cabin, A/C, etc.
Only add more filters if the user explicitly asks to narrow down.

**Rule:** If your search returns 0 results, IMMEDIATELY retry with fewer filters (remove cabin, retarder, airco, min_power one at a time) before telling the user "no results."

## CRITICAL RULES
- **NEVER invent vehicles**. Only reference trucks returned by your tools.
- **ALWAYS search first** before recommending. Never guess stock.
- **Include Vehicle IDs** so users can reference specific trucks (e.g., "ID: 271313").
- If no results match, **relax filters and retry** before saying "no results found."
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
- cabin: keyword like SLEEPER, HIGHLINE, GLOBETROTTER, GIGASPACE, SPACE, BIGSPACE — use this for comfort/premium searches
- min_price / max_price: in EUR
- min_power / max_power: in HP
- max_mileage: in km
- is_new: true/false
- min_beds: 1 or 2
- sort_by: price_asc, price_desc, mileage_asc, power_desc
- limit: number (default 5)

⚠️ DO NOT use has_airco or has_retarder — those fields are not reliable in the inventory data. Use cabin keyword instead to find premium/comfort trucks.
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
    log_agent_thinking()

    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = list(state["messages"])

    # Ensure system prompt is first
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))

    t0 = time.time()
    response = llm_with_tools.invoke(messages)
    elapsed = (time.time() - t0) * 1000

    # Log what the agent decided
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [{"name": tc["name"], "args": tc.get("args", {})} for tc in response.tool_calls]

    log_agent_response(
        response.content or "",
        tool_calls=tool_calls if tool_calls else None,
    )
    log_step(f"LLM latency: {elapsed:.0f}ms", "⏱️")

    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Decide whether to call tools or return the final response."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        log_step("Routing → TOOLS node", "🔀", "\033[93m")
        return "tools"
    log_step("Routing → END (final response)", "🔀", "\033[92m")
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
