"""
Unit tests for Config management - Clean Provider Architecture
"""

import tempfile
from pathlib import Path

import yaml

from rann_agent.core.config import AgentConfig, Config, LLMConfig


class TestConfigLoading:
    def test_config_default_initialization(self):
        config = Config()
        assert config.agent is not None
        assert config.tools is not None
        assert config.logging is not None

    def test_config_from_dict(self):
        config_dict = {
            "agent": {
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4",
                }
            }
        }
        config = Config(**config_dict)
        assert config.agent.llm.provider == "openai"
        assert config.agent.llm.model == "gpt-4"

    def test_config_from_yaml_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(
                {
                    "agent": {
                        "name": "Test Agent",
                        "llm": {
                            "provider": "anthropic",
                            "model": "claude-3-opus",
                        },
                    }
                },
                f,
            )
            config_path = Path(f.name)

        try:
            config = Config.load(config_path)
            assert config.agent.name == "Test Agent"
            assert config.agent.llm.provider == "anthropic"
        finally:
            config_path.unlink()


class TestConfigValidation:
    def test_validate_config_with_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        config = Config()
        config.agent.llm.provider = "openai"
        warnings = config.validate_config()
        assert len(warnings) >= 0

    def test_validate_config_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CUSTOM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        config = Config()
        warnings = config.validate_config()
        assert any("API key" in w for w in warnings)

    def test_get_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        config = Config()
        config.agent.llm.provider = "openai"

        key = config.get_api_key("openai")
        assert key == "sk-test-key"

    def test_get_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = Config()
        config.agent.llm.provider = "openai"

        key = config.get_api_key("openai")
        assert key is None


class TestLLMConfig:
    def test_llm_config_defaults(self):
        llm_config = LLMConfig()
        assert llm_config.provider == "custom"
        assert llm_config.model == "gpt-4o"
        assert llm_config.max_tokens == 8192

    def test_llm_config_custom(self):
        llm_config = LLMConfig(
            provider="openai",
            model="gpt-4-turbo",
            temperature=0.5,
            max_tokens=4096,
        )
        assert llm_config.provider == "openai"
        assert llm_config.model == "gpt-4-turbo"
        assert llm_config.temperature == 0.5
        assert llm_config.max_tokens == 4096


class TestProviderSelection:
    def test_valid_providers(self):
        valid = ["anthropic", "openai", "ollama", "custom"]
        assert "xkiro" not in valid

    def test_custom_provider_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "test-custom-key")
        config = Config()
        config.agent.llm.provider = "custom"

        key = config.get_api_key("custom")
        assert key == "test-custom-key"


class TestAgentConfig:
    def test_agent_config_defaults(self):
        agent_config = AgentConfig()
        assert agent_config.name == "Rann Agent"
        assert agent_config.self_healing.enabled is True
        assert agent_config.orchestration.enabled is True
        assert agent_config.memory.persist is True

    def test_self_healing_config(self):
        agent_config = AgentConfig()
        assert agent_config.self_healing.max_retries == 3
        assert agent_config.self_healing.learn_from_errors is True

    def test_orchestration_config(self):
        agent_config = AgentConfig()
        assert agent_config.orchestration.max_concurrent_agents == 5
        assert agent_config.orchestration.max_depth == 3


class TestToolsConfig:
    def test_tools_config_defaults(self):
        config = Config()
        assert "terminal" in config.tools.enabled
        assert "read_file" in config.tools.enabled
        assert "write_file" in config.tools.enabled
        assert "web_search" in config.tools.enabled

    def test_terminal_tool_config(self):
        config = Config()
        assert config.tools.terminal["default_timeout"] == 300
        assert config.tools.terminal["allow_background"] is True

    def test_files_tool_config(self):
        config = Config()
        assert config.tools.files["max_file_size"] == 10485760  # 10MB
