# PLAN.md - Implementation Roadmap

Execute these phases sequentially. Do not move to the next phase until the current phase is fully implemented, tested, and committed.

## Phase 1: Infrastructure & Data Layer
- [x] Initialize project structure (`backend/`, `frontend/`, `docker-compose.yml`).
- [x] Setup FastAPI skeleton with lifespan events for DB connection pooling.
- [x] Define SQLAlchemy models: `Draw`, `GeneratedBoard`, `BoardResult`, `MonthlyBudget`.
- [x] Implement Alembic for database migrations.
- [x] Create Pydantic schemas for all models.

## Phase 2: The Scraper Engine
- [x] Install and configure Playwright.
- [x] Write scraping logic targeting the SA National Lottery results page.
- [x] Implement parsing logic for Lotto, PowerBall, Lotto Plus 1, and Lotto Plus 2.
- [x] Build the upsert logic to save the last 50 draws to the PostgreSQL DB safely.
- [x] Create a manual trigger endpoint (`POST /api/v1/scrape`) to test it.

## Phase 3: Statistical Pre-Processing
- [x] Create `stats/analyzer.py`.
- [x] Write functions to calculate: Hot numbers (top 10), Cold numbers (bottom 10), Odd/Even ratios, and Consecutive pairs from the last 50 draws.
- [x] Ensure this runs locally in Python *before* calling the LLM to save tokens.

## Phase 4: Qwen-Max AI Integration
- [x] Integrate `dashscope` SDK.
- [x] Construct the System Prompt and User Prompt templates (refer to `PROMPT.md`).
- [x] Implement the API call function expecting a structured JSON response.
- [x] Parse and validate the JSON response using Pydantic.
- [x] Implement the Post-Draw Feedback Loop prompt (analyzing past failures).

## Phase 5: Budget Engine & Board Allocation
- [x] Create `budget/engine.py`.
- [x] Implement monthly initialization (R200 = 40 boards, resets 25th of month on payday cycle).
- [x] Write the confidence-based allocation algorithm (Base 1 board per draw, extra boards for >85% confidence).
- [x] Implement the Circuit Breaker check.
- [x] Create the APScheduler cron job to run the full pipeline (Stats -> AI -> Budget -> Save) automatically before draws.

## Phase 6: Frontend Dashboard
- [x] Initialize React + Vite + Tailwind.
- [x] Build Dashboard View (Budget tracker progress bar).
- [x] Build Generation Hub (List upcoming draws, show AI confidence/reasoning).
- [x] Build Results View (Table comparing generated vs actual).
- [x] Connect frontend to FastAPI endpoints.

## Phase 7: Final Polish
- [x] Add comprehensive logging (Loguru).
- [x] Write basic unit tests for the Budget Engine and Stats Analyzer.
- [x] Create `README.md` with setup instructions.