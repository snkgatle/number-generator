import React, { useEffect, useState } from 'react';
import { MonthlyBudget, CircuitBreakerStatus, AllocationPlan, fetchAllocationPlan } from '../services/api';
import { ProgressBar } from './ui';
import { formatZAR } from '../utils/format';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { CalendarClock, Gauge, ShieldAlert, Sparkles, TrendingUp, Wallet } from 'lucide-react';

interface BudgetTrackerProps {
  budget: MonthlyBudget | null;
  circuitBreaker: CircuitBreakerStatus | null;
  loading: boolean;
}

export const BudgetTracker: React.FC<BudgetTrackerProps> = ({ budget, circuitBreaker, loading }) => {
  const [plan, setPlan] = useState<AllocationPlan | null>(null);

  useEffect(() => {
    fetchAllocationPlan()
      .then(setPlan)
      .catch(() => setPlan(null));
  }, [budget?.remaining_boards]);

  if (loading && !budget) {
    return (
      <div className="card card-body space-y-4">
        <div className="skeleton h-4 w-40" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-12" />
          ))}
        </div>
        <div className="skeleton h-1.5 w-full" />
      </div>
    );
  }

  const totalBoards = budget?.total_boards ?? 20;
  const usedBoards = budget?.used_boards ?? 0;
  const remainingBoards = budget?.remaining_boards ?? totalBoards;
  const totalBudget = Number(budget?.total_budget ?? 200);
  const spentAmount = Number(budget?.spent_amount ?? 0);
  const costPerBoard = Number(budget?.cost_per_board ?? 10);
  const remainingBudget = Math.max(0, totalBudget - spentAmount);
  const percentUsed = Math.min(100, (usedBoards / Math.max(1, totalBoards)) * 100);
  const isExhausted = Boolean(circuitBreaker?.is_exhausted) || remainingBoards <= 0;

  const chartData = [
    { name: 'Spent', value: spentAmount, color: '#6366f1' }, // Indigo
    { name: 'Remaining', value: remainingBudget, color: isExhausted ? '#f43f5e' : '#10b981' }, // Emerald or Rose
  ];

  const items = [
    {
      label: 'Monthly budget',
      value: formatZAR(totalBudget),
      hint: `${formatZAR(costPerBoard)} per bundled board`,
      icon: Wallet,
      accent: 'border-l-indigo-500/80',
    },
    {
      label: 'Spent to date',
      value: formatZAR(spentAmount),
      hint: `${percentUsed.toFixed(0)}% of cycle budget`,
      icon: TrendingUp,
      accent: 'border-l-purple-500/80',
    },
    {
      label: 'Remaining funds',
      value: formatZAR(remainingBudget),
      hint: `${remainingBoards} board${remainingBoards === 1 ? '' : 's'} available`,
      tone: isExhausted ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold',
      icon: isExhausted ? ShieldAlert : Sparkles,
      accent: isExhausted ? 'border-l-rose-500' : 'border-l-emerald-500',
    },
    {
      label: 'Boards generated',
      value: `${usedBoards} / ${totalBoards}`,
      hint: 'Cap resets on 25th',
      accent: 'border-l-sky-500/80',
    },
  ];

  return (
    <section className="card overflow-hidden" aria-labelledby="budget-heading">
      <div className="card-header bg-gradient-to-r from-surface-2 via-surface-2 to-surface-3/50">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 shadow-sm shadow-indigo-500/10">
            <Wallet className="h-4 w-4" />
          </div>
          <div>
            <h2 id="budget-heading" className="card-title text-base">
              Monthly budget & board quota
            </h2>
            <p className="card-subtitle">
              Cycle {budget?.year_month ?? '—'} · Active cycle: 25th to 24th
            </p>
          </div>
        </div>

        <span
          className={`badge px-2.5 py-1 text-xs shadow-sm ${
            isExhausted
              ? 'badge-danger bg-rose-500/15 border border-rose-500/30 text-rose-300'
              : 'badge-success bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
          }`}
        >
          <span className={`dot ${isExhausted ? 'bg-rose-400 animate-pulse' : 'bg-emerald-400'}`} />
          {isExhausted ? 'Safety circuit tripped (0 left)' : 'Quota available'}
        </span>
      </div>

      <div className="card-body space-y-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4 items-center">
          {/* Metrics List */}
          <div className="lg:col-span-3 grid grid-cols-2 gap-3 sm:gap-4 sm:grid-cols-4">
            {items.map((it) => (
              <div
                key={it.label}
                className={`inset p-3.5 border-l-2 ${it.accent} bg-gradient-to-b from-surface-1 to-surface-2/70 transition-all hover:bg-surface-3/40`}
              >
                <div className="flex items-center justify-between text-2xs font-medium uppercase tracking-wider text-zinc-400">
                  <span>{it.label}</span>
                </div>
                <dd className={`num mt-1.5 text-lg font-bold ${it.tone ?? 'text-zinc-100'}`}>{it.value}</dd>
                <dd className="mt-0.5 text-xs text-zinc-500">{it.hint}</dd>
              </div>
            ))}
          </div>

          {/* Interactive Donut Gauge */}
          <div className="lg:col-span-1 flex flex-col items-center justify-center p-2 rounded-lg border border-line/80 bg-surface-1/60">
            <div className="relative h-28 w-28">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip
                    formatter={(val: any) => [formatZAR(Number(val)), '']}
                    contentStyle={{
                      backgroundColor: '#131316',
                      borderColor: '#2e2e34',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: '#f4f4f5',
                    }}
                  />
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={36}
                    outerRadius={50}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="#131316"
                    strokeWidth={2}
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              {/* Center Donut Label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                <span className="text-base font-bold font-mono text-zinc-100">{remainingBoards}</span>
                <span className="text-[10px] uppercase font-mono tracking-tighter text-zinc-500">Left</span>
              </div>
            </div>
            <div className="flex items-center gap-3 text-2xs font-mono text-zinc-400 mt-1">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-indigo-500" />
                Spent {percentUsed.toFixed(0)}%
              </span>
              <span className="flex items-center gap-1">
                <span className={`h-2 w-2 rounded-full ${isExhausted ? 'bg-rose-500' : 'bg-emerald-500'}`} />
                Remain
              </span>
            </div>
          </div>
        </div>

        {/* Budget Pacing (Directive 3/23: projected draws vs remaining quota) */}
        {plan && plan.projected_draws_count > 0 && (
          <div className="flex flex-col gap-2 pt-2 border-t border-line/60 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500/10 border border-amber-500/25 text-amber-400">
                <CalendarClock className="h-3.5 w-3.5" />
              </div>
              <span>
                <span className="font-medium text-zinc-300">Budget pacing:</span>{' '}
                <span className="num">{plan.remaining_boards}</span> boards left across{' '}
                <span className="num">{plan.projected_draws_count}</span> scheduled draws —{' '}
                <span
                  className={
                    plan.remaining_boards < plan.projected_draws_count
                      ? 'text-amber-300 font-medium'
                      : 'text-emerald-300 font-medium'
                  }
                >
                  {plan.remaining_boards >= plan.projected_draws_count
                    ? 'surplus available, bonus boards possible at high confidence'
                    : `${Math.max(1, Math.floor(plan.remaining_boards / plan.projected_draws_count))} board per draw to stay in quota`}
                </span>
                .
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-2xs font-mono text-zinc-500">
              <Gauge className="h-3 w-3" />
              <span>Bonus threshold ≥{plan.confidence_threshold.toFixed(0)}% confidence</span>
            </div>
          </div>
        )}

        {/* Linear Progress Indicator */}
        <div className="space-y-2 pt-2 border-t border-line/60">
          <div className="flex justify-between text-xs text-zinc-400">
            <span>Cycle board consumption</span>
            <span className="num font-semibold text-zinc-200">
              {usedBoards} of {totalBoards} boards ({percentUsed.toFixed(0)}%)
            </span>
          </div>
          <ProgressBar
            value={percentUsed}
            tone={isExhausted ? 'negative' : percentUsed > 75 ? 'warning' : 'default'}
          />
        </div>
      </div>
    </section>
  );
};
