import { useEffect, useState } from 'react';

/** SA lottery draws close at ~21:00 SAST (UTC+2) = 19:00 UTC. */
const DRAW_HOUR_UTC = 19;

export function drawTimeFor(dateStr: string): Date {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCHours(DRAW_HOUR_UTC, 0, 0, 0);
  return d;
}

function formatCountdown(ms: number): string {
  const totalMin = Math.floor(ms / 60000);
  const days = Math.floor(totalMin / 1440);
  const hours = Math.floor((totalMin % 1440) / 60);
  const minutes = totalMin % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${Math.max(minutes, 0)}m`;
}

/** Live countdown until the draw on targetDate closes; null when unknown/past. */
export function useDrawCountdown(targetDate?: string | null): string | null {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!targetDate) {
      setLabel(null);
      return;
    }
    const compute = () => {
      const ms = drawTimeFor(targetDate).getTime() - Date.now();
      setLabel(ms > 0 ? formatCountdown(ms) : null);
    };
    compute();
    const timer = window.setInterval(compute, 30_000);
    return () => window.clearInterval(timer);
  }, [targetDate]);

  return label;
}
