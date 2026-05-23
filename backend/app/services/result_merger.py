import logging
from typing import List, Dict, Any

logger = logging.getLogger("cyberverse.result_merger")


class ResultMerger:
    @staticmethod
    def merge_results(results: List[Dict[str, Any]], failed_chunks: int, total_chunks: int) -> str:
        """
        Consolidates parallel chunk audit responses into a single high-quality Markdown report.
        """
        logger.info("Merging analysis results from %d parallel chunk tasks.", len(results))

        all_security = []
        all_architecture = []
        all_quality = []
        all_performance = []
        all_recommendations = []

        for r in results:
            if not isinstance(r, dict) or r.get("status") != "success":
                continue
            
            data = r.get("data", {})
            if not isinstance(data, dict):
                continue
                
            all_security.extend(data.get("security_findings") or [])
            all_architecture.extend(data.get("architecture_issues") or [])
            all_quality.extend(data.get("code_quality") or [])
            all_performance.extend(data.get("performance_concerns") or [])
            all_recommendations.extend(data.get("recommendations") or [])

        # Executive Summary counts
        critical_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "critical")
        high_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "high")
        medium_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "medium")
        low_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "low")

        sec_severity_summary = f"- Critical: {critical_count}\n- High: {high_count}\n- Medium: {medium_count}\n- Low: {low_count}"

        report_lines = []

        # Executive Summary
        report_lines.append("# Executive Summary")
        report_lines.append(f"CyberVerse AI completed a production-grade automated scan across **{total_chunks}** code chunks of the target codebase.")
        if failed_chunks > 0:
            report_lines.append(
                f"\n> [!WARNING]\n"
                f"> **{failed_chunks}** of **{total_chunks}** chunks encountered Nvidia NIM connection or timeout failures during scan pipelines. "
                f"These chunks were bypassed gracefully, and findings may be partially incomplete.\n"
            )
        
        report_lines.append("\n## Security Summary")
        report_lines.append(sec_severity_summary)
        
        report_lines.append("\n## Architecture & Quality Stats")
        report_lines.append(f"- Total Architectural Concerns: {len(all_architecture)}")
        report_lines.append(f"- Total Code Quality Issues: {len(all_quality)}")
        report_lines.append(f"- Total Performance Issues: {len(all_performance)}")

        # Security Findings
        report_lines.append("\n# Security Findings")
        if all_security:
            for idx, f in enumerate(all_security, 1):
                severity = f.get("severity", "Medium")
                title = f.get("title", "Logical Vulnerability")
                desc = f.get("description", "Vulnerability details.")
                file_path = f.get("file_path", "N/A")
                line_no = f.get("line_number", "N/A")
                report_lines.append(f"### {idx}. {title} [{severity}]")
                report_lines.append(f"- **Location:** `{file_path}:{line_no}`")
                report_lines.append(f"{desc}\n")
        else:
            report_lines.append("No security vulnerabilities were identified in the scanned codebase.\n")

        # Architecture Issues
        report_lines.append("\n# Architecture Issues")
        if all_architecture or all_quality:
            for idx, a in enumerate(all_architecture, 1):
                title = a.get("title", "Architectural Flaw")
                desc = a.get("description", "Flaw details.")
                severity = a.get("severity", "Medium")
                report_lines.append(f"### {idx}. {title} [{severity}]")
                report_lines.append(f"{desc}\n")

            if all_quality:
                report_lines.append("## Code Quality & Technical Debt")
                for idx, q in enumerate(all_quality, 1):
                    title = q.get("title", "Quality Concern")
                    desc = q.get("description", "Quality details.")
                    severity = q.get("severity", "Low")
                    report_lines.append(f"### {idx}. {title} [{severity}]")
                    report_lines.append(f"{desc}\n")
        else:
            report_lines.append("No architecture or code quality issues were identified.\n")

        # Performance Issues
        report_lines.append("\n# Performance Issues")
        if all_performance:
            for idx, p in enumerate(all_performance, 1):
                title = p.get("title", "Performance Bottleneck")
                desc = p.get("description", "Bottleneck details.")
                severity = p.get("severity", "Medium")
                report_lines.append(f"### {idx}. {title} [{severity}]")
                report_lines.append(f"{desc}\n")
        else:
            report_lines.append("No critical performance concerns were identified.\n")

        # Recommendations
        report_lines.append("\n# Recommendations")
        if all_recommendations:
            unique_recs = list(dict.fromkeys(all_recommendations))
            for idx, r in enumerate(unique_recs, 1):
                report_lines.append(f"{idx}. {r}")
        else:
            report_lines.append("Maintain standard dev/sec ops baselines and codebase hygiene.")

        logger.info("Consolidated Markdown report compiled successfully.")
        return "\n".join(report_lines)
