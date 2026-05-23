'use client';

import React from 'react';

interface SplineTrendChartProps {
  points?: Array<{ label: string; value: number }>;
}

export default function SplineTrendChart({ points = [] }: SplineTrendChartProps) {
  if (points.length < 2) {
    return (
      <div className="flex-1 flex items-center justify-center text-[8px] text-gray-500 uppercase tracking-widest border-t border-white/5">
        No trend data
      </div>
    );
  }

  const maxValue = Math.max(...points.map((p) => p.value), 1);
  const width = 160;
  const height = 50;
  const step = width / Math.max(points.length - 1, 1);
  const path = points
    .map((point, idx) => {
      const x = 10 + idx * step;
      const y = height - 8 - (point.value / maxValue) * 34;
      return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <div className="flex-1 flex flex-col justify-between overflow-hidden">
      <div className="flex-1 flex items-end justify-center relative py-2">
        <svg className="w-full h-full" viewBox="0 0 180 56">
          <path d={path} fill="none" stroke="url(#splineGradient)" strokeWidth="2" />
          <defs>
            <linearGradient id="splineGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#00f3ff" />
              <stop offset="50%" stopColor="#8a2be2" />
              <stop offset="100%" stopColor="#ff007f" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <div className="flex justify-between text-[7px] font-black uppercase text-gray-500 pt-1.5 border-t border-white/5 select-none shrink-0">
        {points.map((point) => (
          <span key={point.label}>{point.label}</span>
        ))}
      </div>
    </div>
  );
}
