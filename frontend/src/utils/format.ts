/**
 * Presentation helpers shared across views.
 */

export const GAMES = [
  { id: 'LOTTO', label: 'Lotto', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'LOTTO_PLUS_1', label: 'Lotto Plus 1', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'LOTTO_PLUS_2', label: 'Lotto Plus 2', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'POWERBALL', label: 'PowerBall', days: 'Tue & Fri', drawDays: [2, 5], matrix: '5 from 1–50 + PB 1–16' },
  { id: 'POWERBALL_PLUS', label: 'PowerBall Plus', days: 'Tue & Fri', drawDays: [2, 5], matrix: '5 from 1–50 + PB 1–16' },
  { id: 'DAILY_LOTTO', label: 'Daily Lotto', days: 'Sun, Mon & Thu', drawDays: [0, 1, 4], matrix: '5 from 1–36' },
] as const;

export const BUNDLES = [
  {
    id: 'LOTTO_FAMILY',
    label: 'Lotto Bundle',
    subGames: ['LOTTO', 'LOTTO_PLUS_1', 'LOTTO_PLUS_2'],
    subGamesDisplay: 'Lotto + Plus 1 + Plus 2',
    days: 'Wed & Sat',
    drawDays: [3, 6],
    costPerBoard: 10.0,
    matrix: '6 from 1–52 + bonus',
    badgeClass: 'badge-lotto',
    description: '1 board enters all 3 sub-draws (Lotto R5 + Plus 1 R2.50 + Plus 2 R2.50)',
  },
  {
    id: 'POWERBALL_FAMILY',
    label: 'PowerBall Bundle',
    subGames: ['POWERBALL', 'POWERBALL_PLUS'],
    subGamesDisplay: 'PowerBall + PowerBall Plus',
    days: 'Tue & Fri',
    drawDays: [2, 5],
    costPerBoard: 10.0,
    matrix: '5 from 1–50 + PB 1–16',
    badgeClass: 'badge-powerball',
    description: '1 board enters both sub-draws (PowerBall R5 + PowerBall Plus R5)',
  },
  {
    id: 'DAILY_LOTTO',
    label: 'Daily Lotto',
    subGames: ['DAILY_LOTTO'],
    subGamesDisplay: 'Daily Lotto',
    days: 'Sun, Mon & Thu',
    drawDays: [0, 1, 4],
    costPerBoard: 3.0,
    matrix: '5 from 1–36',
    badgeClass: 'badge-daily',
    description: '1 board plays the Daily Lotto draw (R3.00 per board)',
  },
] as const;

export type GameId = (typeof GAMES)[number]['id'];
export type BundleId = (typeof BUNDLES)[number]['id'];

export function gameLabel(id: string): string {
  if (id === 'LOTTO_FAMILY') return 'Lotto Bundle (Lotto + Plus 1 & 2)';
  if (id === 'POWERBALL_FAMILY') return 'PowerBall Bundle (PB + PB Plus)';
  return GAMES.find((g) => g.id === id)?.label ?? id;
}

export function bundleLabel(id: string): string {
  return BUNDLES.find((b) => b.id === id)?.label ?? gameLabel(id);
}

export function bundleForGame(id: string) {
  return BUNDLES.find((b) => b.id === id || (b.subGames as readonly string[]).includes(id));
}

export function isPowerBallGame(id: string): boolean {
  return id.includes('POWERBALL');
}

const zarFormatter = new Intl.NumberFormat('en-ZA', {
  style: 'currency',
  currency: 'ZAR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatZAR(value: number | string | null | undefined): string {
  return zarFormatter.format(Number(value ?? 0));
}

/** Formats a Date as YYYY-MM-DD using local time (avoids UTC day-shift from toISOString). */
export function toLocalISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Human-readable date, e.g. "Tue, 20 Oct 2026". Accepts YYYY-MM-DD or ISO strings. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString('en-ZA', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

/** Next calendar date (today inclusive) on which the given game is drawn. */
export function nextDrawDate(gameOrBundleId: string, from: Date = new Date()): string {
  const bundle = BUNDLES.find((b) => b.id === gameOrBundleId);
  const game = GAMES.find((g) => g.id === gameOrBundleId);
  const drawDays: readonly number[] = bundle?.drawDays ?? game?.drawDays ?? [];
  for (let i = 0; i <= 7; i++) {
    const candidate = new Date(from);
    candidate.setDate(from.getDate() + i);
    if (drawDays.includes(candidate.getDay())) {
      return toLocalISODate(candidate);
    }
  }
  return toLocalISODate(from);
}

/** Whole days between today and a YYYY-MM-DD date. */
export function daysUntil(isoDate: string): number {
  const target = new Date(`${isoDate}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

export function relativeDay(isoDate: string): string {
  const n = daysUntil(isoDate);
  if (n === 0) return 'Today';
  if (n === 1) return 'Tomorrow';
  if (n > 1) return `In ${n} days`;
  return `${Math.abs(n)} days ago`;
}

/** Formats a board as plain text for manual entry on the official platform. */
export function boardToText(board: {
  game_type: string;
  target_draw_date: string;
  numbers: number[];
  bonus_or_powerball?: number | null;
}): string {
  const main = board.numbers.map((n) => String(n).padStart(2, '0')).join(' ');
  const extra =
    board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined
      ? `  ${isPowerBallGame(board.game_type) ? 'PB' : 'Bonus'} ${String(board.bonus_or_powerball).padStart(2, '0')}`
      : '';
  return `${gameLabel(board.game_type)} · ${board.target_draw_date} · ${main}${extra}`;
}
