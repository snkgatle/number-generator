# Daily Lotto Inclusion Plan (Budget R250)

Status: Planned / not implemented
Prerequisite: Approved increase of the monthly budget from R200 to R250.

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
- Draw schedule: daily (up to ~30 draws/month).
- Cost: R2.50/board (standalone; not bundled like the R10 families).
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
   - Add Daily Lotto API parameters (gameId, winPoolId) to
     `LOTTERY_GAME_CONFIG`.
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
