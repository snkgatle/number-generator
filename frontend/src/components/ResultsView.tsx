import React, { useState, useEffect } from 'react';
import { Ball } from './Ball';
import {
  fetchGeneratedBoards,
  fetchRecentDraws,
  fetchPostDrawFeedback,
  triggerPostDrawPipeline,
  BoardWithResult,
  Draw,
  PostDrawFeedback,
} from '../services/api';
import {
  Trophy,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  Sparkles,
  AlertCircle,
  HelpCircle,
  Copy,
  Check,
  TrendingUp,
  TrendingDown,
  Coins,
  Receipt,
  Calendar,
} from 'lucide-react';

export const ResultsView: React.FC = () => {
  const [boards, setBoards] = useState<BoardWithResult[]>([]);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedGame, setSelectedGame] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [feedbackLoading, setFeedbackLoading] = useState<number | null>(null);
  const [feedbackData, setFeedbackData] = useState<PostDrawFeedback | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const handleCopyBoard = (board: BoardWithResult) => {
    const mainNumbers = board.numbers.map((n) => n.toString().padStart(2, '0')).join(', ');
    const extra =
      board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined
        ? ` | ${board.game_type.includes('POWERBALL') ? 'PB' : 'Bonus'}: ${board.bonus_or_powerball
            .toString()
            .padStart(2, '0')}`
        : '';
    const text = `${board.game_type} (${board.target_draw_date}): ${mainNumbers}${extra}`;

    navigator.clipboard.writeText(text);
    setCopiedId(board.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Compute Financial & Outcome Metrics across all loaded boards
  const totalBoardsCount = boards.length;
  const wonBoards = boards.filter((b) => b.status === 'WON' || (b.result && b.result.prize_amount > 0));
  const lostBoards = boards.filter((b) => b.status === 'LOST');
  const pendingBoards = boards.filter((b) => b.status === 'PENDING' && !b.result);

  const evaluatedBoardsCount = wonBoards.length + lostBoards.length;
  const totalCost = boards.reduce((acc, b) => acc + Number(b.cost || 5), 0);
  const totalWinnings = boards.reduce((acc, b) => acc + Number(b.result?.prize_amount || 0), 0);
  const netProfitLoss = totalWinnings - totalCost;
  const netRoi = totalCost > 0 ? (netProfitLoss / totalCost) * 100 : 0;
  const winRate = evaluatedBoardsCount > 0 ? (wonBoards.length / evaluatedBoardsCount) * 100 : 0;

  // Filter for display
  const filteredBoards = boards.filter((b) => {
    if (statusFilter === 'WON') {
      return b.status === 'WON' || (b.result && b.result.prize_amount > 0);
    }
    if (statusFilter === 'LOST') {
      return b.status === 'LOST';
    }
    if (statusFilter === 'PENDING') {
      return b.status === 'PENDING' && !b.result;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Header & Sync Bar */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-400" />
              Outcome Evaluation & Performance
            </h2>
            <p className="text-xs text-slate-400">
              Comparing AI-predicted boards against official South African National Lottery winning results
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRunEvaluation}
              disabled={evaluating}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white border border-indigo-500/30 text-xs font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/20 active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
              <span>{evaluating ? 'Evaluating Outcomes...' : 'Sync & Evaluate Results'}</span>
            </button>
          </div>
        </div>

        {/* Financial & ROI Performance Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {/* Total Staked */}
          <div className="p-3.5 rounded-xl bg-slate-850/90 border border-slate-800 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Total Staked
              </span>
              <span className="text-lg font-bold font-mono text-slate-200">
                R{totalCost.toFixed(2)}
              </span>
              <span className="text-[10px] text-slate-500 block font-mono">
                {totalBoardsCount} Board(s)
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-slate-400">
              <Receipt className="w-4 h-4" />
            </div>
          </div>

          {/* Total Won */}
          <div className="p-3.5 rounded-xl bg-slate-850/90 border border-slate-800 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Total Won
              </span>
              <span className="text-lg font-bold font-mono text-emerald-400">
                R{totalWinnings.toFixed(2)}
              </span>
              <span className="text-[10px] text-emerald-500/80 block font-mono">
                {wonBoards.length} Winning Board(s)
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Coins className="w-4 h-4" />
            </div>
          </div>

          {/* Net ROI */}
          <div className="p-3.5 rounded-xl bg-slate-850/90 border border-slate-800 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Net ROI
              </span>
              <span
                className={`text-lg font-bold font-mono ${
                  netProfitLoss >= 0 ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {netProfitLoss >= 0 ? '+' : ''}
                {netRoi.toFixed(1)}%
              </span>
              <span className="text-[10px] text-slate-400 block font-mono">
                P/L: {netProfitLoss >= 0 ? '+R' : '-R'}
                {Math.abs(netProfitLoss).toFixed(2)}
              </span>
            </div>
            <div
              className={`p-2.5 rounded-xl border ${
                netProfitLoss >= 0
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
              }`}
            >
              {netProfitLoss >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            </div>
          </div>

          {/* Win Rate */}
          <div className="p-3.5 rounded-xl bg-slate-850/90 border border-slate-800 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Hit Rate
              </span>
              <span className="text-lg font-bold font-mono text-indigo-300">
                {winRate.toFixed(1)}%
              </span>
              <span className="text-[10px] text-slate-400 block font-mono">
                {wonBoards.length}/{evaluatedBoardsCount || 1} Evaluated
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Trophy className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-800 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Game:</span>
            <select
              value={selectedGame}
              onChange={(e) => setSelectedGame(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-850 border border-slate-700 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono text-xs"
            >
              <option value="ALL">All Games</option>
              <option value="LOTTO">LOTTO</option>
              <option value="LOTTO_PLUS_1">LOTTO PLUS 1</option>
              <option value="LOTTO_PLUS_2">LOTTO PLUS 2</option>
              <option value="POWERBALL">POWERBALL</option>
              <option value="POWERBALL_PLUS">POWERBALL PLUS</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            {[
              { id: 'ALL', label: `All (${totalBoardsCount})` },
              { id: 'WON', label: `Won (${wonBoards.length})` },
              { id: 'PENDING', label: `Pending (${pendingBoards.length})` },
              { id: 'LOST', label: `Unmatched (${lostBoards.length})` },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  statusFilter === tab.id
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-750'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Boards List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm">
            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            Loading boards and evaluation outcomes...
          </div>
        ) : filteredBoards.length === 0 ? (
          <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80">
            <HelpCircle className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-300 font-medium text-sm mb-1">No Generated Boards Found</p>
            <p className="text-slate-500 text-xs">
              Use the AI Generator tab to synthesize probabilistic boards for upcoming lottery draws.
            </p>
          </div>
        ) : (
          filteredBoards.map((board) => {
            // Find corresponding official draw
            const matchingDraw = draws.find(
              (d) =>
                d.id === board.draw_id ||
                (board.result && d.id === board.result.draw_id) ||
                (d.game_type === board.game_type && d.draw_date === board.target_draw_date)
            );

            const isPowerBall = board.game_type.includes('POWERBALL');
            const hasResult = !!board.result;
            const prizeAmount = Number(board.result?.prize_amount || 0);
            const isWinner = board.status === 'WON' || prizeAmount > 0;

            // Matched items calculation
            const matchedSet = new Set<number>(
              board.result?.matched_numbers ||
                (matchingDraw ? board.numbers.filter((n) => matchingDraw.numbers.includes(n)) : [])
            );

            const matchedBonus =
              board.result?.matched_bonus ??
              (matchingDraw && board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined
                ? isPowerBall
                  ? matchingDraw.powerball === board.bonus_or_powerball
                  : matchingDraw.bonus_ball === board.bonus_or_powerball
                : false);

            const statusBadge = isWinner
              ? {
                  bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
                  icon: CheckCircle2,
                  label: 'WON PRIZE',
                }
              : board.status === 'LOST' || (hasResult && prizeAmount === 0)
              ? {
                  bg: 'bg-slate-800 text-slate-400 border-slate-700',
                  icon: XCircle,
                  label: 'UNMATCHED',
                }
              : {
                  bg: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
                  icon: Clock,
                  label: 'PENDING DRAW',
                };

            const Icon = statusBadge.icon;

            return (
              <div
                key={board.id}
                className={`p-5 rounded-2xl bg-slate-900/80 border transition-all relative overflow-hidden backdrop-blur-sm ${
                  isWinner
                    ? 'border-emerald-500/40 shadow-xl shadow-emerald-500/5 ring-1 ring-emerald-500/30'
                    : 'border-slate-800 shadow-xl'
                }`}
              >
                {/* Board Meta Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-200 border border-slate-700">
                      Board #{board.id}
                    </span>
                    <span className="text-sm font-bold text-white">{board.game_type}</span>
                    <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-500" />
                      Target: {board.target_draw_date}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      Conf: {board.confidence_score.toFixed(1)}%
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Copy Board to Clipboard */}
                    <button
                      onClick={() => handleCopyBoard(board)}
                      className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1 transition-all"
                      title="Copy numbers for official lottery entry"
                    >
                      {copiedId === board.id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-400">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5 text-slate-400" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>

                    <div
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${statusBadge.bg}`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{statusBadge.label}</span>
                    </div>

                    {matchingDraw && (
                      <button
                        onClick={() => handleOpenFeedback(matchingDraw.id)}
                        disabled={feedbackLoading === matchingDraw.id}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-medium flex items-center gap-1 transition-all"
                      >
                        <Sparkles className="w-3 h-3 text-indigo-400" />
                        <span>{feedbackLoading === matchingDraw.id ? 'Analyzing...' : 'Post-Mortem'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Prize & Division Banner (if evaluated) */}
                {board.result && (
                  <div
                    className={`mb-4 p-3 rounded-xl border flex flex-wrap items-center justify-between gap-2 text-xs font-mono ${
                      isWinner
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                        : 'bg-slate-850/80 border-slate-800 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Trophy className={`w-4 h-4 ${isWinner ? 'text-amber-400' : 'text-slate-500'}`} />
                      <span>
                        <strong className={isWinner ? 'text-emerald-300' : 'text-slate-300'}>
                          {board.result.division || (isWinner ? 'Winning Division' : 'No Division')}
                        </strong>{' '}
                        • Matched {board.result.matched_count} Main Ball(s)
                        {board.result.matched_bonus ? ` + ${isPowerBall ? 'PowerBall' : 'Bonus'}` : ''}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span>
                        Payout:{' '}
                        <strong
                          className={`text-sm font-bold ${isWinner ? 'text-emerald-400' : 'text-slate-400'}`}
                        >
                          R{prizeAmount.toFixed(2)}
                        </strong>
                      </span>
                      <span className="text-[11px] text-slate-500">
                        (Cost: R{Number(board.cost || 5).toFixed(2)})
                      </span>
                    </div>
                  </div>
                )}

                {/* Numbers Grid: Predicted vs Actual */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-3 border-y border-slate-800/80 my-3">
                  {/* Predicted Numbers */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                      AI Generated Board
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      {board.numbers.map((num) => {
                        const isMatch = matchedSet.has(num);
                        return (
                          <Ball
                            key={num}
                            number={num}
                            variant="standard"
                            isMatched={isMatch}
                            size="md"
                          />
                        );
                      })}
                      {board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined && (
                        <div className="flex items-center gap-1.5 pl-2 border-l border-slate-700/60">
                          <Ball
                            number={board.bonus_or_powerball}
                            variant={isPowerBall ? 'powerball' : 'bonus'}
                            isMatched={matchedBonus}
                            size="md"
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Official Winning Outcome */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                      Official Winning Numbers{' '}
                      {matchingDraw ? `(Draw #${matchingDraw.draw_number} • ${matchingDraw.draw_date})` : ''}
                    </span>
                    {matchingDraw ? (
                      <div className="flex flex-wrap items-center gap-2">
                        {matchingDraw.numbers.map((num) => (
                          <Ball key={num} number={num} variant="standard" size="md" />
                        ))}
                        {(matchingDraw.bonus_ball || matchingDraw.powerball) && (
                          <div className="flex items-center gap-1.5 pl-2 border-l border-slate-700/60">
                            <Ball
                              number={(matchingDraw.powerball || matchingDraw.bonus_ball)!}
                              variant={matchingDraw.powerball ? 'powerball' : 'bonus'}
                              size="md"
                            />
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 flex items-center gap-2">
                        <Clock className="w-4 h-4 shrink-0 text-amber-400" />
                        <span>Awaiting official lottery draw results for {board.target_draw_date}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* AI Reasoning */}
                {board.ai_reasoning && (
                  <p className="text-xs text-slate-400 leading-relaxed mt-2 font-mono">
                    <span className="text-slate-500 font-sans font-semibold">AI Reasoning: </span>
                    {board.ai_reasoning}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* AI Post-Draw Feedback Modal */}
      {feedbackData && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full p-6 shadow-2xl relative">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                <h3 className="text-lg font-bold text-white">
                  Qwen-Max Post-Draw Feedback Loop
                </h3>
              </div>
              <button
                onClick={() => setFeedbackData(null)}
                className="text-slate-400 hover:text-white text-xs font-mono px-2 py-1 rounded bg-slate-800"
              >
                Close &times;
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="flex justify-between p-3 rounded-xl bg-slate-850 border border-slate-800">
                <span className="text-slate-400">Alignment Accuracy Rate:</span>
                <span className="font-mono font-bold text-emerald-400 text-sm">
                  {(feedbackData.accuracy_rate * 100).toFixed(1)}%
                </span>
              </div>

              <div>
                <strong className="text-slate-300 block mb-1">Divergence Analysis:</strong>
                <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-300 leading-relaxed font-sans">
                  {feedbackData.divergence_analysis}
                </div>
              </div>

              <div>
                <strong className="text-slate-300 block mb-1">Future Calibration Recommendations:</strong>
                <ul className="space-y-1.5 list-disc list-inside text-slate-300 pl-1">
                  {feedbackData.calibration_recommendations.map((rec, i) => (
                    <li key={i} className="leading-relaxed">{rec}</li>
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
