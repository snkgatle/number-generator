import React, { useState, useEffect } from 'react';
import { Ball, BallRow } from './Ball';
import {
  fetchGameStatistics,
  fetchRecentDraws,
  triggerScrape,
  StatisticalAnalysis,
  Draw,
} from '../services/api';
import { PageHeader, Alert, Segmented } from './ui';
import { GAMES, formatDate, gameLabel, isPowerBallGame } from '../utils/format';
import {
  RotateCw,
  Flame,
  Snowflake,
  Clock,
  History,
  Layers,
} from 'lucide-react';

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
  }, [selectedGame]);

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

  const gameOptions = GAMES.map((g) => ({
    value: g.id,
    label: g.label,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Statistics & draws"
        description="Historical frequency distributions and recent official winning draws."
        actions={
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="btn btn-secondary btn-sm"
          >
            <RotateCw className={`h-3.5 w-3.5 ${scraping ? 'animate-spin' : ''}`} />
            <span>{scraping ? 'Scraping…' : 'Scrape latest draws'}</span>
          </button>
        }
      />

      {/* Game Selector Toolbar */}
      <div className="card card-body flex flex-wrap items-center justify-between gap-4">
        <Segmented
          options={gameOptions}
          value={selectedGame}
          onChange={(v) => setSelectedGame(v)}
          ariaLabel="Select lottery game"
        />
        {stats && (
          <span className="badge badge-neutral num">
            Sample size: {stats.sample_size} draws
          </span>
        )}
      </div>

      {scrapeSuccess && <Alert variant="success">{scrapeSuccess}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card card-body skeleton h-48" />
          ))}
        </div>
      ) : stats ? (
        <div className="space-y-6">
          {/* Top Frequency Distribution */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Hot Numbers */}
            <div className="card">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Flame className="h-4 w-4 text-amber-400" />
                  <h3 className="card-title">Top 10 frequent numbers</h3>
                </div>
                <span className="text-2xs text-zinc-500 font-mono">Last {stats.sample_size} draws</span>
              </div>

              <div className="card-body space-y-2.5">
                {stats.hot_numbers.slice(0, 10).map((item, idx) => (
                  <div key={item.number} className="flex items-center gap-3">
                    <span className="w-5 text-right font-mono text-xs text-zinc-500">{idx + 1}.</span>
                    <Ball number={item.number} variant="standard" size="sm" />
                    <div className="flex-1">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono text-zinc-400">Drawn {item.count}x</span>
                        <span className="font-mono text-amber-400 font-medium">{item.percentage}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full bg-amber-400/80 rounded-full"
                          style={{ width: `${Math.min(100, item.percentage * 3)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cold Numbers */}
            <div className="card">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Snowflake className="h-4 w-4 text-sky-400" />
                  <h3 className="card-title">Bottom 10 infrequent numbers</h3>
                </div>
                <span className="text-2xs text-zinc-500 font-mono">Lowest frequency</span>
              </div>

              <div className="card-body space-y-2.5">
                {stats.cold_numbers.slice(0, 10).map((item, idx) => (
                  <div key={item.number} className="flex items-center gap-3">
                    <span className="w-5 text-right font-mono text-xs text-zinc-500">{idx + 1}.</span>
                    <Ball number={item.number} variant="standard" size="sm" />
                    <div className="flex-1">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-mono text-zinc-400">Drawn {item.count}x</span>
                        <span className="font-mono text-zinc-400 font-medium">{item.percentage}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full bg-zinc-600 rounded-full"
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
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Overdue Absences */}
            <div className="card">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-zinc-400" />
                  <h3 className="card-title">Most overdue numbers</h3>
                </div>
                <span className="text-2xs text-zinc-500 font-mono">Absence count</span>
              </div>

              <div className="card-body">
                <div className="grid grid-cols-3 gap-2">
                  {stats.overdue_numbers.slice(0, 9).map((o) => (
                    <div key={o.number} className="inset p-2.5 flex items-center justify-between">
                      <Ball number={o.number} variant="standard" size="sm" />
                      <div className="text-right">
                        <div className="num text-xs font-semibold text-zinc-200">{o.draws_since_last}</div>
                        <div className="text-2xs text-zinc-500">draws ago</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Parity & Pairs */}
            <div className="card space-y-4">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-zinc-400" />
                  <h3 className="card-title">Odd / Even distribution</h3>
                </div>
              </div>

              <div className="px-5 pb-5 space-y-4">
                <div className="space-y-2">
                  {stats.odd_even_ratios.slice(0, 4).map((r) => (
                    <div key={r.ratio} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-zinc-300">{r.ratio} ratio</span>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-zinc-500">{r.count} draws</span>
                        <span className="font-mono text-zinc-200 font-semibold w-12 text-right">{r.percentage}%</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-3 border-t border-line">
                  <span className="eyebrow block mb-2">Recurring consecutive pairs</span>
                  <div className="flex flex-wrap gap-1.5">
                    {stats.consecutive_pairs.length > 0 ? (
                      stats.consecutive_pairs.slice(0, 6).map((cp, idx) => (
                        <span key={idx} className="badge badge-neutral num">
                          {cp.pair[0]} & {cp.pair[1]} ({cp.count}x)
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-zinc-500">None detected in sample</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Historical Scraped Draws Feed */}
          <div className="card">
            <div className="card-header">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-zinc-400" />
                <h3 className="card-title">Recent official winning draws ({gameLabel(selectedGame)})</h3>
              </div>
              <span className="text-2xs text-zinc-500 font-mono">{draws.length} loaded</span>
            </div>

            <div className="divide-y divide-line/60">
              {draws.map((d) => (
                <div
                  key={d.id}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-3/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="badge badge-neutral num">Draw #{d.draw_number}</span>
                    <span className="text-xs text-zinc-400">{formatDate(d.draw_date)}</span>
                  </div>

                  <BallRow
                    numbers={d.numbers}
                    extra={d.powerball || d.bonus_ball}
                    powerBall={isPowerBallGame(d.game_type)}
                    size="sm"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
