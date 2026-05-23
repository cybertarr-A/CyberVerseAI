import { create } from 'zustand';

import { 
  Project, 
  Scan, 
  Finding, 
  AgentLog, 
  TelemetryData, 
  AgentTelemetry 
} from '../types';


interface CyberState {
  projects: Project[];
  activeProject: Project | null;
  scans: Scan[];
  activeScan: Scan | null;
  logs: AgentLog[];
  phase: 'idle' | 'parsing' | 'analyzing' | 'enriching' | 'scoring' | 'reporting' | 'done' | 'failed';
  progress: number;
  findings: Finding[];
  selectedFinding: Finding | null;
  telemetry: TelemetryData | null;
  agents: Record<string, AgentTelemetry>;
  wsConnection: WebSocket | null;
  
  // Actions
  fetchProjects: () => Promise<void>;
  selectProject: (proj: Project) => void;
  createProject: (name: string, desc: string) => Promise<void>;
  fetchScans: () => Promise<void>;
  fetchTelemetry: () => Promise<void>;
  loadScanDetails: (scanId: string) => Promise<void>;
  startFileScan: (targetName: string, codeContent?: string, fileBlob?: File) => Promise<string>;
  startGitScan: (gitUrl: string) => Promise<string>;
  connectWebSocket: (scanId: string) => void;
  disconnectWebSocket: () => void;
  clearScanState: () => void;
}

const BACKEND_REST_URL =
  process.env.NEXT_PUBLIC_BACKEND_REST_URL ||
  "https://cyberverseai-production.up.railway.app/api/v1";

const BACKEND_WS_URL =
  process.env.NEXT_PUBLIC_BACKEND_WS_URL ||
  "wss://cyberverseai-production.up.railway.app";

console.log("REST URL:", BACKEND_REST_URL);
console.log("WS URL:", BACKEND_WS_URL);

const initialAgents: Record<string, AgentTelemetry> = {
  "Orchestrator AI": { status: 'IDLE', lastInstruction: 'Awaiting target dispatch...', load: 0 },
  "Code Analysis Agent": { status: 'IDLE', lastInstruction: 'Awaiting AST mapping...', load: 0 },
  "Security Review Agent": { status: 'IDLE', lastInstruction: 'Awaiting vulnerability piping...', load: 0 },
  "Threat Intelligence Agent": { status: 'IDLE', lastInstruction: 'Awaiting CWE metadata lookup...', load: 0 },
  "Machine Learning Agent": { status: 'IDLE', lastInstruction: 'Awaiting features array...', load: 0 },
  "Report Agent": { status: 'IDLE', lastInstruction: 'Awaiting compile signals...', load: 0 },
};

export const useCyberStore = create<CyberState>((set, get) => ({
  projects: [],
  activeProject: null,
  scans: [],
  activeScan: null,
  logs: [],
  phase: 'idle',
  progress: 0,
  findings: [],
  selectedFinding: null,
  telemetry: null,
  agents: initialAgents,
  wsConnection: null,

  fetchProjects: async () => {
    try {
      const res = await fetch(`${BACKEND_REST_URL}/projects`);
      if (res.ok) {
        const data = await res.json();
        set({ projects: data });
        if (data.length > 0 && !get().activeProject) {
          set({ activeProject: data[0] });
        }
      }
    } catch (err) {
      console.error('Error loading projects:', err);
    }
  },

  selectProject: (proj: Project) => {
    set({ activeProject: proj });
  },

  createProject: async (name: string, desc: string) => {
    try {
      const res = await fetch(`${BACKEND_REST_URL}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description: desc })
      });
      if (res.ok) {
        await get().fetchProjects();
      }
    } catch (err) {
      console.error('Error creating project:', err);
    }
  },

  fetchScans: async () => {
    try {
      const res = await fetch(`${BACKEND_REST_URL}/scans`);
      if (res.ok) {
        const data = await res.json();
        set({ scans: data });
      }
    } catch (err) {
      console.error('Error loading scans:', err);
    }
  },

  fetchTelemetry: async () => {
    try {
      const res = await fetch(`${BACKEND_REST_URL}/telemetry`);
      if (res.ok) {
        const data = await res.json();
        set({ telemetry: data });
      }
    } catch (err) {
      console.error('Error loading telemetry:', err);
    }
  },

  loadScanDetails: async (scanId: string) => {
    try {
      const res = await fetch(`${BACKEND_REST_URL}/scans/${scanId}`);
      if (res.ok) {
        const data = await res.json();
        set({
          activeScan: data.scan,
          findings: data.findings,
          logs: data.activities.map((a: any) => ({
            agent_name: a.agent_name,
            message: a.message,
            type: a.type,
            timestamp: a.timestamp
          })),
          phase: data.scan.current_phase,
          progress: data.scan.progress,
          selectedFinding: data.findings.length > 0 ? data.findings[0] : null
        });
        
        // If scan is done, set agents to completed
        if (data.scan.status === 'completed') {
          const finishedAgents = { ...initialAgents };
          Object.keys(finishedAgents).forEach(k => {
            finishedAgents[k] = { status: 'COMPLETED', lastInstruction: 'Job finalized.', load: 0 };
          });
          set({ agents: finishedAgents });
        }
      }
    } catch (err) {
      console.error('Error loading scan details:', err);
    }
  },

  startFileScan: async (targetName: string, codeContent?: string, fileBlob?: File) => {
    const proj = get().activeProject;
    if (!proj) throw new Error('No active project found');

    // Create form data
    const formData = new FormData();
    formData.append('project_id', proj.id.toString());
    formData.append('target_name', targetName);
    
    if (codeContent) {
      formData.append('code_content', codeContent);
    } else if (fileBlob) {
      formData.append('file', fileBlob);
    }

    const res = await fetch(`${BACKEND_REST_URL}/scans/file`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      throw new Error('Failed to initiate code scan session');
    }

    const data = await res.json();
    set({
      phase: 'parsing',
      progress: 5,
      findings: [],
      selectedFinding: null,
      logs: [],
      agents: {
        ...initialAgents,
        "Orchestrator AI": { status: 'PROCESSING', lastInstruction: 'Setting up sandbox folders...', load: 45 }
      }
    });

    get().connectWebSocket(data.scan_id);
    await get().fetchScans();
    return data.scan_id;
  },

  startGitScan: async (gitUrl: string) => {
    const proj = get().activeProject;
    if (!proj) throw new Error('No active project found');

    const formData = new FormData();
    formData.append('project_id', proj.id.toString());
    formData.append('git_url', gitUrl);

    const res = await fetch(`${BACKEND_REST_URL}/scans/git`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      throw new Error('Failed to initiate Git repository scan');
    }

    const data = await res.json();
    set({
      phase: 'parsing',
      progress: 5,
      findings: [],
      selectedFinding: null,
      logs: [],
      agents: {
        ...initialAgents,
        "Orchestrator AI": { status: 'PROCESSING', lastInstruction: 'Cloning and checking out tree...', load: 50 }
      }
    });

    get().connectWebSocket(data.scan_id);
    await get().fetchScans();
    return data.scan_id;
  },

  connectWebSocket: (scanId: string) => {
    get().disconnectWebSocket();

    const wsUrl = `${BACKEND_WS_URL}/ws/scan/${scanId}`;
    console.log("Connecting WebSocket:", wsUrl);
    
    const ws = new WebSocket(wsUrl);

/* store immediately */
set({
  wsConnection: ws
});

ws.onopen = () => {
  console.log(
    "WebSocket connected:",
    scanId
  );
};

    ws.onerror = (event) => {
      console.error("WebSocket error:", event);
    };

    ws.onclose = (event) => {
      console.log("WebSocket closed:", event.code);
      set({ wsConnection: null });
    };
    
    ws.onmessage = async (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        console.warn('WebSocket received non-JSON message:', event.data);
        return;
      }
      if (msg.event === 'log') {
        const item: AgentLog = msg.data;
        
        // Set agent telemetry statuses based on logs
        const updatedAgents = { ...get().agents };
        const agent = item.agent_name;
        
        // Telemetry dynamics
        if (updatedAgents[agent]) {
          const currentProgress = get().progress;
          updatedAgents[agent] = {
            status: item.type === 'success' ? 'COMPLETED' : 'PROCESSING',
            lastInstruction: item.message,
            load: item.type === 'success' ? 0 : Math.min(95, Math.max(10, currentProgress))
          };
        }
        
        // Highlight when next agent gets called
        if (agent === "Code Analysis Agent" && item.type !== 'success') {
          updatedAgents["Orchestrator AI"] = { status: 'PROCESSING', lastInstruction: 'Inspecting AST parser callback...', load: 20 };
        } else if (agent === "Security Review Agent" && item.type !== 'success') {
          updatedAgents["Code Analysis Agent"] = { status: 'COMPLETED', lastInstruction: 'Baseline scan saved.', load: 0 };
        } else if (agent === "Threat Intelligence Agent" && item.type !== 'success') {
          updatedAgents["Security Review Agent"] = { status: 'COMPLETED', lastInstruction: 'Security models review finalized.', load: 0 };
        } else if (agent === "Machine Learning Agent" && item.type !== 'success') {
          updatedAgents["Threat Intelligence Agent"] = { status: 'COMPLETED', lastInstruction: 'NVD correlation finished.', load: 0 };
        }

        set({
          logs: [...get().logs, item],
          agents: updatedAgents
        });
      } else if (msg.event === 'status') {
        const phaseName = msg.data.phase;
        const progressVal = msg.data.progress;
        set({ phase: phaseName, progress: progressVal });
      } else if (msg.event === 'completed') {
        await get().loadScanDetails(scanId);
        await get().fetchScans();
        await get().fetchTelemetry();
        get().disconnectWebSocket();
      } else if (msg.event === 'failed') {
        set({
           phase: "failed",
           progress: 100
        });

        get().disconnectWebSocket();
      }
    };
  },

  disconnectWebSocket: () => {
    const ws = get().wsConnection;
    if (ws) {
      ws.close();
      set({ wsConnection: null });
    }
  },

  clearScanState: () => {
    set({
      activeScan: null,
      findings: [],
      selectedFinding: null,
      logs: [],
      phase: 'idle',
      progress: 0,
      agents: initialAgents
    });
  }
}));
