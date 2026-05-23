export interface Project {
  id: number;
  name: string;
  git_url?: string;
  description?: string;
  created_at: string;
}

export interface Scan {
  id: string;
  project_id: number;
  status: string;
  target_type: string;
  target_value: string;
  progress: number;
  current_phase: string;
  risk_score: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  created_at: string;
  completed_at?: string;
}

export interface Finding {
  id: number;
  scan_id: string;
  title: string;
  description: string;
  severity: string;
  file_path?: string;
  line_number?: number;
  code_snippet?: string;
  cwe?: string;
  cve?: string;
  mitre_attack?: string;
  remediation_explanation?: string;
  remediation_code?: string;
  owasp_category?: string;
}

export interface AgentLog {
  agent_name: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'error';
  timestamp: string;
}

export interface SystemStats {
  projects: number;
  scans: number;
  avg_risk: number;
  active_scanning: number;
}

export interface TelemetryData {
  stats: SystemStats;
  vulnerability_counts: {
    Critical: number;
    High: number;
    Medium: number;
    Low: number;
  };
  queue?: {
    queue: string;
    pending_tasks: number | null;
  };
  system?: {
    websocket_connections: number;
    active_scans: number;
    memory_rss_mb: number | null;
    memory_vms_mb?: number | null;
    cpu_percent?: number;
  };
  uptime_seconds?: number;
  recent_findings: Array<{
    id: number;
    title: string;
    severity: string;
    file: string;
    cwe: string;
    cve: string;
  }>;
}

export interface AgentTelemetry {
  status: 'IDLE' | 'PROCESSING' | 'COMPLETED';
  lastInstruction: string;
  load: number;
}
