import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class MLAgent:
    def __init__(self):
        self.name = "Machine Learning Agent"
        self.description = "Computes scan risk from observed code metrics, finding severity, and anomaly indicators."

    def assess_risk(
        self,
        findings: List[Dict[str, Any]],
        target_path: str,
        scan_callback=None,
    ) -> Dict[str, Any]:
        """Compute risk metrics from actual scan artifacts and findings."""
        if scan_callback:
            scan_callback(
                self.name,
                "Extracting codebase metrics and severity features from scanned artifacts...",
                "info",
            )

        loc = self._count_lines_of_code(target_path)
        num_findings = len(findings)
        critical_count = sum(1 for f in findings if f.get("severity") == "Critical")
        high_count = sum(1 for f in findings if f.get("severity") == "High")
        medium_count = sum(1 for f in findings if f.get("severity") == "Medium")
        low_count = sum(1 for f in findings if f.get("severity") == "Low")

        secret_findings = sum(1 for f in findings if f.get("cwe") == "CWE-798")
        injection_findings = sum(
            1 for f in findings if f.get("cwe") in {"CWE-78", "CWE-89", "CWE-95"}
        )
        secret_density = round(secret_findings / max(1, loc / 1000), 4)
        finding_density = round(num_findings / max(1, loc / 1000), 4)

        severity_score = (
            critical_count * 30
            + high_count * 15
            + medium_count * 8
            + low_count * 2
        )
        density_score = min(20.0, finding_density * 1.5)
        injection_score = min(15.0, injection_findings * 5.0)
        secret_score = min(15.0, secret_density * 2.5)

        final_score = round(
            min(100.0, severity_score + density_score + injection_score + secret_score),
            1,
        )
        risk_class = self._risk_class(final_score)
        is_anomaly = bool(
            critical_count > 0
            or secret_density >= 2.0
            or finding_density >= 20.0
            or injection_findings >= 3
        )
        anomaly_score = round(
            min(1.0, (finding_density / 40.0) + (secret_density / 10.0)),
            4,
        )

        if scan_callback:
            scan_callback(
                self.name,
                f"Synthesized risk profile: Risk Class={risk_class}, Score={final_score}, Anomaly={is_anomaly}",
                "success",
            )

        return {
            "risk_score": final_score,
            "risk_class": risk_class,
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "feature_vector": {
                "loc": loc,
                "findings_count": num_findings,
                "finding_density_per_kloc": finding_density,
                "secret_density_per_kloc": secret_density,
                "injection_findings": injection_findings,
            },
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
        }

    def _count_lines_of_code(self, target_path: str) -> int:
        source_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".kt",
            ".php",
            ".rb",
            ".cs",
            ".html",
            ".css",
            ".yml",
            ".yaml",
            ".json",
            ".toml",
        }

        paths: list[str] = []
        if os.path.isfile(target_path):
            paths.append(target_path)
        elif os.path.isdir(target_path):
            for root, dirs, files in os.walk(target_path):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in {".git", "__pycache__", "node_modules", "dist", "build", ".next", ".venv", "venv"}
                ]
                for filename in files:
                    if os.path.splitext(filename)[1].lower() in source_extensions:
                        paths.append(os.path.join(root, filename))

        loc = 0
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    loc += sum(1 for line in handle if line.strip())
            except Exception as exc:
                logger.exception("Failed to count lines of code | file=%s | error=%s", path, exc)
        return max(loc, 1)

    def _risk_class(self, score: float) -> int:
        if score >= 80:
            return 3
        if score >= 50:
            return 2
        if score >= 20:
            return 1
        return 0
