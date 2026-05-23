'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal, Shield, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { useCyberStore } from '../../store/useCyberStore';

export default function ShellTerminal() {
  const logs = useCyberStore((state) => state.logs);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const getLogIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <AlertTriangle size={12} className="text-rose-500 shrink-0 mt-0.5" />;
      case 'success':
        return <CheckCircle size={12} className="text-cyan-400 shrink-0 mt-0.5" />;
      case 'warning':
        return <AlertTriangle size={12} className="text-yellow-500 shrink-0 mt-0.5" />;
      default:
        return <Info size={12} className="text-purple-500 shrink-0 mt-0.5" />;
    }
  };

  const getAgentColor = (name: string) => {
    switch (name) {
      case "Orchestrator AI": return "text-cyan-400";
      case "Code Analysis Agent": return "text-pink-400";
      case "Security Review Agent": return "text-purple-400";
      case "Threat Intelligence Agent": return "text-yellow-400";
      case "Machine Learning Agent": return "text-green-400";
      default: return "text-indigo-400";
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-black/85 border border-purple-500/20 shadow-[0_0_15px_rgba(138,43,226,0.15)] rounded-lg p-3 font-mono text-xs overflow-hidden">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-purple-500/20 pb-2 mb-3 shrink-0 select-none">
        <div className="flex items-center gap-2 text-purple-400 font-bold uppercase tracking-wider">
          <Terminal size={14} className="animate-pulse" />
          <span>Continuous Threat Stream Logs</span>
        </div>
        <div className="text-[10px] text-purple-500/50 uppercase">STREAM_SOCKET_ACTIVE</div>
      </div>

      {/* Terminal logs list */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-purple-500 select-text">
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 text-[10px] py-10 space-y-2">
            <Shield size={24} className="text-purple-500/20 animate-pulse" />
            <p>Orchestrator socket connection active.</p>
            <p className="text-[9px] text-purple-500/30">Awaiting security scans targets to establish telemetry stream.</p>
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="flex gap-2 items-start py-1 border-b border-white/5 hover:bg-white/5 px-1.5 rounded transition-all">
              {getLogIcon(log.type)}
              <div className="flex-1 overflow-hidden leading-relaxed">
                <span className={`font-bold mr-1.5 shrink-0 ${getAgentColor(log.agent_name)}`}>
                  [{log.agent_name.toUpperCase()}]:
                </span>
                <span className="text-gray-300 font-semibold">{log.message}</span>
              </div>
              <span className="text-[8px] text-purple-500/40 shrink-0 mt-0.5">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
