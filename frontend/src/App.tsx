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

  const totalBoards = budget?.total_boards ?? 20;
  const remainingBoards = budget?.remaining_boards ?? 0;
  const remainingZar = budget ? Number(budget.total_budget) - Number(budget.spent_amount) : 0;
  const exhausted = Boolean(circuitBreaker?.is_exhausted) || (budget !== null && remainingBoards <= 0);
  const apiOnline = health?.status === 'ok';

  return (
    <div className="min-h-screen flex flex-col bg-surface-0 text-zinc-100">
      {/* Ambient top glowing edge */}
      <div className="h-[2px] w-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />

      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-30 border-b border-line bg-surface-0/95 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          {/* Brand & Desktop Navigation */}
          <div className="flex items-center gap-6 lg:gap-8">
            <button
              onClick={() => navigate('overview')}
              className="flex items-center gap-2.5 text-left transition-opacity hover:opacity-90"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-[1.5px] shadow-md shadow-indigo-500/20">
                <div className="flex h-full w-full items-center justify-center rounded-[6.5px] bg-surface-0">
                  <Sparkles className="h-4 w-4 text-indigo-400" />
                </div>
              </div>
              <div className="leading-tight">
                <div className="text-sm font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-zinc-50 via-zinc-100 to-zinc-400">
                  LottoMind
                </div>
                <div className="text-2xs font-mono text-zinc-500">Lottery Analytics</div>
              </div>
            </button>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1 rounded-lg border border-line/80 bg-surface-1/80 p-1" aria-label="Primary Navigation">
              {NAV.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  id={`nav-${id}`}
                  onClick={() => navigate(id)}
                  className={`inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-medium transition-all ${
                    activeTab === id
                      ? 'bg-gradient-to-r from-indigo-500/15 to-purple-500/15 border border-indigo-500/30 text-indigo-200 shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-100 hover:bg-surface-2/60'
                  }`}
                  aria-current={activeTab === id ? 'page' : undefined}
                >
                  <Icon className={`h-3.5 w-3.5 ${activeTab === id ? 'text-indigo-400' : ''}`} strokeWidth={1.8} />
                  <span>{label}</span>
                </button>
              ))}
            </nav>
          </div>

          {/* Right Status Indicators & Controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* System Online Badge */}
            <span
              className={`badge ${loading ? 'badge-neutral' : apiOnline ? 'badge-success' : 'badge-danger'}`}
              title={health ? `Database: ${health.database}` : 'Backend unreachable'}
            >
              <span
                className={`dot ${loading ? 'bg-zinc-500 animate-pulse' : apiOnline ? 'bg-emerald-400' : 'bg-rose-400'}`}
              />
              <span className="font-mono">{loading ? 'Connecting' : apiOnline ? 'API Online' : 'Offline'}</span>
            </span>

            {/* Budget Quota Badge */}
            <span
              className={`badge hidden sm:inline-flex ${exhausted ? 'badge-danger' : 'badge-neutral'}`}
              title="Directive 3: Pre-generation circuit breaker limit"
            >
              <span className="font-mono">
                {exhausted ? 'Quota 0 (Exhausted)' : `${remainingBoards} of ${totalBoards} boards left`}
              </span>
            </span>

            {/* Refresh Button */}
            <button
              onClick={loadSystemState}
              className="btn btn-ghost btn-sm"
              aria-label="Refresh status"
              title="Refresh system status"
            >
              <RotateCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>

            {/* Mobile Navigation Toggle */}
            <button
              onClick={() => setNavOpen(!navOpen)}
              className="btn btn-ghost btn-sm md:hidden"
              aria-label="Toggle navigation"
            >
              {navOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {navOpen && (
          <div className="border-t border-line bg-surface-1 px-4 py-3 md:hidden">
            <nav className="flex flex-col gap-1">
              {NAV.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => navigate(id)}
                  className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                    activeTab === id
                      ? 'bg-surface-3 text-zinc-50 shadow-[inset_0_0_0_1px_theme(colors.line.strong)]'
                      : 'text-zinc-400 hover:bg-surface-2 hover:text-zinc-100'
                  }`}
                >
                  <Icon className="h-4 w-4" strokeWidth={1.8} />
                  <span>{label}</span>
                </button>
              ))}
            </nav>
            <div className="mt-3 pt-3 border-t border-line/60 flex items-center justify-between text-2xs text-zinc-400 font-mono">
              <span>Quota: {remainingBoards}/{totalBoards} boards</span>
              <span>{budget ? formatZAR(remainingZar) : '—'} left</span>
            </div>
          </div>
        )}
      </header>

      {/* Main Content View */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
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

      {/* Footer */}
      <footer className="mt-auto border-t border-line bg-surface-1/40 px-4 py-4 text-center text-xs text-zinc-500">
        <div className="mx-auto flex max-w-7xl flex-col sm:flex-row items-center justify-between gap-2">
          <span>LottoMind &copy; {new Date().getFullYear()} &bull; Automated Lottery Intelligence &bull; Decision Support Only</span>
          <span className="font-mono text-zinc-500 text-2xs">
            FastAPI &bull; Qwen-Max &bull; React &bull; TailwindCSS
          </span>
        </div>
      </footer>
    </div>
  );
}
