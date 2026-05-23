'use client';

import React from 'react';
import { Compass, ShieldAlert, Zap } from 'lucide-react';
import { useCyberStore } from '../store/useCyberStore';

export default function ThreatMap() {
  const telemetry = useCyberStore((state) => state.telemetry);
  const activeScan = useCyberStore((state) => state.activeScan);
  const findings = useCyberStore((state) => state.findings);

  // Fallbacks if no data
  const critical = activeScan ? activeScan.critical_count : (telemetry?.vulnerability_counts.Critical || 0);
  const high = activeScan ? activeScan.high_count : (telemetry?.vulnerability_counts.High || 0);
  const medium = activeScan ? activeScan.medium_count : (telemetry?.vulnerability_counts.Medium || 0);
  const low = activeScan ? activeScan.low_count : (telemetry?.vulnerability_counts.Low || 0);
  
  const total = critical + high + medium + low;

  return (
    <div className="w-full h-full flex flex-col cyber-panel-pink bg-black/75 rounded-lg overflow-hidden p-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-pink-500/20 pb-2 mb-3">
        <div className="flex items-center gap-2 text-pink-400 font-semibold uppercase tracking-wider">
          <Compass size={14} className="animate-spin-slow" />
          <span>Vulnerability Hot-Zones & Vectors</span>
        </div>
        <div className="text-[10px] text-pink-500/50">SECTOR_THREAT_MAP</div>
      </div>

      <div className="grid grid-cols-2 gap-3 flex-1">
        {/* Severity Metrics Bar charts */}
        <div className="flex flex-col justify-center space-y-2.5">
          <div>
            <div className="flex justify-between text-[10px] text-red-500 font-bold mb-1">
              <span>CRITICAL VECTORS</span>
              <span>{critical}</span>
            </div>
            <div className="w-full h-2.5 bg-black/60 rounded border border-red-500/20 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-red-600 to-rose-400 shadow-[0_0_10px_#ef4444] transition-all duration-1000"
                style={{ width: `${total ? (critical / total) * 100 : 0}%` }}
              ></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-orange-500 font-bold mb-1">
              <span>HIGH IMPACT</span>
              <span>{high}</span>
            </div>
            <div className="w-full h-2.5 bg-black/60 rounded border border-orange-500/20 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-orange-600 to-amber-400 shadow-[0_0_10px_#f97316] transition-all duration-1000"
                style={{ width: `${total ? (high / total) * 100 : 0}%` }}
              ></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-yellow-500 font-bold mb-1">
              <span>MEDIUM RISK</span>
              <span>{medium}</span>
            </div>
            <div className="w-full h-2.5 bg-black/60 rounded border border-yellow-500/20 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-yellow-600 to-yellow-300 shadow-[0_0_10px_#eab308] transition-all duration-1000"
                style={{ width: `${total ? (medium / total) * 100 : 0}%` }}
              ></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-[10px] text-cyan-400 font-bold mb-1">
              <span>LOW DEFECT</span>
              <span>{low}</span>
            </div>
            <div className="w-full h-2.5 bg-black/60 rounded border border-cyan-500/20 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 shadow-[0_0_10px_#06b6d4] transition-all duration-1000"
                style={{ width: `${total ? (low / total) * 100 : 0}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Vector SVG threat hotzone grid */}
        <div className="relative border border-pink-500/10 bg-black/40 rounded flex items-center justify-center overflow-hidden">
          {/* Cyber Scope HUD SVG */}
          <svg className="absolute w-full h-full p-2 pointer-events-none opacity-45" viewBox="0 0 100 100">
            {/* HUD Grids */}
            <circle cx="50" cy="50" r="45" fill="none" stroke="#ff007f" strokeWidth="0.25" strokeDasharray="2" />
            <circle cx="50" cy="50" r="30" fill="none" stroke="#ff007f" strokeWidth="0.15" />
            <circle cx="50" cy="50" r="15" fill="none" stroke="#ff007f" strokeWidth="0.2" strokeDasharray="1" />
            <line x1="50" y1="5" x2="50" y2="95" stroke="#ff007f" strokeWidth="0.15" strokeDasharray="1" />
            <line x1="5" y1="50" x2="95" y2="50" stroke="#ff007f" strokeWidth="0.15" strokeDasharray="1" />
            
            {/* Blinking threat markers */}
            {critical > 0 && (
              <circle cx="35" cy="40" r="3.5" fill="#f43f5e" className="animate-ping" style={{ transformOrigin: '35px 40px' }} />
            )}
            {high > 0 && (
              <circle cx="65" cy="60" r="2.5" fill="#fb923c" className="animate-pulse" />
            )}
            {medium > 0 && (
              <circle cx="50" cy="25" r="2" fill="#fbbf24" />
            )}
            {low > 0 && (
              <circle cx="28" cy="70" r="1.5" fill="#22d3ee" />
            )}
          </svg>

          {/* HUD Overlay Stats inside scope */}
          <div className="z-10 text-center select-none">
            <div className="flex items-center justify-center gap-1.5 text-pink-400 font-bold mb-0.5">
              <ShieldAlert size={14} className="animate-pulse" />
              <span className="text-sm">{activeScan ? `${activeScan.risk_score}` : `${telemetry?.stats.avg_risk || 0}`}</span>
            </div>
            <div className="text-[9px] text-pink-500/60 font-semibold tracking-wider">AGGREGATE RISK PROFILE</div>
          </div>
        </div>
      </div>
    </div>
  );
}
