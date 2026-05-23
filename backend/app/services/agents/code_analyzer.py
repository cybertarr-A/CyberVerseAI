import os
import json
import logging
import re
import tomllib
from pathlib import Path
from typing import List, Dict, Any
from packaging import version
from packaging.version import InvalidVersion
from app.services.analyzer.ast_analyzer import StaticSecurityScanner, redact_secrets_in_text
from app.services.agents.llm_client import llm_client

logger = logging.getLogger(__name__)


class CodeAnalyzerAgent:
    def __init__(self):
        self.name = "Code Analysis Agent"
        self.description = "Performs deep static code audits, AST structural parsing, and credential scanning."

    def analyze(self, target_path: str, scan_callback=None) -> List[Dict[str, Any]]:
        """Scans the directory structure or individual file and returns baseline findings."""
        if scan_callback:
            scan_callback(self.name, "Initializing Tree-sitter and AST analyzer matrices...", "info")

        findings = []
        
        # 1. Run Core Static Heuristic Scan (Regex & AST)
        if os.path.isdir(target_path):
            if scan_callback:
                scan_callback(self.name, f"Traversing project structure: {target_path}", "info")
            findings = StaticSecurityScanner.scan_project_directory(target_path)
            
            # Hybrid AI semantic pass over source files
            for root, _, files in os.walk(target_path):
                for file in files:
                    if any(x in root for x in ["venv", ".git", "node_modules", "dist", ".next"]):
                        continue
                    if file.endswith((".py", ".js", ".ts", ".tsx", ".html", ".go", ".rs")):
                        filepath = Path(root) / file
                        rel_path = os.path.relpath(str(filepath), target_path)
                        ai_findings = self._run_ai_semantic_audit(str(filepath), rel_path, scan_callback)
                        findings.extend(ai_findings)
        else:
            if scan_callback:
                scan_callback(self.name, f"Analyzing single code target file: {target_path}", "info")
            
            content = ""
            try:
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if target_path.endswith(".py"):
                    findings = StaticSecurityScanner.scan_python_code(target_path, content)
                else:
                    findings = StaticSecurityScanner.scan_generic_code(target_path, content)
            except Exception as e:
                logger.exception(
                    "Error scanning target file | agent=%s | path=%s | error=%s",
                    self.name, target_path, e,
                )
                if scan_callback:
                    scan_callback(self.name, f"Error scanning target file: {str(e)}", "error")

            # Run hybrid AI audit on single file
            if content:
                ai_findings = self._run_ai_semantic_audit(target_path, os.path.basename(target_path), scan_callback)
                findings.extend(ai_findings)

        # Insecure dependency package audits (searching requirements.txt or package.json)
        dep_findings = self._audit_dependencies(target_path)
        findings.extend(dep_findings)

        if scan_callback:
            scan_callback(self.name, f"Analysis complete. Found {len(findings)} initial vulnerability indicators.", "success")
            
        return findings

    def count_tokens(self, text: str) -> int:
        """Estimates the number of tokens in a given text block using standard char/whitespace ratios."""
        return max(1, len(text) // 4)

    def split_into_chunks(self, content: str, file_ext: str, chunk_size_lines: int = 150, overlap_lines: int = 30) -> List[Dict[str, Any]]:
        """
        Splits source code content into overlapping logical chunks.
        Adjusts chunk size and boundaries based on the file type (Python, JS, TS, Go, Rust)
        to optimize AST/logical boundaries and preserve context.
        """
        lines = content.splitlines()
        total_lines = len(lines)
        chunks = []
        
        # Adjust chunk parameters based on programming language characteristics
        if file_ext in [".py"]:
            # Python: slightly smaller chunks to avoid nesting deep scopes
            chunk_size_lines = 120
            overlap_lines = 25
        elif file_ext in [".js", ".ts", ".jsx", ".tsx"]:
            # Javascript / Typescript: typical nested structures, larger chunks
            chunk_size_lines = 160
            overlap_lines = 35
        elif file_ext in [".go", ".rs"]:
            # Go / Rust: strict syntax, procedural/functional
            chunk_size_lines = 180
            overlap_lines = 40

        start = 0
        while start < total_lines:
            end = min(start + chunk_size_lines, total_lines)
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)
            
            # Estimate token counts for the chunk (approx 4 chars per token)
            tokens = self.count_tokens(chunk_content)
            
            chunks.append({
                "start_line": start + 1,
                "end_line": end,
                "content": chunk_content,
                "token_count": tokens
            })
            
            if end == total_lines:
                break
            start += chunk_size_lines - overlap_lines
            
        return chunks

    def _run_ai_semantic_audit(self, abs_path: str, rel_path: str, scan_callback=None) -> List[Dict[str, Any]]:
        """Queries Claude-3.5 to spot high-level semantic flaws using language-aware sliding window chunking."""
        ai_findings = []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            file_ext = os.path.splitext(abs_path)[1].lower()
            
            # Implementation of Language-aware overlapping chunking
            chunks = self.split_into_chunks(content, file_ext)
            
            previous_context = []
            
            for idx, chunk in enumerate(chunks):
                # Build context to propagate information between chunks
                context_str = ""
                if previous_context:
                    context_str = f"Previously discovered issues in this file to maintain context: {', '.join(previous_context)}\n"

                system_prompt = """You are an elite AI Code Auditor specializing in identifying advanced application vulnerabilities, logical bugs, and security anti-patterns.
Inspect the given file content chunk and find any security weaknesses (e.g. broken authorization, input validation flaws, insecure state, unsafe library usage, unescaped output).

Respond ONLY with a JSON array of objects where each element contains strictly these five keys:
- 'title': string (short title of finding)
- 'description': string (clear explanation of vulnerability)
- 'severity': string ('Critical', 'High', 'Medium', or 'Low')
- 'line_number': integer (approximate line number where the issue occurs, relative to the overall file starting at line 1)
- 'cwe': string (CWE ID, e.g. 'CWE-20')

If no security vulnerabilities are found, respond exactly with: []
"""

                sanitized_chunk = redact_secrets_in_text(chunk["content"])

                user_prompt = f"""Audit the following source file chunk: '{rel_path}' (Lines {chunk['start_line']} to {chunk['end_line']})
Estimated chunk tokens: {chunk['token_count']}
{context_str}
Content:
```
{sanitized_chunk}
```

Identify any logical security flaws in this chunk and return the JSON findings array."""

                if scan_callback:
                    scan_callback(
                        self.name, 
                        f"Running deep semantic AI audit on: {rel_path} (Chunk {idx+1}/{len(chunks)} | Lines {chunk['start_line']}-{chunk['end_line']} | Tokens: {chunk['token_count']})...", 
                        "info"
                    )

                llm_result = llm_client.generate_structured_json(system_prompt, user_prompt, [])
                if isinstance(llm_result, list):
                    for item in llm_result:
                        title = item.get("title", "Logical Vulnerability")
                        # Add to context feedback loop for subsequent chunks
                        if title not in previous_context:
                            previous_context.append(title)
                        
                        # Capture exact snippet if possible
                        lines = content.splitlines()
                        line_no = item.get("line_number", 1)
                        snippet = lines[line_no - 1].strip() if line_no - 1 < len(lines) else ""
                        
                        # De-duplicate findings based on title and line number
                        is_duplicate = any(
                            f["title"] == title and abs(f["line_number"] - line_no) <= 3 
                            for f in ai_findings
                        )
                        if not is_duplicate:
                            ai_findings.append({
                                "title": title,
                                "description": item.get("description", "Semantic vulnerability flagged during hybrid AI audit."),
                                "severity": item.get("severity", "Medium"),
                                "file_path": rel_path,
                                "line_number": line_no,
                                "code_snippet": snippet,
                                "cwe": item.get("cwe", "CWE-200")
                            })
        except Exception as e:
            logger.exception(
                "AI semantic audit failed | agent=%s | file=%s | error=%s",
                self.name, rel_path, e,
            )
        return ai_findings

    def _audit_dependencies(self, target_path: str) -> List[Dict[str, Any]]:
        dep_findings = []
        
        # Manifest types we support and scan
        manifest_filenames = ["requirements.txt", "poetry.lock", "pyproject.toml", "package.json"]
        manifest_files = []
        
        if os.path.isfile(target_path):
            basename = os.path.basename(target_path)
            if basename in manifest_filenames:
                manifest_files.append(target_path)
        elif os.path.isdir(target_path):
            for filename in manifest_filenames:
                path = os.path.join(target_path, filename)
                if os.path.exists(path) and os.path.isfile(path):
                    manifest_files.append(path)
                    
        # Vulnerability rules matching: Django, Flask, Requests, FastAPI, urllib3, Express, React
        vulnerability_rules = {
            "django": {
                "fixed_version": "4.2.1",
                "severity": "Critical",
                "cve": None,
                "description": "Django version is older than the configured secure baseline. Upgrade to receive security fixes for known framework-level vulnerabilities."
            },
            "flask": {
                "fixed_version": "2.3.2",
                "severity": "High",
                "cve": None,
                "description": "Flask version is older than the configured secure baseline. Upgrade to receive security fixes in Flask and its supported dependency set."
            },
            "requests": {
                "fixed_version": "2.31.0",
                "severity": "Medium",
                "cve": "CVE-2023-32681",
                "description": "Requests before 2.31.0 leaks Proxy-Authorization headers during cross-origin redirects (CVE-2023-32681)."
            },
            "fastapi": {
                "fixed_version": "0.100.0",
                "severity": "High",
                "cve": None,
                "description": "FastAPI version is older than the configured secure baseline. Upgrade to receive framework and validation security fixes."
            },
            "urllib3": {
                "fixed_version": "1.26.16",
                "severity": "High",
                "cve": "CVE-2023-45803",
                "description": "urllib3 before 1.26.16 is susceptible to HTTP Request Smuggling due to header handling flaws."
            },
            "express": {
                "fixed_version": "4.19.2",
                "severity": "High",
                "cve": None,
                "description": "Express version is older than the configured secure baseline. Upgrade to receive security fixes across Express routing and middleware handling."
            },
            "react": {
                "fixed_version": "18.2.0",
                "severity": "Medium",
                "cve": None,
                "description": "React version is older than the configured secure baseline. Upgrade to receive security and rendering hardening fixes."
            }
        }
        
        for path in manifest_files:
            filename = os.path.basename(path)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                parsed_packages = [] # List of tuples: (package_name, version_str, line_number, raw_line)
                
                if filename == "requirements.txt":
                    for idx, line in enumerate(content.splitlines()):
                        line_num = idx + 1
                        cleaned = line.strip()
                        if not cleaned or cleaned.startswith("#"):
                            continue
                        # Split by version delimiters
                        parts = re.split(r'==|>=|<=|~=|@|>|<', cleaned)
                        if parts:
                            pkg_name = parts[0].strip().lower()
                            if len(parts) > 1:
                                ver_str = parts[1].split('#')[0].strip().strip('"\'')
                                ver_str = re.split(r'\s|;', ver_str)[0]
                                parsed_packages.append((pkg_name, ver_str, line_num, cleaned))
                                
                elif filename == "poetry.lock":
                    blocks = content.split("[[package]]")
                    current_pos = len(blocks[0]) + len("[[package]]") if len(blocks) > 1 else 0
                    for block in blocks[1:]:
                        name_match = re.search(r'name\s*=\s*"([^"]+)"', block)
                        version_match = re.search(r'version\s*=\s*"([^"]+)"', block)
                        if name_match and version_match:
                            pkg_name = name_match.group(1).lower().strip()
                            pkg_version = version_match.group(1).strip()
                            line_num = content[:current_pos].count("\n") + 1
                            parsed_packages.append((pkg_name, pkg_version, line_num, f'name = "{pkg_name}", version = "{pkg_version}"'))
                        current_pos += len(block) + len("[[package]]")
                        
                elif filename == "pyproject.toml":
                    parsed_packages.extend(self._parse_pyproject_dependencies(content))
                            
                elif filename == "package.json":
                    try:
                        data = json.loads(content)
                        deps = {}
                        if "dependencies" in data and isinstance(data["dependencies"], dict):
                            deps.update(data["dependencies"])
                        if "devDependencies" in data and isinstance(data["devDependencies"], dict):
                            deps.update(data["devDependencies"])
                            
                        lines = content.splitlines()
                        for pkg_name, raw_ver in deps.items():
                            pkg_name_lower = pkg_name.lower().strip()
                            pkg_version = re.sub(r'^[\^~>=<]+', '', str(raw_ver)).strip()
                            line_num = 1
                            raw_line = f'"{pkg_name}": "{raw_ver}"'
                            for idx, line in enumerate(lines):
                                if f'"{pkg_name}"' in line:
                                    line_num = idx + 1
                                    raw_line = line.strip()
                                    break
                            parsed_packages.append((pkg_name_lower, pkg_version, line_num, raw_line))
                    except Exception as json_err:
                        logger.exception(
                            "Failed to parse package.json JSON | agent=%s | file=%s | error=%s",
                            self.name,
                            path,
                            json_err,
                        )
                        
                # Perform version comparison audits
                for pkg_name, current_version, line_num, raw_line in parsed_packages:
                    if pkg_name in vulnerability_rules:
                        rule = vulnerability_rules[pkg_name]
                        fixed_version = rule["fixed_version"]
                        
                        try:
                            # Compare current version to fixed version using packaging.version
                            if version.parse(current_version) < version.parse(fixed_version):
                                dep_findings.append({
                                    "title": f"Vulnerable Dependency ({pkg_name})",
                                    "description": rule["description"],
                                    "severity": rule["severity"],
                                    "file_path": filename,
                                    "line_number": line_num,
                                    "code_snippet": raw_line,
                                    "cwe": "CWE-1395",
                                    "cve": rule.get("cve"),
                                    "confidence": "High",
                                    "package": pkg_name,
                                    "current_version": current_version,
                                    "fixed_version": fixed_version,
                                })
                        except (InvalidVersion, ValueError) as e:
                            logger.exception(
                                "Version parsing failed | agent=%s | package=%s | version=%s | error=%s",
                                self.name, pkg_name, current_version, e,
                            )

            except Exception as e:
                logger.exception(
                    "Dependency audit failed | agent=%s | file=%s | error=%s",
                    self.name, path, e,
                )
                
        return dep_findings

    def _parse_pyproject_dependencies(self, content: str) -> List[tuple[str, str, int, str]]:
        parsed: List[tuple[str, str, int, str]] = []
        line_lookup = content.splitlines()
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            logger.exception("Failed to parse pyproject.toml | agent=%s | error=%s", self.name, exc)
            return parsed

        candidates: list[str] = []
        project_deps = data.get("project", {}).get("dependencies", [])
        if isinstance(project_deps, list):
            candidates.extend(str(dep) for dep in project_deps)

        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        if isinstance(optional_deps, dict):
            for deps in optional_deps.values():
                if isinstance(deps, list):
                    candidates.extend(str(dep) for dep in deps)

        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for package_name, raw_spec in poetry_deps.items():
                if package_name.lower() == "python":
                    continue
                if isinstance(raw_spec, str):
                    candidates.append(f"{package_name}{raw_spec}")
                elif isinstance(raw_spec, dict) and raw_spec.get("version"):
                    candidates.append(f"{package_name}{raw_spec['version']}")

        for candidate in candidates:
            match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*([<>=!~^]+)\s*([^,\s;]+)", candidate)
            if not match:
                continue
            package_name = match.group(1).lower().replace("_", "-")
            package_version = re.sub(r"^[\^~>=<!=]+", "", match.group(3)).strip()
            line_num = 1
            raw_line = candidate
            for idx, line in enumerate(line_lookup):
                if package_name.replace("-", "_") in line.lower() or package_name in line.lower():
                    line_num = idx + 1
                    raw_line = line.strip()
                    break
            parsed.append((package_name, package_version, line_num, raw_line))

        return parsed
