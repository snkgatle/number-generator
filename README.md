# LottoMind - Automated South African Lottery Analytics & AI Generation

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3-61dafb.svg)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8.svg)](https://tailwindcss.com)
[![AI Qwen-Max](https://img.shields.io/badge/AI-Qwen--Max%20(DashScope)-ff6a00.svg)](https://www.alibabacloud.com/help/en/model-studio)
[![Tests](https://img.shields.io/badge/Tests-51%20Passed-brightgreen.svg)]()

LottoMind is an end-to-end automated lottery intelligence system designed for South African National Lottery games (**LOTTO**, **LOTTO PLUS 1**, **LOTTO PLUS 2**, **POWERBALL**, and **POWERBALL PLUS**).

The system combines **idempotent Playwright web scraping**, **mathematical frequency pre-processing**, **Alibaba Cloud DashScope Qwen-Max probabilistic generation**, and a **strict R200/month Circuit Breaker** to eliminate emotional bias and strictly enforce financial discipline.

---

## Architecture & Data Flow

```mermaid
graph TD
    A[SA National Lottery Results Page] -->|Playwright Scraper / ON CONFLICT DO NOTHING| B[(PostgreSQL Database)]
    B -->|Last 50 Historical Draws| C[Stats Analyzer]
    C -->|Frequencies, Parity, Latencies| D[Budget Engine]
    D -->|Circuit Breaker Check: Quota > 0?| E{Circuit Breaker}
    E -->|Exhausted: remaining <= 0| F[Halt Execution & Log Alert]
    E -->|Active: 1 Base Board + Bonus for >85%| G[Isolated Prompt Engine]
    G -->|Structured JSON Prompt| H[Alibaba Cloud Qwen-Max]
    H -->|Strict JSON Response| I[Pydantic Schema & Game Matrix Validator]
    I -->|Validated Boards & Reasoning| B
    B -->|REST API v1| J[React + Vite + Tailwind Dashboard]
    K[APScheduler Cron Jobs] -->|Pre-Draw: 18:00 / Post-Draw: 22:30| D
```

---

## Core System Directives

1. **No Hardcoded Secrets**: All credentials and connection URIs are loaded via `pydantic-settings` from `.env`.
2. **Strict JSON Enforcement**: Prompts to Qwen-Max enforce schema outputs validated with Pydantic (`AIGenerationResponse`, `AIBoardRecommendation`) before persisting to PostgreSQL.
3. **Budget Circuit Breaker (Directive 3)**: Before **ANY** board generation executes, the system queries `monthly_budgets`. If `remaining_boards <= 0`, execution is immediately halted with `"Budget Exhausted"`. Max 40 boards @ R5.00/board (R200/month).
4. **Idempotent Scraping**: The Playwright scraper uses PostgreSQL `ON CONFLICT (draw_number, game_type) DO NOTHING` (or SQLite equivalent in tests) to guarantee zero duplicates.
5. **Separation of Concerns**:
   - `backend/app/services/scraper_service.py` handles web fetching and parsing.
   - `backend/app/stats/analyzer.py` handles mathematical frequency and parity analysis.
   - `backend/app/budget/engine.py` handles quota allocation and circuit breaker logic.
   - `backend/app/services/ai_service.py` handles DashScope Qwen-Max inference.
   - `backend/app/services/prompts.py` isolates all prompt templates from application logic.
6. **Resilience & Retries**: External API interactions (DashScope, Playwright) use `tenacity` exponential backoff retries.

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 (Async), `asyncpg`, Alembic, APScheduler, Loguru, Tenacity.
- **AI Integration**: Alibaba Cloud DashScope SDK (`dashscope` / compatible mode) targeting `qwen-max`.
- **Scraper**: Playwright (Async Python).
- **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Lucide Icons.
- **Database**: PostgreSQL 16.
- **Containerization**: Docker & Docker Compose.

---

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose **OR** Python 3.11+ and Node.js 18+.
- Alibaba Cloud DashScope API Key.

### 2. Configure Environment (`.env`)
Copy `.env.example` or update `.env`:
```bash
PROJECT_NAME="LottoMind"
ENVIRONMENT="development"
DEBUG=true

# Database (PostgreSQL)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/lottomind"

# Alibaba Cloud DashScope (Qwen-Max)
DASHSCOPE_API_KEY="sk-your-api-key-here"
DASHSCOPE_BASE_URL="https://maas.qwencloudapi.com/compatible-mode/v1"
QWEN_MODEL="qwen-max"

# Budget Limits
DEFAULT_MONTHLY_BUDGET=200.00
COST_PER_BOARD=5.00
TOTAL_MONTHLY_BOARDS=40
```

### 3. Run with Podman Compose or Docker Compose
The environment supports both **Podman** (`podman-compose`) and **Docker**:

```bash
# Using Podman
podman compose up --build -d

# Or using Docker
docker compose up --build -d
```
- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Run Locally for Development

#### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Automated Scheduling Matrix

LottoMind registers three automated cron jobs via **APScheduler** upon FastAPI startup:

| Job | Trigger Time (SAST) | Description |
| :--- | :--- | :--- |
| **Pre-Draw Pipeline** | `Tue, Wed, Fri, Sat @ 18:00` | Checks circuit breaker $\rightarrow$ runs mathematical frequency analysis $\rightarrow$ prompts Qwen-Max for constrained boards $\rightarrow$ saves pending boards. |
| **Post-Draw Pipeline** | `Tue, Wed, Fri, Sat @ 22:30` | Scrapes official winning numbers with `ON CONFLICT DO NOTHING` $\rightarrow$ evaluates pending boards $\rightarrow$ runs AI divergence post-mortem. |
| **Monthly Rollover** | `25th of month @ 00:01` | Initializes a fresh R200 / 40 board budget quota for the new payday cycle (25th to 24th). |

---

## Running Test Suite

```bash
# Backend Unit and Integration Tests (47 tests)
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests -v

# Frontend Production Build & TypeScript Verification
cd frontend && npm run build
```

---

## License

Personal Project - All Rights Reserved.
