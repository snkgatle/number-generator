import React, { useState, useEffect } from 'react';
import { Ball } from './Ball';
import {
  generateBoards,
  fetchGameStatistics,
  GeneratedBoard,
  StatisticalAnalysis,
  CircuitBreakerStatus,
} from '../services/api';
import {
  Sparkles,
  Cpu,
  Flame,
  Snowflake,
  Clock,
  Scale,
  AlertTriangle,
  CheckCircle2,
  Layers,
} from 'lucide-react';

interface GenerationHubProps {
  circuitBreaker: CircuitBreakerStatus | null;
  onBoardGenerated?: () => void;
}

const SUPPORTED_GAMES = [
  { id: 'LOTTO', name: 'LOTTO', color: 'from-emerald-500 to-teal-700', days: 'Wed & Sat' },
  { id: 'LOTTO_PLUS_1', name: 'LOTTO PLUS 1', color: 'from-teal-500 to-cyan-700', days: 'Wed & Sat' },
  { id: 'LOTTO_PLUS_2', name: 'LOTTO PLUS 2', color: 'from-cyan-500 to-blue-700', days: 'Wed & Sat' },
  { id: 'POWERBALL', name: 'POWERBALL', color: 'from-rose-500 to-red-800', days: 'Tue & Fri' },
  { id: 'POWERBALL_PLUS', name: 'POWERBALL PLUS', color: 'from-amber-500 to-orange-700', days: 'Tue & Fri' },
];

export const GenerationHub: React.FC<GenerationHubProps> = ({
  circuitBreaker,
  onBoardGenerated,
}) => {
  const [selectedGame, setSelectedGame] = useState<string>('LOTTO');
  const [allocatedBoards, setAllocatedBoards] = useState<number>(1);
  const [stats, setStats] = useState<StatisticalAnalysis | null>(null);
  const [statsLoading, setStatsLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [generatedBoards, setGeneratedBoards] = useState<GeneratedBoard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load statistical summary for selected game
  useEffect(() => {
    setStatsLoading(true);
    setError(null);
    fetchGameStatistics(selectedGame, 50)
      .then((data) => {
        setStats(data);
        setStatsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load stats:', err);
        setStatsLoading(false);
      });
  }, [selectedGame]);

  const isExhausted = circuitBreaker?.is_exhausted || (circuitBreaker?.remaining_boards ?? 0) <= 0;
  const remainingQuota = circuitBreaker?.remaining_boards ?? 40;

  const handleGenerate = async () => {
    if (isExhausted) return;
    setError(null);
    setSuccessMsg(null);
    setGenerating(true);

    try {
      const boards = await generateBoards(selectedGame, allocatedBoards);
      setGeneratedBoards(boards);
      setSuccessMsg(`Successfully generated ${boards.length} board(s) using DashScope Qwen-Max!`);
      if (onBoardGenerated) {
        onBoardGenerated();
      }
    } catch (err: any) {
      setError(err.message || 'Generation failed. Check API key and backend logs.');
    } finally {
      setGenerating(false);
    }
  };

  const isPowerBallGame = selectedGame.includes('POWERBALL');

  return (
    <div className="space-y-6">
      {/* Top Controls: Game Selector */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-400" />
              Qwen-Max Generation Hub
            </h2>
            <p className="text-xs text-slate-400">
              Probabilistic number selection weighted by mathematical frequencies and game matrix constraints
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
              <Layers className="w-3.5 h-3.5 text-brand-400" />
              Remaining Quota: <strong className="text-slate-200">{remainingQuota} boards</strong>
            </span>
          </div>
        </div>

        {/* Game Tabs */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 mb-6">
          {SUPPORTED_GAMES.map((game) => {
            const isSelected = selectedGame === game.id;
            return (
              <button
                key={game.id}
                onClick={() => setSelectedGame(game.id)}
                className={`p-3 rounded-xl border text-left transition-all relative overflow-hidden ${
                  isSelected
                    ? 'bg-slate-800 border-indigo-500/80 shadow-lg shadow-indigo-500/20 ring-1 ring-indigo-500'
                    : 'bg-slate-850/60 border-slate-800 hover:border-slate-750 hover:bg-slate-850'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white tracking-tight">{game.name}</span>
                  <span className="text-[10px] font-mono text-slate-400">{game.days}</span>
                </div>
                <div className="text-[11px] text-slate-400">
                  {game.id.includes('POWERBALL') ? '5 Balls (1-50) + 1 PB (1-16)' : '6 Balls (1-52)'}
                </div>
              </button>
            );
          })}
        </div>

        {/* Generation Config Row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-slate-800">
          <div className="flex items-center gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Board Count</label>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 5].map((cnt) => (
                  <button
                    key={cnt}
                    onClick={() => setAllocatedBoards(cnt)}
                    disabled={cnt > remainingQuota || isExhausted}
                    className={`w-9 h-9 rounded-lg font-mono text-xs font-bold transition-all ${
                      allocatedBoards === cnt
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-750 disabled:opacity-30 disabled:cursor-not-allowed'
                    }`}
                  >
                    {cnt}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <button
              onClick={handleGenerate}
              disabled={generating || isExhausted}
              className={`w-full sm:w-auto px-6 py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 shadow-xl transition-all ${
                isExhausted
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-750'
                  : 'bg-gradient-to-r from-emerald-500 via-teal-500 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 text-slate-950 font-bold hover:shadow-emerald-500/20 active:scale-[0.98]'
              }`}
            >
              {generating ? (
                <>
                  <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                  <span>Synthesizing Boards via Qwen-Max...</span>
                </>
              ) : isExhausted ? (
                <>
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span>Circuit Breaker Tripped (Quota 0)</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950" />
                  <span>Generate {allocatedBoards} Board(s) with AI</span>
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="mt-4 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}
      </div>

      {/* Statistical Context Preview (Phase 3 Pre-processing) */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <Scale className="w-4 h-4 text-brand-400" />
          Pre-Processed Statistical Context ({selectedGame})
        </h3>

        {statsLoading ? (
          <div className="text-xs text-slate-400 py-3">Computing historical frequency matrix...</div>
        ) : stats ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Hot Numbers */}
            <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400 mb-2">
                <Flame className="w-3.5 h-3.5" />
                <span>Top Hot Numbers</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {stats.hot_numbers.slice(0, 8).map((n) => (
                  <span
                    key={n.number}
                    className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 font-mono text-xs border border-amber-500/20"
                    title={`Drawn ${n.count} times (${n.percentage}%)`}
                  >
                    #{n.number}
                  </span>
                ))}
              </div>
            </div>

            {/* Cold Numbers */}
            <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-sky-400 mb-2">
                <Snowflake className="w-3.5 h-3.5" />
                <span>Bottom Cold Numbers</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {stats.cold_numbers.slice(0, 8).map((n) => (
                  <span
                    key={n.number}
                    className="px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-300 font-mono text-xs border border-sky-500/20"
                    title={`Drawn only ${n.count} times (${n.percentage}%)`}
                  >
                    #{n.number}
                  </span>
                ))}
              </div>
            </div>

            {/* Parity & Overdue */}
            <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 mb-2">
                <Clock className="w-3.5 h-3.5" />
                <span>Parity & Overdue Absence</span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between text-slate-300">
                  <span className="text-slate-400">Modal Odd/Even:</span>
                  <span className="font-mono font-bold text-white">{stats.most_frequent_odd_even_ratio}</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span className="text-slate-400">Most Overdue:</span>
                  <span className="font-mono text-amber-300">
                    {stats.overdue_numbers.slice(0, 3).map((o) => `#${o.number} (${o.draws_since_last}d)`).join(', ')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500">No historical stats available yet. Trigger scraper to fetch draws.</div>
        )}
      </div>

      {/* Generated Boards Results Display */}
      {generatedBoards.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            AI Recommended Boards ({generatedBoards.length})
          </h3>

          <div className="grid grid-cols-1 gap-4">
            {generatedBoards.map((board, idx) => {
              const isHighConfidence = board.confidence_score >= 85.0;
              return (
                <div
                  key={board.id || idx}
                  className="p-5 rounded-2xl bg-gradient-to-r from-slate-900/90 via-slate-850/80 to-slate-900/90 border border-slate-800 shadow-xl relative overflow-hidden"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 border border-slate-700">
                        Board #{idx + 1}
                      </span>
                      <span className="text-xs font-semibold text-slate-300">{board.game_type}</span>
                      <span className="text-xs text-slate-400 font-mono">Draw: {board.target_draw_date}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <div
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold font-mono border ${
                          isHighConfidence
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                        }`}
                      >
                        <span>{board.confidence_score.toFixed(1)}% Confidence</span>
                        {isHighConfidence && <span className="text-[10px] uppercase font-bold tracking-wider">(Bonus Board)</span>}
                      </div>
                    </div>
                  </div>

                  {/* Balls Display */}
                  <div className="flex flex-wrap items-center gap-2.5 my-4">
                    {board.numbers.map((num) => (
                      <Ball key={num} number={num} variant="standard" size="lg" />
                    ))}

                    {/* Bonus Ball or Powerball */}
                    {board.bonus_or_powerball !== null && board.bonus_or_powerball !== undefined && (
                      <div className="flex items-center gap-2 pl-2 border-l border-slate-700/60">
                        <span className="text-[10px] font-mono text-slate-400 uppercase font-semibold">
                          {isPowerBallGame ? 'PB' : 'Bonus'}
                        </span>
                        <Ball
                          number={board.bonus_or_powerball}
                          variant={isPowerBallGame ? 'powerball' : 'bonus'}
                          size="lg"
                        />
                      </div>
                    )}
                  </div>

                  {/* AI Reasoning */}
                  {board.ai_reasoning && (
                    <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 leading-relaxed font-sans">
                      <strong className="text-slate-400 font-semibold block mb-0.5">Statistical Reasoning:</strong>
                      {board.ai_reasoning}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
