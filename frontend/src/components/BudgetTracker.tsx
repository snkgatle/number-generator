import React from 'react';
import { MonthlyBudget, CircuitBreakerStatus } from '../services/api';
import { ProgressBar } from './ui';
import { formatZAR } from '../utils/format';

interface BudgetTrackerProps {
  budget: MonthlyBudget | null;
  circuitBreaker: CircuitBreakerStatus | null;
  loading: boolean;
}

export const BudgetTracker: React.FC<BudgetTrackerProps> = ({ budget, circuitBreaker, loading }) => {
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

  const totalBoards = budget?.total_boards ?? 40;
  const usedBoards = budget?.used_boards ?? 0;
  const remainingBoards = budget?.remaining_boards ?? totalBoards;
  const totalBudget = Number(budget?.total_budget ?? 200);
  const spentAmount = Number(budget?.spent_amount ?? 0);
  const costPerBoard = Number(budget?.cost_per_board ?? 5);
  const remainingBudget = Math.max(0, totalBudget - spentAmount);
  const percentUsed = Math.min(100, (usedBoards / Math.max(1, totalBoards)) * 100);
  const isExhausted = Boolean(circuitBreaker?.is_exhausted) || remainingBoards <= 0;

  const items = [
    { label: 'Monthly budget', value: formatZAR(totalBudget), hint: `${formatZAR(costPerBoard)} per board` },
    { label: 'Spent', value: formatZAR(spentAmount), hint: `${percentUsed.toFixed(0)}% of budget` },
    {
      label: 'Remaining',
      value: formatZAR(remainingBudget),
      hint: `${remainingBoards} boards`,
      tone: isExhausted ? 'text-rose-400' : 'text-zinc-50',
    },
    { label: 'Boards used', value: `${usedBoards} / ${totalBoards}`, hint: 'Bonus board above 85% confidence' },
  ];

  return (
    <section className="card" aria-labelledby="budget-heading">
      <div className="card-header">
        <div>
          <h2 id="budget-heading" className="card-title">
            Monthly budget
          </h2>
          <p className="card-subtitle">
            Cycle {budget?.year_month ?? '—'} · runs from the 25th to the 24th
          </p>
        </div>
        <span className={`badge ${isExhausted ? 'badge-danger' : 'badge-success'}`}>
          <span className={`dot ${isExhausted ? 'bg-rose-400' : 'bg-emerald-400'}`} />
          {isExhausted ? 'Generation paused' : 'Generation allowed'}
        </span>
      </div>

      <div className="card-body space-y-5">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-4">
          {items.map((it) => (
            <div key={it.label}>
              <dt className="eyebrow">{it.label}</dt>
              <dd className={`num mt-1.5 text-lg font-semibold ${it.tone ?? 'text-zinc-50'}`}>{it.value}</dd>
              <dd className="mt-0.5 text-xs text-zinc-500">{it.hint}</dd>
            </div>
          ))}
        </dl>

        <div className="space-y-2">
          <div className="flex justify-between text-xs text-zinc-500">
            <span>Quota used</span>
            <span className="num">{percentUsed.toFixed(0)}%</span>
          </div>
          <ProgressBar value={percentUsed} tone={isExhausted ? 'negative' : percentUsed > 75 ? 'warning' : 'default'} />
        </div>
      </div>
    </section>
  );
};
