import React, { useState, useEffect } from 'react';
import { Ball, BallRow } from './Ball';
import {
  generateBoards,
  fetchGameStatistics,
  fetchCircuitBreaker,
  GeneratedBoard,
  StatisticalAnalysis,
  CircuitBreakerStatus,
} from '../services/api';
import { PageHeader, Alert, CopyButton, Segmented } from './ui';
import {
  BUNDLES,
  formatDate,
  formatZAR,
  gameLabel,
  bundleLabel,
  bundleForGame,
  isPowerBallGame,
  nextDrawDate,
  boardToText,
} from '../utils/format';
import { Sparkles, Calendar, Layers, ShieldCheck, Flame, Snowflake, Clock, CheckCircle2 } from 'lucide-react';

interface GenerationHubProps {
  circuitBreaker: CircuitBreakerStatus | null;
  onBoardGenerated?: () => void;
}

export const GenerationHub: React.FC<GenerationHubProps> = ({
  circuitBreaker,
  onBoardGenerated,
}) => {
  const [selectedGame, setSelectedGame] = useState<string>('LOTTO_FAMILY');
  const [allocatedBoards, setAllocatedBoards] = useState<number>(1);
  const [targetDate, setTargetDate] = useState<string>(nextDrawDate('LOTTO_FAMILY'));
  const [stats, setStats] = useState<StatisticalAnalysis | null>(null);
  const [statsLoading, setStatsLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [generatedBoards, setGeneratedBoards] = useState<GeneratedBoard[]>([]);
  const [poolBreaker, setPoolBreaker] = useState<CircuitBreakerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Sync target date when game changes
  useEffect(() => {
    setTargetDate(nextDrawDate(selectedGame));
  }, [selectedGame]);

  // Load the circuit breaker for the pool that owns the selected bundle
  useEffect(() => {
    const pool = selectedGame === 'DAILY_LOTTO' ? 'DAILY_LOTTO' : 'BUNDLE';
    fetchCircuitBreaker(pool)
      .then(setPoolBreaker)
      .catch(() => setPoolBreaker(null));
  }, [selectedGame]);

  // Load statistical summary for selected game or bundle
  useEffect(() => {
    setStatsLoading(true);
    setError(null);
    const statQueryGame = selectedGame === 'POWERBALL_FAMILY' ? 'POWERBALL' : selectedGame === 'LOTTO_FAMILY' ? 'LOTTO' : selectedGame;
    fetchGameStatistics(statQueryGame, 50)
      .then((data) => {
        setStats(data);
        setStatsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load stats:', err);
        setStatsLoading(false);
      });
  }, [selectedGame]);

  const activeBreaker = poolBreaker ?? circuitBreaker;
  const isExhausted = Boolean(activeBreaker?.is_exhausted) || (activeBreaker?.remaining_boards ?? 0) <= 0;
  const remainingQuota = activeBreaker?.remaining_boards ?? 20;
  const currentBundle = bundleForGame(selectedGame);
  const costPerBoard = currentBundle?.costPerBoard ?? 10.0;
  const estimatedCost = allocatedBoards * costPerBoard;

  const handleGenerate = async () => {
    if (isExhausted) return;
    setError(null);
    setSuccessMsg(null);
    setGenerating(true);

    try {
      const boards = await generateBoards(selectedGame, allocatedBoards, targetDate);
      setGeneratedBoards(boards);
      setSuccessMsg(
        `Generated ${boards.length} board${boards.length > 1 ? 's' : ''} for ${bundleLabel(selectedGame)} on ${formatDate(targetDate)}.`
      );
      if (onBoardGenerated) {
        onBoardGenerated();
      }
    } catch (err: any) {
      setError(err.message || 'Generation failed. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const bundleOptions = BUNDLES.map((b) => ({
    value: b.id,
    label: (
      <span className="flex items-center gap-1.5 py-0.5">
        <span className="font-semibold">{b.label}</span>
        <span className="text-2xs text-zinc-400 font-normal">({b.days} · {formatZAR(b.costPerBoard)})</span>
      </span>
    ),
  }));

  const countOptions = [1, 2, 3, 5].map((cnt) => ({
    value: cnt,
    label: <span className="num">{cnt}</span>,
    disabled: cnt > remainingQuota || isExhausted,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Generate boards"
        description="Bundle-based board generation applying 1 ticket across all sub-draws with multi-draw optimization."
      />

      {error && <Alert variant="error">{error}</Alert>}
      {successMsg && <Alert variant="success">{successMsg}</Alert>}

      {/* Main Configuration Card */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Generation parameters</h2>
            <p className="card-subtitle">Select game bundle, draw date, and quantity to generate</p>
          </div>
          <span className="badge badge-neutral">
            <Layers className="h-3 w-3" />
            <span className="num">{remainingQuota}</span> boards left in budget
          </span>
        </div>

        <div className="card-body space-y-5">
          {/* Bundle Selector */}
          <div>
            <label className="label">Select game bundle</label>
            <div className="flex flex-wrap gap-2">
              <Segmented
                options={bundleOptions}
                value={selectedGame}
                onChange={(g) => setSelectedGame(g)}
                ariaLabel="Lottery game bundle selection"
              />
            </div>
            {currentBundle && (
              <div className="mt-2 flex items-center gap-2 text-xs text-accent">
                <CheckCircle2 className="h-3.5 w-3.5 text-accent shrink-0" />
                <span>
                  <strong>1 Generated Board applies to:</strong> {currentBundle.subGamesDisplay} ({currentBundle.description})
                </span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-5 pt-2 border-t border-line sm:grid-cols-3">
            {/* Board Count */}
            <div>
              <label className="label">Number of boards</label>
              <Segmented
                options={countOptions}
                value={allocatedBoards}
                onChange={(cnt) => setAllocatedBoards(cnt)}
                ariaLabel="Board count selection"
              />
            </div>

            {/* Target Draw Date */}
            <div>
              <label className="label flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-zinc-500" />
                Target draw date
              </label>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="input num"
              />
            </div>

            {/* Cost Preview & Action */}
            <div className="flex flex-col justify-end">
              <div className="flex items-center justify-between text-xs text-zinc-500 mb-1.5">
                <span>Total cost</span>
                <span className="num font-semibold text-zinc-200">{formatZAR(estimatedCost)}</span>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating || isExhausted}
                className="btn btn-primary w-full"
              >
                {generating ? (
                  <>
                    <span className="dot bg-white animate-pulse" />
                    <span>Synthesizing boards…</span>
                  </>
                ) : isExhausted ? (
                  <span>Budget exhausted</span>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span>Generate {allocatedBoards} board{allocatedBoards > 1 ? 's' : ''}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Pre-Processed Statistical Summary */}
      <div className="card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Statistical context ({gameLabel(selectedGame)})</h3>
            <p className="card-subtitle">Last 50 draws baseline for parity and frequency</p>
          </div>
          {stats && (
            <span className="badge badge-neutral num">
              {stats.sample_size} draws sampled
            </span>
          )}
        </div>

        <div className="card-body">
          {statsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-20" />
              ))}
            </div>
          ) : stats ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {/* Hot Numbers */}
              <div className="inset p-3.5 space-y-2 border-l-2 border-l-amber-500/80 bg-surface-1/70">
                <div className="flex items-center gap-1.5 text-xs font-medium text-amber-400">
                  <Flame className="h-3.5 w-3.5" />
                  <span>Frequent numbers</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {stats.hot_numbers.slice(0, 7).map((n) => (
                    <Ball key={n.number} number={n.number} size="sm" />
                  ))}
                </div>
              </div>

              {/* Cold Numbers */}
              <div className="inset p-3.5 space-y-2 border-l-2 border-l-sky-500/80 bg-surface-1/70">
                <div className="flex items-center gap-1.5 text-xs font-medium text-sky-400">
                  <Snowflake className="h-3.5 w-3.5" />
                  <span>Infrequent numbers</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {stats.cold_numbers.slice(0, 7).map((n) => (
                    <Ball key={n.number} number={n.number} size="sm" />
                  ))}
                </div>
              </div>

              {/* Parity & Overdue */}
              <div className="inset p-3.5 space-y-1.5 text-xs">
                <div className="flex items-center gap-1.5 font-medium text-zinc-300 mb-1">
                  <Clock className="h-3.5 w-3.5 text-zinc-500" />
                  <span>Parity & overdue</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Modal odd/even:</span>
                  <span className="num font-semibold text-zinc-200">{stats.most_frequent_odd_even_ratio}</span>
                </div>
                <div className="flex justify-between text-zinc-400">
                  <span>Most overdue:</span>
                  <span className="num text-zinc-200">
                    {stats.overdue_numbers.slice(0, 3).map((o) => `${o.number} (${o.draws_since_last}d)`).join(', ')}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-zinc-500">No statistical context available for this game yet.</div>
          )}
        </div>
      </div>

      {/* Generated Boards Results Display */}
      {generatedBoards.length > 0 && (
        <section className="space-y-4" aria-labelledby="generated-boards-heading">
          <div className="flex items-center justify-between">
            <h3 id="generated-boards-heading" className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" />
              Generated boards ({generatedBoards.length})
            </h3>
            <span className="badge badge-neutral flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              Collision checked
            </span>
          </div>

          <div className="space-y-3">
            {generatedBoards.map((board, idx) => {
              const isHighConfidence = board.confidence_score >= 90.0;
              const textToCopy = boardToText(board);

              return (
                <div key={board.id || idx} className="card card-body space-y-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-2">
                      <span className="badge badge-neutral num">Board #{idx + 1}</span>
                      <span className="text-sm font-medium text-zinc-200">{gameLabel(board.game_type)}</span>
                      <span className="text-xs text-zinc-500">Target: {formatDate(board.target_draw_date)}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`badge ${isHighConfidence ? 'badge-accent' : 'badge-neutral'}`}
                        title="Model confidence score"
                      >
                        <span className="num">{board.confidence_score.toFixed(1)}%</span> confidence
                        {isHighConfidence && <span>· Bonus</span>}
                      </span>
                      {typeof board.ev_score === 'number' && (
                        <span
                          className={`badge ${board.ev_score >= 80 ? 'badge-success' : board.ev_score >= 50 ? 'badge-neutral' : 'badge-warning'}`}
                          title="Directive 20: Expected Value score — penalizes human-biased combinations (all ≤31, sequences)"
                        >
                          <span className="num">EV {board.ev_score.toFixed(0)}</span>/100
                        </span>
                      )}
                      {typeof board.simulated_hit_rate === 'number' && (
                        <span
                          className="badge badge-neutral"
                          title="Directive 15: Monte Carlo hit rate across 10,000 weighted simulations"
                        >
                          <span className="num">MC {(board.simulated_hit_rate * 100).toFixed(1)}%</span>
                        </span>
                      )}
                      <CopyButton text={textToCopy} label="Copy board" />
                    </div>
                  </div>

                  <div className="py-1">
                    <BallRow
                      numbers={board.numbers}
                      extra={board.bonus_or_powerball}
                      powerBall={isPowerBallGame(board.game_type)}
                      size="md"
                    />
                  </div>

                  {board.ai_reasoning && (
                    <div className="inset p-3 text-xs text-zinc-400 leading-relaxed font-sans">
                      <span className="font-medium text-zinc-300">Reasoning: </span>
                      {board.ai_reasoning}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
};
