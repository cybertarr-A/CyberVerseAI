import logging
from typing import List, Dict, Any
from app.services.agents.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SecurityReviewerAgent:
    def __init__(self):
        self.name = "Security Review Agent"
        self.description = "Audits logic against OWASP core benchmarks, generates deep structural remediation protocols, and provides secure code examples."

    def review_findings(self, findings: List[Dict[str, Any]], scan_callback=None) -> List[Dict[str, Any]]:
        if scan_callback:
            scan_callback(self.name, "Benchmarking vulnerabilities against OWASP Top 10 vulnerabilities...", "info")

        reviewed_findings = []
        for idx, f in enumerate(findings):
            # Formulate structured LLM review prompts
            cwe = f.get("cwe", "")
            
            system_prompt = """You are an elite, world-class Senior Security Auditor and OWASP benchmark expert.
Your job is to review a security vulnerability finding, map it to the correct OWASP category, write a comprehensive, clear, and action-oriented explanation of how it should be remediated, and provide a secure, drop-in code fix.

You must respond ONLY with a JSON object containing exactly these three keys:
- 'owasp_category': string (e.g. 'A03:2021-Injection (SQL Injection)')
- 'remediation_explanation': string (deep explanation of root cause and secure fix guidelines)
- 'remediation_code': string (a clean, syntactically correct, commented code block illustrating the secure implementation)
"""

            user_prompt = f"""Review the following security vulnerability finding:
Finding Title: {f.get('title')}
CWE ID: {cwe}
Severity: {f.get('severity', 'Medium')}
File Path: {f.get('file_path')}
Line Number: {f.get('line_number')}
Vulnerable Code Snippet:
{f.get('code_snippet')}

Provide the detailed secure audit and code remedy in JSON format."""

            # Static Fallback mapping values
            fallback_owasp = self._map_cwe_to_owasp(cwe)
            fallback_remediation = self._generate_remediation_content(cwe, f.get("code_snippet", ""))
            fallback_dict = {
                "owasp_category": fallback_owasp,
                "remediation_explanation": fallback_remediation["explanation"],
                "remediation_code": fallback_remediation["secure_code"]
            }

            # Query LLM client with fallback
            logger_message = f"Invoking AI Security Agent to review vulnerability: {f.get('title')}..."
            if scan_callback:
                scan_callback(self.name, logger_message, "info")

            llm_result = LLMClient.get_instance().generate_structured_json(system_prompt, user_prompt, fallback_dict)

            reviewed_f = {
                **f,
                "owasp_category": llm_result.get("owasp_category", fallback_owasp),
                "remediation_explanation": llm_result.get("remediation_explanation", fallback_remediation["explanation"]),
                "remediation_code": llm_result.get("remediation_code", fallback_remediation["secure_code"]),
            }
            reviewed_findings.append(reviewed_f)
            
            if scan_callback:
                scan_callback(self.name, f"Completed AI review of finding #{idx+1}: {f['title']}", "info")

        if scan_callback:
            scan_callback(self.name, f"Finished security review of all {len(findings)} findings.", "success")
            
        return reviewed_findings

    def _map_cwe_to_owasp(self, cwe: str) -> str:
        cwe_map = {
            "CWE-89": "A03:2021-Injection (SQL Injection)",
            "CWE-78": "A03:2021-Injection (Command Injection)",
            "CWE-79": "A03:2021-Injection (Cross-Site Scripting)",
            "CWE-798": "A07:2021-Identification and Authentication Failures (Hardcoded Credentials)",
            "CWE-328": "A02:2021-Cryptographic Failures (Weak Hashing)",
            "CWE-95": "A03:2021-Injection (Unsafe eval/exec)",
            "CWE-1395": "A06:2021-Vulnerable and Outdated Components",
            "CWE-22": "A01:2021-Broken Access Control (Directory Traversal)",
            "CWE-200": "A01:2021-Broken Access Control (Credential Exposure)"
        }
        return cwe_map.get(cwe, "A04:2021-Insecure Design")

    def _generate_remediation_content(self, cwe: str, snippet: str) -> Dict[str, str]:
        if cwe == "CWE-89": # SQL Injection
            return {
                "explanation": "Replace raw dynamic string interpolation with parameterized SQL query bindings. Modern database drivers ensure user-supplied input is sanitized and treated purely as parameters rather than executable commands.",
                "secure_code": "query = \"SELECT * FROM users WHERE username = %s\"\ncursor.execute(query, (user_input,))"
            }
        elif cwe == "CWE-78": # Command Injection
            return {
                "explanation": "Do not pass user string expressions directly to shells or use subprocess with shell=True. Pass arguments as a list and disable shell execution so shell commands cannot be combined.",
                "secure_code": "import subprocess\nsubprocess.Popen([\"ping\", \"-c\", \"1\", user_ip], shell=False)"
            }
        elif cwe == "CWE-79": # XSS
            return {
                "explanation": "Ensure all user-controlled dynamic strings are properly escaped or sanitized before inserting them into HTML pages. In frontend frameworks, avoid using direct HTML insertion props like .innerHTML or dangerouslySetInnerHTML.",
                "secure_code": "import DOMPurify from 'dompurify';\nconst cleanHTML = DOMPurify.sanitize(renderedUserContent);\nelement.innerHTML = cleanHTML;"
            }
        elif cwe == "CWE-798": # Secrets
            return {
                "explanation": "Never store credentials, private keys, API secrets, or certificates inside code repositories. Load credentials at runtime from system environment variables or query a high-security key vault (e.g. AWS Secrets Manager, HashiCorp Vault).",
                "secure_code": "import os\nservice_api_key = os.getenv(\"SERVICE_API_KEY\")\nif not service_api_key:\n    raise RuntimeError(\"Missing SERVICE_API_KEY environment variable\")"
            }
        elif cwe == "CWE-328": # Weak hash
            return {
                "explanation": "Replace insecure cryptographic hash algorithms (MD5, SHA1) with secure alternatives (SHA-256, SHA-3) or slow hashing schemes designed specifically for secrets (bcrypt, Argon2, PBKDF2).",
                "secure_code": "import hashlib\nhash_obj = hashlib.sha256(value.encode())\nsecure_hash = hash_obj.hexdigest()"
            }
        elif cwe == "CWE-95": # eval/exec
            return {
                "explanation": "Avoid using eval() and exec() entirely. To parse structured text like configurations, use safe parsers like json.loads() or ast.literal_eval() which are strictly restricted to evaluating static primitives.",
                "secure_code": "import json\ndata = json.loads(user_string)"
            }
        elif cwe == "CWE-1395" or cwe == "CWE-22": # Vulnerable framework or Directory Traversal
            return {
                "explanation": "Update the affected package library immediately in requirements.txt or package.json to the latest secure version. Clean user file inputs before referencing file systems to avoid traversal paths.",
                "secure_code": "from pathlib import Path\nbase_dir = Path(\"/var/www\").resolve()\nsafe_filename = Path(user_filename).name\nfile_path = (base_dir / safe_filename).resolve()\nif base_dir not in file_path.parents and file_path != base_dir:\n    raise ValueError(\"Access denied: directory traversal path detected\")"
            }
        else:
            return {
                "explanation": "Implement input sanitization, strict pattern validation, and apply the principle of least privilege across database, network, and file system bounds.",
                "secure_code": "if not input_val.isalnum():\n    raise ValueError(\"Invalid characters detected\")"
            }
