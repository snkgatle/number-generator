import React, { useEffect, useState } from 'react';
import { MonthlyBudget, CircuitBreakerStatus, BoardWithResult, fetchGeneratedBoards, markBoardPlayed } from '../services/api';
import type { Tab } from '../App';
import { BudgetTracker } from './BudgetTracker';
import { PageHeader, EmptyState } from './ui';
import { BallRow } from './Ball';
import { GAMES, formatDate, formatZAR, gameLabel, isPowerBallGame, nextDrawDate, relativeDay } from '../utils/format';
import { useDrawCountdown } from '../utils/useCountdown';
import { ArrowRight, CalendarDays, CheckCircle2, Circle, Hourglass, Sparkles, Ticket } from 'lucide-react';

interface OverviewProps {
  budget: MonthlyBudget | null;
  circuitBreaker: CircuitBreakerStatus | null;
  loading: boolean;
  onNavigate: (tab: Tab) => void;
}

export function boardOutcome(b: BoardWithResult): 'won' | 'lost' | 'pending' {
  const prize = Number(
    b.total_prize ??
    (b.results && b.results.length > 0
      ? b.results.reduce((s, r) => s + Number(r.prize_amount || 0), 0)
      : b.result?.prize_amount ?? 0)
  );
  if (b.status === 'WON' || prize > 0) return 'won';
  if (b.status === 'LOST' || (b.results && b.results.length > 0) || b.result) return 'lost';
  return 'pending';
}

export const OutcomeBadge: React.FC<{ board: BoardWithResult }> = ({ board }) => {
  const o = boardOutcome(board);
  if (o === 'won') return <span className="badge badge-success">Won</span>;
  if (o === 'lost') return <span className="badge badge-neutral">No prize</span>;
  return <span className="badge badge-warning">Awaiting draw</span>;
};

function getGameTagStyle(gameId: string): string {
  if (gameId.includes('POWERBALL')) {
    return 'bg-rose-500/15 border-rose-500/30 text-rose-300';
  } else if (gameId.includes('PLUS_2')) {
    return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300';
  } else if (gameId.includes('PLUS')) {
    return 'bg-sky-500/15 border-sky-500/30 text-sky-300';
  }
  return 'bg-indigo-500/15 border-indigo-500/30 text-indigo-300';
}

export const Overview: React.FC<OverviewProps> = ({ budget, circuitBreaker, loading, onNavigate }) => {
  const [boards, setBoards] = useState<BoardWithResult[]>([]);
  const [boardsLoading, setBoardsLoading] = useState(true);

  useEffect(() => {
    fetchGeneratedBoards(undefined, 6)
      .then(setBoards)
      .catch(() => setBoards([]))
      .finally(() => setBoardsLoading(false));
  }, []);

  const handleTogglePlayed = async (boardId: number) => {
    try {
      const updated = await markBoardPlayed(boardId);
      setBoards((prev) => prev.map((b) => (b.id === updated.id ? { ...b, ...updated } : b)));
    } catch {
      /* non-fatal: badge stays as-is */
    }
  };

  const upcoming = GAMES.map((g) => ({ ...g, next: nextDrawDate(g.id) })).sort((a, b) =>
    a.next.localeCompare(b.next),
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Budget position, upcoming draws and your most recent boards."
        actions={
          <button id="overview-generate" className="btn btn-primary" onClick={() => onNavigate('generate')}>
            <Sparkles className="h-4 w-4" />
            Generate boards
          </button>
        }
      />

      <BudgetTracker budget={budget} circuitBreaker={circuitBreaker} loading={loading} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        {/* Upcoming draws */}
        <section className="card xl:col-span-2 overflow-hidden" aria-labelledby="upcoming-heading">
          <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                <CalendarDays className="h-4 w-4" />
              </div>
              <div>
                <h2 id="upcoming-heading" className="card-title">
                  Upcoming draws
                </h2>
                <p className="card-subtitle">Next scheduled draw per game</p>
              </div>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Game</th>
                <th>Next draw</th>
                <th className="text-right">When</th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((g) => (
                <tr key={g.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className={`badge border text-xs px-2 py-0.5 ${getGameTagStyle(g.id)}`}>
                        {g.label}
                      </span>
                    </div>
                    <div className="text-2xs text-zinc-500 mt-0.5">{g.days}</div>
                  </td>
                  <td className="text-zinc-300 font-mono text-xs">{formatDate(g.next)}</td>
                  <td className="text-right">
                    <span
                      className={`badge border ${
                        relativeDay(g.next) === 'Today'
                          ? 'bg-amber-500/15 border-amber-500/30 text-amber-300 font-bold animate-pulse'
                          : 'badge-neutral'
                      }`}
                    >
                      {relativeDay(g.next)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Recent boards */}
        <section className="card xl:col-span-3 overflow-hidden" aria-labelledby="recent-heading">
          <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-purple-500/10 border border-purple-500/30 text-purple-400">
                <Ticket className="h-4 w-4" />
              </div>
              <div>
                <h2 id="recent-heading" className="card-title">
                  Recent boards
                </h2>
                <p className="card-subtitle">Latest generated boards and their outcome</p>
              </div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('results')}>
              View all
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {boardsLoading ? (
            <div className="space-y-3 p-5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-10" />
              ))}
            </div>
          ) : boards.length === 0 ? (
            <EmptyState
              icon={Ticket}
              title="No boards yet"
              description="Generated boards will appear here together with their draw outcome."
            />
          ) : (
            <ul className="divide-y divide-line/60">
              {boards.map((b) => (
                <RecentBoardRow key={b.id} board={b} onTogglePlayed={handleTogglePlayed} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
};

const RecentBoardRow: React.FC<{
  board: BoardWithResult;
  onTogglePlayed: (boardId: number) => void;
}> = ({ board, onTogglePlayed }) => {
  const matched = new Set(board.result?.matched_numbers ?? []);
  const outcome = boardOutcome(board);
  const countdown = useDrawCountdown(outcome === 'pending' ? board.target_draw_date : null);
  const isPlayed = board.status === 'PLAYED';

  return (
    <li className="flex flex-col gap-3 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between hover:bg-surface-3/30 transition-colors">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={`badge border text-xs px-2 py-0.5 ${getGameTagStyle(board.game_type)}`}>
            {gameLabel(board.game_type)}
          </span>
          <span className="text-xs text-zinc-500">{formatDate(board.target_draw_date)}</span>
          {outcome === 'pending' && countdown && (
            <span
              className="badge badge-warning gap-1"
              title="Time until this draw closes (~21:00 SAST)"
            >
              <Hourglass className="h-3 w-3" />
              <span className="num">{countdown}</span>
            </span>
          )}
        </div>
        <div className="mt-2">
          <BallRow
            numbers={board.numbers}
            extra={board.bonus_or_powerball}
            powerBall={isPowerBallGame(board.game_type)}
            matched={matched}
            extraMatched={board.result?.matched_bonus}
            size="sm"
          />
        </div>
      </div>
      <div className="flex items-center gap-3 sm:flex-col sm:items-end sm:gap-1.5">
        <div className="flex items-center gap-2">
          <OutcomeBadge board={board} />
          {outcome === 'pending' && (
            <button
              onClick={() => onTogglePlayed(board.id)}
              className={`btn btn-sm ${isPlayed ? 'btn-ghost text-emerald-300' : 'btn-ghost text-zinc-400'}`}
              title={
                isPlayed
                  ? `Played on the official platform${board.played_at ? ` · ${new Date(board.played_at).toLocaleString()}` : ''} — click to undo`
                  : 'Directive 10: mark as manually played on the official lottery platform'
              }
              aria-label={isPlayed ? 'Mark board as not played' : 'Mark board as played'}
            >
              {isPlayed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
              <span className="text-2xs">{isPlayed ? 'Played' : 'Mark played'}</span>
            </button>
          )}
        </div>
        {board.result && (
          <span className="num text-xs text-zinc-400">{formatZAR(board.result.prize_amount)}</span>
        )}
      </div>
    </li>
  );
};
