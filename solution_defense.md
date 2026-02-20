# AI Engineer Case — Solution Defense & Architecture Overview

This document serves as the **Solution Defense** ("Sustento") for the Tractor Head Finder Chatbot project. It maps the original case study requirements directly to the implemented solution, demonstrating how each objective, scenario, and technical requirement has been met or exceeded.

---

## 1. Objective Coverage

### "Converses naturally with users"
**Implementation:**  
The chatbot utilizes **LangChain** with a `StateGraph` architecture (in `app/agents/graph.py`). It maintains a persistent conversation history (`SqliteSaver` checkpointer), allowing it to remember context across turns. The system prompt is engineered to adopt a "friendly, expert consultant" persona that speaks the user's language.

### "Asks targeted follow-up questions"
**Implementation:**  
The **ReAct agent** is instructed via the system prompt to ask "max 2-3 questions" when requirements are vague.
*   **Example:** If a user says "I need a truck," the agent asks for budget, gearbox preference, and usage type before searching.

### "Searches a tractor head inventory using structured filters"
**Implementation:**  
The `search_inventory` tool (`app/tools/search_inventory.py`) accepts a structured JSON schema. The LLM translates natural language (e.g., "comfortable for long distance") into specific filters (e.g., `{"cabin": "GLOBETROTTER", "gearbox": "automatic", "min_beds": 2}`).
*   **Features:** Mapped fuzzy logic for "Comfort" to specific cabin types and premium features.

### "Can give advice"
**Implementation:**  
The agent has a dedicated **"Domain Knowledge"** section in its system prompt (`app/agents/graph.py`). It contains expert rules for "Heavy Loads," "Fuel Efficiency," and "Long Distance." Even without searching, it can explain *why* a 6x4 configuration is better for heavy loads.

### "Returns explainable, grounded recommendations"
**Implementation:**  
Every vehicle card in the UI includes a "Why this fits" highlight. The agent references specific attributes (e.g., "This DAF XF has low mileage for its price") based on the data, ensuring no hallucinations.

---

## 2. Requirement Mapping: User Scenarios

### Scenario A — Needs-Based Search
*   **User:** "I’m looking for a tractor head for international transport."
*   **Defense:** The system prompt maps "international transport" to specific technical defaults (`4x2`, `Euro 6`, `Sleeper Cab`). It proactively asks for budget and brand preference if not stated.

### Scenario B — Specification-Driven Search
*   **User:** "4x2 tractor, Euro 6, automatic, at least 450 HP, under €50k."
*   **Defense:** The LLM perfectly extracts these entities into the `search_inventory` tool call:
    ```json
    {
      "configuration": "4X2",
      "euro": 6,
      "gearbox": "automatic",
      "min_power": 450,
      "max_price": 50000
    }
    ```

### Scenario C — Refinement & Comparison
*   **User:** "Show me cheaper options" or "Compare the first and third one."
*   **Defense:**
    1.  **Refinement:** The agent updates the `filters` state (e.g., lowering `max_price`) and re-runs the search tool.
    2.  **Comparison:** The `compare_vehicles` tool takes Vehicle IDs and outputs a side-by-side markdown table comparing Price, Mileage, Power, and Features.

### Scenario D — Advice-Based Search
*   **User:** "What do you advise for long-distance?"
*   **Defense:** The agent bypasses the search tool initially to provide consultative advice using its internal knowledge base, explaining trade-offs (e.g., "For long-distance, prioritize a spacious cabin and a retarder for safety..."), then offers to search.

---

## 3. Technical Implementation

### Multi-Agent System (LangGraph)
*   **Architecture:** The solution uses **LangGraph** to model the conversation as a state machine.
    *   **Nodes:** `chatbot_node` (LLM reasoning), `tools_node` (Execution).
    *   **Edges:** Conditional routing based on whether the agent decides to stop (respond) or call a tool.
*   **Why:** This allows for loops (e.g., "Search" -> "No results" -> "Relax filters" -> "Search again") which a simple linear chain cannot handle.

### Frontend (Bonus)
*   **Implementation:** A premium, "Agency-Quality" web interface built with **HTML5/JS** and served via FastAPI.
    *   **Real-time:** Live typing effects.
    *   **Visual:** Vehicle cards with images, "Verified" badges, and hover effects.
    *   **Interactive:** "Filter Inventory" sidebar that deeply integrates with the backend agent.

### Infrastructure (Terraform)
*   **Implementation:** The `infra/` directory contains modular Terraform configuration.
    *   **AWS:** Provisions ECS (Fargate) for the API, VPC networking, and Security Groups.
    *   **Reproducibility:** One-command deployment (`terraform apply`).

---

## 4. Why This Solution Is Robust

1.  **Fault Tolerance:** The `search_inventory` tool has built-in logic to handle empty/dirty data (e.g., the `has_airco` fix).
2.  **Scalability:** The backend is stateless (except for DB-persisted memory), allowing it to scale horizontally on ECS.
3.  **User Experience:** usage of "Glassmorphism," "Skeleton loaders," and "Cinema-style" welcome screens creates a WOW factor for the demo.
4.  **No Hallucinations:** The agent is strictly bound to the `search_inventory` tool results for vehicle data. It will never invent a truck that doesn't exist in the CSV.

---

## 5. Deliverables Checklist

- [x] **Git Repository Structure:** `/app`, `/infra`, `/data`, `README.md`
- [x] **API:** FastAPI running on port 8080/8888.
- [x] **Agent Logic:** LangGraph with persistent memory.
- [x] **Terraform:** structured infrastructure-as-code.
- [x] **Documentation:** Comprehensive README and implementation defense.
