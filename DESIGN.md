
---

## File 4: `DESIGN.md`
*Purpose: Outlines the software architecture, folder structure, database schema, and UI wireframe specifications for Antigravity to follow.*

```markdown
# DESIGN.md - Architecture & System Design

## 1. Directory Structure
Antigravity must scaffold the project exactly like this:

```text
lottoland-ai/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings (.env loader)
│   │   │   └── database.py         # Async SQLAlchemy engine
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── draw.py
│   │   │   ├── board.py
│   │   │   └── budget.py
│   │   ├── schemas/                # Pydantic validation schemas
│   │   ├── api/                    # FastAPI Routers
│   │   │   ├── v1/
│   │   │   │   ├── scraper.py
│   │   │   │   ├── generator.py
│   │   │   │   └── dashboard.py
│   │   ├── services/               # Business Logic
│   │   │   ├── scraper_service.py  # Playwright logic
│   │   │   ├── stats_service.py    # Math/Frequency logic
│   │   │   ├── prompts.py          # Stores all Qwen prompt templates 
│   │   │   ├── ai_service.py       # DashScope Qwen integration
│   │   │   └── budget_service.py   # R200 Circuit breaker logic
│   │   └── scheduler/              # APScheduler background tasks
│   └── tests/
└── frontend/                       # React + Vite + Tailwind
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   └── services/api.ts         # Axios/Fetch wrappers