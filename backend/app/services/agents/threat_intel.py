import logging
from typing import List, Dict, Any
from app.services.agents.llm_client import llm_client

logger = logging.getLogger(__name__)

# Curated CWE → MITRE ATT&CK / CAPEC correlation database.
# Used as deterministic fallback when the LLM provider is unavailable.
THREAT_METRIC_DB = {
    "CWE-89": {
        "mitre_attack": "T1190: Exploit Public-Facing Application",
        "capec": "CAPEC-66: SQL Injection",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "SQL Injection represents one of the oldest and most dangerous vector "
            "categories. Exploited by APT actors (e.g., APT29, Cozy Bear) to compromise "
            "state databases and exfiltrate primary configurations."
        ),
    },
    "CWE-78": {
        "mitre_attack": "T1203: Exploitation for Client Execution",
        "capec": "CAPEC-88: OS Command Injection",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "OS Command injection allows direct control of the terminal pipeline. "
            "Frequently exploited by ransomware syndicates (like LockBit) to download "
            "staging beacons (e.g. Cobalt Strike) and achieve initial access."
        ),
    },
    "CWE-79": {
        "mitre_attack": "T1189: Drive-by Compromise",
        "capec": "CAPEC-63: Cross-Site Scripting (XSS)",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Cross-Site Scripting allows execution of malicious payloads in client "
            "browsers. Frequently targeted in financial theft and session hijacking."
        ),
    },
    "CWE-798": {
        "mitre_attack": "T1552: Unsecured Credentials (Credentials in Files)",
        "capec": "CAPEC-150: Collect Credentials from Repositories",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Hardcoded keys in public and internal repositories represent the primary "
            "driver of cloud account hijackings. Automated credential harvesters scrape "
            "commits within seconds of upload."
        ),
    },
    "CWE-328": {
        "mitre_attack": "T1553: Subvert Trust Controls",
        "capec": "CAPEC-97: Cryptographic Collision Exploitation",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Cryptographic vulnerabilities allow adversaries to forge trust signatures "
            "or perform hash-collision forgery. Deprecated hashing like MD5 allows "
            "rapid collision synthesis."
        ),
    },
    "CWE-95": {
        "mitre_attack": "T1210: Exploitation of Remote Services",
        "capec": "CAPEC-242: Direct Code Execution",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Arbitrary Python execution bypasses standard access control systems. "
            "Allows immediate web shell installation and lateral host movement."
        ),
    },
    "CWE-1395": {
        "mitre_attack": "T1195: Supply Chain Compromise",
        "capec": "CAPEC-310: Dependency Injection",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Supply chain poisoning targets dependencies inside developer frameworks. "
            "Exploits out-of-date and unpatched utilities to execute high-severity "
            "remote codes."
        ),
    },
    "CWE-22": {
        "mitre_attack": "T1083: File and Directory Discovery",
        "capec": "CAPEC-126: Path Traversal",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Directory traversal allows adversaries to read arbitrary files from the "
            "server file system. Combined with credential exposure it enables full "
            "infrastructure compromise."
        ),
    },
    "CWE-200": {
        "mitre_attack": "T1005: Data from Local System",
        "capec": "CAPEC-118: Collect and Analyze Information",
        "nvd_url": "https://nvd.nist.gov/vuln/search",
        "intel_summary": (
            "Information exposure vulnerabilities leak sensitive system data that "
            "adversaries leverage for privilege escalation and lateral movement."
        ),
    },
}


class ThreatIntelAgent:
    def __init__(self):
        self.name = "Threat Intelligence Agent"
        self.description = (
            "Maps internal static vulnerabilities to global CVE/CWE databases "
            "and active threat group attack matrices (MITRE ATT&CK)."
        )

    def enrich_findings(
        self, findings: List[Dict[str, Any]], scan_callback=None
    ) -> List[Dict[str, Any]]:
        if scan_callback:
            scan_callback(
                self.name,
                "Correlating discovered code patterns against NVD databases...",
                "info",
            )

        enriched_findings = []
        for idx, f in enumerate(findings):
            cwe = f.get("cwe", "")

            system_prompt = """You are an expert Cyber Threat Intelligence Analyst and MITRE ATT&CK/CAPEC specialist.
Your task is to take a vulnerability finding and enrich it with professional threat intelligence data.

You must respond ONLY with a JSON object containing exactly these five keys:
- 'cve': string (e.g. 'CVE-2023-42115' or most relevant vulnerability match)
- 'mitre_attack': string (e.g. 'T1190: Exploit Public-Facing Application')
- 'capec_mapping': string (e.g. 'CAPEC-66: SQL Injection')
- 'nvd_url': string (e.g. 'https://nvd.nist.gov/vuln/detail/CVE-2023-42115')
- 'threat_intelligence_context': string (A professional analysis detailing which threat groups, ransomware syndicates, or APT actors exploit this weakness, and the standard operational impact of a successful breach.)
"""

            user_prompt = f"""Enrich the following vulnerability finding:
Finding Title: {f.get('title')}
CWE ID: {cwe}
Severity: {f.get('severity', 'Medium')}
File Path: {f.get('file_path')}
Vulnerable Code Snippet:
{f.get('code_snippet')}

Provide the professional Threat Intelligence context in JSON format."""

            # Deterministic fallback — no random values; use CWE-keyed database or N/A.
            intel = THREAT_METRIC_DB.get(cwe)
            if intel:
                fallback_dict = {
                    "cve": f.get("cve") or "N/A",
                    "mitre_attack": intel["mitre_attack"],
                    "capec_mapping": intel["capec"],
                    "nvd_url": intel["nvd_url"],
                    "threat_intelligence_context": intel["intel_summary"],
                }
            else:
                fallback_dict = {
                    "cve": f.get("cve") or "N/A",
                    "mitre_attack": f.get("mitre_attack") or "N/A",
                    "capec_mapping": "N/A",
                    "nvd_url": "https://nvd.nist.gov/vuln/search",
                    "threat_intelligence_context": (
                        f"Vulnerability classified under {cwe or 'unknown CWE'}. "
                        "Correlate with NVD and MITRE ATT&CK for active exploitation context."
                    ),
                }

            llm_result = llm_client.generate_structured_json(
                system_prompt, user_prompt, fallback_dict
            )

            enriched_f = {
                **f,
                "cve": llm_result.get("cve", fallback_dict["cve"]),
                "mitre_attack": llm_result.get(
                    "mitre_attack", fallback_dict["mitre_attack"]
                ),
                "capec_mapping": llm_result.get(
                    "capec_mapping", fallback_dict["capec_mapping"]
                ),
                "nvd_url": llm_result.get("nvd_url", fallback_dict["nvd_url"]),
                "threat_intelligence_context": llm_result.get(
                    "threat_intelligence_context",
                    fallback_dict["threat_intelligence_context"],
                ),
            }
            enriched_findings.append(enriched_f)

            if scan_callback:
                scan_callback(
                    self.name,
                    f"Mapped threat intelligence to finding: {f['title']} -> {enriched_f['cve']}",
                    "info",
                )

        if scan_callback:
            scan_callback(
                self.name,
                f"Finished threat vector correlation for {len(findings)} findings.",
                "success",
            )

        return enriched_findings
