"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

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
def mock_config():
    """Mock configuration for testing"""
    from rann_agent.core.config import Config
    
    config = Config()
    config.agent.llm.provider = "mock"
    config.agent.llm.model = "mock-model"
    config.tools.enabled = ["terminal", "files"]
    
    return config


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    # Create test files
    (temp_dir / "test.py").write_text("print('hello')")
    (temp_dir / "test.txt").write_text("Sample text content")
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "nested.txt").write_text("Nested file")
    
    return temp_dir
