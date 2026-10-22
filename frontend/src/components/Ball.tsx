import React from 'react';

interface BallProps {
  number: number;
  variant?: 'standard' | 'bonus' | 'powerball';
  isMatched?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  colorCoded?: boolean;
}

/**
 * Returns a distinctive lottery ball gradient based on number ranges (1-9, 10-19, 20-29, 30-39, 40+).
 */
function getBallTone(number: number): string {
  if (number <= 9) {
    // 1-9: Golden Honey
    return 'bg-gradient-to-br from-amber-300 via-amber-400 to-amber-600 text-amber-950 font-bold ring-amber-300/70 shadow-sm shadow-amber-500/25';
  } else if (number <= 19) {
    // 10-19: Vivid Ocean Blue
    return 'bg-gradient-to-br from-sky-300 via-blue-500 to-indigo-700 text-white font-bold ring-sky-300/60 shadow-sm shadow-blue-500/25';
  } else if (number <= 29) {
    // 20-29: Emerald Green
    return 'bg-gradient-to-br from-emerald-300 via-emerald-500 to-teal-700 text-emerald-950 font-bold ring-emerald-300/70 shadow-sm shadow-emerald-500/25';
  } else if (number <= 39) {
    // 30-39: Royal Purple / Violet
    return 'bg-gradient-to-br from-purple-300 via-violet-600 to-indigo-800 text-white font-bold ring-purple-300/60 shadow-sm shadow-purple-500/25';
  } else {
    // 40+: Sunset Coral / Ruby
    return 'bg-gradient-to-br from-rose-300 via-rose-500 to-red-700 text-white font-bold ring-rose-300/70 shadow-sm shadow-rose-500/25';
  }
}

/**
 * Vibrant lottery number token with 3D specular sheen and crisp contrast.
 */
export const Ball: React.FC<BallProps> = ({
  number,
  variant = 'standard',
  isMatched = false,
  size = 'md',
  className = '',
  colorCoded = true,
}) => {
  const sizeClasses = {
    sm: 'h-7 w-7 text-xs',
    md: 'h-8 w-8 text-[13px]',
    lg: 'h-10 w-10 text-sm font-bold',
  }[size];

  let tone: string;
  if (isMatched) {
    tone =
      'bg-gradient-to-br from-emerald-300 via-emerald-400 to-teal-600 text-emerald-950 font-black ring-2 ring-emerald-300 ring-offset-1 ring-offset-zinc-950 shadow-md shadow-emerald-500/50 scale-105';
  } else if (variant === 'powerball') {
    tone =
      'bg-gradient-to-br from-red-400 via-rose-600 to-red-800 text-white font-black ring-2 ring-rose-400/80 shadow-md shadow-rose-600/40';
  } else if (variant === 'bonus') {
    tone =
      'bg-gradient-to-br from-amber-200 via-amber-400 to-yellow-600 text-amber-950 font-black ring-2 ring-amber-300/90 shadow-md shadow-amber-500/40';
  } else if (colorCoded) {
    tone = getBallTone(number);
  } else {
    tone = 'bg-surface-3 text-zinc-100 ring-line-strong';
  }

  const label = variant === 'powerball' ? 'PowerBall' : variant === 'bonus' ? 'Bonus ball' : 'Number';

  return (
    <span
      className={`num relative inline-flex select-none items-center justify-center rounded-full ring-1 ring-inset transition-transform duration-150 hover:scale-110 overflow-hidden ${sizeClasses} ${tone} ${className}`}
      title={`${label} ${number}${isMatched ? ' — matched!' : ''}`}
    >
      {/* Specular 3D highlight */}
      <span
        aria-hidden
        className="pointer-events-none absolute -top-0.5 left-1.5 h-2 w-3 rounded-full bg-white/40 blur-[0.6px]"
      />
      <span className="relative z-10">{number}</span>
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
  colorCoded?: boolean;
}> = ({ numbers, extra, powerBall = false, matched, extraMatched = false, size = 'md', colorCoded = true }) => (
  <div className="flex flex-wrap items-center gap-1.5">
    {numbers.map((n) => (
      <Ball key={n} number={n} size={size} isMatched={matched?.has(n)} colorCoded={colorCoded} />
    ))}
    {extra !== null && extra !== undefined && (
      <>
        <span className="mx-1 h-5 w-px bg-line-strong" aria-hidden />
        <Ball
          number={extra}
          size={size}
          variant={powerBall ? 'powerball' : 'bonus'}
          isMatched={extraMatched}
          colorCoded={colorCoded}
        />
      </>
    )}
  </div>
);
