import React, { useState, useEffect } from 'react';
import { BallRow } from './Ball';
import {
  fetchGeneratedBoards,
  fetchRecentDraws,
  fetchPostDrawFeedback,
  triggerPostDrawPipeline,
  markBoardPlayed,
  fetchPrizeTiers,
  BoardWithResult,
  Draw,
  PostDrawFeedback,
} from '../services/api';
import { PageHeader, StatCard, Alert, EmptyState, Segmented, CopyButton, TierReference } from './ui';
import type { PrizeTierRow } from '../components/ui';
import {
  GAMES,
  formatDate,
  formatZAR,
  gameLabel,
  bundleLabel,
  isPowerBallGame,
  boardToText,
} from '../utils/format';
import {
  RotateCw,
  Trophy,
  Coins,
  TrendingUp,
  TrendingDown,
  Receipt,
  Sparkles,
  Ticket,
  X,
  CheckCircle2,
  Circle,
  Hourglass,
} from 'lucide-react';
import { useDrawCountdown } from '../utils/useCountdown';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export const DrawCountdownBadge: React.FC<{ targetDate: string }> = ({ targetDate }) => {
  const countdown = useDrawCountdown(targetDate);
  if (!countdown) return null;
  return (
    <span className="badge badge-warning gap-1" title="Time until this draw closes (~21:00 SAST)">
      <Hourglass className="h-3 w-3" />
      <span className="num">{countdown}</span>
    </span>
  );
};

/** Small key explaining ball highlight styles — matched, bonus, powerball, standard ranges. */
export const MatchLegend: React.FC = () => (
  <div className="flex flex-wrap items-center gap-3 text-2xs text-zinc-500 font-mono px-1 pt-1">
    <span className="flex items-center gap-1">
      <span className="inline-block h-4 w-4 rounded-full bg-gradient-to-br from-emerald-300 via-emerald-400 to-teal-600 ring-1 ring-inset" />
      <span>Matched</span>
    </span>
    <span className="flex items-center gap-1">
      <span className="inline-block h-4 w-4 rounded-full bg-gradient-to-br from-amber-200 via-amber-400 to-yellow-600 ring-1 ring-inset" />
      <span>Bonus ball</span>
    </span>
    <span className="flex items-center gap-1">
      <span className="inline-block h-4 w-4 rounded-full bg-gradient-to-br from-red-400 via-rose-600 to-red-800 ring-1 ring-inset" />
      <span>PowerBall</span>
    </span>
  </div>
);

export const ResultsView: React.FC = () => {
  const [boards, setBoards] = useState<BoardWithResult[]>([]);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedGame, setSelectedGame] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [feedbackLoading, setFeedbackLoading] = useState<number | null>(null);
  const [feedbackData, setFeedbackData] = useState<PostDrawFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tierCache, setTierCache] = useState<Record<string, PrizeTierRow[]>>({});

  // Cache prize tiers once per game type
  useEffect(() => {
    if (Object.keys(tierCache).length > 0 || loading) return;
    const games = [...new Set(boards.map((b) => b.game_type))];
    const loadAll = async () => {
      const results: Record<string, PrizeTierRow[]> = {};
      for (const g of games) {
        try {
          const data = await fetchPrizeTiers(g);
          results[g] = data.tiers;
        } catch { /* non-critical */ }
      }
      setTierCache(results);
    };
    void loadAll();
  }, [loading]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [bData, dData] = await Promise.all([
        fetchGeneratedBoards(selectedGame === 'ALL' ? undefined : selectedGame, 50),
        fetchRecentDraws(40),
      ]);
      setBoards(bData);
      setDraws(dData);
    } catch (err: any) {
      setError(err.message || 'Failed to load results and historical draws');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedGame]);

  // Auto-refresh while there are pending boards and the tab is visible
  const hasPending = boards.some(
    (b) => (b.status === 'PENDING' || b.status === 'PLAYED') && (!b.results || b.results.length === 0) && !b.result
  );
  useEffect(() => {
    if (!hasPending || loading) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadData();
      }
    }, 60_000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasPending, loading, selectedGame]);

  const handleTogglePlayed = async (boardId: number) => {
    try {
      const updated = await markBoardPlayed(boardId);
      setBoards((prev) => prev.map((b) => (b.id === updated.id ? { ...b, ...updated } : b)));
    } catch (err: any) {
      setError(err.message || 'Failed to toggle played status');
    }
  };

  const handleRunEvaluation = async () => {
    setEvaluating(true);
    try {
      await triggerPostDrawPipeline();
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Evaluation pipeline failed');
    } finally {
      setEvaluating(false);
    }
  };

  const handleOpenFeedback = async (drawId: number) => {
    setFeedbackLoading(drawId);
    try {
      const fb = await fetchPostDrawFeedback(drawId);
      setFeedbackData(fb);
    } catch (err: any) {
      setError(err.message || 'Feedback retrieval failed');
    } finally {
      setFeedbackLoading(null);
    }
  };

  // Metrics
  const totalCount = boards.length;
  const wonBoards = boards.filter((b) => {
    const prize = Number(b.total_prize ?? (b.result?.prize_amount ?? 0));
    return b.status === 'WON' || prize > 0;
  });
  const lostBoards = boards.filter((b) => b.status === 'LOST');
  const pendingBoards = boards.filter(
    (b) => (b.status === 'PENDING' || b.status === 'PLAYED') && (!b.results || b.results.length === 0) && !b.result
  );

  const evaluatedCount = wonBoards.length + lostBoards.length;
  const totalCost = boards.reduce((acc, b) => acc + Number(b.cost || 10), 0);
  const totalWinnings = boards.reduce((acc, b) => {
    if (b.total_prize !== undefined && b.total_prize !== null) {
      return acc + Number(b.total_prize);
    }
    if (b.results && b.results.length > 0) {
      return acc + b.results.reduce((sub, r) => sub + Number(r.prize_amount || 0), 0);
    }
    return acc + Number(b.result?.prize_amount || 0);
  }, 0);
  const netPL = totalWinnings - totalCost;
  const netRoi = totalCost > 0 ? (netPL / totalCost) * 100 : 0;
  const hitRate = evaluatedCount > 0 ? (wonBoards.length / evaluatedCount) * 100 : 0;

  // Visual Chart Data
  const outcomePieData = [
    { name: 'Won (Prize)', value: wonBoards.length, color: '#10b981' },
    { name: 'Awaiting Draw', value: pendingBoards.length, color: '#f59e0b' },
    { name: 'No Prize', value: lostBoards.length, color: '#64748b' },
  ].filter((d) => d.value > 0);

  const financialHistory = [...boards]
    .reverse()
    .reduce((acc: any[], b, idx) => {
      const cost = Number(b.cost || 10);
      const prize = Number(
        b.total_prize ??
          (b.results && b.results.length > 0
            ? b.results.reduce((s, r) => s + Number(r.prize_amount || 0), 0)
            : b.result?.prize_amount ?? 0)
      );
      const prevCost = idx > 0 ? acc[idx - 1].cumCost : 0;
      const prevPrize = idx > 0 ? acc[idx - 1].cumPrize : 0;
      acc.push({
        board: `#${idx + 1}`,
        cumCost: prevCost + cost,
        cumPrize: prevPrize + prize,
        date: formatDate(b.target_draw_date),
      });
      return acc;
    }, []);

  const filteredBoards = boards.filter((b) => {
    const prize = Number(b.total_prize ?? (b.result?.prize_amount ?? 0));
    const hasResults = Boolean((b.results && b.results.length > 0) || b.result);
    if (statusFilter === 'WON') return b.status === 'WON' || prize > 0;
    if (statusFilter === 'LOST') return b.status === 'LOST' || (hasResults && prize === 0);
    if (statusFilter === 'PENDING') return (b.status === 'PENDING' || b.status === 'PLAYED') && !hasResults;
    return true;
  });

  const gameFilterOptions = [
    { value: 'ALL', label: 'All bundles & games' },
    { value: 'LOTTO_FAMILY', label: 'Lotto Bundle' },
    { value: 'POWERBALL_FAMILY', label: 'PowerBall Bundle' },
    ...GAMES.map((g) => ({ value: g.id, label: g.label })),
  ];

  const statusFilterOptions = [
    { value: 'ALL', label: `All (${totalCount})` },
    { value: 'WON', label: `Won (${wonBoards.length})` },
    { value: 'PENDING', label: `Pending (${pendingBoards.length})` },
    { value: 'LOST', label: `No prize (${lostBoards.length})` },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Results & history"
        description="Compare generated boards with official winning draws and track net return."
        actions={
          <button
            onClick={handleRunEvaluation}
            disabled={evaluating}
            className="btn btn-secondary btn-sm"
          >
            <RotateCw className={`h-3.5 w-3.5 ${evaluating ? 'animate-spin' : ''}`} />
            <span>{evaluating ? 'Evaluating…' : 'Sync & evaluate results'}</span>
          </button>
        }
      />

      {error && <Alert variant="error">{error}</Alert>}

      {/* Financial Metrics */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Total staked"
          value={formatZAR(totalCost)}
          hint={`${totalCount} board${totalCount === 1 ? '' : 's'}`}
          icon={Receipt}
        />
        <StatCard
          label="Total winnings"
          value={formatZAR(totalWinnings)}
          hint={`${wonBoards.length} winning board${wonBoards.length === 1 ? '' : 's'}`}
          tone="positive"
          icon={Coins}
        />
        <StatCard
          label="Net return"
          value={`${netPL >= 0 ? '+' : ''}${netRoi.toFixed(1)}%`}
          hint={`P/L: ${netPL >= 0 ? '+' : ''}${formatZAR(netPL)}`}
          tone={netPL >= 0 ? 'positive' : 'negative'}
          icon={netPL >= 0 ? TrendingUp : TrendingDown}
        />
        <StatCard
          label="Hit rate"
          value={`${hitRate.toFixed(1)}%`}
          hint={`${wonBoards.length} of ${evaluatedCount || 1} evaluated`}
          tone="default"
          icon={Trophy}
        />
      </div>

      {/* Visual Analytics Row: Cumulative Finance Chart & Outcome Donut */}
      {boards.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Cumulative Spend vs Prize AreaChart */}
          <div className="card lg:col-span-2">
            <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                  <TrendingUp className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="card-title">Cumulative return progression</h3>
                  <p className="card-subtitle">Cumulative cost vs prize winnings across generated boards</p>
                </div>
              </div>
              <span className={`badge ${netPL >= 0 ? 'badge-success' : 'badge-neutral'} font-mono text-2xs`}>
                Net P/L: {formatZAR(netPL)}
              </span>
            </div>

            <div className="card-body">
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={financialHistory} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
                    <defs>
                      <linearGradient id="prizeGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#232328" vertical={false} />
                    <XAxis dataKey="board" stroke="#71717a" fontSize={11} tickLine={false} />
                    <YAxis stroke="#71717a" fontSize={11} tickLine={false} tickFormatter={(v) => `R${v}`} />
                    <Tooltip
                      formatter={(val: any, name: any) => [
                        formatZAR(Number(val)),
                        name === 'cumPrize' ? 'Winnings' : 'Staked',
                      ]}
                      labelFormatter={(_label, payload) => payload?.[0]?.payload?.date || ''}
                      contentStyle={{
                        backgroundColor: '#131316',
                        borderColor: '#2e2e34',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: '#f4f4f5',
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="cumCost"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#costGradient)"
                    />
                    <Area
                      type="monotone"
                      dataKey="cumPrize"
                      stroke="#10b981"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#prizeGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-2 flex items-center justify-center gap-6 text-xs text-zinc-400">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-indigo-500" />
                  Staked (ZAR)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-emerald-400" />
                  Prizes Won (ZAR)
                </span>
              </div>
            </div>
          </div>

          {/* Outcome Distribution Donut */}
          <div className="card">
            <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  <Trophy className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="card-title">Outcome ratio</h3>
                  <p className="card-subtitle">Generated board statuses</p>
                </div>
              </div>
            </div>

            <div className="card-body flex flex-col items-center justify-center">
              <div className="h-48 w-full relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Tooltip
                      formatter={(val: any, name: any) => [`${val} boards`, name]}
                      contentStyle={{
                        backgroundColor: '#131316',
                        borderColor: '#2e2e34',
                        borderRadius: '8px',
                        fontSize: '12px',
                        color: '#f4f4f5',
                      }}
                    />
                    <Pie
                      data={outcomePieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={42}
                      outerRadius={62}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="#131316"
                      strokeWidth={2}
                    >
                      {outcomePieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                  <span className="text-base font-bold font-mono text-emerald-400">{hitRate.toFixed(0)}%</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-500">Hit Rate</span>
                </div>
              </div>

              <div className="w-full space-y-1.5 mt-1">
                {outcomePieData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 font-mono text-zinc-300">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                      {item.name}
                    </span>
                    <span className="num font-semibold text-zinc-200">{item.value} boards</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="card card-body flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between bg-gradient-to-r from-surface-2 via-surface-2 to-surface-3/30">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            options={gameFilterOptions}
            value={selectedGame}
            onChange={(v) => setSelectedGame(v)}
            ariaLabel="Filter by game"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Segmented
            options={statusFilterOptions}
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
            ariaLabel="Filter by status"
          />
        </div>
      </div>

      {/* Boards List */}
      <div className="space-y-4">
        {loading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card card-body skeleton h-28" />
            ))}
          </div>
        ) : filteredBoards.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={Ticket}
              title="No boards match your filter"
              description="Generate new boards in the Generator tab or switch your filter above."
            />
          </div>
        ) : (
          filteredBoards.map((board) => {
            const matchingDraw = draws.find(
              (d) =>
                d.id === board.draw_id ||
                (board.result && d.id === board.result.draw_id) ||
                (d.game_type === board.game_type && d.draw_date === board.target_draw_date)
            );

            const isPowerBall = isPowerBallGame(board.bundle_name || board.game_type);
            const totalPrize = Number(
              board.total_prize ??
              (board.results && board.results.length > 0
                ? board.results.reduce((s, r) => s + Number(r.prize_amount || 0), 0)
                : board.result?.prize_amount || 0)
            );
            const isWinner = board.status === 'WON' || totalPrize > 0;
            const hasMultiResults = Boolean(board.results && board.results.length > 0);
            const isEvaluated = hasMultiResults || Boolean(board.result);

            const matchedSet = new Set<number>(
              board.results && board.results.length > 0
                ? board.results.flatMap((r) => r.matched_numbers || [])
                : board.result?.matched_numbers ||
                  (matchingDraw ? board.numbers.filter((n) => matchingDraw.numbers.includes(n)) : [])
            );

            const matchedBonus =
              board.results && board.results.length > 0
                ? board.results.some((r) => r.matched_bonus)
                : (board.result?.matched_bonus ??
                  (matchingDraw && board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined
                    ? isPowerBall
                      ? matchingDraw.powerball === board.bonus_or_powerball
                      : matchingDraw.bonus_ball === board.bonus_or_powerball
                    : false));

            const displayLabel = bundleLabel(board.bundle_name || board.game_type);

            return (
              <div key={board.id} className="card card-body space-y-4">
                {/* Board Meta Header */}
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge badge-neutral num">Board #{board.id}</span>
                    <span className="text-sm font-semibold text-zinc-100">{displayLabel}</span>
                    <span className="text-xs text-zinc-500">Draw: {formatDate(board.target_draw_date)}</span>
                    <span className="text-xs text-zinc-500 font-mono">
                      Conf: {board.confidence_score.toFixed(1)}%
                      {typeof board.ev_score === 'number' && ` · EV: ${board.ev_score.toFixed(0)}/100`}
                      {typeof board.simulated_hit_rate === 'number' &&
                        ` · MC: ${(board.simulated_hit_rate * 100).toFixed(1)}%`}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isWinner ? (
                      <span className="badge badge-success">Won</span>
                    ) : isEvaluated ? (
                      <span className="badge badge-neutral">No prize</span>
                    ) : (
                      <>
                        <span className="badge badge-warning">Awaiting draw</span>
                        <DrawCountdownBadge targetDate={board.target_draw_date} />
                      </>
                    )}

                    {!isEvaluated && !isWinner && (
                      <button
                        onClick={() => handleTogglePlayed(board.id)}
                        className={`btn btn-sm ${board.status === 'PLAYED' ? 'btn-ghost text-emerald-300' : 'btn-ghost text-zinc-400'}`}
                        title={
                          board.status === 'PLAYED'
                            ? 'Marked as played on the official platform — click to undo'
                            : 'Directive 10: mark as manually played on the official lottery platform'
                        }
                      >
                        {board.status === 'PLAYED' ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                          <Circle className="h-3.5 w-3.5" />
                        )}
                        <span className="text-2xs">{board.status === 'PLAYED' ? 'Played' : 'Mark played'}</span>
                      </button>
                    )}

                    <CopyButton text={boardToText(board)} />

                    {matchingDraw && (
                      <button
                        onClick={() => handleOpenFeedback(matchingDraw.id)}
                        disabled={feedbackLoading === matchingDraw.id}
                        className="btn btn-ghost btn-sm"
                        title="View post-draw model divergence analysis"
                      >
                        <Sparkles className="h-3.5 w-3.5 text-accent" />
                        <span>{feedbackLoading === matchingDraw.id ? 'Analyzing…' : 'Analysis'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Multi-Draw Prize Breakdown Banner if evaluated across sub-draws */}
                {hasMultiResults && board.results ? (
                  <div
                    className={`space-y-2 rounded-md border p-3 text-xs font-mono ${
                      isWinner
                        ? 'border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-300'
                        : 'border-line bg-surface-1 text-zinc-400'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/40 pb-2">
                      <div className="flex items-center gap-2">
                        <Trophy className={`h-4 w-4 ${isWinner ? 'text-amber-400' : 'text-zinc-600'}`} />
                        <span>
                          <strong className={isWinner ? 'text-emerald-200' : 'text-zinc-300'}>
                            {isWinner ? 'Multi-Draw Winning Board' : 'No Sub-Draw Prize'}
                          </strong>{' '}
                          · Combined outcome across bundle plays
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span>
                          Total Payout:{' '}
                          <strong className={`text-sm ${isWinner ? 'text-emerald-300' : 'text-zinc-400'}`}>
                            {formatZAR(totalPrize)}
                          </strong>
                        </span>
                        <span className="text-zinc-500">(Cost: {formatZAR(board.cost || 10)})</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                      {board.results.map((r) => {
                        const rWon = Number(r.prize_amount || 0) > 0;
                        return (
                          <div
                            key={r.id || r.game_type}
                            className="rounded bg-surface-2/60 px-2.5 py-1.5 flex items-center justify-between text-2xs"
                          >
                            <div>
                              <span className="font-semibold text-zinc-300">{gameLabel(r.game_type || '')}</span>
                              <div className="text-zinc-500">
                                {r.matched_count} match{r.matched_bonus ? ' + PB' : ''}
                                {r.division ? ` · ${r.division}` : ''}
                              </div>
                            </div>
                            <span className={`font-semibold ${rWon ? 'text-emerald-400' : 'text-zinc-500'}`}>
                              {formatZAR(r.prize_amount)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : board.result ? (
                  <div
                    className={`flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs font-mono ${
                      isWinner
                        ? 'border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-300'
                        : 'border-line bg-surface-1 text-zinc-400'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Trophy className={`h-4 w-4 ${isWinner ? 'text-amber-400' : 'text-zinc-600'}`} />
                      <span>
                        <strong className={isWinner ? 'text-emerald-200' : 'text-zinc-300'}>
                          {board.result.division || (isWinner ? 'Winning Division' : 'No Division')}
                        </strong>{' '}
                        · Matched {board.result.matched_count} main ball{board.result.matched_count === 1 ? '' : 's'}
                        {board.result.matched_bonus ? ` + ${isPowerBall ? 'PowerBall' : 'Bonus'}` : ''}
                      </span>
                      {/* Prize tier reference — shows all possible tiers on hover */}
                      {tierCache[board.game_type] && board.result?.division && (
                        <TierReference
                          tiers={tierCache[board.game_type]}
                          selectedDivision={board.result.division}
                          gameType={board.game_type}
                        />
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span>
                        Payout:{' '}
                        <strong className={`text-sm ${isWinner ? 'text-emerald-300' : 'text-zinc-400'}`}>
                          {formatZAR(totalPrize)}
                        </strong>
                      </span>
                      <span className="text-zinc-500">(Cost: {formatZAR(board.cost || 10)})</span>
                    </div>
                  </div>
                ) : null}

                {/* Numbers Grid: Predicted vs Actual */}
                <div className="grid grid-cols-1 gap-4 pt-3 border-t border-line/60 md:grid-cols-2">
                  {/* Generated Board */}
                  <div>
                    <span className="eyebrow block mb-2">Generated board</span>
                    <BallRow
                      numbers={board.numbers}
                      extra={board.bonus_or_powerball}
                      powerBall={isPowerBall}
                      matched={matchedSet}
                      extraMatched={matchedBonus}
                      size="md"
                    />
                  </div>

                  {/* Official Winning Outcome */}
                  <div>
                    <span className="eyebrow block mb-2">
                      Official winning numbers{' '}
                      {matchingDraw ? `· Draw #${matchingDraw.draw_number} (${formatDate(matchingDraw.draw_date)})` : ''}
                    </span>
                    {matchingDraw ? (
                      <>
                        <BallRow
                          numbers={matchingDraw.numbers}
                          extra={matchingDraw.powerball || matchingDraw.bonus_ball}
                          powerBall={Boolean(matchingDraw.powerball)}
                          size="md"
                        />
                        <MatchLegend />
                      </>
                    ) : (
                      <div className="text-xs text-zinc-500 italic py-1.5">
                        Awaiting official lottery draw results for {formatDate(board.target_draw_date)}
                      </div>
                    )}
                  </div>
                </div>

                {/* Reasoning */}
                {board.ai_reasoning && (
                  <div className="inset p-3 text-xs text-zinc-400 leading-relaxed font-sans">
                    <span className="font-medium text-zinc-300">Reasoning: </span>
                    {board.ai_reasoning}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* AI Post-Draw Feedback Modal */}
      {feedbackData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="card max-w-xl w-full p-6 shadow-2xl relative border-line-strong">
            <div className="flex items-center justify-between pb-4 border-b border-line">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                <h3 className="text-base font-semibold text-zinc-100">Draw performance analysis</h3>
              </div>
              <button
                onClick={() => setFeedbackData(null)}
                className="btn btn-ghost btn-sm text-zinc-400 hover:text-white"
                aria-label="Close modal"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 pt-4 text-xs">
              <div className="flex items-center justify-between inset p-3">
                <span className="text-zinc-400">Alignment accuracy rate:</span>
                <span className="num font-semibold text-emerald-400 text-sm">
                  {(feedbackData.accuracy_rate * 100).toFixed(1)}%
                </span>
              </div>

              <div>
                <span className="eyebrow block mb-1.5">Divergence analysis</span>
                <div className="inset p-3 text-zinc-300 leading-relaxed font-sans">
                  {feedbackData.divergence_analysis}
                </div>
              </div>

              <div>
                <span className="eyebrow block mb-1.5">Calibration recommendations</span>
                <ul className="space-y-1.5 list-disc list-inside text-zinc-300 pl-1">
                  {feedbackData.calibration_recommendations.map((rec, i) => (
                    <li key={i} className="leading-relaxed">
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
