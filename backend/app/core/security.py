import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes and validates a filename to prevent path traversal, command injection,
    shell injection, and null-byte bypasses.
    
    Allowed characters: letters, numbers, underscores, dots, hyphens.
    Specifically rejects: null bytes, directory traversals, special shell characters.
    """
    if not filename:
        raise ValueError("Security violation: Filename cannot be empty.")

    # 1. Prevent Null Byte injection
    if "\x00" in filename:
        raise ValueError("Security violation: Filename contains invalid null bytes.")

    # 2. Extract strictly the base name using Path(filename).name to mitigate traversal
    safe_name = Path(filename).name

    # 3. Detect and reject path traversal attempts
    # If the safe_name is not equal to the original filename, it means directory separators were present.
    if safe_name != filename or "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Security violation: Path traversal or directory traversal sequences are strictly prohibited.")

    # 4. Strict whitelist validation: only letters, numbers, underscores, dots, and hyphens.
    # If the filename contains any other characters (such as special shell characters like ;, &, |, $, etc.), reject it.
    if not re.match(r"^[a-zA-Z0-9_.-]+$", safe_name):
        raise ValueError(
            f"Security violation: Filename '{filename}' contains invalid characters. "
            f"Only alphanumeric characters, underscores, hyphens, and dots are permitted."
        )

    # 5. Enforce standard maximum length boundary (255 characters)
    if len(safe_name) > 255:
        raise ValueError("Security violation: Filename exceeds maximum allowed length of 255 characters.")

    return safe_name


def validate_scan_id(scan_id: str) -> str:
    """
    Validates that a scan_id is a properly formatted UUID string.
    Prevents injection attacks through scan ID path parameters.
    """
    if not scan_id:
        raise ValueError("Security violation: Scan ID cannot be empty.")
    try:
        parsed = uuid.UUID(scan_id, version=4)
        return str(parsed)
    except (ValueError, AttributeError):
        raise ValueError(f"Security violation: Invalid scan ID format. Expected UUID v4, got: {scan_id!r}")


def validate_git_url(url: str) -> str:
    """
    Rigorously validates repository Git URLs to prevent argument injection
    and shell/command execution exploits during cloning.
    
    Returns the cleaned URL on success, raises ValueError on rejection.
    """
    if not url:
        raise ValueError("Security Violation: Git URL cannot be empty.")

    cleaned = url.strip()

    if cleaned.startswith("-"):
        raise ValueError("Security Violation: Git URL cannot begin with a hyphen.")

    # Reject null bytes
    if "\x00" in cleaned:
        raise ValueError("Security Violation: Git URL contains null bytes.")

    # Reject shell metacharacters that could enable command chaining
    dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "{", "}", "<", ">", "\n", "\r"]
    for char in dangerous_chars:
        if char in cleaned:
            raise ValueError(f"Security Violation: Git URL contains dangerous character: {char!r}")

    # Whitelist pattern for secure URLs — excludes shell metacharacters.
    pattern = r"^(https?://|git@)[a-zA-Z0-9._~:/?#\[\]@!=+,;%-]+$"
    if not re.match(pattern, cleaned):
        raise ValueError("Security Violation: Git URL contains illegal or unsafe characters.")

    if cleaned.startswith(("http://", "https://")):
        parsed = urlsplit(cleaned)
        if parsed.username or parsed.password:
            raise ValueError(
                "Security Violation: Git URL must not embed credentials or access tokens."
            )
        if not parsed.netloc or "." not in parsed.netloc:
            raise ValueError("Security Violation: Git URL host is invalid.")

    # Enforce maximum URL length to prevent buffer-based attacks
    if len(cleaned) > 2048:
        raise ValueError("Security Violation: Git URL exceeds maximum allowed length.")

    return cleaned


def redact_url_for_log(url: str) -> str:
    """Return a Git/HTTP URL with any accidental userinfo removed before logging."""
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    return url
