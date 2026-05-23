'use client';

import React from 'react';
import { Cpu, Server, Activity, ShieldCheck } from 'lucide-react';
import { useCyberStore } from '../store/useCyberStore';

export function TopHudPanel() {
  const phase = useCyberStore((state) => state.phase);
  const progress = useCyberStore((state) => state.progress);
  const activeScan = useCyberStore((state) => state.activeScan);
  const telemetry = useCyberStore((state) => state.telemetry);

  return (
    <div className="w-full grid grid-cols-4 gap-3 font-mono text-xs select-none">
      {/* Platform Title */}
      <div className="cyber-panel-cyan bg-black/85 p-3 rounded-lg flex items-center justify-between border-l-4 border-l-cyan-500">
        <div>
          <h1 className="text-sm font-black tracking-widest text-cyan-400 glow-text-cyan uppercase">
            CyberVerse AI
          </h1>
          <p className="text-[9px] text-cyan-500/50 uppercase mt-0.5 font-bold">
            Autonomous Security Research Platform
          </p>
        </div>
        <Cpu size={18} className="text-cyan-400 animate-pulse shrink-0" />
      </div>

      {/* Target Status */}
      <div className="cyber-panel-cyan bg-black/85 p-3 rounded-lg flex items-center justify-between">
        <div>
          <span className="text-[9px] text-cyan-500/50 uppercase font-bold">Target Module</span>
          <p className="text-gray-200 truncate max-w-[150px] font-semibold mt-0.5">
            {activeScan ? activeScan.target_value : 'No scan active'}
          </p>
        </div>
        <Server size={16} className="text-teal-400 shrink-0" />
      </div>

      {/* Active Scanner Phase progress */}
      <div className="cyber-panel-cyan bg-black/85 p-3 rounded-lg flex flex-col justify-center">
        <div className="flex justify-between items-center mb-1">
          <span className="text-[9px] text-cyan-500/50 uppercase font-bold">Scanner Pipeline</span>
          <span className="text-[10px] text-cyan-400 font-bold uppercase">{phase}</span>
        </div>
        <div className="w-full h-1.5 bg-black/60 rounded overflow-hidden border border-cyan-500/10">
          <div 
            className="h-full bg-cyan-400 transition-all duration-500 shadow-[0_0_8px_#22d3ee]"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      {/* Aggregate Statistics */}
      <div className="cyber-panel-cyan bg-black/85 p-3 rounded-lg flex items-center justify-between">
        <div>
          <span className="text-[9px] text-cyan-500/50 uppercase font-bold">Aggregate Systems Health</span>
          <p className="text-gray-200 mt-0.5 font-semibold">
            {telemetry ? `${telemetry.stats.scans} scans run` : 'Ready'}
          </p>
        </div>
        <Activity size={16} className="text-emerald-400 shrink-0 animate-pulse" />
      </div>
    </div>
  );
}

export function AgentTelemetryGrid() {
  const agents = useCyberStore((state) => state.agents);
  const phase = useCyberStore((state) => state.phase);

  const getAgentColor = (name: string) => {
    switch (name) {
      case "Orchestrator AI": return "border-cyan-500/30 text-cyan-400";
      case "Code Analysis Agent": return "border-pink-500/30 text-pink-400";
      case "Security Review Agent": return "border-purple-500/30 text-purple-400";
      case "Threat Intelligence Agent": return "border-yellow-500/30 text-yellow-400";
      case "Machine Learning Agent": return "border-green-500/30 text-green-400";
      case "Report Agent": return "border-indigo-500/30 text-indigo-400";
      default: return "border-gray-500/30 text-gray-400";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PROCESSING': return 'text-amber-400 font-semibold animate-pulse';
      case 'COMPLETED': return 'text-emerald-400 font-bold';
      default: return 'text-gray-500';
    }
  };

  return (
    <div className="w-full h-full flex flex-col font-mono text-xs cyber-panel-purple bg-black/75 rounded-lg p-3 overflow-hidden">
      <div className="flex items-center justify-between border-b border-purple-500/20 pb-2 mb-3 shrink-0">
        <div className="flex items-center gap-2 text-purple-400 font-semibold uppercase tracking-wider">
          <Server size={14} className="animate-pulse" />
          <span>Active Agent Command Center</span>
        </div>
        <div className="text-[10px] text-purple-500/50 uppercase">TELEMETRY_DYNAMICS</div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 scrollbar-thin">
        {Object.entries(agents).map(([name, state]) => (
          <div 
            key={name}
            className={`p-2.5 bg-black/55 border rounded flex flex-col space-y-1.5 transition-all duration-300 ${getAgentColor(name)}`}
          >
            <div className="flex justify-between items-center select-none">
              <span className="font-bold tracking-wide">{name.toUpperCase()}</span>
              <span className={`text-[9px] uppercase ${getStatusColor(state.status)}`}>
                {state.status}
              </span>
            </div>
            
            <div className="text-[10px] text-gray-400 leading-relaxed font-semibold italic truncate">
              &gt; {state.lastInstruction}
            </div>

            {state.status === 'PROCESSING' && (
              <div className="w-full h-1 bg-black/60 rounded overflow-hidden">
                <div 
                  className="h-full bg-current transition-all duration-300 animate-pulse"
                  style={{ width: `${state.load}%` }}
                ></div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
