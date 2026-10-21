/**
 * Presentation helpers shared across views.
 */

export const GAMES = [
  { id: 'LOTTO', label: 'Lotto', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'LOTTO_PLUS_1', label: 'Lotto Plus 1', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'LOTTO_PLUS_2', label: 'Lotto Plus 2', days: 'Wed & Sat', drawDays: [3, 6], matrix: '6 from 1–52 + bonus' },
  { id: 'POWERBALL', label: 'PowerBall', days: 'Tue & Fri', drawDays: [2, 5], matrix: '5 from 1–50 + PB 1–16' },
  { id: 'POWERBALL_PLUS', label: 'PowerBall Plus', days: 'Tue & Fri', drawDays: [2, 5], matrix: '5 from 1–50 + PB 1–16' },
] as const;

export type GameId = (typeof GAMES)[number]['id'];

export function gameLabel(id: string): string {
  return GAMES.find((g) => g.id === id)?.label ?? id;
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
export function nextDrawDate(gameId: string, from: Date = new Date()): string {
  const game = GAMES.find((g) => g.id === gameId);
  const drawDays: readonly number[] = game?.drawDays ?? [];
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
