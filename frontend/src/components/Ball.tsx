import React from 'react';

interface BallProps {
  number: number;
  variant?: 'standard' | 'bonus' | 'powerball';
  isMatched?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Ball: React.FC<BallProps> = ({
  number,
  variant = 'standard',
  isMatched = false,
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-11 h-11 text-base font-bold',
  }[size];

  // Colors and 3D specular highlight styling
  const variantStyles = {
    standard: isMatched
      ? 'from-emerald-400 via-emerald-500 to-teal-700 text-slate-950 ring-2 ring-emerald-300 shadow-lg shadow-emerald-500/30'
      : 'from-slate-700 via-slate-800 to-slate-900 text-slate-100 border border-slate-700/60 shadow-md',
    bonus: isMatched
      ? 'from-amber-300 via-amber-400 to-yellow-600 text-slate-950 ring-2 ring-amber-300 shadow-lg shadow-amber-500/40'
      : 'from-amber-500 via-amber-600 to-yellow-700 text-slate-950 font-bold border border-amber-400/60 shadow-md shadow-amber-600/20',
    powerball: isMatched
      ? 'from-rose-400 via-rose-500 to-red-700 text-white ring-2 ring-rose-300 shadow-lg shadow-rose-500/40'
      : 'from-rose-500 via-red-600 to-red-800 text-white font-bold border border-rose-400/60 shadow-md shadow-rose-600/20',
  }[variant];

  return (
    <div
      className={`relative inline-flex items-center justify-center rounded-full bg-gradient-to-br select-none transition-transform hover:scale-105 ${sizeClasses} ${variantStyles} ${className}`}
      title={`${variant.toUpperCase()}: ${number}${isMatched ? ' (MATCHED)' : ''}`}
    >
      {/* 3D Specular reflection highlight */}
      <div className="absolute top-1 left-1.5 w-2 h-1.5 bg-white/40 rounded-full blur-[0.5px] pointer-events-none transform -rotate-45" />
      <span className="relative z-10 font-mono tracking-tighter font-extrabold">{number}</span>
    </div>
  );
};
