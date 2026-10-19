/**
 * REST API client for LottoMind Backend
 */

const API_BASE_URL = '/api/v1';

export interface HealthResponse {
  status: string;
  project: string;
  database: string;
}

export interface MonthlyBudget {
  id: number;
  year_month: string;
  total_budget: number;
  cost_per_board: number;
  total_boards: number;
  used_boards: number;
  remaining_boards: number;
  spent_amount: number;
  is_exhausted: boolean;
  created_at: string;
  updated_at: string;
}

export interface Draw {
  id: number;
  draw_number: number;
  game_type: string;
  draw_date: string;
  numbers: number[];
  bonus_ball?: number | null;
  powerball?: number | null;
  created_at: string;
}

export interface GeneratedBoard {
  id: number;
  budget_id?: number | null;
  draw_id?: number | null;
  game_type: string;
  target_draw_date: string;
  numbers: number[];
  bonus_or_powerball?: number | null;
  confidence_score: number;
  ai_reasoning?: string | null;
  status: string;
  cost: number;
  created_at: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Failed to check health: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchCurrentBudget(): Promise<MonthlyBudget> {
  const response = await fetch(`${API_BASE_URL}/dashboard/budget/current`);
  if (!response.ok) {
    throw new Error(`Failed to fetch current budget: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchRecentDraws(limit = 10, gameType?: string): Promise<Draw[]> {
  const url = gameType
    ? `${API_BASE_URL}/scraper/draws?limit=${limit}&game_type=${gameType}`
    : `${API_BASE_URL}/scraper/draws?limit=${limit}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch draws: ${response.statusText}`);
  }
  return response.json();
}

export interface ScrapeGameResult {
  game_type: string;
  draws_found: number;
  draws_inserted: number;
  latest_draw_number?: number | null;
  status: string;
  error?: string | null;
}

export interface ScrapeResponse {
  status: string;
  total_found: number;
  total_inserted: number;
  details: ScrapeGameResult[];
  message: string;
}

export async function triggerScrape(limit = 50, gameTypes?: string[]): Promise<ScrapeResponse> {
  const response = await fetch(`${API_BASE_URL}/scraper/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ limit, game_types: gameTypes }),
  });
  if (!response.ok) {
    throw new Error(`Failed to trigger scraper: ${response.statusText}`);
  }
  return response.json();
}

export interface NumberFrequency {
  number: number;
  count: number;
  percentage: number;
}

export interface StatisticalAnalysis {
  game_type: string;
  sample_size: number;
  date_range_start?: string | null;
  date_range_end?: string | null;
  hot_numbers: NumberFrequency[];
  cold_numbers: NumberFrequency[];
  overdue_numbers: { number: number; draws_since_last: number }[];
  odd_even_ratios: { ratio: string; count: number; percentage: number }[];
  most_frequent_odd_even_ratio: string;
  consecutive_pairs: { pair: number[]; count: number }[];
  llm_prompt_context: {
    hot_numbers: number[];
    cold_numbers: number[];
    odd_even_ratio: string;
    consecutive_pairs: number[][];
    overdue_numbers: number[];
  };
}

export async function fetchGameStatistics(gameType: string, sampleSize = 50): Promise<StatisticalAnalysis> {
  const response = await fetch(`${API_BASE_URL}/stats/${gameType}?sample_size=${sampleSize}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch statistics for ${gameType}: ${response.statusText}`);
  }
  return response.json();
}

export interface PostDrawFeedback {
  game_type: string;
  draw_date: string;
  accuracy_rate: number;
  divergence_analysis: string;
  calibration_recommendations: string[];
}

export async function generateBoards(gameType: string, allocatedBoards = 1, targetDrawDate?: string): Promise<GeneratedBoard[]> {
  const response = await fetch(`${API_BASE_URL}/generator/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_type: gameType,
      allocated_boards: allocatedBoards,
      target_draw_date: targetDrawDate,
    }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Generation failed: ${response.statusText}`);
  }
  return response.json();
}

export interface BoardResult {
  id: number;
  board_id: number;
  draw_id: number;
  matched_numbers: number[];
  matched_count: number;
  matched_bonus: boolean;
  division?: string | null;
  prize_amount: number;
  evaluated_at: string;
}

export interface BoardWithResult extends GeneratedBoard {
  result?: BoardResult | null;
}

export interface CircuitBreakerStatus {
  allowed: boolean;
  year_month: string;
  remaining_boards: number;
  used_boards: number;
  total_boards: number;
  spent_amount: number;
  is_exhausted: boolean;
  message: string;
}

export interface BoardAllocationRecommendation {
  game_type: string;
  target_draw_date: string;
  base_boards: number;
  bonus_boards: number;
  total_allocated: number;
  confidence_score?: number | null;
  reasoning: string;
  circuit_breaker_active: boolean;
  remaining_budget_boards: number;
}

export interface AllocationPlan {
  year_month: string;
  total_budget_zar: number;
  total_boards: number;
  used_boards: number;
  remaining_boards: number;
  is_exhausted: boolean;
  confidence_threshold: number;
  cost_per_board_zar: number;
  projected_draws_count: number;
  recommendations: BoardAllocationRecommendation[];
}

export async function fetchGeneratedBoards(gameType?: string, limit = 50): Promise<GeneratedBoard[]> {
  const url = gameType
    ? `${API_BASE_URL}/generator/boards?limit=${limit}&game_type=${gameType}`
    : `${API_BASE_URL}/generator/boards?limit=${limit}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch boards: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchBoardById(boardId: number): Promise<BoardWithResult> {
  const response = await fetch(`${API_BASE_URL}/generator/boards/${boardId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch board details: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchCircuitBreaker(): Promise<CircuitBreakerStatus> {
  const response = await fetch(`${API_BASE_URL}/dashboard/circuit-breaker`);
  if (!response.ok) {
    throw new Error(`Failed to check circuit breaker: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchAllocationPlan(yearMonth?: string): Promise<AllocationPlan> {
  const url = yearMonth
    ? `${API_BASE_URL}/dashboard/allocation-plan?year_month=${yearMonth}`
    : `${API_BASE_URL}/dashboard/allocation-plan`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch allocation plan: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerPreDrawPipeline(gameTypes?: string[], targetDate?: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/generator/pipeline/pre-draw`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_types: gameTypes, target_date: targetDate }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Pre-draw pipeline failed: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchPostDrawFeedback(drawId: number): Promise<PostDrawFeedback> {
  const response = await fetch(`${API_BASE_URL}/generator/feedback/${drawId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Feedback evaluation failed: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerPostDrawPipeline(): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/generator/pipeline/post-draw`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Post-draw pipeline failed: ${response.statusText}`);
  }
  return response.json();
}

