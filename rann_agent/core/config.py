"""
Configuration management
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import os


class LLMConfig(BaseModel):
    provider: str = "xkiro"
    model: str = "minimax/minimax-m2.7-highspeed:free"
    temperature: float = 0.7
    max_tokens: int = 8192
    fallback_providers: List[Dict[str, str]] = []
    retry: Dict[str, Any] = {
        "max_attempts": 3,
        "backoff_multiplier": 2.0,
    }


class SelfHealingConfig(BaseModel):
    enabled: bool = True
    max_retries: int = 3
    strategies: List[str] = ["analyze_error", "search_similar_issues", "propose_fixes"]
    learn_from_errors: bool = True
    error_db: str = "~/.rann-agent/data/error_patterns.db"


class OrchestrationConfig(BaseModel):
    enabled: bool = True
    max_concurrent_agents: int = 5
    max_depth: int = 3
    task_timeout: int = 3600
    message_queue: str = "memory"


class MemoryConfig(BaseModel):
    persist: bool = True
    database: str = "sqlite"
    max_context_length: int = 100000
    compression: bool = True
    vector_search: bool = False
    embedding_model: str = "text-embedding-3-small"
    global_memory: bool = True


class AgentConfig(BaseModel):
    name: str = "Rann Agent"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    self_healing: SelfHealingConfig = Field(default_factory=SelfHealingConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)


class ToolsConfig(BaseModel):
    enabled: List[str] = ["terminal", "files", "web", "code_exec", "git"]
    terminal: Dict[str, Any] = {
        "default_timeout": 300,
        "max_timeout": 3600,
        "allow_background": True,
    }
    files: Dict[str, Any] = {"max_file_size": 10485760}
    web: Dict[str, Any] = {"max_concurrent_requests": 10, "timeout": 30}
    code_exec: Dict[str, Any] = {"sandbox": True, "timeout": 300}


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Dict[str, Any] = {
        "enabled": True,
        "path": "~/.rann-agent/logs/agent.log",
    }
    console: Dict[str, Any] = {"enabled": True, "colorize": True}


class APIConfig(BaseModel):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors: Dict[str, Any] = {"enabled": True}
    websocket: Dict[str, Any] = {"enabled": True, "path": "/ws"}


class AdvancedConfig(BaseModel):
    parallel_tools: bool = True
    max_parallel_tools: int = 5
    streaming: bool = True
    cache_llm_responses: bool = True
    cache_tool_results: bool = True


class Config(BaseSettings):
    """Main configuration class"""
    
    agent: AgentConfig = Field(default_factory=AgentConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    
    # Environment variables
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    database_url: str = Field(
        "sqlite:///~/.rann-agent/data/sessions.db",
        alias="DATABASE_URL"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from file and environment
        
        Args:
            config_path: Path to config.yaml (defaults to ./config.yaml)
        """
        # Try to load from config.yaml
        if config_path is None:
            config_path = Path("config.yaml")
            if not config_path.exists():
                config_path = Path.home() / ".rann-agent" / "config.yaml"
        
        config_dict = {}
        if config_path.exists():
            with open(config_path) as f:
                config_dict = yaml.safe_load(f) or {}
        
        # Merge with environment variables
        return cls(**config_dict)
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider"""
        if provider == "anthropic":
            return self.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        elif provider == "openai":
            return self.openai_api_key or os.getenv("OPENAI_API_KEY")
        elif provider == "xkiro":
            return os.getenv("HERMES_CUSTOM_API_XKIRO_COM_API_KEY")
        elif provider == "custom":
            return os.getenv("CUSTOM_API_KEY") or os.getenv("HERMES_CUSTOM_SEEKAI_CC_API_KEY")
        return None
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of warnings"""
        warnings = []
        
        # Check API keys
        provider = self.agent.llm.provider
        if not self.get_api_key(provider):
            warnings.append(f"No API key found for provider: {provider}")
        
        # Check paths exist
        data_dir = Path(self.database_url.replace("sqlite:///", "")).parent
        if not data_dir.exists():
            warnings.append(f"Data directory does not exist: {data_dir}")
        
        return warnings
