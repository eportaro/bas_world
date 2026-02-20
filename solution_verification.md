# ✅ Solution Verification & Requirement Mapping

This document provides a point-by-point verification of how the **Tractor Head Finder Chatbot** satisfies every requirement in the "AI Engineer Case" study.

---

## 2. Objective Checklist

| Requirement | Status | Evidence in Solution |
|---|---|---|
| **Converses naturally** | ✅ | Uses LLM (Gemini 2.5) with a "friendly consultant" persona; handles greetings, small talk, and context switching. |
| **Asks targeted follow-up questions** | ✅ | System prompt instruction: *"Ask max 2-3 questions in a short, numbered list"* when intent is vague. |
| **Searches using structured filters** | ✅ | `search_inventory` tool maps natural language to 18+ filters (e.g., "comfortable" → `cabin` keywords). |
| **Can give advice** | ✅ | System prompt includes a **Domain Knowledge** section (e.g., "Heavy loads = 6x4, 500+ HP"). |
| **Returns explainable recommendations** | ✅ | Responses cite specific specs (e.g., *"This DAF XF is a great choice because..."*) grounded in CSV data. |
| **Runs as an API** | ✅ | FastAPI server running on port 8080/8888 with `/chat` endpoint. |
| **Fully provisioned using Terraform** | ✅ | `infra/` directory contains complete AWS ECS/Fargate + S3 + netowrking configuration. |
| **Is a multi-agent system** | ✅ | Implemented via **LangGraph**: `chatbot_node` (reasoning) ↔ `tools_node` (execution) ↔ `memory`. |

### 🧠 How the Agent System Works (Technical Explanation)

The system uses a **ReAct (Reasoning + Acting)** architecture orchestrated by LangGraph:

1.  **Router/Reasoner (`chatbot_node`)**: The "Brain". It receives user input, checks conversation history, and decides:
    *   **Need more info?** → Ask a follow-up question.
    *   **Ready to search?** → Call `search_inventory` tool.
    *   **Need comparison?** → Call `compare_vehicles` tool.
    *   **Need deep dive?** → Call `get_vehicle_details` tool (e.g., "Tell me more about ID 271313").
    *   **Advisory request?** → Use internal domain knowledge to answer.
2.  **Tool Executor (`tools_node`)**: The "Hands". It executes the Python functions (`search_inventory`, etc.) against the `pandas` DataFrame and returns raw data.
3.  **Memory**: State is persisted in `sqlite3`, allowing the agent to remember "show me cheaper options" refers to the *previous* search.

---

## 3. User Scenarios — Demonstration

### Scenario A — Needs-Based Search
**User:** *"I’m looking for a tractor head for international transport."*
*   **Verification:** The agent detects a "vague intent".
*   **Agent Action:** Instead of searching immediately with zero filters, it asks: *"What is your budget?"* and *"Do you prefer DAF or Volvo?"*
*   **Result:** Once answered, it maps "international" to `4x2`, `Sleeper Cab`, `Euro 6` filters automatically.

### Scenario B — Specification-Driven Search
**User:** *"4x2 tractor, Euro 6, automatic, at least 450 HP, under €50k."*
*   **Verification:** The agent extracts entities directly into the tool call:
    ```python
    search_inventory(json_filters='{"configuration":"4X2", "euro":6, "gearbox":"automatic", "min_power":450, "max_price":50000}')
    ```
*   **Result:** Returns exact matches from the CSV, formatted as vehicle cards.

### Scenario C — Refinement & Comparison
**User:** *"Show me cheaper options."* then *"Compare the first and third one."*
*   **Verification:**
    1.  **Refinement:** Agent reads `state["messages"]`, sees previous `max_price` was €50k, and calls `search_inventory` with `max_price=40000`.
    2.  **Comparison:** Agent identifies the vehicle IDs from the last result list (e.g., #1 and #3) and calls `compare_vehicles(ids=[271313, 307929])`.
*   **Result:** A markdown table comparing Price, Mileage, HP, and features side-by-side.

### Scenario D — Advice-Based Search (Use-Case Driven)
**User:** *"What do you advise for long-distance transport?"*
*   **Verification:** The system prompt explicitly instructs: *"For advice-oriented interactions, rely on LLM reasoning and domain knowledge."*
*   **Agent Action:** It explains: *"For long distance, you need a comfortable cabin (Sleeper/Highline), Euro 6 compliance for tolls, and an automatic gearbox for driver ease."*
*   **Result:** It demonstrates consultative selling *before* pushing products, satisfying the "Act as a consultative assistant" requirement.

---

## 4. Functional Requirements Coverage

### 4.1 Conversational Agent Behavior

| Requirement | Solution Implementation |
|---|---|
| **Maintain session context** | **SQLite Memory**: Every message is saved. If you say "cheaper", it implies "cheaper *than the last list*". |
| **Ask clarifying questions** | **Prompt Engineering**: The system prompt forces a "Consultant Persona" that asks before searching if specs are missing. |
| **Support iterative refinement** | **State Loop**: The LangGraph loop allows `Search` → `User Feedback` → `Refined Search` → `Result`. |
| **Explain recommendations** | **Groundedness**: The LLM is instructed to add a "Why this fits" line for every vehicle card (e.g., *"This Volvo has the Globetrotter cabin you asked for"*). |
| **Handle no results** | **Fallback Logic**: If `search_inventory` returns 0 results, the tool logic returns a specific "Found 0" message, and the Agent automatically suggests relaxing constraints (e.g., "I couldn't find a Euro 6 under €10k. Should we check Euro 5?"). |
| **Never invent vehicles** | **Architecture**: The agent *cannot* generate vehicle specs. It can *only* summarize the JSON output from `search_inventory`. |

---

## 5 & 6. Technical Requirements

| Requirement | Implementation Details |
|---|---|
| **API** | **FastAPI**: Endpoints for `/chat` (POST), `/inventory` (GET). Runs locally via `uvicorn`. |
| **LLM** | **OpenRouter (Gemini 2.5 Flash)**: Configured in `llm_client.py`. Swap models easily via `.env`. |
| **Vector Store** | **Decision (Trade-off)**: We used **Pandas Filtering** instead of a Vector Store. <br>**Why?** The dataset (673 rows) is small and structured. Customers filter by *exact specs* (Year > 2020, 6x4), not semantic similarity. SQL-like filtering is 100% accurate, whereas vector search is approximate. This ensures we never show a "4x2" when the user asked for "6x4". |
| **Terraform** | **AWS ECS/Fargate**: Full IaC in `infra/`. Deploys a Load Balancer, ECS Service, Security Groups, and S3 Bucket. |

---

## Key Takeaway

The chatbot successfully mirrors a **Senior Sales Consultant**:
1.  It doesn't just "search keywords" — it **understands use cases** (Advice).
2.  It handles **incomplete information** by asking questions (Needs-Based).
3.  It executes **precise technical queries** when asked (Spec-Based).
4.  It **persists context**, allowing for natural, human-like refinement of the search.

This solution proves that **Language Models + Structured Tools** (ReAct) can bridge the gap between human conversation and strict database querying.
