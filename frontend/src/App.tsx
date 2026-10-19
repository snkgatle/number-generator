import { useState, useEffect } from 'react';
import {
  fetchHealth,
  fetchCurrentBudget,
  fetchCircuitBreaker,
  HealthResponse,
  MonthlyBudget,
  CircuitBreakerStatus,
} from './services/api';
import { BudgetTracker } from './components/BudgetTracker';
import { GenerationHub } from './components/GenerationHub';
import { ResultsView } from './components/ResultsView';
import { StatsExplorer } from './components/StatsExplorer';
import {
  Sparkles,
  LayoutDashboard,
  Cpu,
  Trophy,
  BarChart3,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';

type Tab = 'dashboard' | 'generator' | 'results' | 'stats';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [budget, setBudget] = useState<MonthlyBudget | null>(null);
  const [circuitBreaker, setCircuitBreaker] = useState<CircuitBreakerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadSystemState = async () => {
    try {
      const [hData, bData, cbData] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchCurrentBudget().catch(() => null),
        fetchCircuitBreaker().catch(() => null),
      ]);
      if (hData) setHealth(hData);
      if (bData) setBudget(bData);
      if (cbData) setCircuitBreaker(cbData);
    } catch (err: any) {
      setError(err.message || 'Unable to communicate with LottoMind service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSystemState();
  }, []);

  const isCircuitBreakerTripped = circuitBreaker?.is_exhausted || (budget?.remaining_boards ?? 40) <= 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-brand-500 selection:text-slate-950">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-50 px-4 sm:px-6 py-3.5 shadow-lg shadow-black/40">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Brand Identity */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-500 via-emerald-400 to-teal-300 flex items-center justify-center shadow-lg shadow-brand-500/25 ring-1 ring-white/20">
              <Sparkles className="w-5 h-5 text-slate-950 font-bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-black tracking-tight text-white">LottoMind</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/15 text-brand-400 font-mono font-bold border border-brand-500/30">
                  QWEN-MAX AI
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                South African National Lottery Analytics & Probabilistic Generation
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-slate-850/80 p-1 rounded-xl border border-slate-700/60 backdrop-blur-md">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Dashboard</span>
            </button>

            <button
              onClick={() => setActiveTab('generator')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'generator'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span className="hidden md:inline">AI Generator</span>
            </button>

            <button
              onClick={() => setActiveTab('results')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'results'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Trophy className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Results &amp; History</span>
            </button>

            <button
              onClick={() => setActiveTab('stats')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === 'stats'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Stats Matrix</span>
            </button>
          </nav>

          {/* Health & Circuit Breaker Status Pill */}
          <div className="hidden lg:flex items-center gap-2 font-mono text-xs">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-850 border border-slate-700/60">
              <span
                className={`w-2 h-2 rounded-full ${
                  loading ? 'bg-amber-400 animate-pulse' : health?.status === 'ok' ? 'bg-emerald-400' : 'bg-rose-400'
                }`}
              />
              <span className="text-slate-300">
                {loading ? 'Checking...' : health?.status === 'ok' ? 'API Online' : 'Degraded'}
              </span>
            </div>

            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${
                isCircuitBreakerTripped
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              }`}
              title="Directive 3: Pre-generation circuit breaker check"
            >
              {isCircuitBreakerTripped ? (
                <>
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Quota 0</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>R{budget ? Number(budget.total_budget - budget.spent_amount).toFixed(0) : '200'} Left</span>
                </>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex-1 w-full space-y-6">
        {error && (
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center justify-between">
            <span>Service Note: {error}</span>
            <button onClick={loadSystemState} className="underline text-amber-200 hover:text-white font-mono">Retry</button>
          </div>
        )}

        {/* Always present: Budget Progress & Circuit Breaker Monitor */}
        <BudgetTracker
          budget={budget}
          circuitBreaker={circuitBreaker}
          loading={loading}
          onRefresh={loadSystemState}
        />

        {/* Tab Views */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Quick AI Generator Card */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 font-mono">
                      Probabilistic AI Generator
                    </span>
                    <span className="text-xs text-slate-400 font-mono">DashScope Qwen-Max</span>
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Synthesize Next Draw Boards</h3>
                  <p className="text-xs text-slate-400 leading-relaxed mb-6">
                    Runs mathematical pre-processing (hot/cold numbers, parity ratio, and overdue latencies) before prompting Qwen-Max for constrained lottery boards.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('generator')}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/20 transition-all flex items-center justify-center gap-2"
                >
                  <Cpu className="w-4 h-4" />
                  <span>Open Generation Hub</span>
                </button>
              </div>

              {/* Outcome Comparison Card */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400 font-mono">
                      Draw Evaluations
                    </span>
                    <span className="text-xs text-slate-400 font-mono">Idempotent Sync</span>
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Match Predictions Against Results</h3>
                  <p className="text-xs text-slate-400 leading-relaxed mb-6">
                    Automated Playwright scraper syncs official winning numbers and matches predicted boards, triggering post-draw divergence post-mortems.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('results')}
                  className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 font-semibold text-sm transition-all flex items-center justify-center gap-2"
                >
                  <Trophy className="w-4 h-4 text-amber-400" />
                  <span>View Historical Results</span>
                </button>
              </div>
            </div>

            {/* Live Stats Explorer Preview */}
            <StatsExplorer />
          </div>
        )}

        {activeTab === 'generator' && (
          <GenerationHub
            circuitBreaker={circuitBreaker}
            onBoardGenerated={loadSystemState}
          />
        )}

        {activeTab === 'results' && <ResultsView />}

        {activeTab === 'stats' && <StatsExplorer />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/40 backdrop-blur-md px-6 py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>LottoMind &copy; {new Date().getFullYear()} &bull; Automated South African Lottery Intelligence</span>
          <span className="font-mono text-slate-400">
            Powered by FastAPI &bull; Playwright &bull; Qwen-Max &bull; React &bull; Tailwind
          </span>
        </div>
      </footer>
    </div>
  );
}
