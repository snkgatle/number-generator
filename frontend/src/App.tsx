import { useState, useEffect, type ElementType } from 'react';
import {
  fetchHealth,
  fetchCurrentBudget,
  fetchCircuitBreaker,
  HealthResponse,
  MonthlyBudget,
  CircuitBreakerStatus,
} from './services/api';
import { Overview } from './components/Overview';
import { GenerationHub } from './components/GenerationHub';
import { ResultsView } from './components/ResultsView';
import { StatsExplorer } from './components/StatsExplorer';
import { ProgressBar } from './components/ui';
import { formatZAR } from './utils/format';
import { LayoutGrid, Sparkles, Trophy, BarChart3, Menu, X, RotateCw } from 'lucide-react';

export type Tab = 'overview' | 'generate' | 'results' | 'stats';

const NAV: { id: Tab; label: string; icon: ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'generate', label: 'Generate boards', icon: Sparkles },
  { id: 'results', label: 'Results', icon: Trophy },
  { id: 'stats', label: 'Statistics', icon: BarChart3 },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [navOpen, setNavOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [budget, setBudget] = useState<MonthlyBudget | null>(null);
  const [circuitBreaker, setCircuitBreaker] = useState<CircuitBreakerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadSystemState = async () => {
    setLoading(true);
    const [hData, bData, cbData] = await Promise.all([
      fetchHealth().catch(() => null),
      fetchCurrentBudget().catch(() => null),
      fetchCircuitBreaker().catch(() => null),
    ]);
    setHealth(hData);
    if (bData) setBudget(bData);
    if (cbData) setCircuitBreaker(cbData);
    setLoading(false);
  };

  useEffect(() => {
    loadSystemState();
  }, []);

  const navigate = (tab: Tab) => {
    setActiveTab(tab);
    setNavOpen(false);
    window.scrollTo({ top: 0 });
  };

  const totalBoards = budget?.total_boards ?? 40;
  const remainingBoards = budget?.remaining_boards ?? 0;
  const remainingZar = budget ? Number(budget.total_budget) - Number(budget.spent_amount) : 0;
  const usedPct = budget ? (budget.used_boards / Math.max(1, totalBoards)) * 100 : 0;
  const exhausted = Boolean(circuitBreaker?.is_exhausted) || (budget !== null && remainingBoards <= 0);
  const apiOnline = health?.status === 'ok';
  const current = NAV.find((n) => n.id === activeTab)!;

  const sidebar = (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-line px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md border border-line-strong bg-surface-3">
          <span className="h-3 w-3 rounded-full border-2 border-accent" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-zinc-50">LottoMind</div>
          <div className="text-2xs text-zinc-500">Lottery analytics</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 p-3" aria-label="Primary">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            id={`nav-${id}`}
            onClick={() => navigate(id)}
            className={`nav-item ${activeTab === id ? 'nav-item-active' : ''}`}
            aria-current={activeTab === id ? 'page' : undefined}
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} />
            {label}
          </button>
        ))}
      </nav>

      {/* Budget summary */}
      <div className="space-y-3 border-t border-line p-4">
        <div className="flex items-center justify-between">
          <span className="eyebrow">Budget · {budget?.year_month ?? '—'}</span>
          <span className={`dot ${exhausted ? 'bg-rose-500' : 'bg-emerald-500'}`} />
        </div>
        <div>
          <div className="num text-sm font-medium text-zinc-100">
            {budget ? formatZAR(remainingZar) : '—'} <span className="text-zinc-500">left</span>
          </div>
          <div className="mt-0.5 text-xs text-zinc-500">
            {budget ? `${remainingBoards} of ${totalBoards} boards remaining` : 'Loading…'}
          </div>
        </div>
        <ProgressBar value={usedPct} tone={exhausted ? 'negative' : usedPct > 75 ? 'warning' : 'default'} />
        <p className="text-2xs leading-relaxed text-zinc-600">
          Decision support only. Boards are entered manually on the official National Lottery platform.
        </p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface-0">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-line bg-surface-1 lg:block">
        {sidebar}
      </aside>

      {/* Mobile sidebar */}
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setNavOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-line bg-surface-1">
            <button
              onClick={() => setNavOpen(false)}
              className="btn btn-ghost btn-sm absolute right-2 top-3"
              aria-label="Close navigation"
            >
              <X className="h-4 w-4" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-line bg-surface-0/85 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNavOpen(true)}
              className="btn btn-ghost btn-sm lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <span className="text-sm text-zinc-500">LottoMind</span>
            <span className="text-zinc-700">/</span>
            <span className="text-sm font-medium text-zinc-200">{current.label}</span>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`badge ${loading ? 'badge-neutral' : apiOnline ? 'badge-success' : 'badge-danger'}`}
              title={health ? `Database: ${health.database}` : 'Backend unreachable'}
            >
              <span
                className={`dot ${loading ? 'bg-zinc-500 animate-pulse' : apiOnline ? 'bg-emerald-400' : 'bg-rose-400'}`}
              />
              {loading ? 'Connecting' : apiOnline ? 'Online' : 'Offline'}
            </span>
            <span
              className={`badge hidden sm:inline-flex ${exhausted ? 'badge-danger' : 'badge-neutral'}`}
              title="Generation is blocked when the monthly board quota reaches zero"
            >
              {exhausted ? 'Budget exhausted' : `${remainingBoards} boards left`}
            </span>
            <button
              onClick={loadSystemState}
              className="btn btn-ghost btn-sm"
              aria-label="Refresh status"
              title="Refresh status"
            >
              <RotateCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
          {!loading && !health && (
            <div className="mb-6 rounded-md border border-amber-500/25 bg-amber-500/[0.06] px-3.5 py-2.5 text-sm text-amber-300">
              The backend could not be reached. Data shown may be incomplete.{' '}
              <button onClick={loadSystemState} className="underline underline-offset-2 hover:text-amber-200">
                Retry
              </button>
            </div>
          )}

          {activeTab === 'overview' && (
            <Overview
              budget={budget}
              circuitBreaker={circuitBreaker}
              loading={loading}
              onNavigate={navigate}
            />
          )}
          {activeTab === 'generate' && (
            <GenerationHub circuitBreaker={circuitBreaker} onBoardGenerated={loadSystemState} />
          )}
          {activeTab === 'results' && <ResultsView />}
          {activeTab === 'stats' && <StatsExplorer />}
        </main>
      </div>
    </div>
  );
}
