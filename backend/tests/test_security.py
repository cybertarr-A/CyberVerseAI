"""
Unit tests for app.core.security module.
Tests filename sanitization, scan ID validation, and Git URL validation
against path traversal, null bytes, shell injection, and argument injection attacks.
"""
import pytest
from app.core.security import sanitize_filename, validate_scan_id, validate_git_url, redact_url_for_log


class TestSanitizeFilename:
    """Tests for the sanitize_filename function."""

    def test_valid_filenames(self):
        assert sanitize_filename("script.py") == "script.py"
        assert sanitize_filename("my-file_v2.tar.gz") == "my-file_v2.tar.gz"
        assert sanitize_filename("README.md") == "README.md"

    def test_empty_filename_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_filename("")

    def test_null_byte_injection(self):
        with pytest.raises(ValueError, match="null bytes"):
            sanitize_filename("script.py\x00.jpg")

    def test_path_traversal_dotdot(self):
        with pytest.raises(ValueError, match="traversal"):
            sanitize_filename("../../etc/passwd")

    def test_path_traversal_slash(self):
        with pytest.raises(ValueError, match="traversal"):
            sanitize_filename("uploads/../../secret.key")

    def test_path_traversal_backslash(self):
        with pytest.raises(ValueError, match="traversal"):
            sanitize_filename("..\\windows\\system32\\cmd.exe")

    def test_shell_metacharacters_rejected(self):
        dangerous_names = [
            "file;danger",
            "file|danger",
            "file&danger",
            "file`danger`",
        ]
        for name in dangerous_names:
            with pytest.raises(ValueError):
                sanitize_filename(name)

    def test_max_length_enforcement(self):
        long_name = "a" * 256
        with pytest.raises(ValueError, match="maximum allowed length"):
            sanitize_filename(long_name)

    def test_max_length_boundary(self):
        name_255 = "a" * 251 + ".txt"  # 255 chars
        assert sanitize_filename(name_255) == name_255


class TestValidateScanId:
    """Tests for the validate_scan_id function."""

    def test_valid_uuid(self):
        valid_id = "550e8400-e29b-41d4-a716-446655440000"
        assert validate_scan_id(valid_id) == valid_id

    def test_empty_scan_id(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_scan_id("")

    def test_non_uuid_string(self):
        with pytest.raises(ValueError, match="Invalid scan ID"):
            validate_scan_id("not-a-uuid")

    def test_sql_injection_attempt(self):
        with pytest.raises(ValueError, match="Invalid scan ID"):
            validate_scan_id("' OR 1=1 --")

    def test_path_traversal_attempt(self):
        with pytest.raises(ValueError, match="Invalid scan ID"):
            validate_scan_id("../../etc/passwd")


class TestValidateGitUrl:
    """Tests for the validate_git_url function."""

    def test_valid_https_url(self):
        url = "https://github.com/user/repo.git"
        assert validate_git_url(url) == url

    def test_valid_git_ssh_url(self):
        url = "git@github.com:user/repo.git"
        assert validate_git_url(url) == url

    def test_empty_url_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_git_url("")

    def test_hyphen_prefix_argument_injection(self):
        with pytest.raises(ValueError, match="cannot begin with a hyphen"):
            validate_git_url("--upload-pack=evil")

    def test_null_byte_injection(self):
        with pytest.raises(ValueError, match="null bytes"):
            validate_git_url("https://github.com/repo\x00.git")

    def test_shell_metacharacters(self):
        dangerous_urls = [
            "https://github.com/repo;rm -rf /",
            "https://github.com/repo|cat /etc/passwd",
            "https://github.com/repo&background",
            "https://github.com/repo$(whoami)",
            "https://github.com/repo`id`",
        ]
        for url in dangerous_urls:
            with pytest.raises(ValueError, match="dangerous character"):
                validate_git_url(url)

    def test_max_length_enforcement(self):
        long_url = "https://github.com/" + "a" * 2040
        with pytest.raises(ValueError, match="maximum allowed length"):
            validate_git_url(long_url)

    def test_non_http_non_git_protocol_rejected(self):
        with pytest.raises(ValueError, match="illegal or unsafe"):
            validate_git_url("ftp://evil.com/payload.git")

    def test_embedded_http_credentials_rejected(self):
        with pytest.raises(ValueError, match="must not embed credentials"):
            validate_git_url("https://token123@github.com/user/repo.git")

    def test_url_redaction_removes_userinfo(self):
        assert (
            redact_url_for_log("https://token123@github.com/user/repo.git")
            == "https://github.com/user/repo.git"
        )
