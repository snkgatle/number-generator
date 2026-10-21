import React from 'react';

interface BallProps {
  number: number;
  variant?: 'standard' | 'bonus' | 'powerball';
  isMatched?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * Flat lottery number token. Colour is reserved for meaning:
 * neutral by default, amber for bonus, rose for PowerBall, emerald when matched.
 */
export const Ball: React.FC<BallProps> = ({
  number,
  variant = 'standard',
  isMatched = false,
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'h-7 w-7 text-xs',
    md: 'h-8 w-8 text-[13px]',
    lg: 'h-10 w-10 text-sm',
  }[size];

  let tone: string;
  if (isMatched) {
    tone = 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/50';
  } else if (variant === 'powerball') {
    tone = 'bg-rose-500/10 text-rose-300 ring-rose-500/35';
  } else if (variant === 'bonus') {
    tone = 'bg-amber-500/10 text-amber-300 ring-amber-500/35';
  } else {
    tone = 'bg-surface-3 text-zinc-200 ring-line-strong';
  }

  const label = variant === 'powerball' ? 'PowerBall' : variant === 'bonus' ? 'Bonus ball' : 'Number';

  return (
    <span
      className={`num inline-flex select-none items-center justify-center rounded-full font-medium ring-1 ring-inset ${sizeClasses} ${tone} ${className}`}
      title={`${label} ${number}${isMatched ? ' — matched' : ''}`}
    >
      {number}
    </span>
  );
};

/** Renders a full board (main numbers + optional bonus / PowerBall) in one row. */
export const BallRow: React.FC<{
  numbers: number[];
  extra?: number | null;
  powerBall?: boolean;
  matched?: Set<number>;
  extraMatched?: boolean;
  size?: 'sm' | 'md' | 'lg';
}> = ({ numbers, extra, powerBall = false, matched, extraMatched = false, size = 'md' }) => (
  <div className="flex flex-wrap items-center gap-1.5">
    {numbers.map((n) => (
      <Ball key={n} number={n} size={size} isMatched={matched?.has(n)} />
    ))}
    {extra !== null && extra !== undefined && (
      <>
        <span className="mx-1 h-5 w-px bg-line-strong" aria-hidden />
        <Ball number={extra} size={size} variant={powerBall ? 'powerball' : 'bonus'} isMatched={extraMatched} />
      </>
    )}
  </div>
);
