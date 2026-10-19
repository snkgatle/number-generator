import React from 'react';
import { MonthlyBudget, CircuitBreakerStatus } from '../services/api';
import { ShieldCheck, ShieldAlert, Zap, TrendingUp, Layers, DollarSign } from 'lucide-react';

interface BudgetTrackerProps {
  budget: MonthlyBudget | null;
  circuitBreaker: CircuitBreakerStatus | null;
  loading: boolean;
  onRefresh?: () => void;
}

export const BudgetTracker: React.FC<BudgetTrackerProps> = ({
  budget,
  circuitBreaker,
  loading,
}) => {
  if (loading && !budget) {
    return (
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse">
        <div className="h-6 w-48 bg-slate-800 rounded mb-4" />
        <div className="h-24 bg-slate-800/60 rounded" />
      </div>
    );
  }

  const totalBoards = budget?.total_boards || 40;
  const usedBoards = budget?.used_boards || 0;
  const remainingBoards = budget?.remaining_boards ?? 40;
  const totalBudget = Number(budget?.total_budget || 200);
  const spentAmount = Number(budget?.spent_amount || 0);
  const remainingBudget = Math.max(0, totalBudget - spentAmount);
  const percentUsed = Math.min(100, Math.round((usedBoards / totalBoards) * 100));

  const isExhausted = circuitBreaker?.is_exhausted || remainingBoards <= 0;

  return (
    <div className="p-6 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/50 border border-slate-800 shadow-xl relative overflow-hidden backdrop-blur-sm">
      {/* Background glow accent */}
      <div
        className={`absolute top-0 right-0 w-80 h-80 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20 ${
          isExhausted ? 'bg-rose-500/10' : 'bg-emerald-500/10'
        }`}
      />

      {/* Header and Circuit Breaker Pill */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              Monthly Budget Engine
            </h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
              {budget?.year_month || 'Current'}
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
              Resets 25th monthly
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Strict R200/month safety circuit breaker & confidence allocation protocol (Payday Cycle: 25th – 24th)
          </p>
        </div>

        {/* Circuit Breaker Status Indicator */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-medium">
          {isExhausted ? (
            <div className="flex items-center gap-2 text-rose-400 bg-rose-500/10 border-rose-500/30 px-3 py-1 rounded-lg">
              <ShieldAlert className="w-4 h-4 animate-bounce text-rose-400" />
              <span className="font-semibold uppercase tracking-wider">Circuit Breaker Tripped</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-emerald-400 bg-emerald-500/10 border-emerald-500/30 px-3 py-1 rounded-lg">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="font-semibold uppercase tracking-wider">Circuit Breaker Active</span>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2 mb-6">
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-400 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-brand-400" />
            Board Allocation Quota
          </span>
          <span className="font-mono font-semibold text-slate-200">
            {usedBoards} / {totalBoards} boards used ({remainingBoards} remaining)
          </span>
        </div>
        <div className="w-full h-3 rounded-full bg-slate-800/80 p-0.5 border border-slate-700/60 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ease-out ${
              isExhausted
                ? 'bg-gradient-to-r from-rose-500 to-red-600'
                : percentUsed > 75
                ? 'bg-gradient-to-r from-amber-500 to-amber-600'
                : 'bg-gradient-to-r from-emerald-500 to-teal-400 shadow-sm shadow-emerald-500/50'
            }`}
            style={{ width: `${percentUsed}%` }}
          />
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <span>Monthly Budget</span>
          </div>
          <div className="text-lg font-bold text-white font-mono">
            R{totalBudget.toFixed(2)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">R5.00 per board</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
            <span>Total Spent</span>
          </div>
          <div className="text-lg font-bold text-white font-mono">
            R{spentAmount.toFixed(2)}
          </div>
          <div className="text-[11px] text-sky-400 mt-0.5">{percentUsed}% utilized</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
            <span>Remaining Funds</span>
          </div>
          <div className="text-lg font-bold text-emerald-400 font-mono">
            R{remainingBudget.toFixed(2)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">{remainingBoards} boards left</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-850/80 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Confidence Rule</span>
          </div>
          <div className="text-sm font-semibold text-slate-200">
            &gt; 85% = +1 Board
          </div>
          <div className="text-[11px] text-amber-400/90 mt-0.5">Dynamic bonus allocation</div>
        </div>
      </div>
    </div>
  );
};
