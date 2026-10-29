# Daily Lotto Inclusion Plan (Budget R250)

Status: Implemented (backend + frontend parity)
Budget: R200 BUNDLE pool + R50 DAILY_LOTTO pool
Play cadence: Sunday, Monday and Thursday only (system play days).

## Objective

Determine whether Daily Lotto can be added to LottoMind, and how, given a
budget increase to R250/month.

## Current system architecture

- Games supported: Lotto Family (LOTTO, LOTTO_PLUS_1, LOTTO_PLUS_2) and
  PowerBall Family (POWERBALL, POWERBALL_PLUS).
- Budget: R200/month -> 20 boards at R10/board (bundle cost, Directive 23).
- Game matrices: Lotto 6/52 with bonus; PowerBall 5/50 + PowerBall 1/16.
- Draw frequency: ~8-9 draws/month per bundle.

## Daily Lotto characteristics

- Matrix: 5 numbers from 1-36 (distinct from Lotto and PowerBall).
- Official draw schedule: nightly. LottoMind's play cadence is Sun/Mon/Thu
  (13 play days in a typical cycle) to stay inside the R50 pool.
- Cost: R3.00/board (standalone; not bundled like the R10 families). Daily
  Lotto Plus was discontinued in June 2026 and is therefore not modelled.
- No bonus ball, no PowerBall.

## Budget options with R250

- Option A (keep current + add Daily Lotto):
  - 20 Lotto/PowerBall boards = R200
  - 20 Daily Lotto boards = R50
  - Total: 40 boards/month (20 bundled + 20 daily)
- Option B (redistribute):
  - 18 Lotto/PowerBall boards = R180
  - 28 Daily Lotto boards = R70
  - Total: 46 boards/month (more Daily Lotto coverage)
- Option C (separate budgets):
  - Lotto/PowerBall: R200 (20 boards)
  - Daily Lotto: R50 (20 boards, tracked separately)
  - Cleaner accounting, more complex implementation

## Required changes

1. Schema (`backend/app/schemas/enums.py`):
   - Add `DAILY_LOTTO` to `GameType`.
   - Add `DAILY_FAMILY` to `BundleType` (or keep Daily Lotto standalone).
   - Define 5/36 matrix rules in `GAME_RULES` / `BUNDLE_RULES`.
   - Set draw days to all weekdays `[0,1,2,3,4,5,6]` in `GAME_DRAW_DAYS`
     and `BUNDLE_DRAW_DAYS`.
2. Scraper (`backend/app/services/scraper_service.py`):
   - Add Daily Lotto API parameters to `LOTTERY_GAME_CONFIG`:
     `gameId=11001`, `winPoolId=100`, `plusFlag=0` (verified live on
     2026-10-29 against `issueWinPoolInfoPageQuery`).
   - Handle the different response structure (5 main numbers, no bonus).
3. Budget model (`backend/app/models/budget.py`):
   - Support variable `cost_per_board`, OR track Daily Lotto in a separate
     budget bucket.
4. AI / prompts (`backend/app/services/ai_service.py`,
   `backend/app/services/prompts.py`):
   - Number range 1-36 instead of 1-52 / 1-50.
   - Separate statistical patterns and Monte Carlo weights.
5. Prize service (`backend/app/services/prize_service.py`):
   - Daily Lotto prize tiers (match 2-5).
   - Separate ZAR ROI calculations.

## Open questions (resolve before implementation)

1. Budget allocation: Option A, B, or C?
2. Daily Lotto boards per draw: 1/day (~30/month) or more aggressive on
   high-confidence days?
3. Bundling: part of a bundle, or always standalone?
4. Rollout priority: full feature parity (analytics, wheeling, feedback) or
   MVP first (generation + basic evaluation)?


## Implementation summary (as built)

- Database: `monthly_budgets.pool` discriminator with unique
  `(year_month, pool)`; `DAILY_LOTTO` seeded into `game_bundles` (5/36, R3.00).
- Configuration: `BUNDLE_MONTHLY_BUDGET=200`, `DAILY_LOTTO_MONTHLY_BUDGET=50`,
  `DAILY_LOTTO_COST_PER_BOARD=3.00`.
- Bundle model: `DAILY_LOTTO -> [DAILY_LOTTO]` so the existing
  stats/AI/wheeling/dedup/evaluation/feedback pipeline works unchanged.
- Scheduling: pre-draw and post-draw cron run daily; the weekday resolver only
  emits Daily Lotto on Sun/Mon/Thu and the existing bundles on their nights.
- Prize tiers: Match 5 / 4 / 3 / 2 with indicative pari-mutuel payouts.
- Monte Carlo: minimum hit threshold driven by `mc_hit_threshold` (2 for
  Daily Lotto and PowerBall, 3 for Lotto).
- Frontend: Daily Lotto appears in game/bundle selectors, results filters,
  generation quota (pool-aware circuit breaker) and a dedicated budget card.
- Budget outcome: R200 bundle pool + R50 daily pool = R250 total; 20 bundle
  boards and 16 daily boards of quota (actual spend at full daily play
  R200 + 13 x R3 = R239).
