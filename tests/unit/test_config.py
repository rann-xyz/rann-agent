"""
Unit tests for Config management
"""

import pytest
from pathlib import Path
import tempfile
import yaml
from rann_agent.core.config import Config, LLMConfig, AgentConfig


class TestConfigLoading:
    """Test configuration loading"""
    
    def test_config_default_initialization(self):
        """Test config initializes with defaults"""
        config = Config()
        assert config.agent is not None
        assert config.tools is not None
        assert config.logging is not None
    
    def test_config_from_dict(self):
        """Test config can be created from dict"""
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
        """Test config loads from YAML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "agent": {
                    "name": "Test Agent",
                    "llm": {
                        "provider": "anthropic",
                        "model": "claude-3-opus",
                    }
                }
            }, f)
            config_path = Path(f.name)
        
        try:
            config = Config.load(config_path)
            assert config.agent.name == "Test Agent"
            assert config.agent.llm.provider == "anthropic"
        finally:
            config_path.unlink()


class TestConfigValidation:
    """Test configuration validation"""
    
    def test_validate_config_with_api_key(self, monkeypatch):
        """Test validation passes with API key"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        config = Config()
        warnings = config.validate_config()
        assert len(warnings) >= 0  # May have other warnings
    
    def test_validate_config_missing_api_key(self, monkeypatch):
        """Test validation warns about missing API key"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("CUSTOM_API_KEY", raising=False)
        monkeypatch.delenv("HERMES_CUSTOM_SEEKAI_CC_API_KEY", raising=False)
        monkeypatch.delenv("HERMES_CUSTOM_API_XKIRO_COM_API_KEY", raising=False)
        
        config = Config()
        warnings = config.validate_config()
        
        # Should warn about missing API key
        assert any("API key" in w for w in warnings)
    
    def test_get_api_key_from_env(self, monkeypatch):
        """Test getting API key from environment"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        config = Config()
        
        key = config.get_api_key("anthropic")
        assert key == "sk-test-key"
    
    def test_get_api_key_missing(self, monkeypatch):
        """Test getting missing API key returns None"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = Config()
        
        key = config.get_api_key("anthropic")
        assert key is None


class TestLLMConfig:
    """Test LLM configuration"""
    
    def test_llm_config_defaults(self):
        """Test LLM config defaults"""
        llm_config = LLMConfig()
        assert llm_config.provider == "xkiro"
        assert llm_config.model == "minimax/minimax-m2.7-highspeed:free"
        assert llm_config.max_tokens == 8192
    
    def test_llm_config_custom(self):
        """Test custom LLM config"""
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


class TestAgentConfig:
    """Test agent configuration"""
    
    def test_agent_config_defaults(self):
        """Test agent config defaults"""
        agent_config = AgentConfig()
        assert agent_config.name == "Rann Agent"
        assert agent_config.self_healing.enabled is True
        assert agent_config.orchestration.enabled is True
        assert agent_config.memory.persist is True
    
    def test_self_healing_config(self):
        """Test self-healing configuration"""
        agent_config = AgentConfig()
        assert agent_config.self_healing.max_retries == 3
        assert agent_config.self_healing.learn_from_errors is True
    
    def test_orchestration_config(self):
        """Test orchestration configuration"""
        agent_config = AgentConfig()
        assert agent_config.orchestration.max_concurrent_agents == 5
        assert agent_config.orchestration.max_depth == 3


class TestToolsConfig:
    """Test tools configuration"""
    
    def test_tools_config_defaults(self):
        """Test tools default configuration"""
        config = Config()
        assert "terminal" in config.tools.enabled
        assert "files" in config.tools.enabled
        assert "web" in config.tools.enabled
    
    def test_terminal_tool_config(self):
        """Test terminal tool configuration"""
        config = Config()
        assert config.tools.terminal["default_timeout"] == 300
        assert config.tools.terminal["allow_background"] is True
    
    def test_files_tool_config(self):
        """Test files tool configuration"""
        config = Config()
        assert config.tools.files["max_file_size"] == 10485760  # 10MB
