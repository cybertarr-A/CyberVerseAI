import time
import pytest
from unittest.mock import patch, MagicMock
from app.services.agents.llm_client import LLMClient
from app.tasks.analysis_tasks import analyze_chunk


def test_llm_client_singleton():
    """Verify that LLMClient behaves as a thread-safe singleton."""
    with patch("app.services.agents.llm_client.Groq") as mock_groq:
        client1 = LLMClient.get_instance()
        client2 = LLMClient.get_instance()
        assert client1 is client2


def test_llm_client_redis_lock_and_cooldown():
    """Verify Redis distributed locking and frequency cooldown throttling in LLMClient."""
    with patch("app.services.agents.llm_client.Groq") as mock_groq:
        client = LLMClient.get_instance()
        
        # Mock groq chat completions call
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "mocked completion content"
        client.client.chat.completions.create = MagicMock(return_value=mock_completion)

        # Mock Redis lock and cooldown get/set
        mock_redis = MagicMock()
        client.redis_client = mock_redis
        
        # Simulate lock successfully acquired
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock
        
        # Simulate last request time was long ago
        mock_redis.get.return_value = str(time.time() - 10)
        
        res = client.generate_completion("sys", "user")
        assert res == "mocked completion content"
        mock_redis.lock.assert_called_with("cyberverse:lock:groq_request", timeout=60)
        mock_lock.acquire.assert_called()
        mock_lock.release.assert_called()


def test_analyze_chunk_graceful_fallback():
    """Verify analyze_chunk task intercepts LLM failures and returns graceful fallback."""
    with patch("app.services.agents.llm_client.LLMClient.get_instance") as mock_client_instance:
        mock_client = MagicMock()
        mock_client.generate_structured_json.side_effect = RuntimeError("Groq rate limit simulated")
        mock_client_instance.return_value = mock_client
        
        result = analyze_chunk("dummy codebase chunk")
        
        assert result["status"] == "partial_success"
        assert result["error"] == "rate_limit"
        assert "data" in result
        assert result["data"]["security_findings"] == []
        assert result["data"]["architecture_issues"] == []
        assert result["data"]["code_quality"] == []
        assert result["data"]["performance_concerns"] == []
        assert result["data"]["recommendations"] == []
