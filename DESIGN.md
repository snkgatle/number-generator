
---

## File 4: `DESIGN.md`

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
│   │   │   ├── budget.py
│   │   │   └── analytics.py
│   │   ├── schemas/                # Pydantic validation schemas
│   │   ├── api/                    # FastAPI Routers
│   │   │   ├── v1/
│   │   │   │   ├── scraper.py
│   │   │   │   ├── generator.py
│   │   │   │   ├── analytics.py
│   │   │   │   └── dashboard.py
│   │   ├── services/               # Business Logic
│   │   │   ├── scraper_service.py  # Playwright logic (includes metadata extraction)
│   │   │   ├── stats_service.py    # Math/Frequency, Monte Carlo, Chi-Square logic
│   │   │   ├── ai_service.py       # DashScope Qwen integration
│   │   │   ├── prompts.py          # Stores all Qwen prompt templates
│   │   │   ├── budget_service.py   # R200 Circuit breaker logic
│   │   │   ├── prize_service.py    # SA Lottery Prize Tier mapping & ROI calc
│   │   │   ├── dedup_service.py    # Hash-based board collision prevention
│   │   │   └── notifier.py         # Telegram/Discord webhook alerts
│   │   └── scheduler/              # APScheduler background tasks
│   └── tests/
└── frontend/                       # React + Vite + Tailwind
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   └── services/api.ts         # Axios/Fetch wrappers