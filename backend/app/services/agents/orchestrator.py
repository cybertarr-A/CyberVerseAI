import asyncio
import datetime
import logging
from typing import List, Dict, Any

from app.services.agents.code_analyzer import CodeAnalyzerAgent
from app.services.agents.security_reviewer import SecurityReviewerAgent
from app.services.agents.threat_intel import ThreatIntelAgent
from app.services.agents.ml_agent import MLAgent
from app.services.agents.report_agent import ReportAgent

logger = logging.getLogger(__name__)


class ScanConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[Any]] = {}
        self._active_connections_count = 0
        self._failed_connections_count = 0

    @property
    def metrics(self) -> Dict[str, int]:
        return {
            "active_connections": self._active_connections_count,
            "failed_connections": self._failed_connections_count,
            "tracked_scans": len(self.active_connections),
        }

    def register(self, scan_id: str, websocket: Any):
        if scan_id not in self.active_connections:
            self.active_connections[scan_id] = []
        self.active_connections[scan_id].append(websocket)
        self._active_connections_count += 1
        logger.info(
            "[WS REGISTER] Registered websocket channel for Scan %s. Total active: %d",
            scan_id,
            self._active_connections_count,
        )

    def unregister(self, scan_id: str, websocket: Any):
        if scan_id in self.active_connections:
            if websocket in self.active_connections[scan_id]:
                self.active_connections[scan_id].remove(websocket)
                self._active_connections_count = max(0, self._active_connections_count - 1)
                logger.info(
                    "[WS UNREGISTER] Unregistered websocket channel for Scan %s. Total active: %d",
                    scan_id,
                    self._active_connections_count,
                )
            if not self.active_connections[scan_id]:
                del self.active_connections[scan_id]

    async def broadcast_event(self, scan_id: str, payload: Dict[str, Any]):
        if scan_id not in self.active_connections:
            return

        dead_channels = []
        channels = list(self.active_connections[scan_id])

        for connection in channels:
            try:
                await connection.send_json(payload)
            except Exception as e:
                self._failed_connections_count += 1
                dead_channels.append(connection)
                logger.exception(
                    "WebSocket broadcast failed | scan_id=%s | error=%s", scan_id, e
                )

        for dead_conn in dead_channels:
            self.unregister(scan_id, dead_conn)

    async def cancel_pending_tasks(self) -> None:
        """Compatibility hook for lifespan shutdown."""
        return None

    async def run_heartbeat_sweep(self):
        """
        Periodically send heartbeat pings and remove dead websocket clients.
        """
        logger.info("[WS HEARTBEAT] Initialized background connection heartbeat sweeper.")
        while True:
            await asyncio.sleep(15)
            scan_ids = list(self.active_connections.keys())

            for scan_id in scan_ids:
                if scan_id not in self.active_connections:
                    continue

                channels = list(self.active_connections[scan_id])
                dead_channels = []

                for connection in channels:
                    try:
                        await connection.send_json(
                            {
                                "event": "ping",
                                "timestamp": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(),
                            }
                        )
                    except Exception as e:
                        self._failed_connections_count += 1
                        dead_channels.append(connection)
                        logger.warning(
                            "[WS HEARTBEAT FAIL] Connection ping failed for Scan ID %s: %s. Marking as dead.",
                            scan_id,
                            e,
                        )

                for dead_conn in dead_channels:
                    self.unregister(scan_id, dead_conn)


ws_manager = ScanConnectionManager()


class OrchestratorAgent:
    def __init__(self):
        self.name = "Orchestrator AI"
        self.description = "Coordinates multi-agent scan execution plan, pipeline statuses, and dashboard telemetry."
        self.code_analyzer = CodeAnalyzerAgent()
        self.security_reviewer = SecurityReviewerAgent()
        self.threat_intel = ThreatIntelAgent()
        self.ml_agent = MLAgent()
        self.report_agent = ReportAgent()
