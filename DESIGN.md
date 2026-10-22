
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

    ### Abbreviated Wheeling Algorithm (`dedup_service.py` or new `wheel_service.py`)
1. Receive a pool of $N$ numbers from Qwen-Max (e.g., 12 numbers).
2. Receive the target board count from `budget_service.py` (e.g., 3 boards).
3. Apply a predefined abbreviated wheel matrix (e.g., a "3 if 4" wheel) to select subsets of the pool.
4. Ensure the total generated boards do not exceed the allocated budget for that draw.
5. Pass the wheeled boards through the deduplication hash check before saving.