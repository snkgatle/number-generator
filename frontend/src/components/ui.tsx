import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, Check, Copy, Info, ChevronDown } from 'lucide-react';

/* ─── Tier reference popover (Directive 14) ──────────────────────── */

export interface PrizeTierRow {
  division: string;
  match_main: number;
  match_bonus: boolean;
  payout: number;
}

interface TooltipProps {
  tiers: PrizeTierRow[];
  selectedDivision?: string;
  gameType: string;
}

export const TierReference: React.FC<TooltipProps> = ({ tiers, selectedDivision, gameType }) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="inline-flex items-center gap-0.5 text-xs font-mono cursor-help text-zinc-400 hover:text-accent transition-colors"
        aria-label="Show prize tier reference"
      >
        <span className="text-2xs">{selectedDivision ?? 'Tiers'}</span>
        <ChevronDown className={`h-2.5 w-2.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          {/* Overlay to close on click outside */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute left-0 top-full z-50 mt-1 min-w-[280px] rounded-md border border-line bg-surface-1 p-2 shadow-xl animate-slide-in-right pointer-events-auto">
            <div className="mb-1 flex items-center justify-between text-2xs uppercase tracking-wider text-zinc-500">
              <span>Prize tiers · {gameType}</span>
              <button onClick={() => setOpen(false)} className="hover:text-zinc-300" title="Close">×</button>
            </div>
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-zinc-500">
                  <th className="text-left py-1 pr-2">Division</th>
                  <th className="text-left py-1 px-1">Match</th>
                  <th className="text-right py-1 pl-2">Payout</th>
                </tr>
              </thead>
              <tbody>
                {tiers.map((t, i) => (
                  <tr
                    key={i}
                    className={`${
                      t.division === selectedDivision
                        ? 'bg-indigo-500/10 text-accent'
                        : 'text-zinc-300'
                    }`}
                  >
                    <td className="py-0.5 pr-2 whitespace-nowrap truncate max-w-[120px]">{t.division}</td>
                    <td className="px-1 whitespace-nowrap text-zinc-400">
                      {t.match_main} main{t.match_bonus ? ' + bonus/PB' : ''}
                    </td>
                    <td className="text-right pl-2 tabular-nums text-emerald-300">
                      R{t.payout.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Page header                                                                 */
/* -------------------------------------------------------------------------- */

export const PageHeader: React.FC<{
  title: string;
  description?: string;
  actions?: React.ReactNode;
}> = ({ title, description, actions }) => (
  <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-subtitle">{description}</p>}
    </div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>
);

/* -------------------------------------------------------------------------- */
/* Stat card                                                                   */
/* -------------------------------------------------------------------------- */

type Tone = 'default' | 'positive' | 'negative' | 'warning';

const toneText: Record<Tone, string> = {
  default: 'text-zinc-50',
  positive: 'text-emerald-400',
  negative: 'text-rose-400',
  warning: 'text-amber-400',
};

export const StatCard: React.FC<{
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: Tone;
  icon?: React.ElementType;
}> = ({ label, value, hint, tone = 'default', icon: Icon }) => (
  <div className="card card-body">
    <div className="flex items-center justify-between">
      <span className="eyebrow">{label}</span>
      {Icon && <Icon className="h-4 w-4 text-zinc-600" strokeWidth={1.75} />}
    </div>
    <div className={`num mt-2 text-2xl font-semibold tracking-tight ${toneText[tone]}`}>{value}</div>
    {hint && <div className="mt-1 text-xs text-zinc-500">{hint}</div>}
  </div>
);

/* -------------------------------------------------------------------------- */
/* Alert                                                                       */
/* -------------------------------------------------------------------------- */

const alertStyles = {
  error: { cls: 'border-rose-500/25 bg-rose-500/[0.06] text-rose-300', Icon: AlertCircle },
  success: { cls: 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-300', Icon: CheckCircle2 },
  warning: { cls: 'border-amber-500/25 bg-amber-500/[0.06] text-amber-300', Icon: AlertCircle },
  info: { cls: 'border-line-strong bg-surface-1 text-zinc-300', Icon: Info },
} as const;

export const Alert: React.FC<{
  variant?: keyof typeof alertStyles;
  children: React.ReactNode;
  action?: React.ReactNode;
}> = ({ variant = 'info', children, action }) => {
  const { cls, Icon } = alertStyles[variant];
  return (
    <div className={`flex items-start gap-2.5 rounded-md border px-3.5 py-2.5 text-sm ${cls}`} role="status">
      <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.75} />
      <div className="flex-1">{children}</div>
      {action}
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Empty state                                                                 */
/* -------------------------------------------------------------------------- */

export const EmptyState: React.FC<{
  icon: React.ElementType;
  title: string;
  description?: string;
  action?: React.ReactNode;
}> = ({ icon: Icon, title, description, action }) => (
  <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface-1">
      <Icon className="h-5 w-5 text-zinc-500" strokeWidth={1.75} />
    </div>
    <p className="text-sm font-medium text-zinc-200">{title}</p>
    {description && <p className="mt-1 max-w-sm text-sm text-zinc-500">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

/* -------------------------------------------------------------------------- */
/* Segmented control                                                           */
/* -------------------------------------------------------------------------- */

export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: { value: T; label: React.ReactNode; disabled?: boolean }[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="segmented" role="tablist" aria-label={ariaLabel}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="tab"
          aria-selected={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={`segmented-item ${value === o.value ? 'segmented-item-active' : ''}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Copy button                                                                 */
/* -------------------------------------------------------------------------- */

export const CopyButton: React.FC<{ text: string; label?: string; id?: string }> = ({
  text,
  label = 'Copy',
  id,
}) => {
  const [copied, setCopied] = useState(false);
  const handle = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable (e.g. insecure context) — no-op */
    }
  };
  return (
    <button id={id} type="button" onClick={handle} className="btn btn-ghost btn-sm" title="Copy numbers for manual entry">
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      <span className={copied ? 'text-emerald-400' : ''}>{copied ? 'Copied' : label}</span>
    </button>
  );
};

/* -------------------------------------------------------------------------- */
/* Progress bar                                                                */
/* -------------------------------------------------------------------------- */

export const ProgressBar: React.FC<{ value: number; tone?: Tone }> = ({ value, tone = 'default' }) => {
  const bar =
    tone === 'negative' ? 'bg-rose-500' : tone === 'warning' ? 'bg-amber-500' : 'bg-accent';
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${bar}`}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
};
