import React, { useState, useEffect } from 'react';
import { Ball } from './Ball';
import {
  fetchGameStatistics,
  fetchRecentDraws,
  triggerScrape,
  StatisticalAnalysis,
  Draw,
} from '../services/api';
import {
  BarChart3,
  Flame,
  Snowflake,
  Clock,
  RotateCcw,
  History,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

const GAMES = ['LOTTO', 'LOTTO_PLUS_1', 'LOTTO_PLUS_2', 'POWERBALL', 'POWERBALL_PLUS'];

export const StatsExplorer: React.FC = () => {
  const [selectedGame, setSelectedGame] = useState<string>('LOTTO');
  const sampleSize = 50;
  const [stats, setStats] = useState<StatisticalAnalysis | null>(null);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [scraping, setScraping] = useState<boolean>(false);
  const [scrapeSuccess, setScrapeSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStatsAndDraws = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sData, dData] = await Promise.all([
        fetchGameStatistics(selectedGame, sampleSize),
        fetchRecentDraws(15, selectedGame),
      ]);
      setStats(sData);
      setDraws(dData);
    } catch (err: any) {
      setError(err.message || 'Failed to load statistical metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatsAndDraws();
  }, [selectedGame, sampleSize]);

  const handleScrape = async () => {
    setScraping(true);
    setScrapeSuccess(null);
    try {
      const res = await triggerScrape(50, [selectedGame]);
      setScrapeSuccess(res.message);
      await loadStatsAndDraws();
    } catch (err: any) {
      setError(err.message || 'Scraping failed');
    } finally {
      setScraping(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-emerald-400" />
              Historical Statistical Matrix
            </h2>
            <p className="text-xs text-slate-400">
              Mathematical frequency distribution computed locally before LLM prompt synthesis (Phase 3)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleScrape}
              disabled={scraping}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition-all active:scale-95"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${scraping ? 'animate-spin' : ''}`} />
              <span>{scraping ? 'Scraping National Lottery...' : 'Scrape Latest Draws'}</span>
            </button>
          </div>
        </div>

        {/* Game selection buttons */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {GAMES.map((g) => (
            <button
              key={g}
              onClick={() => setSelectedGame(g)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedGame === g
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-850 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {g}
            </button>
          ))}
        </div>

        {scrapeSuccess && (
          <div className="mt-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{scrapeSuccess}</span>
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-500 text-sm">Computing mathematical frequencies...</div>
      ) : stats ? (
        <div className="space-y-6">
          {/* Hot vs Cold Numbers Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Hot Numbers */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Flame className="w-5 h-5 text-amber-400" />
                  <h3 className="text-base font-bold text-white">Top 10 Hot Numbers</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">Last {stats.sample_size} Draws</span>
              </div>

              <div className="space-y-2.5">
                {stats.hot_numbers.slice(0, 10).map((item, idx) => (
                  <div key={item.number} className="flex items-center gap-3">
                    <span className="w-5 text-right font-mono text-xs text-slate-500">{idx + 1}.</span>
                    <Ball number={item.number} variant="standard" size="sm" />
                    <div className="flex-1">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono text-slate-300">Drawn {item.count}x</span>
                        <span className="font-mono text-amber-400 font-semibold">{item.percentage}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-amber-500 to-yellow-400 rounded-full"
                          style={{ width: `${Math.min(100, item.percentage * 3)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cold Numbers */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Snowflake className="w-5 h-5 text-sky-400" />
                  <h3 className="text-base font-bold text-white">Bottom 10 Cold Numbers</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">Lowest Probability</span>
              </div>

              <div className="space-y-2.5">
                {stats.cold_numbers.slice(0, 10).map((item, idx) => (
                  <div key={item.number} className="flex items-center gap-3">
                    <span className="w-5 text-right font-mono text-xs text-slate-500">{idx + 1}.</span>
                    <Ball number={item.number} variant="standard" size="sm" />
                    <div className="flex-1">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono text-slate-300">Drawn {item.count}x</span>
                        <span className="font-mono text-sky-400 font-semibold">{item.percentage}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 rounded-full"
                          style={{ width: `${Math.max(5, item.percentage * 3)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Overdue Numbers & Parity Ratios */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Overdue Absences */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-amber-400" />
                  <h3 className="text-base font-bold text-white">Most Overdue Numbers</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">Absence Latency</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {stats.overdue_numbers.slice(0, 9).map((o) => (
                  <div
                    key={o.number}
                    className="p-3 rounded-xl bg-slate-850/80 border border-slate-800 flex items-center justify-between"
                  >
                    <Ball number={o.number} variant="standard" size="sm" />
                    <div className="text-right">
                      <div className="text-xs font-mono font-bold text-amber-400">
                        {o.draws_since_last}
                      </div>
                      <div className="text-[10px] text-slate-500">draws ago</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Parity Ratios & Consecutive Pairs */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm space-y-4">
              <div>
                <h3 className="text-base font-bold text-white mb-2">Odd/Even Parity Distribution</h3>
                <div className="space-y-2">
                  {stats.odd_even_ratios.slice(0, 4).map((r) => (
                    <div key={r.ratio} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-slate-300 font-semibold">{r.ratio} Ratio</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-slate-400">{r.count} draws</span>
                        <span className="font-mono text-emerald-400 font-bold w-12 text-right">{r.percentage}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800">
                <h4 className="text-xs font-bold text-slate-300 mb-2">Recurring Consecutive Pairs</h4>
                <div className="flex flex-wrap gap-2">
                  {stats.consecutive_pairs.length > 0 ? (
                    stats.consecutive_pairs.slice(0, 6).map((cp, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 font-mono text-xs text-slate-200"
                      >
                        {cp.pair[0]} &amp; {cp.pair[1]} ({cp.count}x)
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">None detected in sample</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Historical Scraped Draws Feed */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">Recent Official Draws ({selectedGame})</h3>
              </div>
              <span className="text-xs font-mono text-slate-400">{draws.length} loaded</span>
            </div>

            <div className="space-y-2">
              {draws.map((d) => (
                <div
                  key={d.id}
                  className="p-3 rounded-xl bg-slate-850/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-slate-200">Draw #{d.draw_number}</span>
                    <span className="text-xs text-slate-400 font-mono">{d.draw_date}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5">
                    {d.numbers.map((n) => (
                      <Ball key={n} number={n} variant="standard" size="sm" />
                    ))}
                    {(d.bonus_ball || d.powerball) && (
                      <div className="flex items-center gap-1 pl-2 border-l border-slate-700/60">
                        <Ball
                          number={(d.powerball || d.bonus_ball)!}
                          variant={d.powerball ? 'powerball' : 'bonus'}
                          size="sm"
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
