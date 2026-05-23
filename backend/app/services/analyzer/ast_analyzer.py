import ast
import re
import os
import math
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# Common regex patterns for hardcoded secrets
SECRET_PATTERNS = {
    "Generic Password/Secret": re.compile(r'(?i)(password|passwd|secret|pass_phrase|private_key|auth_token|api_key|apikey|access_token|client_secret)\s*[:=]\s*["\']([^"\']{5,})["\']'),
    "AWS API Key": re.compile(r'AKIA[0-9A-Z]{16}'),
    "AWS Secret Access Key": re.compile(r'aws_secret_access_key\s*[:=]\s*["\']([0-9a-zA-Z+/]{40})["\']'),
    "Generic Private Key": re.compile(r'-----BEGIN [A-Z ]+ PRIVATE KEY-----'),
    "Stripe API Key": re.compile(r'sk_live_[0-9a-zA-Z]{24}'),
    "Slack Webhook URL": re.compile(r'https://hooks\.slack\.com/services/T[0-9A-Z]+/[0-9A-Z]+/([0-9a-zA-Z]{24})'),
    "GitHub Token": re.compile(r'gh[oprs]_[0-9a-zA-Z]{36}'),
}

def calculate_shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy of a string to assess if it's a high-entropy secret."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in range(256):
        p_x = float(data.count(chr(x))) / len(data)
        if p_x > 0:
            entropy += - p_x * math.log(p_x, 2)
    return entropy


def redact_secret_match(line: str, match: re.Match) -> str:
    """Redact only the secret value portion of a matched source line."""
    if len(match.groups()) > 1:
        start, end = match.span(2)
        return f"{line[:start]}[REDACTED]{line[end:]}"
    start, end = match.span(0)
    return f"{line[:start]}[REDACTED_SECRET]{line[end:]}"


def redact_secrets_in_text(content: str) -> str:
    """Redact known secret patterns before content is logged, stored, or sent to LLMs."""
    redacted_lines = []
    for line in content.splitlines():
        redacted = line
        for pattern in SECRET_PATTERNS.values():
            match = pattern.search(redacted)
            if match:
                redacted = redact_secret_match(redacted, match)
        redacted_lines.append(redacted)
    return "\n".join(redacted_lines)

class ASTSecurityVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str, lines: List[str]):
        self.filepath = filepath
        self.lines = lines
        self.findings: List[Dict[str, Any]] = []

    def add_finding(self, node: ast.AST, title: str, description: str, severity: str, cwe: str):
        line_num = getattr(node, 'lineno', 1)
        code_snippet = self.lines[line_num - 1].strip() if line_num - 1 < len(self.lines) else ""
        self.findings.append({
            "title": title,
            "description": description,
            "severity": severity,
            "file_path": self.filepath,
            "line_number": line_num,
            "code_snippet": code_snippet,
            "cwe": cwe,
            "confidence": "High",
        })

    def visit_Call(self, node: ast.Call):
        # 1. Detect weak hashing algorithms: hashlib.md5 or hashlib.sha1
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                if node.func.attr in ["md5", "sha1"]:
                    self.add_finding(
                        node,
                        title=f"Insecure Cryptographic Hash ({node.func.attr.upper()})",
                        description=f"Usage of weak cryptographic hashing algorithm {node.func.attr.upper()} detected. This algorithm is vulnerable to collision attacks and is deprecated for security contexts.",
                        severity="Medium",
                        cwe="CWE-328"
                    )
            
            # 2. Detect unsafe subprocess shell executions
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                if node.func.attr in ["Popen", "run", "call", "check_output"]:
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            self.add_finding(
                                node,
                                title="Subprocess Run with shell=True",
                                description="Running shell command via subprocess with shell=True is highly vulnerable to command injection. User-controlled strings can execute arbitrary shell commands.",
                                severity="High",
                                cwe="CWE-78"
                            )
            
            # 3. SQL injection: cursor.execute with dynamic SQL string formatting/concatenation
            if node.func.attr == "execute":
                if len(node.args) > 0:
                    first_arg = node.args[0]
                    is_unsafe = False
                    reason = ""
                    
                    # check for string formatting f"..."
                    if isinstance(first_arg, ast.JoinedStr):
                        is_unsafe = True
                        reason = "f-string formatting"
                    # check for string formatting % or .format()
                    elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                        is_unsafe = True
                        reason = "modulus string formatting"
                    elif isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute) and first_arg.func.attr == "format":
                        is_unsafe = True
                        reason = ".format() dynamic string construction"
                    
                    if is_unsafe:
                        self.add_finding(
                            node,
                            title="Potential SQL Injection",
                            description=f"Raw SQL query executed via cursor.execute using {reason}. Dynamic queries can lead to SQL Injection. Use parameterized query bindings instead.",
                            severity="High",
                            cwe="CWE-89"
                        )

        # 4. Detect eval/exec
        if isinstance(node.func, ast.Name):
            if node.func.id in ["eval", "exec"]:
                self.add_finding(
                    node,
                    title="Dangerous Code Execution (eval/exec)",
                    description=f"Using `{node.func.id}()` allows execution of dynamic, arbitrary Python code. If input is user-supplied, it leads to remote code execution.",
                    severity="Critical",
                    cwe="CWE-95"
                )
            
        # 5. Detect os.system calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                self.add_finding(
                    node,
                    title="Insecure Command Execution (os.system)",
                    description="Using os.system leads to easy shell command injection. Avoid using os.system; use subprocess with proper arguments list instead.",
                    severity="High",
                    cwe="CWE-78"
                )

            # 6. Detect unsafe deserialization via pickle.loads/load
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                if node.func.attr in ["load", "loads"]:
                    self.add_finding(
                        node,
                        title="Unsafe Pickle Deserialization",
                        description="pickle deserialization can execute arbitrary code when the input is attacker-controlled. Use a safe structured format such as JSON for untrusted data.",
                        severity="Critical",
                        cwe="CWE-502",
                    )

            # 7. Detect disabled TLS certificate verification in HTTP clients
            if node.func.attr in ["get", "post", "put", "delete", "patch", "request"]:
                for kw in node.keywords:
                    if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        self.add_finding(
                            node,
                            title="TLS Certificate Verification Disabled",
                            description="HTTP client call disables TLS certificate verification, enabling machine-in-the-middle attacks against outbound requests.",
                            severity="High",
                            cwe="CWE-295",
                        )

            # 8. Detect unsafe YAML loading without SafeLoader
            if node.func.attr == "load" and isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                has_safe_loader = any(
                    kw.arg in {"Loader", "loader"}
                    and isinstance(kw.value, ast.Attribute)
                    and kw.value.attr in {"SafeLoader", "CSafeLoader"}
                    for kw in node.keywords
                )
                if not has_safe_loader:
                    self.add_finding(
                        node,
                        title="Unsafe YAML Deserialization",
                        description="yaml.load without SafeLoader can construct arbitrary Python objects from attacker-controlled YAML content.",
                        severity="High",
                        cwe="CWE-502",
                    )

        self.generic_visit(node)

class StaticSecurityScanner:
    @staticmethod
    def scan_file_for_secrets(filepath: str, content: str) -> List[Dict[str, Any]]:
        findings = []
        lines = content.splitlines()
        
        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1
            for name, pattern in SECRET_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    # Filter out short or synthetic-looking strings to reduce false positives.
                    secret_val = match.group(2) if len(match.groups()) > 1 else match.group(0)
                    entropy = calculate_shannon_entropy(secret_val)
                    
                    # If regex matches specifically or entropy is high enough
                    if "Key" in name or "Token" in name or entropy > 3.0:
                        findings.append({
                            "title": f"Hardcoded {name}",
                            "description": f"A potential hardcoded sensitive item matches the pattern of a {name}. Storing credentials in plain text poses extreme supply chain and identity leak risks.",
                            "severity": "Critical" if "Key" in name or "Token" in name or "PrivateKey" in name else "High",
                            "file_path": filepath,
                            "line_number": line_num,
                            "code_snippet": redact_secret_match(line, match).strip(),
                            "cwe": "CWE-798",
                            "confidence": "High" if entropy > 3.5 else "Medium",
                        })
        return findings

    @staticmethod
    def scan_python_code(filepath: str, content: str) -> List[Dict[str, Any]]:
        findings = []
        
        # 1. Run Secrets scanner
        findings.extend(StaticSecurityScanner.scan_file_for_secrets(filepath, content))
        
        # 2. Run Python AST scanner
        try:
            tree = ast.parse(content, filename=filepath)
            lines = content.splitlines()
            visitor = ASTSecurityVisitor(filepath, lines)
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError as e:
            logger.warning(
                "AST parse failed for %s, using regex-only scan: %s", filepath, e
            )
            
        return findings

    @staticmethod
    def scan_generic_code(filepath: str, content: str) -> List[Dict[str, Any]]:
        """Fallback scanner for JS/TS/JSON/YAML/etc. using regex matching for XSS, SQLi, and Secrets."""
        findings = []
        findings.extend(StaticSecurityScanner.scan_file_for_secrets(filepath, content))
        
        # Simple string scans for generic code
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            line_num = idx + 1
            # XSS (innerHTML or dynamic insert)
            if "innerHTML" in line and ("+" in line or "`" in line):
                findings.append({
                    "title": "Potential DOM-based Cross-Site Scripting (XSS)",
                    "description": "Unescaped variable or HTML string assignment directly into .innerHTML can allow remote script execution.",
                    "severity": "High",
                    "file_path": filepath,
                    "line_number": line_num,
                    "code_snippet": line.strip(),
                    "cwe": "CWE-79",
                    "confidence": "Medium",
                })
            # SQL Injection indicators in NodeJS/JS
            if "query(" in line and ("+" in line or "`" in line) and any(kw in line.upper() for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
                findings.append({
                    "title": "Dynamic SQL Execution",
                    "description": "Concatenation of variables inside database query methods indicates potential SQL injection risks.",
                    "severity": "High",
                    "file_path": filepath,
                    "line_number": line_num,
                    "code_snippet": line.strip(),
                    "cwe": "CWE-89",
                    "confidence": "Medium",
                })
            if re.search(r"\beval\s*\(", line):
                findings.append({
                    "title": "Dangerous JavaScript eval Usage",
                    "description": "eval executes dynamic code and can become remote code execution or XSS when attacker-controlled strings reach it.",
                    "severity": "Critical",
                    "file_path": filepath,
                    "line_number": line_num,
                    "code_snippet": line.strip(),
                    "cwe": "CWE-95",
                    "confidence": "Medium",
                })
            if "dangerouslySetInnerHTML" in line:
                findings.append({
                    "title": "Unsafe React HTML Injection",
                    "description": "dangerouslySetInnerHTML bypasses React output escaping. Ensure content is sanitized with a proven sanitizer before rendering.",
                    "severity": "High",
                    "file_path": filepath,
                    "line_number": line_num,
                    "code_snippet": line.strip(),
                    "cwe": "CWE-79",
                    "confidence": "Medium",
                })
            if re.search(r"\bchild_process\.(exec|execSync)\s*\(", line):
                findings.append({
                    "title": "Node.js Shell Command Execution",
                    "description": "child_process exec APIs invoke a shell and can enable command injection when arguments include untrusted input. Prefer execFile/spawn with argument arrays.",
                    "severity": "High",
                    "file_path": filepath,
                    "line_number": line_num,
                    "code_snippet": line.strip(),
                    "cwe": "CWE-78",
                    "confidence": "Medium",
                })
                
        return findings

    @staticmethod
    def scan_project_directory(dir_path: str) -> List[Dict[str, Any]]:
        all_findings = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                # Skip virtualenvs, git, or build artifacts
                if any(x in root for x in ["venv", ".git", "__pycache__", "node_modules", "dist", "build", ".next"]):
                    continue
                
                filepath = Path(root) / file
                rel_path = os.path.relpath(str(filepath), dir_path)
                
                try:
                    with filepath.open("r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    if file.endswith(".py"):
                        all_findings.extend(StaticSecurityScanner.scan_python_code(rel_path, content))
                    elif file.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".yaml", ".yml", ".json")):
                        all_findings.extend(StaticSecurityScanner.scan_generic_code(rel_path, content))
                except Exception as e:
                    logger.exception(
                        f"Operation failed: {e} | File Path: {rel_path}"
                    )
                    
        return all_findings
