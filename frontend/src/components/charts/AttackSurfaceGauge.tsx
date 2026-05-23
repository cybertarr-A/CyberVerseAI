'use client';

import React from 'react';

interface AttackSurfaceGaugeProps {
  totalEndpoints?: number;
  stats?: Array<{ name: string; value: number; color: string }>;
}

export default function AttackSurfaceGauge({
  totalEndpoints = 0,
  stats = [
    { name: 'Critical', value: 0, color: '#ff007f' },
    { name: 'High', value: 0, color: '#ea580c' },
    { name: 'Medium', value: 0, color: '#eab308' },
    { name: 'Low', value: 0, color: '#00f3ff' }
  ]
}: AttackSurfaceGaugeProps) {
  const safeTotal = Math.max(0, totalEndpoints);
  let offset = 0;
  const segments = stats.map((s) => {
    const pct = safeTotal > 0 ? (s.value / safeTotal) * 100 : 0;
    const segment = { ...s, pct, offset };
    offset -= pct;
    return segment;
  });

  return (
    <div className="flex items-center justify-between flex-1">
      {/* Visual SVG Donut */}
      <div className="w-[66px] h-[66px] shrink-0 relative flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#1a233a" strokeWidth="2.5" />
          {segments.map((segment) => (
            <circle
              key={segment.name}
              cx="18"
              cy="18"
              r="15.91"
              fill="transparent"
              stroke={segment.color}
              strokeWidth="2.5"
              strokeDasharray={`${segment.pct}, 100`}
              strokeDashoffset={segment.offset}
            />
          ))}
        </svg>
        <div className="absolute text-center select-none">
          <span className="text-xs font-black text-gray-100 leading-none">{safeTotal}</span>
          <span className="text-[5.5px] text-gray-500 uppercase font-black tracking-tighter block mt-0.5">Findings</span>
        </div>
      </div>

      {/* Legend Block */}
      <div className="ml-3 flex-1 space-y-0.5 text-[8px] text-[#8b9bb4]">
        {stats.map((s, i) => (
          <div key={i} className="flex justify-between items-center hover:bg-white/5 px-1 rounded transition-colors py-0.5">
            <span className="flex items-center">
              <span className="w-1.5 h-1.5 rounded-full mr-1.5 shrink-0" style={{ backgroundColor: s.color }}></span>
              {s.name}
            </span>
            <span className="font-bold text-gray-200">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
