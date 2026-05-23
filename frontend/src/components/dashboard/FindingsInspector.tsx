'use client';

import React, { useState } from 'react';
import { ShieldCheck, FileDown, ShieldAlert, BookOpen, Key, RefreshCw } from 'lucide-react';
import { useCyberStore } from '../../store/useCyberStore';
import { Finding } from '../../types';
import { getSeverityColor } from '../../utils/helpers';

export default function FindingsInspector() {
  const activeScan = useCyberStore((state) => state.activeScan);
  const findings = useCyberStore((state) => state.findings);
  const selectedFinding = useCyberStore((state) => state.selectedFinding);
  const setSelectedFinding = (f: Finding) => useCyberStore.setState({ selectedFinding: f });

  const [tab, setTab] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [downloading, setDownloading] = useState<string | null>(null);

  if (!activeScan) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-gray-500 font-mono text-xs border border-dashed border-cyan-500/10 rounded-lg p-5">
        <ShieldCheck size={36} className="text-cyan-500/20 mb-2" />
        <p className="text-center">Awaiting vulnerability analysis reports...</p>
        <p className="text-[10px] text-cyan-500/30 mt-1">Complete a code scan payload to compile real-time findings.</p>
      </div>
    );
  }

  const filteredFindings = findings.filter((f) => {
    if (tab === 'ALL') return true;
    return f.severity.toUpperCase() === tab;
  });

  const handleExport = async (format: 'pdf' | 'markdown' | 'json') => {
    setDownloading(format);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_BACKEND_REST_URL;
      const url = `${baseUrl}/scans/${activeScan.id}/report/${format}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Report synthesis failed');

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `cyberverse_report_${activeScan.id}.${format === 'markdown' ? 'md' : format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error(err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="w-full h-full flex flex-col font-mono text-xs overflow-hidden">
      {/* Exporter Controls */}
      <div className="flex items-center justify-between border-b border-purple-500/20 pb-2 mb-3">
        <div className="flex items-center gap-2 text-purple-400 font-semibold uppercase tracking-wider">
          <ShieldAlert size={14} className="animate-pulse" />
          <span>Vulnerability Finding Records ({findings.length})</span>
        </div>
        <div className="flex items-center gap-1.5">
          {(['pdf', 'markdown', 'json'] as const).map((fmt) => (
            <button
              key={fmt}
              onClick={() => handleExport(fmt)}
              disabled={downloading !== null}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-purple-600/20 text-purple-400 border border-purple-500/30 hover:bg-purple-600/30 hover:scale-105 active:scale-95 transition-all text-[10px] uppercase font-bold"
            >
              <FileDown size={11} />
              <span>{downloading === fmt ? `${fmt.toUpperCase()}...` : fmt.toUpperCase()}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Severity Filter Tabs */}
      <div className="flex gap-1.5 border-b border-purple-500/10 pb-2 mb-3 shrink-0">
        {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((tag) => (
          <button
            key={tag}
            onClick={() => setTab(tag)}
            className={`px-2 py-0.5 rounded text-[10px] border transition-colors uppercase ${tab === tag ? 'bg-purple-500/20 border-purple-500/30 text-purple-400 font-bold' : 'border-transparent text-gray-400 hover:text-purple-400'}`}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="flex-1 grid grid-cols-5 gap-3 overflow-hidden">
        {/* Left Side: Findings List */}
        <div className="col-span-2 border border-purple-500/10 rounded bg-black/45 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto divide-y divide-purple-500/5 p-1.5 space-y-1">
            {filteredFindings.length === 0 ? (
              <div className="text-gray-500 text-center py-6">No matching findings found.</div>
            ) : (
              filteredFindings.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setSelectedFinding(f)}
                  className={`w-full text-left p-2 rounded transition-all flex flex-col space-y-1 focus:outline-none ${selectedFinding?.id === f.id ? 'bg-purple-500/10 border border-purple-500/20' : 'hover:bg-purple-500/5 border border-transparent'}`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="font-semibold text-gray-200 truncate">{f.title}</span>
                    <span className={`text-[8px] font-bold border px-1.5 py-0.5 rounded shrink-0 ${getSeverityColor(f.severity)}`}>
                      {f.severity.toUpperCase()}
                    </span>
                  </div>
                  <span className="text-[10px] text-purple-500/60 truncate">
                    {f.file_path ? `${f.file_path}:${f.line_number}` : 'Global component'}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right Side: Deep Vulnerability Inspector Panel */}
        <div className="col-span-3 border border-purple-500/10 rounded bg-black/55 p-3 flex flex-col overflow-y-auto space-y-3.5 scrollbar-thin">
          {selectedFinding ? (
            <>
              {/* Header Title */}
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-gray-100">{selectedFinding.title}</h3>
                  <span className={`text-[9px] font-bold border px-2 py-0.5 rounded ${getSeverityColor(selectedFinding.severity)}`}>
                    {selectedFinding.severity.toUpperCase()}
                  </span>
                </div>
                <div className="text-[10px] text-purple-500/60 mt-1 border-b border-purple-500/10 pb-1.5">
                  FILE: {selectedFinding.file_path || 'Unknown'} : Line {selectedFinding.line_number || 1}
                </div>
              </div>

              {/* Classification matrices */}
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="bg-black/60 p-2 border border-purple-500/5 rounded">
                  <div className="text-purple-400 font-bold mb-0.5 flex items-center gap-1">
                    <BookOpen size={11} />
                    <span>CWE MAPPING</span>
                  </div>
                  <div className="text-gray-300 font-semibold">{selectedFinding.cwe || 'N/A'}</div>
                </div>
                <div className="bg-black/60 p-2 border border-purple-500/5 rounded">
                  <div className="text-purple-400 font-bold mb-0.5 flex items-center gap-1">
                    <Key size={11} />
                    <span>MITRE ATT&CK</span>
                  </div>
                  <div className="text-gray-300 truncate font-semibold">{selectedFinding.mitre_attack || 'N/A'}</div>
                </div>
              </div>

              {/* OWASP & Description */}
              <div className="space-y-1.5">
                <span className="text-[10px] text-teal-400 font-bold uppercase tracking-wider block">OWASP Benchmark:</span>
                <p className="text-gray-300 bg-teal-500/5 border border-teal-500/10 rounded px-2.5 py-1.5 leading-relaxed font-semibold">
                  {selectedFinding.owasp_category || 'A04:2021-Insecure Design'}
                </p>
                
                <span className="text-[10px] text-purple-500/60 font-bold uppercase tracking-wider block">Detailed Analysis:</span>
                <p className="text-gray-300 leading-relaxed bg-black/40 p-2 border border-purple-500/5 rounded">
                  {selectedFinding.description}
                </p>
              </div>

              {/* Code Snippet */}
              {selectedFinding.code_snippet && (
                <div className="space-y-1.5">
                  <span className="text-[10px] text-rose-400 font-bold uppercase tracking-wider block">Vulnerable Code Snippet:</span>
                  <pre className="bg-black/90 border border-rose-500/20 rounded p-2 text-rose-300 overflow-x-auto text-[9px] leading-relaxed">
                    <code>{selectedFinding.code_snippet}</code>
                  </pre>
                </div>
              )}

              {/* Remediation code blocks */}
              <div className="space-y-1.5 border-t border-purple-500/10 pt-3">
                <div className="flex items-center gap-1.5 text-emerald-400 font-bold uppercase tracking-wider text-[10px]">
                  <RefreshCw size={12} className="animate-spin-slow" />
                  <span>Defensive Remediation Protocol</span>
                </div>
                <p className="text-gray-300 leading-relaxed bg-emerald-500/5 border border-emerald-500/10 rounded p-2.5">
                  {selectedFinding.remediation_explanation || 'Utilize strict validation filters and enforce secure credential management configurations.'}
                </p>
                {selectedFinding.remediation_code && (
                  <pre className="bg-black/95 border border-emerald-500/20 rounded p-2 text-emerald-300 overflow-x-auto text-[9px] leading-relaxed">
                    <code>{selectedFinding.remediation_code}</code>
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="text-gray-500 h-full flex flex-col items-center justify-center gap-2">
              <ShieldAlert size={20} className="text-purple-500/20" />
              <span>Select a vulnerability finding record to inspect security mitigations.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
