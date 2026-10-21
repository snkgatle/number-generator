import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, Check, Copy, Info } from 'lucide-react';

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
