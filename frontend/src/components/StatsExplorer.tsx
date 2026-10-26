import React, { useState, useEffect } from 'react';
import { Ball, BallRow } from './Ball';
import {
  fetchGameStatistics,
  fetchRecentDraws,
  triggerScrape,
  StatisticalAnalysis,
  Draw,
  NumberFrequency,
} from '../services/api';
import { PageHeader, Alert, Segmented } from './ui';
import { GAMES, formatDate, gameLabel, isPowerBallGame, BUNDLES, bundleLabel } from '../utils/format';
import {
  RotateCw,
  Flame,
  Clock,
  History,
  BarChart2,
  PieChart as PieIcon,
  TrendingUp,
  Grid,
  Layers,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  ReferenceLine,
} from 'recharts';

const PARITY_COLORS = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#6366f1'];

export const StatsExplorer: React.FC = () => {
  const [selectedGame, setSelectedGame] = useState<string>('LOTTO');
  const [selectedBundle, setSelectedBundle] = useState<string>('LOTTO_FAMILY');
  const sampleSize = 50;
  const [stats, setStats] = useState<StatisticalAnalysis | null>(null);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [scraping, setScraping] = useState<boolean>(false);
  const [scrapeSuccess, setScrapeSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'charts' | 'matrix' | 'draws'>('charts');
  const [inspectedNumber, setInspectedNumber] = useState<number | null>(null);

  // Resolve which game name to show — maps bundle selections to their representative API endpoint
  const getApiGameForBundle = (bundleId: string): string => {
    if (bundleId === 'LOTTO_FAMILY') return 'LOTTO';
    return 'POWERBALL';
  };

  const viewName = (() => {
    if (selectedGame === 'LOTTO_FAMILY' || selectedGame === 'POWERBALL_FAMILY') {
      return { displayName: bundleLabel(selectedGame), apiKey: getApiGameForBundle(selectedGame) };
    }
    return { displayName: gameLabel(selectedGame), apiKey: selectedGame };
  })();

  const loadStatsAndDraws = async () => {
    setLoading(true);
    setError(null);
    try {
      const game = viewName.apiKey;
      const [sData, dData] = await Promise.all([
        fetchGameStatistics(game, sampleSize),
        fetchRecentDraws(20, game),
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
  }, [selectedGame, selectedBundle]);

  const handleScrape = async () => {
    setScraping(true);
    setScrapeSuccess(null);
    try {
      const game = viewName.apiKey;
      const res = await triggerScrape(50, [game]);
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

  const bundleOptions = BUNDLES.map((b) => ({
    value: b.id,
    label: (
      <span className="flex items-center gap-1.5 py-0.5">
        <Layers className="h-3 w-3 text-accent" />
        <span>{bundleLabel(b.id)}</span>
      </span>
    ),
  }));

  // When a bundle is selected, use its representative sub-game for API calls
  // Frequency Bar Chart Data (Top 10 Hot vs Top 5 Cold)
  const frequencyChartData = stats
    ? [
        ...stats.hot_numbers.slice(0, 8).map((h) => ({
          number: `#${h.number}`,
          count: h.count,
          percentage: h.percentage,
          type: 'hot',
        })),
        ...stats.cold_numbers.slice(0, 4).map((c) => ({
          number: `#${c.number}`,
          count: c.count,
          percentage: c.percentage,
          type: 'cold',
        })),
      ]
    : [];

  // Parity Donut Chart Data
  const parityChartData = stats
    ? stats.odd_even_ratios.slice(0, 5).map((r, i) => ({
        name: `${r.ratio} Ratio`,
        value: r.count,
        percentage: r.percentage,
        color: PARITY_COLORS[i % PARITY_COLORS.length],
      }))
    : [];

  // Historical Draw Sum Fluctuation Data
  const sumTrendData = draws
    .slice()
    .reverse()
    .map((d) => {
      const sum = d.numbers.reduce((acc, n) => acc + n, 0);
      return {
        draw: `#${d.draw_number}`,
        sum,
        date: formatDate(d.draw_date),
      };
    });

  const averageSum =
    sumTrendData.length > 0
      ? Math.round(sumTrendData.reduce((acc, d) => acc + d.sum, 0) / sumTrendData.length)
      : 130;

  // Number Matrix configuration (1 to 52 for LOTTO, 1 to 50 for PowerBall)
  const totalNumbers = isPowerBallGame(selectedGame) ? 50 : 52;
  const numbersList = Array.from({ length: totalNumbers }, (_, i) => i + 1);

  const hotSet = new Set(stats?.hot_numbers.slice(0, 10).map((h) => h.number) || []);
  const coldSet = new Set(stats?.cold_numbers.slice(0, 10).map((c) => c.number) || []);
  const overdueMap = new Map(stats?.overdue_numbers.map((o) => [o.number, o.draws_since_last]) || []);
  const frequencyMap = new Map<number, NumberFrequency>();
  stats?.hot_numbers.forEach((h) => frequencyMap.set(h.number, h));
  stats?.cold_numbers.forEach((c) => frequencyMap.set(c.number, c));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Statistics & analytics"
        description="Deep statistical distributions, interactive charts, and historical winning trends."
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

      {/* Game / Bundle Selector Toolbar */}
      <div className="card card-body flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-surface-2 via-surface-2 to-surface-3/30">
        <div className="flex flex-col sm:flex-row gap-3">
          <Segmented
            options={gameOptions}
            value={selectedGame}
            onChange={(v) => setSelectedGame(v)}
            ariaLabel="Select lottery game"
          />
          <Segmented
            options={bundleOptions}
            value={selectedBundle}
            onChange={(v) => {
              setSelectedGame(v);
              setSelectedBundle(v);
            }}
            ariaLabel="Select game bundle"
          />
        </div>

        <div className="flex items-center gap-3">
          {stats && (
            <span className="badge badge-neutral num">
              Sample: {stats.sample_size} draws
            </span>
          )}
          <Segmented
            options={[
              { value: 'charts', label: <span className="flex items-center gap-1.5"><BarChart2 className="h-3.5 w-3.5 text-indigo-400" /> Charts</span> },
              { value: 'matrix', label: <span className="flex items-center gap-1.5"><Grid className="h-3.5 w-3.5 text-amber-400" /> Heatmap</span> },
              { value: 'draws', label: <span className="flex items-center gap-1.5"><History className="h-3.5 w-3.5 text-emerald-400" /> Draws</span> },
            ]}
            value={activeTab}
            onChange={(t) => setActiveTab(t)}
            ariaLabel="View mode"
          />
        </div>
      </div>

      {scrapeSuccess && <Alert variant="success">{scrapeSuccess}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card card-body skeleton h-52" />
          ))}
        </div>
      ) : stats ? (
        <div className="space-y-6">
          {/* TAB 1: INTERACTIVE CHARTS */}
          {activeTab === 'charts' && (
            <>
              {/* Primary Charts Row: Frequency Histogram & Parity Donut */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Frequency Bar Chart */}
                <div className="card lg:col-span-2">
                  <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400">
                        <Flame className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="card-title">Frequency distribution (Hot vs Cold)</h3>
                        <p className="card-subtitle">Number appearance count over {stats.sample_size} draws</p>
                      </div>
                    </div>
                    <span className="badge badge-neutral font-mono text-2xs">Top & bottom outliers</span>
                  </div>

                  <div className="card-body">
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={frequencyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#232328" vertical={false} />
                          <XAxis dataKey="number" stroke="#71717a" fontSize={11} tickLine={false} />
                          <YAxis stroke="#71717a" fontSize={11} tickLine={false} />
                          <Tooltip
                            formatter={(val: any, _name: any, item: any) => [
                              `${val} draws (${item.payload.percentage}%)`,
                              item.payload.type === 'hot' ? 'Hot Number' : 'Cold Number',
                            ]}
                            contentStyle={{
                              backgroundColor: '#131316',
                              borderColor: '#2e2e34',
                              borderRadius: '8px',
                              fontSize: '12px',
                              color: '#f4f4f5',
                            }}
                          />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {frequencyChartData.map((entry, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={entry.type === 'hot' ? '#f59e0b' : '#38bdf8'}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="mt-3 flex items-center justify-center gap-6 text-xs text-zinc-400">
                      <span className="flex items-center gap-1.5">
                        <span className="h-2.5 w-2.5 rounded-sm bg-amber-500" />
                        Frequent (Hot)
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="h-2.5 w-2.5 rounded-sm bg-sky-400" />
                        Infrequent (Cold)
                      </span>
                    </div>
                  </div>
                </div>

                {/* Odd/Even Parity Donut Chart */}
                <div className="card">
                  <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-purple-500/10 border border-purple-500/30 text-purple-400">
                        <PieIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="card-title">Parity breakdown</h3>
                        <p className="card-subtitle">Odd : Even ratios in history</p>
                      </div>
                    </div>
                  </div>

                  <div className="card-body flex flex-col items-center justify-center">
                    <div className="h-52 w-full relative">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Tooltip
                            formatter={(val: any, _name: any, item: any) => [
                              `${val} draws (${item.payload.percentage}%)`,
                              item.payload.name,
                            ]}
                            contentStyle={{
                              backgroundColor: '#131316',
                              borderColor: '#2e2e34',
                              borderRadius: '8px',
                              fontSize: '12px',
                              color: '#f4f4f5',
                            }}
                          />
                          <Pie
                            data={parityChartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={45}
                            outerRadius={68}
                            paddingAngle={4}
                            dataKey="value"
                            stroke="#131316"
                            strokeWidth={2}
                          >
                            {parityChartData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                        <span className="text-xs uppercase font-mono tracking-wider text-zinc-500">Dominant</span>
                        <span className="text-sm font-bold font-mono text-purple-300">
                          {stats.most_frequent_odd_even_ratio}
                        </span>
                      </div>
                    </div>

                    <div className="w-full space-y-1.5 mt-2">
                      {parityChartData.slice(0, 3).map((item) => (
                        <div key={item.name} className="flex items-center justify-between text-xs">
                          <span className="flex items-center gap-1.5 font-mono text-zinc-300">
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                            {item.name}
                          </span>
                          <span className="num font-semibold text-zinc-200">{item.percentage}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Secondary Row: Draw Sum Trend Chart & Overdue Numbers */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Sum Fluctuation Trend */}
                <div className="card lg:col-span-2">
                  <div className="card-header">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                        <TrendingUp className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="card-title">Draw sum equilibrium & variance</h3>
                        <p className="card-subtitle">Aggregate sum per draw over recent official results</p>
                      </div>
                    </div>
                    <span className="badge badge-neutral num text-2xs">Mean: ~{averageSum}</span>
                  </div>

                  <div className="card-body">
                    <div className="h-56 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={sumTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#232328" vertical={false} />
                          <XAxis dataKey="draw" stroke="#71717a" fontSize={11} tickLine={false} />
                          <YAxis stroke="#71717a" fontSize={11} tickLine={false} domain={['auto', 'auto']} />
                          <Tooltip
                            formatter={(val: any) => [`Sum: ${val}`, 'Total Sum']}
                            labelFormatter={(_label, payload) => payload?.[0]?.payload?.date || ''}
                            contentStyle={{
                              backgroundColor: '#131316',
                              borderColor: '#2e2e34',
                              borderRadius: '8px',
                              fontSize: '12px',
                              color: '#f4f4f5',
                            }}
                          />
                          <ReferenceLine
                            y={averageSum}
                            stroke="#10b981"
                            strokeDasharray="4 4"
                            label={{ value: `Avg ${averageSum}`, fill: '#10b981', fontSize: 10, position: 'right' }}
                          />
                          <Line
                            type="monotone"
                            dataKey="sum"
                            stroke="#8b5cf6"
                            strokeWidth={2.5}
                            dot={{ fill: '#8b5cf6', strokeWidth: 1, r: 3 }}
                            activeDot={{ r: 6, fill: '#c084fc' }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Overdue Numbers Card */}
                <div className="card">
                  <div className="card-header">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-400">
                        <Clock className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="card-title">Most overdue</h3>
                        <p className="card-subtitle">Draws elapsed since last drawn</p>
                      </div>
                    </div>
                  </div>

                  <div className="card-body">
                    <div className="grid grid-cols-2 gap-2.5">
                      {stats.overdue_numbers.slice(0, 6).map((o) => (
                        <div
                          key={o.number}
                          className="inset p-2.5 flex items-center justify-between border-l-2 border-l-rose-500/80 bg-surface-1/70"
                        >
                          <Ball number={o.number} size="sm" />
                          <div className="text-right">
                            <span className="num font-bold text-xs text-rose-300">{o.draws_since_last}</span>
                            <span className="block text-[10px] text-zinc-500">draws ago</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="pt-4 mt-4 border-t border-line">
                      <span className="eyebrow block mb-2">Recurring consecutive pairs</span>
                      <div className="flex flex-wrap gap-1.5">
                        {stats.consecutive_pairs.length > 0 ? (
                          stats.consecutive_pairs.slice(0, 4).map((cp, idx) => (
                            <span key={idx} className="badge badge-accent num bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                              {cp.pair[0]} & {cp.pair[1]} ({cp.count}x)
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-zinc-500">No consecutive pairs detected</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* TAB 2: INTERACTIVE NUMBER HEATMAP MATRIX */}
          {activeTab === 'matrix' && (
            <div className="card">
              <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                    <Grid className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="card-title">Lottery number matrix ({gameLabel(selectedGame)})</h3>
                    <p className="card-subtitle">Visual heatmap of all {totalNumbers} numbers: hot, cold, and overdue</p>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full ring-2 ring-amber-400 bg-amber-500/40" />
                    Hot (Top 10)
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full ring-2 ring-sky-400 bg-sky-500/40" />
                    Cold (Bottom 10)
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full ring-2 ring-rose-400 bg-rose-500/40" />
                    Overdue
                  </span>
                </div>
              </div>

              <div className="card-body space-y-6">
                <div className="grid grid-cols-6 sm:grid-cols-9 md:grid-cols-13 gap-2.5">
                  {numbersList.map((num) => {
                    const isHot = hotSet.has(num);
                    const isCold = coldSet.has(num);
                    const overdue = overdueMap.get(num) ?? 0;
                    const isOverdue = overdue >= 10;
                    const isSelected = inspectedNumber === num;

                    let borderClass = 'border-line';
                    if (isHot) borderClass = 'border-amber-400/80 shadow-sm shadow-amber-500/20';
                    else if (isCold) borderClass = 'border-sky-400/80 shadow-sm shadow-sky-500/20';
                    else if (isOverdue) borderClass = 'border-rose-400/80 shadow-sm shadow-rose-500/20';

                    return (
                      <button
                        key={num}
                        onClick={() => setInspectedNumber(isSelected ? null : num)}
                        className={`group relative flex flex-col items-center justify-center p-2 rounded-lg border bg-surface-1 transition-all duration-150 hover:scale-105 hover:bg-surface-3 ${borderClass} ${
                          isSelected ? 'ring-2 ring-accent bg-surface-3' : ''
                        }`}
                      >
                        <Ball number={num} size="sm" />
                        <span className="mt-1 text-[10px] font-mono text-zinc-500 group-hover:text-zinc-300">
                          {overdue > 0 ? `${overdue}d` : 'drawn'}
                        </span>
                        {isHot && (
                          <span className="absolute -top-1 -right-1 flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Inspected Number Detail Drawer */}
                {inspectedNumber !== null && (
                  <div className="inset p-4 bg-gradient-to-r from-surface-1 via-surface-2 to-surface-3/50 flex flex-wrap items-center justify-between gap-4 border-l-4 border-l-accent">
                    <div className="flex items-center gap-3">
                      <Ball number={inspectedNumber} size="lg" />
                      <div>
                        <div className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                          Number {inspectedNumber} Metrics
                          {hotSet.has(inspectedNumber) && <span className="badge badge-warning">Hot outlier</span>}
                          {coldSet.has(inspectedNumber) && <span className="badge badge-neutral text-sky-400">Cold outlier</span>}
                        </div>
                        <div className="text-xs text-zinc-400">
                          {overdueMap.has(inspectedNumber)
                            ? `Absent for ${overdueMap.get(inspectedNumber)} consecutive draws`
                            : 'Appeared in recent draw'}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <span className="text-2xs uppercase text-zinc-500 font-mono">Drawn count</span>
                        <div className="num text-base font-bold text-zinc-200">
                          {frequencyMap.get(inspectedNumber)?.count ?? '—'} draws
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-2xs uppercase text-zinc-500 font-mono">Hit rate</span>
                        <div className="num text-base font-bold text-amber-400">
                          {frequencyMap.get(inspectedNumber)?.percentage ?? '—'}%
                        </div>
                      </div>
                      <button
                        onClick={() => setInspectedNumber(null)}
                        className="btn btn-ghost btn-sm text-zinc-400"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: HISTORICAL SCRAPED DRAWS FEED */}
          {activeTab === 'draws' && (
            <div className="card">
              <div className="card-header bg-gradient-to-r from-surface-2 to-surface-3/40">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <History className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="card-title">Recent official winning draws ({gameLabel(selectedGame)})</h3>
                    <p className="card-subtitle">Scraped official results verified against Ithuba records</p>
                  </div>
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
                      <span className="badge badge-neutral num font-bold">Draw #{d.draw_number}</span>
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
          )}
        </div>
      ) : null}
    </div>
  );
};

