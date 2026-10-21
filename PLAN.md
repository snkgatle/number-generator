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

## Phase 3.5: Temporal Analytics Engine
- [x] Create `temporal_analytics` database table.
- [x] Write SQL/Python logic to calculate weekly vs monthly sum averages, parity drifts, and co-occurrence pairs.
- [x] Implement the "Pattern Discovery" Qwen prompts (`PROMPT.md`).
- [x] Build the APScheduler cron job to run weekly analysis and save Qwen's insights to the DB.
- [x] Inject the `actionable_bias_for_generation` output into the primary Board Generation prompt context.

## Phase 3.6: Environmental Metadata & Simulation
- [x] Add metadata columns to the `draws` database table.
- [x] Implement `run_monte_carlo_stress_test()` in `stats_service.py` to validate AI-generated boards locally (10,000 iterations).
- [x] Implement `calculate_environmental_correlations()` with strict p-value filtering (p < 0.05 via SciPy) to prevent AI overfitting on machine names or draw times.
- [x] Update Qwen prompts to conditionally include validated anomalies and simulation hit rates.


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

## Phase 5.5: Resilience, Deduplication & ROI
- [x] Implement `tenacity` retry logic for DashScope API calls.
- [x] Build Statistical and Random fallback generators in case AI fails.
- [x] Implement `dedup_service.py` to hash and filter duplicate boards across games for the same date.
- [x] Map SA National Lottery prize tiers in `prize_service.py` and calculate ZAR ROI per draw.
- [x] Integrate Telegram Bot API or Discord Webhook in `notifier.py` for budget exhaustion and high-match alerts.
- [x] Write `pytest` unit tests specifically targeting the Budget Engine circuit breaker and Deduplication logic.


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