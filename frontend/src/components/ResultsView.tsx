import React, { useState, useEffect } from 'react';
import { Ball } from './Ball';
import {
  fetchGeneratedBoards,
  fetchRecentDraws,
  fetchPostDrawFeedback,
  triggerPostDrawPipeline,
  GeneratedBoard,
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
} from 'lucide-react';

export const ResultsView: React.FC = () => {
  const [boards, setBoards] = useState<GeneratedBoard[]>([]);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedGame, setSelectedGame] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [feedbackLoading, setFeedbackLoading] = useState<number | null>(null);
  const [feedbackData, setFeedbackData] = useState<PostDrawFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [bData, dData] = await Promise.all([
        fetchGeneratedBoards(selectedGame === 'ALL' ? undefined : selectedGame, 50),
        fetchRecentDraws(30),
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

  const filteredBoards = boards.filter((b) => {
    if (statusFilter !== 'ALL' && b.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-400" />
              Outcome Evaluation & Results
            </h2>
            <p className="text-xs text-slate-400">
              Comparing AI-predicted boards against official South African National Lottery winning results
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRunEvaluation}
              disabled={evaluating}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center gap-2 transition-all"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
              <span>{evaluating ? 'Matching Draws...' : 'Sync & Evaluate Results'}</span>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
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

          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Status:</span>
            <div className="flex items-center gap-1.5">
              {['ALL', 'PENDING', 'WON', 'LOST'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${
                    statusFilter === st
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-750'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Boards Comparison List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-sm">Loading boards and evaluation outcomes...</div>
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
            // Find corresponding official draw if evaluated
            const matchingDraw = draws.find(
              (d) => d.id === board.draw_id || (d.game_type === board.game_type && d.draw_date === board.target_draw_date)
            );

            const winningSet = matchingDraw ? new Set(matchingDraw.numbers) : new Set();
            const isPowerBall = board.game_type.includes('POWERBALL');

            const statusBadge = {
              WON: {
                bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
                icon: CheckCircle2,
                label: 'WON PRIZE',
              },
              LOST: {
                bg: 'bg-slate-800 text-slate-400 border-slate-700',
                icon: XCircle,
                label: 'UNMATCHED',
              },
              PENDING: {
                bg: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
                icon: Clock,
                label: 'PENDING DRAW',
              },
            }[board.status] || {
              bg: 'bg-slate-800 text-slate-400 border-slate-700',
              icon: Clock,
              label: board.status,
            };

            const Icon = statusBadge.icon;

            return (
              <div
                key={board.id}
                className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm relative overflow-hidden"
              >
                {/* Board Meta Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-200 border border-slate-700">
                      #{board.id}
                    </span>
                    <span className="text-sm font-bold text-white">{board.game_type}</span>
                    <span className="text-xs text-slate-400 font-mono">Target: {board.target_draw_date}</span>
                    <span className="text-xs text-slate-400 font-mono">Confidence: {board.confidence_score.toFixed(1)}%</span>
                  </div>

                  <div className="flex items-center gap-2">
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
                        <span>{feedbackLoading === matchingDraw.id ? 'Analyzing...' : 'AI Post-Mortem'}</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Numbers Grid: Predicted vs Actual */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-2 border-y border-slate-800/80 my-3">
                  {/* Predicted Numbers */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                      AI Predicted Board
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      {board.numbers.map((num) => {
                        const isMatch = winningSet.has(num);
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
                            isMatched={
                              matchingDraw
                                ? (isPowerBall && matchingDraw.powerball === board.bonus_or_powerball) ||
                                  (!isPowerBall && matchingDraw.bonus_ball === board.bonus_or_powerball)
                                : false
                            }
                            size="md"
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Official Winning Numbers (if available) */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                      Official Winning Outcome {matchingDraw ? `(Draw #${matchingDraw.draw_number})` : ''}
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
                      <div className="text-xs text-slate-500 italic py-2">
                        Awaiting official lottery draw results...
                      </div>
                    )}
                  </div>
                </div>

                {/* Reasoning Preview */}
                {board.ai_reasoning && (
                  <p className="text-xs text-slate-400 leading-relaxed mt-2 font-mono">
                    <span className="text-slate-500 font-sans">Reasoning: </span>
                    {board.ai_reasoning}
                  </p>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* AI Post-Draw Feedback Modal/Drawer */}
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
