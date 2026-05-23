'use client';

import React, { useState } from 'react';
import { GitBranch, FileCode, Play, Terminal, HelpCircle } from 'lucide-react';
import { useCyberStore } from '../../store/useCyberStore';

export default function ASTConsole() {
  const activeProject = useCyberStore((state) => state.activeProject);
  const phase = useCyberStore((state) => state.phase);
  const startFileScan = useCyberStore((state) => state.startFileScan);
  const startGitScan = useCyberStore((state) => state.startGitScan);
  const clearScanState = useCyberStore((state) => state.clearScanState);

  const [tab, setTab] = useState<'code' | 'git'>('code');
  const [targetName, setTargetName] = useState('source.py');
  const [codeContent, setCodeContent] = useState('');
  
  const [gitUrl, setGitUrl] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const isScanning = phase !== 'idle' && phase !== 'done' && phase !== 'failed';

  const handleLaunch = async () => {
    if (isScanning) return;
    setErrorMsg('');
    try {
      if (tab === 'code') {
        if (!codeContent.trim()) {
          setErrorMsg('Please paste code content to scan');
          return;
        }
        await startFileScan(targetName, codeContent);
      } else {
        if (!gitUrl.trim()) {
          setErrorMsg('Please provide a Git repository URL');
          return;
        }
        await startGitScan(gitUrl);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Scan dispatch failed.');
    }
  };

  return (
    <div className="w-full h-full flex flex-col cyber-panel-cyan bg-black/75 rounded-lg p-3 font-mono text-xs overflow-hidden">
      {/* Console tabs */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2 mb-3">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setTab('code')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded transition-colors ${tab === 'code' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'text-gray-400 hover:text-cyan-400'}`}
            disabled={isScanning}
          >
            <FileCode size={13} />
            <span>AST Code sandbox</span>
          </button>
          <button
            onClick={() => setTab('git')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded transition-colors ${tab === 'git' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'text-gray-400 hover:text-cyan-400'}`}
            disabled={isScanning}
          >
            <GitBranch size={13} />
            <span>Git Repository check</span>
          </button>
        </div>
        <div className="text-[10px] text-cyan-500/50 uppercase">TARGET_DISPATCHER</div>
      </div>

      {/* Dispatch form contents */}
      <div className="flex-1 flex flex-col space-y-3 overflow-hidden">
        {tab === 'code' ? (
          <div className="flex-1 flex flex-col space-y-2 overflow-hidden">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-cyan-500/60 uppercase">TARGET NAME:</span>
              <input
                type="text"
                value={targetName}
                onChange={(e) => setTargetName(e.target.value)}
                className="flex-1 bg-black/60 border border-cyan-500/20 rounded px-2 py-1 text-cyan-300 focus:outline-none focus:border-cyan-400 text-[11px]"
                disabled={isScanning}
              />
            </div>
            <div className="flex-1 flex flex-col overflow-hidden">
              <span className="text-[10px] text-cyan-500/60 uppercase mb-1">SOURCE PAYLOAD:</span>
              <textarea
                value={codeContent}
                onChange={(e) => setCodeContent(e.target.value)}
                className="flex-1 bg-black/80 border border-cyan-500/20 rounded p-2 text-gray-300 font-mono text-[10px] leading-relaxed resize-none focus:outline-none focus:border-cyan-400 overflow-y-auto"
                disabled={isScanning}
              />
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col space-y-2">
            <div className="flex flex-col space-y-1">
              <span className="text-[10px] text-cyan-500/60 uppercase">REPOSITORY URL:</span>
              <input
                type="text"
                placeholder="https://github.com/..."
                value={gitUrl}
                onChange={(e) => setGitUrl(e.target.value)}
                className="w-full bg-black/60 border border-cyan-500/20 rounded px-2.5 py-2 text-cyan-300 focus:outline-none focus:border-cyan-400 text-[11px]"
                disabled={isScanning}
              />
            </div>
            <div className="flex-1 flex flex-col justify-center border border-cyan-500/5 bg-black/35 rounded p-3 text-gray-400 space-y-2 text-[10px] leading-relaxed">
              <div className="flex gap-2">
                <Terminal size={14} className="text-cyan-500 shrink-0" />
                <p>Spawns safe sandboxed git clone vectors. CodeAnalyzer scans AST trees, maps files to MITRE indices and generates actionable mitigation procedures.</p>
              </div>
              <div className="flex gap-2">
                <HelpCircle size={14} className="text-pink-500 shrink-0" />
                <p>Note: Since this is an authorized defensive analyzer, execution performs purely static analysis on scripts, configs, and dependencies without remote executions.</p>
              </div>
            </div>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center justify-between border-t border-cyan-500/10 pt-3">
          <div className="text-[10px] text-teal-400">
            {activeProject ? `ACTIVE PROJ: ${activeProject.name}` : 'Awaiting project init...'}
          </div>

          <div className="flex gap-2 shrink-0">
            <button
              onClick={clearScanState}
              className="px-3 py-1.5 rounded border border-gray-500/30 text-gray-400 hover:text-white transition-colors"
              disabled={isScanning}
            >
              Reset workspace
            </button>
            <button
              onClick={handleLaunch}
              className={`flex items-center gap-1.5 px-4.5 py-1.5 rounded font-bold uppercase transition-all tracking-wider ${isScanning ? 'bg-cyan-500/10 text-cyan-500 border border-cyan-500/20 cursor-not-allowed animate-pulse' : 'bg-gradient-to-r from-cyan-500 to-teal-500 text-black hover:scale-105 active:scale-95 shadow-[0_0_12px_rgba(6,182,212,0.4)]'}`}
              disabled={isScanning}
            >
              <Play size={13} className={isScanning ? 'animate-spin' : ''} />
              <span>{isScanning ? 'Pumping...' : 'Launch scanner'}</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="text-[10px] text-rose-500 font-bold border border-rose-500/20 bg-rose-500/5 px-2.5 py-1 rounded">
            ERROR: {errorMsg}
          </div>
        )}
      </div>
    </div>
  );
}
