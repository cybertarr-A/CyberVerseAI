'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { 
  Terminal, 
  Settings, 
  Search, 
  Play, 
  Skull, 
  ChevronRight,
  Grid
} from 'lucide-react';
import { useCyberStore } from '../store/useCyberStore';

// Dynamic import for R3F 3D CyberScene to prevent SSR compilation bottlenecks
const ThreatGalaxyScene = dynamic(() => import('../scenes/ThreatGalaxy/ThreatGalaxyScene'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-[#050814] flex items-center justify-center font-mono text-cyan-400 text-xs select-none">
      <div className="text-center space-y-2">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <p className="animate-pulse tracking-widest uppercase">LOADING IMMERSIVE 3D HOLOSPHERES...</p>
      </div>
    </div>
  )
});

// Import newly refactored visual modular components
import ASTConsole from '../components/dashboard/ASTConsole';
import FindingsInspector from '../components/dashboard/FindingsInspector';
import ShellTerminal from '../components/layout/ShellTerminal';
import AttackSurfaceGauge from '../components/charts/AttackSurfaceGauge';
import SplineTrendChart from '../components/charts/SplineTrendChart';

export default function Home() {
  const fetchProjects = useCyberStore((state) => state.fetchProjects);
  const fetchTelemetry = useCyberStore((state) => state.fetchTelemetry);
  const fetchScans = useCyberStore((state) => state.fetchScans);
  
  const activeProject = useCyberStore((state) => state.activeProject);
  const activeScan = useCyberStore((state) => state.activeScan);
  const phase = useCyberStore((state) => state.phase);
  const progress = useCyberStore((state) => state.progress);
  const agents = useCyberStore((state) => state.agents);
  const logs = useCyberStore((state) => state.logs);
  const telemetry = useCyberStore((state) => state.telemetry);
  const findings = useCyberStore((state) => state.findings);

  const [activeTab, setActiveTab] = useState<'command' | 'analysis' | 'settings'>('command');
  const [askInput, setAskInput] = useState('');
  const [aiAssistantLogs, setAiAssistantLogs] = useState<string[]>([
    "Orchestrator AI initialized.",
    "System fully operational. Ready for security audit."
  ]);

  useEffect(() => {
    // Initial data fetch
    fetchProjects();
    fetchTelemetry();
    fetchScans();
  }, [fetchProjects, fetchTelemetry, fetchScans]);

  const handleAskSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!askInput.trim()) return;
    const query = askInput.trim();
    setAiAssistantLogs(prev => [
      ...prev, 
      `User: ${query}`, 
      `Orchestrator AI: Evaluating security target. Dispatched query parameters...`
    ]);
    setAskInput('');
  };

  // Helper values derived from telemetry / store fallback
  const riskScoreVal = activeScan ? activeScan.risk_score.toFixed(1) : (telemetry?.stats.avg_risk.toFixed(1) || "0.0");
  const criticalCount = activeScan ? findings.filter(f => f.severity.toLowerCase() === 'critical').length : (telemetry?.vulnerability_counts.Critical || 0);
  const highCount = activeScan ? findings.filter(f => f.severity.toLowerCase() === 'high').length : (telemetry?.vulnerability_counts.High || 0);
  const mediumCount = activeScan ? findings.filter(f => f.severity.toLowerCase() === 'medium').length : (telemetry?.vulnerability_counts.Medium || 0);
  const lowCount = activeScan ? findings.filter(f => f.severity.toLowerCase() === 'low').length : (telemetry?.vulnerability_counts.Low || 0);
  const totalFindingsVal = activeScan ? findings.length : criticalCount + highCount + mediumCount + lowCount;
  const severityPercent = (count: number) => totalFindingsVal > 0 ? Number(((count / totalFindingsVal) * 100).toFixed(1)) : 0;
  const criticalPct = severityPercent(criticalCount);
  const highPct = severityPercent(highCount);
  const mediumPct = severityPercent(mediumCount);
  const lowPct = severityPercent(lowCount);
  const cpuPercent = telemetry?.system?.cpu_percent;
  const memoryMb = telemetry?.system?.memory_rss_mb;
  const queueLength = telemetry?.queue?.pending_tasks;
  const activeScanning = telemetry?.stats.active_scanning || 0;
  const recentInsights = activeScan ? findings.slice(0, 3) : (telemetry?.recent_findings || []).slice(0, 3);
  const riskScoreNum = Number(riskScoreVal);
  const riskLabel = riskScoreNum >= 80 ? 'CRITICAL' : riskScoreNum >= 50 ? 'HIGH' : riskScoreNum >= 20 ? 'MEDIUM' : 'LOW';
  const formatUptime = (seconds?: number) => {
    if (!seconds) return '0m';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  // Status mapping for visual styles
  const getAgentStatusDot = (status: string) => {
    switch (status) {
      case 'PROCESSING': return 'bg-emerald-400 animate-pulse';
      case 'COMPLETED': return 'bg-cyan-400';
      default: return 'bg-gray-500';
    }
  };

  const getAgentColorClass = (name: string) => {
    switch (name) {
      case 'Orchestrator AI': return 'text-cyan-400 border-cyan-500/20';
      case 'Code Analysis Agent': return 'text-pink-400 border-pink-500/20';
      case 'Security Review Agent': return 'text-purple-400 border-purple-500/20';
      case 'Threat Intelligence Agent': return 'text-yellow-400 border-yellow-500/20';
      case 'Machine Learning Agent': return 'text-green-400 border-green-500/20';
      default: return 'text-indigo-400 border-indigo-500/20';
    }
  };

  return (
    <main className="min-h-screen bg-[#070913] text-[#e0e5ff] flex font-mono select-none overflow-hidden h-screen">
      {/* 1. LEFT SIDEBAR */}
      <section className="w-[280px] shrink-0 border-r border-[#1a233a] bg-[#0b0f19]/90 backdrop-blur-xl flex flex-col p-4 space-y-5 overflow-y-auto">
        {/* LOGO AREA */}
        <div className="flex items-center gap-2 pb-3 border-b border-[#1a233a]">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-indigo-600 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.4)]">
            <Skull size={18} className="text-black shrink-0" />
          </div>
          <div>
            <h1 className="text-xs font-black tracking-widest text-cyan-400 uppercase glow-text-cyan">
              CYBERVERSE AI
            </h1>
            <p className="text-[8px] text-cyan-500/60 uppercase font-bold tracking-tighter">
              AUTONOMOUS RESEARCH PLATFORM
            </p>
          </div>
        </div>

        {/* MAIN NAVIGATION */}
        <div className="space-y-1">
          <span className="text-[9px] text-[#4f5d75] font-bold uppercase tracking-wider block px-2 mb-2 select-none">
            MAIN NAVIGATION
          </span>
          <button 
            onClick={() => setActiveTab('command')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-left transition-all ${activeTab === 'command' ? 'bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-400 font-bold' : 'text-[#8b9bb4] hover:text-cyan-400 hover:bg-white/5'}`}
          >
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide">
              <Grid size={14} className="shrink-0" />
              <span>Command Center</span>
            </div>
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#22d3ee]"></span>
          </button>

          <button 
            onClick={() => setActiveTab('analysis')}
            className={`w-full flex items-center justify-between px-3 py-2 rounded text-left transition-all ${activeTab === 'analysis' ? 'bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-400 font-bold' : 'text-[#8b9bb4] hover:text-cyan-400 hover:bg-white/5'}`}
          >
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide">
              <Terminal size={14} className="shrink-0" />
              <span>Code Analysis</span>
            </div>
            {findings.length > 0 && (
              <span className="bg-rose-500/20 text-rose-400 text-[8px] px-1.5 py-0.5 rounded border border-rose-500/30 font-black">
                {findings.length}
              </span>
            )}
          </button>

          <button 
            onClick={() => setActiveTab('settings')}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded text-[#8b9bb4] hover:text-cyan-400 hover:bg-white/5 text-[11px] uppercase tracking-wide transition-all ${activeTab === 'settings' ? 'bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-400 font-bold' : ''}`}
          >
            <Settings size={14} className="shrink-0" />
            <span>Settings / Keys</span>
          </button>
        </div>

        {/* ACTIVE AGENTS PANEL */}
        <div className="space-y-2">
          <div className="flex items-center justify-between px-2 mb-1 select-none">
            <span className="text-[9px] text-[#4f5d75] font-bold uppercase tracking-wider">
              ACTIVE AGENTS
            </span>
            <span className="bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-[7px] px-1 rounded uppercase font-bold">
              6 ACTIVE
            </span>
          </div>

          <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
            {Object.entries(agents).map(([name, state]) => (
              <div 
                key={name}
                className={`p-2 bg-[#0e1322] border rounded flex items-center justify-between hover:border-cyan-500/30 transition-all duration-300 ${getAgentColorClass(name)}`}
              >
                <div className="flex items-center gap-2 overflow-hidden">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${getAgentStatusDot(state.status)}`}></span>
                  <div className="overflow-hidden">
                    <p className="text-[9px] font-bold truncate leading-tight">{name}</p>
                    <p className="text-[7px] text-gray-400 truncate mt-0.5 italic">{state.lastInstruction}</p>
                  </div>
                </div>
                {state.status === 'PROCESSING' && (
                  <div className="w-8 shrink-0 flex items-center justify-end">
                    <span className="text-[8px] text-cyan-400 font-bold animate-pulse">{state.load}%</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* SYSTEM STATUS DONUT GAUGE */}
        <div className="mt-auto pt-3 border-t border-[#1a233a]">
          <div className="bg-[#0c101c] border border-cyan-500/10 rounded-lg p-2.5 flex items-center justify-between">
            <div className="w-[54px] h-[54px] shrink-0 relative flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-[#1a233a]"
                  strokeWidth="2.5"
                  stroke="currentColor"
                  fill="transparent"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="text-cyan-400 filter drop-shadow-[0_0_4px_#22d3ee]"
                  strokeDasharray="93, 100"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="transparent"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <div className="absolute text-center">
                <span className="text-[9px] font-black text-cyan-400 block tracking-tighter">{activeScanning}</span>
              </div>
            </div>
            <div className="ml-3 flex-1">
              <span className="text-[8px] text-cyan-500/60 uppercase font-black tracking-widest block">SYSTEM STATUS</span>
              <span className="text-[9px] text-emerald-400 font-bold block uppercase tracking-wider mt-0.5 animate-pulse">{telemetry ? 'OPERATIONAL' : 'CONNECTING'}</span>
              
              <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[8px] text-gray-400 mt-1 border-t border-white/5 pt-1">
                <div>CPU: <span className="text-gray-200">{typeof cpuPercent === 'number' ? `${cpuPercent.toFixed(1)}%` : 'N/A'}</span></div>
                <div>MEM: <span className="text-gray-200">{typeof memoryMb === 'number' ? `${memoryMb.toFixed(0)}MB` : 'N/A'}</span></div>
                <div>SCANS: <span className="text-gray-200">{activeScanning}</span></div>
                <div>QUEUE: <span className="text-gray-200">{typeof queueLength === 'number' ? queueLength : 'N/A'}</span></div>
              </div>
            </div>
          </div>
          
          <div className="text-[7px] text-[#4f5d75] font-black text-center uppercase tracking-widest mt-2 block">
            System Uptime: {formatUptime(telemetry?.uptime_seconds)}
          </div>
        </div>
      </section>

      {/* 2. MAIN COCKPIT VIEW AREA */}
      <section className="flex-1 flex flex-col overflow-y-auto p-4 space-y-4 relative h-screen">
        {activeTab === 'command' && (
          <>
            {/* TOP HEADER SECTION */}
            <header className="grid grid-cols-6 gap-3 shrink-0">
              {/* Mission Overview */}
              <div className="col-span-2 bg-[#0c101c]/90 border border-cyan-500/10 rounded-lg p-2.5 flex flex-col justify-center relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <span className="text-[8px] text-cyan-500/60 font-black tracking-wider uppercase">MISSION OVERVIEW</span>
                  <span className="bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[7px] px-1.5 py-0.5 rounded uppercase font-black tracking-wide animate-pulse flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-emerald-400"></span> LIVE
                  </span>
                </div>
                <p className="text-[10px] text-gray-200 font-bold mt-1.5 truncate text-cyan-400 tracking-wider">
                  Target: {activeScan ? activeScan.target_value : (activeProject?.git_url || activeProject?.name || "No active target")}
                </p>
              </div>

              {/* Risk Score */}
              <div className="col-span-1 bg-[#0c101c]/90 border border-rose-500/20 rounded-lg p-2.5 flex flex-col items-center justify-center relative overflow-hidden">
                <span className="text-[8px] text-rose-500/60 font-black tracking-wider uppercase">RISK SCORE</span>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-base font-black text-rose-500 tracking-tighter">{riskScoreVal}</span>
                  <span className="text-[7px] text-rose-400 font-black border border-rose-500/30 bg-rose-500/10 px-1 rounded">{riskLabel}</span>
                </div>
              </div>

              {/* Total Findings */}
              <div className="col-span-1 bg-[#0c101c]/90 border border-cyan-500/20 rounded-lg p-2.5 flex flex-col items-center justify-center relative overflow-hidden">
                <span className="text-[8px] text-cyan-500/60 font-black tracking-wider uppercase">TOTAL FINDINGS</span>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-base font-black text-cyan-400 tracking-tighter">{totalFindingsVal}</span>
                  <span className="text-[7px] text-emerald-400 font-black tracking-widest">+28</span>
                </div>
              </div>

              {/* Severity Counts Grid */}
              <div className="col-span-2 bg-[#0c101c]/90 border border-white/5 rounded-lg p-2 flex items-center justify-around">
                <div className="text-center px-1.5">
                  <span className="text-[8px] text-rose-400/60 font-bold block uppercase">CRITICAL</span>
                  <span className="text-[11px] font-black text-rose-500 block mt-1">{criticalCount}</span>
                </div>
                <div className="text-center px-1.5">
                  <span className="text-[8px] text-orange-400/60 font-bold block uppercase">HIGH</span>
                  <span className="text-[11px] font-black text-orange-400 block mt-1">{highCount}</span>
                </div>
                <div className="text-center px-1.5">
                  <span className="text-[8px] text-yellow-400/60 font-bold block uppercase">MEDIUM</span>
                  <span className="text-[11px] font-black text-yellow-400 block mt-1">{mediumCount}</span>
                </div>
                <div className="text-center px-1.5">
                  <span className="text-[8px] text-cyan-400/60 font-bold block uppercase">LOW</span>
                  <span className="text-[11px] font-black text-cyan-400 block mt-1">{lowCount}</span>
                </div>
              </div>
            </header>

            {/* CENTRAL 3D SPHERE BLOCK & SIDEBAR MATRIX */}
            <div className="grid grid-cols-4 gap-4 flex-1 min-h-0">
              {/* Central Threat Galaxy */}
              <div className="col-span-3 border border-[#1a233a] bg-[#080c16]/95 rounded-lg relative overflow-hidden flex flex-col h-full">
                {/* 3D Holosphere Canvas */}
                <div className="flex-1 relative">
                  <ThreatGalaxyScene />
                </div>

                {/* Overlaid UI 1: Threat Landscape (Left) */}
                <div className="absolute top-12 left-4 z-10 w-[140px] bg-[#0c101c]/80 border border-white/5 p-2 rounded pointer-events-auto">
                  <span className="text-[7px] text-[#4f5d75] font-black tracking-widest block uppercase mb-1.5">THREAT LANDSCAPE</span>
                  <div className="space-y-1 text-[8px] leading-none">
                    <div className="flex justify-between py-1 border-b border-white/5">
                      <span className="text-rose-500 font-bold uppercase">CRITICAL</span>
                      <span className="font-bold text-gray-200">{criticalCount}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-white/5">
                      <span className="text-orange-400 font-bold uppercase">HIGH</span>
                      <span className="font-bold text-gray-200">{highCount}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-white/5">
                      <span className="text-yellow-400 font-bold uppercase">MEDIUM</span>
                      <span className="font-bold text-gray-200">{mediumCount}</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-cyan-400 font-bold uppercase">LOW</span>
                      <span className="font-bold text-gray-200">{lowCount}</span>
                    </div>
                  </div>
                  
                  <button 
                    onClick={() => setActiveTab('analysis')}
                    className="w-full bg-[#1a233a]/40 border border-cyan-500/20 text-cyan-400 text-[8px] py-1 rounded mt-2 uppercase font-black tracking-wider transition-all hover:bg-cyan-500/10 active:scale-95"
                  >
                    View Findings
                  </button>
                </div>

                {/* Overlaid UI 2: Events Feed (Right) */}
                <div className="absolute top-12 right-4 z-10 w-[200px] bg-[#0c101c]/80 border border-white/5 p-2.5 rounded pointer-events-auto max-h-[220px] flex flex-col">
                  <span className="text-[7px] text-[#4f5d75] font-black tracking-widest block uppercase mb-2">REAL-TIME EVENTS</span>
                  
                  <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 scrollbar-thin max-h-[140px]">
                    {logs.length === 0 ? (
                      <div className="text-gray-500 text-[8px] italic py-4 text-center">Awaiting log stream...</div>
                    ) : (
                      logs.slice(-5).reverse().map((l, i) => (
                        <div key={i} className="flex gap-1.5 items-start text-[8px] leading-tight border-b border-white/5 pb-1">
                          <span className={`w-1 h-1 rounded-full shrink-0 mt-1 ${
                            l.type === 'error' ? 'bg-rose-500' : l.type === 'success' ? 'bg-cyan-400' : 'bg-purple-500'
                          }`}></span>
                          <div className="overflow-hidden">
                            <span className="text-[#8b9bb4] truncate font-bold block">{l.agent_name.toUpperCase()}</span>
                            <span className="text-gray-300 block italic leading-normal truncate">{l.message}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <button 
                    onClick={() => setActiveTab('analysis')}
                    className="w-full bg-[#1a233a]/40 border border-cyan-500/20 text-cyan-400 text-[8px] py-1 rounded mt-2 uppercase font-black tracking-wider transition-all hover:bg-cyan-500/10 active:scale-95 text-center block"
                  >
                    Open Live Terminal
                  </button>
                </div>

                {/* Overlaid UI 3: Mission Timeline (Bottom) */}
                <div className="absolute bottom-3 left-4 right-4 z-10 bg-[#0c101c]/80 border border-white/5 p-2 rounded flex flex-col select-none">
                  <span className="text-[7px] text-[#4f5d75] font-black tracking-widest uppercase block mb-1">MISSION TIMELINE</span>
                  <div className="flex items-center justify-between text-[8px] relative pt-2">
                    <div className="absolute left-0 right-0 top-3 h-0.5 bg-[#1a233a] z-0"></div>
                    <div className="absolute left-0 top-3 h-0.5 bg-cyan-400 z-1" style={{ width: `${progress}%` }}></div>
                    
                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress >= 5 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">INITIATED</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>

                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress >= 20 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">RECON</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>

                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress >= 40 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">CODE SCAN</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>

                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress >= 60 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">ANALYSIS</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>

                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress >= 85 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">REPORTING</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>

                    <div className="z-10 text-center relative flex flex-col items-center">
                      <span className={`w-2.5 h-2.5 rounded-full border-2 ${progress === 100 ? 'bg-cyan-400 border-cyan-400' : 'bg-[#0c101c] border-[#1a233a]'}`}></span>
                      <span className="text-gray-200 mt-1 font-bold">COMPLETE</span>
                      <span className="text-[6px] text-gray-500 font-semibold mt-0.5">--:--</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Side: Scan Progress & Live Agent Activity */}
              <div className="col-span-1 flex flex-col space-y-4 h-full overflow-hidden">
                {/* 1. SCAN PROGRESS BAR */}
                <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 shrink-0 flex flex-col justify-center relative overflow-hidden">
                  <div className="flex items-center justify-between text-[9px] font-black mb-1.5 tracking-wider">
                    <span className="text-cyan-500/60 uppercase">SCAN PROGRESS</span>
                    <span className="text-cyan-400">{progress}%</span>
                  </div>
                  <div className="w-full h-2.5 bg-black/60 rounded border border-cyan-500/15 overflow-hidden p-[1px]">
                    <div 
                      className="h-full bg-cyan-400 rounded-sm transition-all duration-500 filter drop-shadow-[0_0_8px_#22d3ee] shadow-[0_0_6px_#22d3ee]"
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                  <span className="text-[7.5px] text-gray-500 font-black uppercase tracking-wider mt-1.5 block">
                    STATUS: {progress === 100 ? "COMPLETE" : progress > 0 ? "RUNNING" : "AWAITING DISPATCH"}
                  </span>
                </div>

                {/* 2. AGENT NETWORK STATUS */}
                <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 shrink-0 flex flex-col justify-center overflow-hidden">
                  <span className="text-[9px] text-[#4f5d75] font-black tracking-widest block uppercase mb-2">AGENT NETWORK STATUS</span>
                  <div className="h-[90px] border border-white/5 rounded bg-black/35 relative flex items-center justify-center">
                    <svg className="w-[180px] h-full" viewBox="0 0 180 90">
                      <line x1="90" y1="45" x2="30" y2="25" stroke="#ff007f" strokeWidth="1" strokeDasharray="3" className="laser-active" />
                      <line x1="90" y1="45" x2="150" y2="25" stroke="#8a2be2" strokeWidth="1" />
                      <line x1="90" y1="45" x2="30" y2="65" stroke="#22c55e" strokeWidth="1" />
                      <line x1="90" y1="45" x2="150" y2="65" stroke="#eab308" strokeWidth="1" />
                      
                      <circle cx="90" cy="45" r="8" fill="#00f3ff" className="animate-pulse" />
                      <circle cx="90" cy="45" r="4" fill="#000" />
                      
                      <circle cx="30" cy="25" r="5" fill="#ff007f" />
                      <circle cx="150" cy="25" r="5" fill="#8a2be2" />
                      <circle cx="30" cy="65" r="5" fill="#22c55e" />
                      <circle cx="150" cy="65" r="5" fill="#eab308" />

                      <text x="90" y="32" fontSize="6" fill="#00f3ff" textAnchor="middle" fontWeight="bold">ORCHESTRATOR</text>
                      <text x="30" y="16" fontSize="5" fill="#ff007f" textAnchor="middle">ANALYZER</text>
                      <text x="150" y="16" fontSize="5" fill="#8a2be2" textAnchor="middle">REVIEWER</text>
                    </svg>
                  </div>
                </div>

                {/* 3. LIVE AGENT ACTIVITY TABLE */}
                <div className="bg-[#0b0f19]/90 border border-white/5 rounded-lg p-3 flex-1 flex flex-col overflow-hidden">
                  <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-white/5 shrink-0 select-none">
                    <span className="text-[9px] text-[#4f5d75] font-black tracking-widest block uppercase">LIVE AGENT ACTIVITY</span>
                    <span className="text-[7px] text-cyan-400 font-bold uppercase tracking-wider">TRACKING</span>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[8.5px]">
                    <div className="grid grid-cols-5 font-bold uppercase text-[#4f5d75] pb-1 border-b border-white/5 shrink-0 select-none">
                      <span className="col-span-2">AGENT</span>
                      <span className="col-span-1">STATUS</span>
                      <span className="col-span-2">TASK</span>
                    </div>

                    <div className="space-y-1.5">
                      {Object.entries(agents).map(([name, state]) => (
                        <div key={name} className="grid grid-cols-5 items-center py-1 border-b border-white/5 hover:bg-white/5 transition-all">
                          <span className="col-span-2 font-bold text-gray-200 truncate">{name.replace(" Agent", "")}</span>
                          <span className="col-span-1 flex items-center">
                            <span className={`w-1.5 h-1.5 rounded-full shrink-0 mr-1.5 ${getAgentStatusDot(state.status)}`}></span>
                            <span className={state.status === 'PROCESSING' ? 'text-emerald-400 animate-pulse' : state.status === 'COMPLETED' ? 'text-cyan-400' : 'text-gray-500'}>
                              {state.status === 'PROCESSING' ? 'Active' : state.status === 'COMPLETED' ? 'Ready' : 'Idle'}
                            </span>
                          </span>
                          <span className="col-span-2 truncate text-gray-400 font-semibold italic">{state.lastInstruction}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* BOTTOM STATS DECK */}
            <footer className="grid grid-cols-4 gap-4 shrink-0 h-[190px]">
              {/* Gauge 1: Attack Surface */}
              <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 flex flex-col justify-between overflow-hidden">
                <span className="text-[8px] text-cyan-500/60 font-black tracking-widest block uppercase">ATTACK SURFACE</span>
                <AttackSurfaceGauge
                  totalEndpoints={totalFindingsVal}
                  stats={[
                    { name: 'Critical', value: criticalCount, color: '#ff007f' },
                    { name: 'High', value: highCount, color: '#ea580c' },
                    { name: 'Medium', value: mediumCount, color: '#eab308' },
                    { name: 'Low', value: lowCount, color: '#00f3ff' }
                  ]}
                />
                <div className="text-[7.5px] text-cyan-400 text-center uppercase tracking-widest font-black pt-1.5 border-t border-white/5 cursor-pointer hover:underline">
                  View Attack Surface &rarr;
                </div>
              </div>

              {/* Gauge 2: Spline Trend Line */}
              <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 flex flex-col justify-between overflow-hidden">
                <div className="flex justify-between items-center shrink-0 mb-1 select-none">
                  <span className="text-[8px] text-cyan-500/60 font-black tracking-widest uppercase">VULNERABILITY TREND</span>
                  <span className="bg-[#1a233a]/60 text-[6.5px] px-1 rounded font-black text-cyan-400">LIVE</span>
                </div>
                <SplineTrendChart />
              </div>

              {/* Gauge 3: Severity Donut */}
              <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 flex flex-col justify-between overflow-hidden">
                <span className="text-[8px] text-cyan-500/60 font-black tracking-widest block uppercase">SEVERITY DISTRIBUTION</span>
                
                <div className="flex items-center justify-between flex-1">
                  <div className="w-[66px] h-[66px] shrink-0 relative flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#1a233a" strokeWidth="2.5" />
                      <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#ff007f" strokeWidth="2.5" strokeDasharray={`${criticalPct}, 100`} />
                      <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#ea580c" strokeWidth="2.5" strokeDasharray={`${highPct}, 100`} strokeDashoffset={-criticalPct} />
                      <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#eab308" strokeWidth="2.5" strokeDasharray={`${mediumPct}, 100`} strokeDashoffset={-(criticalPct + highPct)} />
                      <circle cx="18" cy="18" r="15.91" fill="transparent" stroke="#06b6d4" strokeWidth="2.5" strokeDasharray={`${lowPct}, 100`} strokeDashoffset={-(criticalPct + highPct + mediumPct)} />
                    </svg>
                    <div className="absolute text-center">
                      <span className="text-xs font-black text-gray-100 leading-none">{totalFindingsVal}</span>
                      <span className="text-[5.5px] text-gray-500 uppercase font-black tracking-tighter block mt-0.5">Total</span>
                    </div>
                  </div>

                  <div className="ml-3 flex-1 space-y-0.5 text-[8px] text-gray-400">
                    <div className="flex justify-between">
                      <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1 shrink-0"></span> Critical</span>
                      <span className="font-bold text-gray-200">{criticalCount} ({criticalPct}%)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-orange-500 mr-1 shrink-0"></span> High</span>
                      <span className="font-bold text-gray-200">{highCount} ({highPct}%)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400 mr-1 shrink-0"></span> Medium</span>
                      <span className="font-bold text-gray-200">{mediumCount} ({mediumPct}%)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mr-1 shrink-0"></span> Low</span>
                      <span className="font-bold text-gray-200">{lowCount} ({lowPct}%)</span>
                    </div>
                  </div>
                </div>

                <div className="pt-1.5 border-t border-white/5 flex items-center justify-center text-[7.5px] font-black uppercase text-gray-500 select-none">
                  Telemetry compilation complete
                </div>
              </div>

              {/* Gauge 4: AI Insights */}
              <div className="bg-[#0b0f19]/90 border border-cyan-500/10 rounded-lg p-3 flex flex-col justify-between overflow-hidden">
                <div className="flex justify-between items-center mb-1 border-b border-white/5 pb-1 shrink-0 select-none">
                  <span className="text-[8px] text-cyan-500/60 font-black tracking-widest uppercase">AI INSIGHTS</span>
                  <span className="text-[7.5px] text-purple-400 font-bold uppercase tracking-wider">COGNITIVE</span>
                </div>

                <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 py-1 text-[8px] leading-tight">
                  {recentInsights.length === 0 ? (
                    <div className="text-gray-500 text-center py-4 uppercase tracking-widest">
                      No findings yet
                    </div>
                  ) : (
                    recentInsights.map((finding) => (
                      <div key={finding.id} className="bg-[#1a233a]/15 border border-purple-500/10 p-1.5 rounded relative overflow-hidden flex flex-col">
                        <div className="flex justify-between items-center font-bold">
                          <span className="text-gray-200 truncate">{finding.title}</span>
                          <span className="bg-rose-500/10 text-rose-500 border border-rose-500/20 text-[6.5px] px-1 rounded uppercase font-black shrink-0 ml-1">
                            {finding.severity}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="text-[7.5px] text-cyan-400 text-center uppercase tracking-widest font-black pt-1.5 border-t border-white/5 cursor-pointer hover:underline">
                  View All Insights &rarr;
                </div>
              </div>
            </footer>

            {/* GLOBAL BOTTOM COMMAND TOOLBAR */}
            <form onSubmit={handleAskSubmit} className="flex gap-2 p-2 bg-[#0c101c] border border-cyan-500/20 rounded-lg shadow-[0_0_15px_rgba(6,182,212,0.1)] shrink-0 items-center">
              <Search size={14} className="text-cyan-400 ml-1.5 shrink-0" />
              <input
                type="text"
                placeholder="Ask Orchestrator AI to evaluate vulnerabilities, query MITRE metrics, or review codes..."
                value={askInput}
                onChange={(e) => setAskInput(e.target.value)}
                className="flex-1 bg-transparent border-none text-[10px] text-gray-200 placeholder-cyan-500/30 focus:outline-none px-2 font-mono py-1"
              />
              <button 
                type="submit"
                className="bg-cyan-500 text-black hover:bg-cyan-400 px-3 py-1.5 rounded text-[8.5px] uppercase font-black tracking-wider transition-all active:scale-95 flex items-center gap-1.5"
              >
                <span>Submit Query</span>
                <ChevronRight size={10} className="stroke-[3]" />
              </button>
            </form>
            
            {aiAssistantLogs.length > 2 && (
              <div className="text-[8.5px] text-gray-400 bg-black/60 border border-cyan-500/10 p-2 rounded max-h-[80px] overflow-y-auto mt-1 leading-relaxed">
                {aiAssistantLogs.slice(-3).map((line, idx) => (
                  <div key={idx}>{line}</div>
                ))}
              </div>
            )}
          </>
        )}

        {activeTab === 'analysis' && (
          <div className="flex-1 flex flex-col space-y-4 overflow-hidden h-full">
            {/* Interactive code scan panels */}
            <div className="grid grid-cols-5 gap-4 h-[440px] shrink-0">
              {/* Left Column: Input Dispatcher */}
              <div className="col-span-2 h-full min-h-0">
                <ASTConsole />
              </div>
              
              {/* Right Column: Live Terminal Feed */}
              <div className="col-span-3 h-full min-h-0">
                <ShellTerminal />
              </div>
            </div>

            {/* Widescreen vulnerability Findings grid */}
            <div className="flex-1 min-h-0 bg-black/75 border border-purple-500/20 rounded-lg p-3 overflow-hidden shadow-[0_0_15px_rgba(138,43,226,0.1)]">
              <FindingsInspector />
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="flex-1 flex flex-col justify-center items-center overflow-hidden h-full">
            <div className="bg-[#0b0f19] border border-cyan-500/20 p-6 rounded-lg max-w-lg w-full space-y-4">
              <div className="flex items-center gap-3 border-b border-cyan-500/10 pb-3 mb-2">
                <Settings size={22} className="text-cyan-400" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-cyan-400">Settings & API Credentials</h3>
              </div>

              <div className="text-[11px] text-gray-400 leading-relaxed space-y-3">
                <p>
                  Configure model providers and runtime credentials through backend environment variables:
                </p>
                <code className="block bg-black/55 border border-white/5 p-2 rounded text-[10px] text-cyan-300">
                  backend/.env
                </code>
                
                <p>
                  Production deployments should inject these values through the process manager or secret store before service startup.
                </p>

                <div className="bg-cyan-500/5 border border-cyan-500/10 p-3 rounded space-y-1.5 mt-2">
                  <span className="text-[10px] font-bold text-cyan-400 block uppercase">Loaded LLM Target</span>
                  <div className="flex justify-between items-center text-[10px] text-gray-200">
                    <span>Active Provider:</span>
                    <span className="font-bold text-cyan-300">Configured on backend</span>
                  </div>
                  <div className="flex justify-between items-center text-[10px] text-gray-200">
                    <span>Selected Model:</span>
                    <span className="font-bold text-teal-400">Environment controlled</span>
                  </div>
                </div>

                <div className="border border-purple-500/10 bg-purple-500/5 p-3 rounded space-y-1 mt-2">
                  <span className="text-[10px] font-bold text-purple-400 block uppercase">Dependency Intelligence</span>
                  <p className="text-[9px]">
                    Findings are generated from scanned files, manifests, and agent review output persisted by the backend.
                  </p>
                </div>
              </div>

              <button 
                onClick={() => setActiveTab('command')}
                className="w-full bg-gradient-to-r from-cyan-500 to-teal-500 text-black font-bold uppercase text-[10px] tracking-wider py-2 rounded transition-all active:scale-95 shadow-[0_0_12px_rgba(6,182,212,0.3)]"
              >
                Return to Command Center
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
