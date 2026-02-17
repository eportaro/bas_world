# 🚛 BAS World — AI Tractor Head Finder

An AI-powered multi-agent chatbot that helps customers find the perfect tractor head from BAS World's inventory of 673+ vehicles.

## Architecture

```
User ─→ Frontend (Chat UI) ─→ FastAPI ─→ LangGraph Agent ─→ Tools
                                                │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                        search_inventory   compare_vehicles   get_details
                              │
                        Pandas DataFrame
                        (trekkers.csv)
```

### Multi-Agent System (LangGraph)

The chatbot uses a **ReAct agent** pattern orchestrated by LangGraph:

1. **Intent Detection** — Classifies user intent (search, refine, compare, advise)
2. **Filter Extraction** — Converts natural language → structured JSON filters
3. **Tool Execution** — Calls the appropriate tool with extracted parameters
4. **Grounded Response** — Only references real vehicles from inventory
5. **Memory Persistence** — SQLite checkpointer maintains conversation context

### Key Technologies

| Component | Technology |
|-----------|-----------|
| LLM | Gemini 2.5 Flash via OpenRouter |
| Orchestration | LangGraph (ReAct agent) |
| API | FastAPI |
| Data | Pandas + CSV |
| Memory | SQLite checkpointer |
| Infrastructure | Terraform + LocalStack |
| Containerization | Docker + Docker Compose |

## Quick Start

### Prerequisites
- Python 3.11+
- Docker (for LocalStack/containers)

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
# Edit .env with your OpenRouter API key

# 4. Run the server
uvicorn app.api.main:app --reload --port 8000

# 5. Open the frontend
# Visit http://localhost:8000
```

### Docker

```bash
docker-compose up -d chatbot-api
# Visit http://localhost:8000
```

### Terraform (LocalStack)

```bash
# Start LocalStack
docker-compose up -d localstack

# Deploy infrastructure
cd infra/terraform
terraform init
terraform plan
terraform apply -auto-approve
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Main conversation endpoint |
| GET | `/health` | Health check |
| GET | `/inventory/{id}` | Get vehicle by ID |
| GET | `/inventory` | Filter inventory (query params) |
| GET | `/` | Chat frontend |

## Project Structure

```
bas_world_ai_project/
├── app/
│   ├── agents/          # LangGraph multi-agent system
│   │   ├── graph.py     # Agent graph with ReAct pattern
│   │   └── state.py     # Shared agent state
│   ├── api/
│   │   └── main.py      # FastAPI application
│   ├── schemas/
│   │   └── schemas.py   # Pydantic models
│   ├── services/
│   │   ├── data_loader.py   # CSV loading & normalization
│   │   └── llm_client.py    # OpenRouter LLM config
│   └── tools/
│       └── search_inventory.py  # Search, compare, detail tools
├── data/
│   └── trekkers.csv     # Inventory (673 vehicles)
├── frontend/
│   └── index.html       # Chat UI
├── infra/
│   └── terraform/       # AWS infrastructure (LocalStack)
├── tests/
│   └── test_search.py   # Unit tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Test Scenarios

1. **Needs-based**: "I need a tractor for international long-distance transport"
2. **Spec-based**: "4x2, Euro 6, automatic, 450+ HP, under €50,000"
3. **Refinement**: Follow-up in same session: "Show me cheaper options"
4. **Advisory**: "What do you recommend for heavy loads?"

## Running Tests

```bash
python -m pytest tests/ -v
```
