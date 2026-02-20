# 🚛 BAS World — AI Tractor Head Finder

> **An AI-powered multi-agent chatbot** that helps customers find the perfect tractor head from BAS World's inventory of **673+ vehicles** across **9 brands**, with natural-language search, structured filtering, side-by-side comparisons, and expert advisory capabilities.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct_Agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Terraform](https://img.shields.io/badge/Terraform-AWS_ECS-purple.svg)](https://www.terraform.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

---

## 📋 Table of Contents

1. [Problem & Solution Overview](#1-problem--solution-overview)
2. [System Architecture](#2-system-architecture)
3. [Agent Design — Tools, Memory & Decision Logic](#3-agent-design--tools-memory--decision-logic)
4. [Project Structure](#4-project-structure)
5. [Data & Inventory](#5-data--inventory)
6. [Frontend — UX & UI Design](#6-frontend--ux--ui-design)
7. [AWS Architecture & Terraform](#7-aws-architecture--terraform)
8. [Observability & Reliability](#8-observability--reliability)
9. [Setup & Running Locally](#9-setup--running-locally)
10. [Demo Flow — What to Show Live](#10-demo-flow--what-to-show-live)
11. [Testing the Bot — Questions & Expected Answers](#11-testing-the-bot--questions--expected-answers)
12. [Trade-offs & Future Improvements](#12-trade-offs--future-improvements)
13. [Evaluation Criteria Mapping](#13-evaluation-criteria-mapping)
14. [Presentation Deck & Verification Docs](#14-presentation-deck--verification-docs)

---

## 1. Problem & Solution Overview

### The Problem

BAS World is one of Europe's largest commercial vehicle dealers. Customers looking for tractor heads face:

- **Information overload** — 673+ vehicles with 30+ attributes each (brand, config, euro, power, price, mileage, gearbox, fuel, cabin, retarder, A/C, beds, etc.)
- **Complex filtering** — finding the right truck requires combining multiple technical criteria
- **Domain expertise gap** — not all customers know which specs they need for their use case (long-distance, heavy loads, distribution, etc.)
- **Language barriers** — customers come from multiple countries and languages

### The Solution

An **AI-powered conversational assistant** that:

| Capability | How It Works |
|---|---|
| 🗣️ **Natural language search** | "I need a DAF for long-distance, under €40k" → structured query |
| 🔍 **Multi-criteria filtering** | Brand, config, euro, gearbox, fuel, price, power, mileage, cabin... |
| 📊 **Side-by-side comparison** | Compare 2-5 vehicles in a structured table |
| 🧠 **Expert advisory** | Recommends specs based on use case (heavy loads → 6x4, 500+ HP, retarder) |
| 🌍 **Multilingual** | Responds in the user's language (English, Spanish, Dutch, etc.) |
| 💬 **Multi-turn memory** | Remembers context — "show cheaper ones" refines previous search |
| 🎯 **Grounded responses** | Never invents vehicles — all results come from real inventory data |

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER                                       │
│                    (Browser / Chat Interface)                            │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ HTTP POST /chat
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI SERVER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  POST /chat   │  │ GET /meta    │  │GET /inventory│  │ GET /health│  │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  LANGGRAPH REACT AGENT                           │    │
│  │                                                                  │    │
│  │  ┌───────────┐    ┌──────────────────────┐                      │    │
│  │  │  System    │    │   chatbot_node       │◄─── SQLite Memory    │    │
│  │  │  Prompt    │───►│   (Gemini 2.5 Flash) │     (multi-turn)     │    │
│  │  └───────────┘    └──────────┬───────────┘                      │    │
│  │                              │                                   │    │
│  │                   ┌──────────┼──────────┐                       │    │
│  │                   ▼          ▼          ▼                        │    │
│  │           ┌──────────┐ ┌─────────┐ ┌──────────┐                │    │
│  │           │ search_  │ │compare_ │ │get_vehic.│                │    │
│  │           │inventory │ │vehicles │ │_details  │                │    │
│  │           └────┬─────┘ └────┬────┘ └────┬─────┘                │    │
│  │                │            │           │                       │    │
│  │                ▼            ▼           ▼                       │    │
│  │         ┌────────────────────────────────────┐                  │    │
│  │         │       pandas DataFrame (CSV)       │                  │    │
│  │         │         673 vehicles × 30 cols      │                  │    │
│  │         └────────────────────────────────────┘                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Service Orchestration Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  User    │────►│  FastAPI      │────►│  LangGraph   │────►│  OpenAI  │
│  Browser │◄────│  (main.py)    │◄────│  (graph.py)  │◄────│  Router  │
└──────────┘     └──────┬───────┘     └──────┬───────┘     └──────────┘
                        │                     │                   │
                        │                     ▼                   │
                        │              ┌──────────────┐           │
                        │              │  Tool Node    │           │
                        │              │  - search     │           │
                        │              │  - compare    │           │
                        │              │  - details    │           │
                        │              └──────┬───────┘           │
                        │                     ▼                   │
                        │              ┌──────────────┐           │
                        │              │  data_loader  │           │
                        │              │  (pandas CSV) │           │
                        │              └──────────────┘           │
                        ▼
                 ┌──────────────┐
                 │  Frontend    │
                 │  (index.html)│
                 │  + sidebar   │
                 │  + filters   │
                 └──────────────┘
```

---

## 3. Agent Design — Tools, Memory & Decision Logic

### 3.1 Agent Architecture (LangGraph ReAct Pattern)

The agent uses a **ReAct (Reasoning + Acting)** architecture via LangGraph:

```
                    ┌─────────────────────┐
                    │    START             │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │   chatbot_node      │◄──────────────┐
                    │   (LLM + System     │               │
                    │    Prompt)           │               │
                    └──────────┬──────────┘               │
                               │                          │
                     ┌─────────┴─────────┐                │
                     │ has tool_calls?    │                │
                     └────┬──────────┬───┘                │
                    YES   │          │ NO                  │
                          ▼          ▼                     │
               ┌──────────────┐  ┌──────┐                │
               │  ToolNode     │  │ END  │                │
               │  (execute     │  │      │                │
               │   tool call)  │  └──────┘                │
               └──────┬───────┘                           │
                      │      tool results                 │
                      └───────────────────────────────────┘
```

**Key design decisions:**

| Decision | Rationale |
|---|---|
| **Single-agent ReAct** (vs. multi-agent) | Simpler, faster, fewer LLM calls — sufficient for this domain |
| **Gemini 2.5 Flash** via OpenRouter | Fast, cost-effective, excellent function-calling capability |
| **SQL-backed memory** (`SqliteSaver`) | Persistent multi-turn conversations, survives restarts |
| **System prompt engineering** | Detailed format rules ensure consistent, scannable responses |
| **Temperature 0.3** | Low enough for factual accuracy, high enough for natural language |

### 3.2 Tools

The agent has **3 tools**, all grounded in the real inventory CSV:

#### `search_inventory(filters_json: str)`

**Purpose:** Structured search with 18+ filter dimensions.

**Input:** JSON string with optional fields:
```json
{
  "brand": "DAF",
  "configuration": "4X2",
  "euro": 6,
  "gearbox": "automatic",
  "fuel": "diesel",
  "min_price": 20000,
  "max_price": 50000,
  "min_power": 400,
  "cabin": "SLEEPER",
  "has_retarder": true,
  "sort_by": "price_asc",
  "limit": 5
}
```

**Output:** JSON with matching vehicles + count.

**Key behaviors:**
- Excludes damaged vehicles by default
- Supports 4 sort orders: `price_asc`, `price_desc`, `mileage_asc`, `power_desc`
- Partial-match on cabin name (e.g., "SLEEPER" matches "SUPER SPACE CAB SLEEPER")
- Returns structured data that the frontend renders as vehicle cards

#### `compare_vehicles(vehicle_ids: list[int])`

**Purpose:** Side-by-side comparison of 2-5 vehicles.

**Output:** Structured comparison with all key specs + human-readable summary.

#### `get_vehicle_details(vehicle_id: int)`

**Purpose:** Detailed view of a single vehicle by its ID.

### 3.3 Memory & Conversation Persistence

```python
# graph.py — SQLite-backed conversation memory
checkpointer = SqliteSaver(sqlite3.connect("data/memory.db"))
graph.compile(checkpointer=checkpointer)
```

- **Multi-turn context:** The agent remembers previous searches. "Show me cheaper" → adjusts `max_price` from prior search.
- **Session-based:** Each conversation has a unique `session_id` (UUID).
- **Persistent:** Survives server restarts via SQLite at `data/memory.db`.

### 3.4 Decision Logic — System Prompt

The system prompt (`SYSTEM_PROMPT` in `graph.py`) acts as the agent's "brain":

| Responsibility | Approach |
|---|---|
| **Intent detection** | The LLM naturally detects: search, refine, compare, advisory, greeting, out-of-scope |
| **Filter extraction** | Translates natural language to JSON tool arguments |
| **Domain knowledge** | Built-in knowledge: long-distance → 4x2, 450-530HP, sleeper, retarder |
| **Response formatting** | Strict rules: bullet lists for results, tables for comparisons, 3-5 sentences for advice |
| **Language detection** | Auto-responds in the user's language |
| **Grounding** | "NEVER invent vehicles" — always runs `search_inventory` first |

### 3.5 LLM Configuration

```python
# llm_client.py — OpenRouter integration
ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    model="google/gemini-2.5-flash",
    temperature=0.3,
    max_tokens=4096,
)
```

**Why OpenRouter?** Unified API that lets you swap models (Gemini, GPT-4o, Claude) without changing code. Currently using **Gemini 2.5 Flash** for the best balance of speed, cost, and quality.

---

## 4. Project Structure

```
bas_world/
├── app/                          # Application code
│   ├── agents/
│   │   ├── graph.py              # LangGraph ReAct agent + system prompt
│   │   └── state.py              # AgentState (messages, filters, intent)
│   ├── api/
│   │   └── main.py               # FastAPI endpoints (chat, inventory, meta)
│   ├── schemas/
│   │   └── schemas.py            # Pydantic models (TractorHead, SearchFilters, etc.)
│   ├── services/
│   │   ├── data_loader.py        # CSV loading, normalization, pandas operations
│   │   └── llm_client.py         # OpenRouter LLM configuration
│   └── tools/
│       └── search_inventory.py   # 3 LangChain tools (search, compare, details)
│
├── data/
│   └── trekkers.csv              # Inventory dataset (673 vehicles, 30+ columns)
│
├── frontend/
│   ├── index.html                # Chat UI with sidebar filters & vehicle cards
│   └── images/                   # Static assets (truck brand images)
│
├── infra/
│   └── terraform/
│       ├── main.tf               # AWS resources (S3, ECR, ECS, API GW, CloudWatch)
│       ├── variables.tf          # Configurable parameters
│       └── outputs.tf            # Deployment outputs
│
├── pres_basworld/                # 📊 Presentation Deck (10 HTML slides)
│   ├── index.html                # Slide runner & navigation
│   ├── title-slide.html          # Slide 1: Title
│   ├── slide-02-*.html           # Slide 2: Challenge & Objective
│   ├── slide-03-*.html           # Slide 3: Solution Architecture
│   ├── slide-04-*.html           # Slide 4: Conversational Behavior
│   ├── slide-05-*.html           # Slide 5: ReAct Engine
│   ├── slide-06-*.html           # Slide 6: Structured Search
│   ├── slide-07-*.html           # Slide 7: Advisory Demo
│   ├── slide-08-*.html           # Slide 8: Premium UX
│   ├── slide-09-*.html           # Slide 9: Infrastructure & Deployment
│   └── slide-10-*.html           # Slide 10: Conclusion & Roadmap
│
├── tests/
│   └── test_search.py            # 19 pytest tests (loader, search, tools)
│
├── solution_verification.md      # ✅ Requirement ↔ Code mapping
├── solution_defense.md           # 🛡️ Architecture decision justification
├── Dockerfile                    # Container image (python:3.11-slim)
├── docker-compose.yml            # API + LocalStack services
├── requirements.txt              # Python dependencies
├── run.bat                       # Windows quick-start script
├── .env                          # Environment variables (API keys)
└── .gitignore
```

---

## 5. Data & Inventory

### Dataset: `trekkers.csv`

| Metric | Value |
|---|---|
| Total vehicles | 673 |
| Columns | 30+ |
| File format | CSV (semicolon-separated) |
| File size | ~158 KB |

### Inventory Dimensions

| Dimension | Unique Values |
|---|---|
| **Brands** | DAF (219), Mercedes (105), Scania (94), MAN (90), Volvo (61), Iveco (55), Renault (32), Ford (14), Ginaf (1) |
| **Configurations** | 4X2 (577), 6X4 (48), 6X2 (37), 8X4 (3), 6X6 (2), 4X4 (2), 8X2 (1), 10X4 (1) |
| **Euro norms** | 2, 4, 5, 6 |
| **Gearboxes** | Automatic (641), Manual (23), Semi-automatic (5) |
| **Fuels** | Diesel (646), LNG (16), CNG (5), Electric (2), Unknown (2) |
| **Condition** | Used (majority), New |

### Data Normalization Pipeline (`data_loader.py`)

1. Load CSV with semicolon separator
2. Handle duplicate column names (CSV has repeated headers)
3. Translate Dutch gearbox names → English (`AUTOMAAT` → `automatic`, `HANDGESCHAKELD` → `manual`)
4. Normalize brand, cabin, configuration to uppercase
5. Normalize fuel to lowercase
6. Parse booleans, integers, floats with null handling

---

## 6. Frontend — UX & UI Design

### Design Philosophy

| Principle | Implementation |
|---|---|
| **BAS World branding** | Dark header (#1a1a1a), green accent (#00a651), Inter font |
| **Conversational first** | Chat-centric UI with markdown rendering, typing indicators |
| **Progressive discovery** | Welcome cards for common use cases → chat → filters |
| **Data density** | Vehicle cards show brand, model, config, power, euro, gearbox, fuel, price, mileage |
| **Brand identity in cards** | SVG truck illustrations with brand-specific color gradients |

### UI Components

```
┌─────────────────────────────────────────────────────────────────┐
│  BAS World    AI Tractor Head Finder   671 vehicles  [Filters]  │ ← Header
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                   │
│  🔍 FILTERS  │           💬 CHAT AREA                           │
│              │                                                   │
│  ☐ Brand     │     🚛 Find Your Perfect Tractor Head             │
│    DAF  (219)│     Tell me what you need...                      │
│    MERC (105)│                                                   │
│    SCAN  (94)│     ┌──────────┐  ┌──────────┐                   │
│    MAN   (90)│     │🌍 Long   │  │🔧 Specs  │                   │
│    VOLVO (61)│     │ Distance │  │  Search  │                   │
│    ...       │     └──────────┘  └──────────┘                   │
│              │     ┌──────────┐  ┌──────────┐                   │
│  ☐ Config    │     │💪 Heavy  │  │💰 Budget │                   │
│    4X2  (577)│     │  Loads   │  │ Friendly │                   │
│    6X4   (48)│     └──────────┘  └──────────┘                   │
│    6X2   (37)│                                                   │
│              │  ─────────────────────────────────────────────    │
│  ☐ Euro Norm │  [💰 Cheaper] [📊 Compare] [🛋️ Comfort] [➕ More] │
│  ☐ Gearbox   │  ┌────────────────────────────────────────────┐  │
│  ☐ Fuel Type │  │ Describe what you're looking for...    [▸] │  │
│  € Price     │  └────────────────────────────────────────────┘  │
│              │                                                   │
│ [🔎 Search]  │                                                   │
├──────────────┴──────────────────────────────────────────────────┤
```

### Vehicle Cards

Each vehicle card displays:

```
┌──────────────────────────────────────┐
│  [Brand-colored SVG truck graphic]   │
│  [USED]                        [NEW] │
├──────────────────────────────────────┤
│  DAF XF 480 FT                       │
│  SUPER SPACE CAB • 312,000 km        │
│  ┌─────┐ ┌───────┐ ┌────────┐       │
│  │ 4X2 │ │480 HP │ │Euro 6  │       │
│  └─────┘ └───────┘ └────────┘       │
│  ┌──────────┐ ┌────────┐ ┌───┐      │
│  │automatic │ │diesel  │ │A/C│      │
│  └──────────┘ └────────┘ └───┘      │
│──────────────────────────────────────│
│  € 32,500           312,000 km      │
│  Ref. no. 271313                     │
└──────────────────────────────────────┘
```

### Sidebar → Agent Integration

When the user selects filters in the sidebar and clicks **"🔎 Search with Filters"**, the frontend translates the selections into a **natural language query** that is sent to the agent:

```
User selects: Brand=DAF, Euro=6, Gearbox=automatic, Max price=€50,000
   ↓
Generated message: "Find tractor heads with: brand: DAF, Euro 6, automatic gearbox, maximum price €50.000"
   ↓
Agent receives natural language → extracts filters → calls search_inventory
   ↓
Results displayed as vehicle cards in chat
```

This approach keeps the agent as the **single source of intelligence** — the sidebar is a UX convenience, not a bypass.

---

## 7. AWS Architecture & Terraform

### Cloud Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS (eu-west-1)                          │
│                                                                  │
│   ┌──────────────────┐                                           │
│   │  API Gateway v2   │◄──── Public HTTPS endpoint               │
│   │  (HTTP protocol)  │                                          │
│   └────────┬─────────┘                                           │
│            │                                                     │
│   ┌────────▼──────────────────────────────────────────────┐     │
│   │              ECS Cluster (Fargate)                     │     │
│   │   ┌──────────────────────────────────────────────┐    │     │
│   │   │  Task Definition                              │    │     │
│   │   │  CPU: 512 (0.5 vCPU)  Memory: 1024 MB        │    │     │
│   │   │  ┌──────────────────────────────────────┐    │    │     │
│   │   │  │  Container: bas-world-chatbot-api     │    │    │     │
│   │   │  │  Image: ECR → :latest                 │    │    │     │
│   │   │  │  Port: 8000                           │    │    │     │
│   │   │  │  Env: OPENROUTER_MODEL, API_PORT      │    │    │     │
│   │   │  └──────────────────────────────────────┘    │    │     │
│   │   └──────────────────────────────────────────────┘    │     │
│   └───────────────────────────────────────────────────────┘     │
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│   │  S3 Bucket    │    │  ECR Registry │    │  CloudWatch Logs │  │
│   │  trekkers.csv │    │  Docker image │    │  14d retention   │  │
│   └──────────────┘    └──────────────┘    │  Container       │  │
│                                            │  Insights enabled│  │
│   ┌──────────────┐                         └──────────────────┘  │
│   │  IAM Role     │                                              │
│   │  ECS Task     │                                              │
│   │  Execution    │                                              │
│   └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Terraform Setup

| File | Purpose |
|---|---|
| `main.tf` | 8 resources: S3 bucket, S3 object, ECR repo, IAM role + policy, CloudWatch logs, ECS cluster + task def, API Gateway |
| `variables.tf` | 8 configurable vars: project name, env, region, LocalStack toggle, API port, model, CPU, memory |
| `outputs.tf` | 5 outputs: API endpoint, S3 bucket, ECR URL, ECS cluster name, log group |

**LocalStack support:**
```hcl
# Flip one variable to switch between local and production
variable "use_localstack" {
  default = true     # true = local dev, false = real AWS
}
```

**How to deploy:**
```bash
# Local (with LocalStack)
docker-compose up -d localstack
cd infra/terraform
terraform init
terraform plan
terraform apply -auto-approve

# Production (real AWS)
terraform apply -var="use_localstack=false"
```

### Git Strategy

```
main ──── production-ready code
  └── feature/* ──── development branches
```

---

## 8. Observability & Reliability

### Current Implementation

| Layer | Mechanism |
|---|---|
| **Application logs** | Structured logging via `structlog` (JSON format) with trace IDs |
| **Health checks** | `GET /health` endpoint, Docker HEALTHCHECK every 30s |
| **Container restarts** | `restart: unless-stopped` in docker-compose |
| **AWS logs** | CloudWatch Logs with 14-day retention + Container Insights |
| **Error handling** | Structured error responses from FastAPI (HTTP 404, 500) |
| **Agent tracing** | LLM call logging with token counts, latency, and tool invocations |

### Production Roadmap

| Improvement | Approach |
|---|---|
| **Tracing** | LangSmith or OpenTelemetry for full LLM call tracing (latency, tokens, cost) |
| **Metrics** | Prometheus metrics: request count, latency, LLM tokens, search result counts |
| **Alerting** | CloudWatch alarms on error rates, p95 latency, task failures |
| **Rate limiting** | API Gateway throttling + per-session rate limits to control costs |

---

## 9. Setup & Running Locally

### Prerequisites

- Python 3.11+ (tested with 3.13)
- An [OpenRouter](https://openrouter.ai/) API key

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-repo/bas-world-chatbot.git
cd bas-world-chatbot

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY

# 5. Run the server
uvicorn app.api.main:app --host 0.0.0.0 --port 8888

# 6. Open in browser
# http://localhost:8888
```

### Running with Docker

```bash
# Full stack (API + LocalStack)
docker-compose up -d

# API only
docker-compose up -d chatbot-api

# With Terraform infrastructure
docker-compose up -d localstack
cd infra/terraform
terraform init && terraform apply -auto-approve
```

### Running Tests

```bash
pip install pytest
python -m pytest tests/test_search.py -v  # 19 tests
```

---

## 10. Demo Flow — What to Show Live

### Recommended 10-minute Demo Script

#### 1️⃣ Welcome (30 sec)
- Open `http://localhost:8888`
- Show the BAS World branded interface, filters sidebar, welcome cards

#### 2️⃣ Natural Language Search (2 min)
- Click **"🌍 Long Distance"** welcome card
- Show the agent asking follow-up questions (budget, brand preference, gearbox)
- Agent calls `search_inventory` → vehicle cards appear with brand-colored SVGs

#### 3️⃣ Filter Refinement (1.5 min)
- Type: **"Show me cheaper options"** → agent picks up prior context, adjusts `max_price`
- Show that context persists across turns (multi-turn memory)

#### 4️⃣ Sidebar Filters (1.5 min)
- Toggle the **Filters** sidebar
- Select: Brand = SCANIA, Euro = 6, Gearbox = automatic
- Click **"🔎 Search with Filters"** → natural language query generated → agent processes

#### 5️⃣ Comparison (1.5 min)
- Type: **"Compare the first and third options"**
- Agent calls `compare_vehicles` → formatted comparison table appears

#### 6️⃣ Expert Advisory (1.5 min)
- Type: **"I need to transport heavy construction materials across Europe. What specs should I look for?"**
- Agent gives domain-expert advice (6x4, 500+ HP, retarder, heavy suspension)
- Then automatically searches inventory for matching vehicles

#### 7️⃣ Architecture & Code (1.5 min)
- Show `graph.py` → ReAct agent loop
- Show `search_inventory.py` → tool definitions
- Show `main.tf` → Terraform infrastructure
- Show test output → 19/19 passed

---

## 11. Testing the Bot — Questions & Expected Answers

### Test Scenarios

| # | User Input | Expected Behavior | Agent Intervenes How |
|---|---|---|---|
| 1 | *"I need a tractor for long-distance transport"* | Asks 2-3 follow-up questions (budget, brand, gearbox) | Intent: advisory → asks clarifiers |
| 2 | *"4x2, Euro 6, automatic, at least 450 HP, under €50,000"* | Directly searches and returns 5 matching vehicles | Extracts filters → `search_inventory({config:4X2, euro:6, ...})` |
| 3 | *"Show me cheaper options"* | Adjusts price from previous context, returns lower-priced vehicles | Uses multi-turn memory → `search_inventory({max_price: lower})` |
| 4 | *"Compare the first and third options"* | Table comparing two vehicles side-by-side | Extracts IDs → `compare_vehicles([id1, id3])` |
| 5 | *"Do you have any electric trucks?"* | Shows the 2 electric vehicles in inventory | `search_inventory({fuel: "electric"})` |
| 6 | *"What's the cheapest DAF with a retarder?"* | Finds DAF vehicles with retarder, sorted by price | `search_inventory({brand: "DAF", has_retarder: true, sort_by: "price_asc"})` |
| 7 | *"I need something for heavy loads"* | Advisory: recommends 6x4, 500+ HP, retarder, then searches | Domain knowledge → advisory → search |
| 8 | *"Necesito un camión para carga pesada"* (Spanish) | Responds in Spanish, same quality search | Auto language detection |
| 9 | *"Show me MAN trucks under 400 HP, manual gearbox"* | Returns filtered results (should be few — most are automatic) | `search_inventory({brand: "MAN", max_power: 400, gearbox: "manual"})` |
| 10 | *"What's the weather like?"* | Politely redirects to truck topics | Out-of-scope detection → redirect |

### Iteration Examples

```
User: "I need an automatic Euro 6 DAF"
Bot: [searches, returns 5 results around €30-50k]

User: "Show me cheaper options"
Bot: [re-searches with lower max_price, returns budget options]

User: "Any of these with a retarder?"
Bot: [adds has_retarder=true filter, refines results]

User: "Compare the first two"
Bot: [generates comparison table]
```

---

## 12. Trade-offs & Future Improvements

### Current Trade-offs

| Trade-off | Decision | Rationale |
|---|---|---|
| **Single agent vs. multi-agent** | Single ReAct | Lower latency, simpler debugging, sufficient for this domain |
| **CSV vs. database** | CSV + pandas | Simple, no infrastructure needed; works for 673 records |
| **Gemini Flash vs. GPT-4o** | Gemini 2.5 Flash via OpenRouter | Faster, cheaper, excellent tool-calling; swap via env var |
| **LocalStack vs. real AWS** | LocalStack for demo | Free, local, reproducible; flip `use_localstack=false` for production |
| **No authentication** | Open access | Demo/prototype scope; add JWT/OAuth2 for production |
| **SQLite memory** | File-based | Simple for single-instance; swap to Redis for horizontal scaling |

### Future Improvements

| Area | Improvement | Effort |
|---|---|---|
| **🔄 Streaming** | Server-Sent Events for token-by-token responses | Medium |
| **🖼️ Real images** | Integrate BAS World image CDN for vehicle photos | Low |
| **📊 Analytics** | Track popular searches, conversion funnel, popular brands | Medium |
| **🔒 Auth** | JWT tokens, session persistence across devices | Medium |
| **🌐 Multi-language UI** | i18n for frontend labels (not just chat responses) | Low |
| **📱 Mobile app** | React Native wrapper with push notifications | High |
| **🧠 RAG** | Add truck manuals/specs as retrieval-augmented context | Medium |
| **💳 Financing** | Integrate price calculator / financing options tool | Medium |
| **📈 Vector search** | Semantic search using embeddings for "trucks like this one" | Medium |
| **🔄 Live inventory** | Real-time sync with BAS World's actual inventory API | High |

---

## 13. Evaluation Criteria Mapping

| Criterion | Implementation | Evidence |
|---|---|---|
| **Agent quality — Tool usage** | 3 well-defined tools with structured I/O, 18+ filter dimensions | `search_inventory.py` |
| **Agent quality — Reasoning** | Domain knowledge in system prompt, multi-turn context, intent detection | `graph.py` SYSTEM_PROMPT |
| **Agent quality — Grounding** | Never invents data; all results from CSV; includes vehicle IDs | Rule: "NEVER invent vehicles" |
| **Terraform quality — Structure** | Modular: main.tf, variables.tf, outputs.tf; 8 resources | `infra/terraform/` |
| **Terraform quality — Reproducibility** | LocalStack support; `terraform apply -auto-approve` | `use_localstack` variable |
| **Communication — README** | This document — architecture, agent design, demo flow, test scenarios | `README.md` |
| **Communication — Presentation** | 10-slide HTML deck covering all topics with diagrams and examples | `pres_basworld/` |

---

## 14. Presentation Deck & Verification Docs

This project includes a **10-slide HTML presentation** and formal verification documents:

| Document | Description |
|---|---|
| **[📊 Presentation Deck](pres_basworld/index.html)** | Full slide deck with dark-mode premium design. Open in browser and navigate with arrows. |
| **[✅ Solution Verification](solution_verification.md)** | Explicit mapping of every case-study requirement to the code that implements it. |
| **[🛡️ Solution Defense](solution_defense.md)** | Technical justification for architecture choices (ReAct vs multi-agent, Pandas vs Vector DB, etc.). |

### Presentation Slide Overview

| # | Slide | Key Content |
|---|---|---|
| 1 | **Title** | BAS World AI Concierge Agent |
| 2 | **Challenge & Objective** | Problem statement + Requirement Verification Matrix |
| 3 | **Solution Architecture** | LangGraph ReAct flow diagram |
| 4 | **Conversational Behavior** | Context retention, disambiguation, follow-ups |
| 5 | **ReAct Engine** | Scenarios A & B with tool-call traces |
| 6 | **Structured Search** | 18+ filters, Pandas/SQL search engine |
| 7 | **Advisory Demo** | Scenario D: expert guidance flow |
| 8 | **Premium UX** | Glassmorphism UI, human-in-the-loop feel |
| 9 | **Infrastructure** | AWS ECS/Fargate, CI/CD, Observability |
| 10 | **Conclusion & Roadmap** | Requirements met, business impact, future phases |

---

## 📝 Notes

- **Focus on clarity over complexity** — the single-agent architecture is intentional; a multi-agent system would add latency and complexity without proportional benefit for this domain.
- **Mock services are explained** — LocalStack emulates AWS locally; the Terraform is production-ready when `use_localstack=false`.
- **Production scope items** — streaming responses, real images, authentication, and Redis-based memory are documented above as future improvements with estimated effort levels.

---

<div align="center">

**Built with ❤️ for the BAS World AI Engineering Case**

*Powered by LangGraph • FastAPI • Gemini 2.5 Flash • Terraform*

</div>
