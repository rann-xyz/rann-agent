"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
import os
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch

# Set mock API keys BEFORE importing anything that reads them
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")


# Configure asyncio for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing"""
    provider = Mock()
    provider.complete = AsyncMock(return_value={
        "content": "Mocked response",
        "usage": {"input_tokens": 10, "output_tokens": 20},
        "model": "mock-model",
    })
    provider.stream = AsyncMock(return_value=iter(["Mocked", " stream", " response"]))
    return provider


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    from rann_agent.core.config import Config
    
    config = Config()
    config.agent.llm.provider = "mock"
    config.agent.llm.model = "mock-model"
    config.tools.enabled = ["terminal", "files"]
    
    return config


@pytest.fixture
def mock_agent_with_llm(mock_llm_provider):
    """Create a mock agent with mocked LLM provider"""
    from rann_agent.core.agent import Agent
    
    with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
        agent = Agent()
        agent.llm = mock_llm_provider
        return agent


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    # Create test files
    (temp_dir / "test.py").write_text("print('hello')")
    (temp_dir / "test.txt").write_text("Sample text content")
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "nested.txt").write_text("Nested file")
    
    return temp_dir
