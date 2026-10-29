/**
 * REST API client for LottoMind Backend
 */

const RAW_API_URL = import.meta.env.VITE_API_URL || '';
const API_BASE_URL = RAW_API_URL ? `${RAW_API_URL.replace(/\/+$/, '')}/api/v1` : '/api/v1';

let authToken: string | null = localStorage.getItem('lottomind_auth_token');

export function setStoredToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('lottomind_auth_token', token);
  } else {
    localStorage.removeItem('lottomind_auth_token');
  }
}

export function getStoredToken(): string | null {
  return authToken;
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }
  return fetch(input, {
    ...init,
    headers,
    credentials: 'include',
  });
}

export interface AuthStatus {
  authenticated: boolean;
  expires_at?: string | null;
  message?: string | null;
}

export async function requestTelegramOtp(): Promise<{ message: string; expires_in_seconds: number }> {
  const res = await apiFetch(`${API_BASE_URL}/auth/request-otp`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to dispatch Telegram OTP');
  }
  return res.json();
}

export async function verifyTelegramOtp(otp_code: string): Promise<{ success: boolean; token: string }> {
  const res = await apiFetch(`${API_BASE_URL}/auth/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ otp_code }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid or expired OTP code');
  }
  const data = await res.json();
  if (data.token) {
    setStoredToken(data.token);
  }
  return data;
}

export async function logoutUser(): Promise<void> {
  try {
    await apiFetch(`${API_BASE_URL}/auth/logout`, { method: 'POST' });
  } finally {
    setStoredToken(null);
  }
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await apiFetch(`${API_BASE_URL}/auth/status`);
  if (!res.ok) {
    return { authenticated: false };
  }
  return res.json();
}

export interface HealthResponse {
  status: string;
  project: string;
  database: string;
}

export type BudgetPool = 'BUNDLE' | 'DAILY_LOTTO';

export interface MonthlyBudget {
  id: number;
  year_month: string;
  pool: BudgetPool;
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
  bundle_id?: number | null;
  budget_id?: number | null;
  draw_id?: number | null;
  bundle_name?: string;
  game_type: string;
  target_draw_date: string;
  numbers: number[];
  bonus_or_powerball?: number | null;
  confidence_score: number;
  ai_reasoning?: string | null;
  status: string;
  cost: number;
  simulated_hit_rate?: number | null;
  ev_score?: number | null;
  played_at?: string | null;
  created_at: string;
  results?: BoardResult[];
  result?: BoardResult | null;
  total_prize?: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiFetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Failed to check health: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchCurrentBudget(pool: BudgetPool = 'BUNDLE'): Promise<MonthlyBudget> {
  const response = await apiFetch(`${API_BASE_URL}/dashboard/budget/current?pool=${pool}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch current budget: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchAllBudgets(): Promise<MonthlyBudget[]> {
  const response = await apiFetch(`${API_BASE_URL}/dashboard/budgets`);
  if (!response.ok) {
    throw new Error(`Failed to fetch budgets: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchRecentDraws(limit = 10, gameType?: string): Promise<Draw[]> {
  const url = gameType
    ? `${API_BASE_URL}/scraper/draws?limit=${limit}&game_type=${gameType}`
    : `${API_BASE_URL}/scraper/draws?limit=${limit}`;
  const response = await apiFetch(url);
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
  const response = await apiFetch(`${API_BASE_URL}/scraper/scrape`, {
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
  const response = await apiFetch(`${API_BASE_URL}/stats/${gameType}?sample_size=${sampleSize}`);
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

export async function generateBoards(
  gameTypeOrBundle: string,
  allocatedBoards = 1,
  targetDrawDate?: string
): Promise<GeneratedBoard[]> {
  const isBundle = gameTypeOrBundle.includes('FAMILY');
  const response = await apiFetch(`${API_BASE_URL}/generator/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bundle_name: isBundle ? gameTypeOrBundle : undefined,
      game_type: gameTypeOrBundle,
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
  game_type?: string;
  matched_numbers: number[];
  matched_count: number;
  matched_bonus: boolean;
  division?: string | null;
  prize_amount: number;
  evaluated_at: string;
}

export interface BoardWithResult extends GeneratedBoard {
  results?: BoardResult[];
  result?: BoardResult | null;
  total_prize?: number;
}

export interface CircuitBreakerStatus {
  allowed: boolean;
  year_month: string;
  pool: BudgetPool;
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
  pool: BudgetPool;
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

export async function fetchGeneratedBoards(
  gameType?: string,
  limit = 50,
  bundleName?: string
): Promise<BoardWithResult[]> {
  let url = `${API_BASE_URL}/generator/boards?limit=${limit}`;
  if (bundleName) {
    url += `&bundle_name=${bundleName}`;
  } else if (gameType) {
    url += `&game_type=${gameType}`;
  }
  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch boards: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchBoardById(boardId: number): Promise<BoardWithResult> {
  const response = await apiFetch(`${API_BASE_URL}/generator/boards/${boardId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch board details: ${response.statusText}`);
  }
  return response.json();
}

export async function markBoardPlayed(boardId: number): Promise<BoardWithResult> {
  const response = await apiFetch(`${API_BASE_URL}/generator/boards/${boardId}/played`, {
    method: 'PATCH',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to toggle played status');
  }
  return response.json();
}

export async function fetchCircuitBreaker(pool: BudgetPool = 'BUNDLE'): Promise<CircuitBreakerStatus> {
  const response = await apiFetch(`${API_BASE_URL}/dashboard/circuit-breaker?pool=${pool}`);
  if (!response.ok) {
    throw new Error(`Failed to check circuit breaker: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchAllocationPlan(
  yearMonth?: string,
  pool: BudgetPool = 'BUNDLE'
): Promise<AllocationPlan> {
  const params = new URLSearchParams({ pool });
  if (yearMonth) params.set('year_month', yearMonth);
  const url = `${API_BASE_URL}/dashboard/allocation-plan?${params.toString()}`;
  const response = await apiFetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch allocation plan: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerPreDrawPipeline(gameTypes?: string[], targetDate?: string): Promise<any> {
  const response = await apiFetch(`${API_BASE_URL}/generator/pipeline/pre-draw`, {
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
  const response = await apiFetch(`${API_BASE_URL}/generator/feedback/${drawId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Feedback evaluation failed: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerPostDrawPipeline(): Promise<any> {
  const response = await apiFetch(`${API_BASE_URL}/generator/pipeline/post-draw`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Post-draw pipeline failed: ${response.statusText}`);
  }
  return response.json();
}

/* ─── Prize tier reference (Directive 14) ───────────────────────── */

export interface PrizeTier {
  division: string;
  match_main: number;
  match_bonus: boolean;
  payout: number;
}

export interface PrizeMatrix {
  game_type: string;
  matrix: Record<string, unknown>;
  tiers: PrizeTier[];
}

export async function fetchPrizeTiers(gameType: string): Promise<PrizeMatrix> {
  const response = await apiFetch(`${API_BASE_URL}/prizes/tiers/${encodeURIComponent(gameType)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch prize tiers: ${response.statusText}`);
  }
  return response.json();
}

