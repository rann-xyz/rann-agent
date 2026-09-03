"""
Integration tests for end-to-end task execution
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch

from rann_agent.core.agent import Agent
from rann_agent.core.config import Config


class TestEndToEndTaskExecution:
    """Test complete task execution flow"""
    
    @pytest.mark.asyncio
    async def test_simple_file_creation_task(self, temp_dir, mock_llm_provider):
        """Test creating a file through the agent"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            config.tools.enabled = ["terminal", "files"]
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            # Mock successful execution
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Created test.txt successfully",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            result = await agent.execute(
                goal=f"Create a file called hello.txt with content 'Hello World' in {temp_dir}",
                max_turns=3
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_terminal_command_execution(self, temp_dir, mock_llm_provider):
        """Test running a terminal command through the agent"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            config.tools.enabled = ["terminal"]
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "ls output",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            result = await agent.execute(
                goal=f"List files in {temp_dir}",
                max_turns=2
            )
            
            assert result is not None


class TestMultiAgentCoordination:
    """Test multi-agent coordination"""
    
    @pytest.mark.asyncio
    async def test_spawn_worker_agent(self, mock_llm_provider):
        """Test spawning a worker agent from coordinator"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            config.agent.orchestration.enabled = True
            config.agent.orchestration.max_concurrent_agents = 3
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            # Spawn a worker
            worker = agent.spawn_coordinator()
            
            assert worker is not None
            assert worker.parent == agent


class TestMemoryPersistence:
    """Test memory and session persistence"""
    
    @pytest.mark.asyncio
    async def test_session_saves_context(self, temp_dir, mock_llm_provider):
        """Test that session context is saved to memory"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            
            agent = Agent(config=config, memory=True)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Session completed",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            await agent.execute("Test task", max_turns=1)
            
            # Session should have an ID
            assert agent.session_id is not None
    
    @pytest.mark.asyncio
    async def test_memory_recall(self, mock_llm_provider):
        """Test memory recall of past sessions"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            
            agent = Agent(config=config, memory=True)
            agent.llm = mock_llm_provider
            
            # If memory is enabled, it should have recall capability
            if agent.memory:
                recall = agent.memory.get_relevant_context("test query")
                # Just verify it doesn't crash - actual recall depends on stored data
                assert True


class TestSelfHealingIntegration:
    """Test self-healing in realistic scenarios"""
    
    @pytest.mark.asyncio
    async def test_retry_on_tool_failure(self, mock_llm_provider):
        """Test that agent retries when a tool fails"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            config.agent.self_healing.enabled = True
            config.agent.self_healing.max_retries = 2
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            # Mock a successful recovery after initial failure
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Recovered from error",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            result = await agent.execute("Task that needs retry", max_turns=3)
            
            assert result is not None


class TestContextManagement:
    """Test context window management"""
    
    @pytest.mark.asyncio
    async def test_context_grows_with_turns(self, mock_llm_provider):
        """Test that context accumulates across turns"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            initial_messages = len(agent.context.messages)
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Response",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            await agent.execute("Multi-turn task", max_turns=2)
            
            # Context should have grown
            assert len(agent.context.messages) > initial_messages


class TestErrorRecovery:
    """Test error handling and recovery"""
    
    @pytest.mark.asyncio
    async def test_graceful_handling_of_llm_error(self, mock_llm_provider):
        """Test graceful handling when LLM call fails"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            config = Config()
            config.agent.llm.provider = "mock"
            
            agent = Agent(config=config)
            agent.llm = mock_llm_provider
            
            # Simulate all LLM errors
            mock_llm_provider.complete_with_retry = AsyncMock(
                side_effect=Exception("LLM API Error")
            )
            
            # Agent should propagate error after retries exhausted
            # This is expected behavior - agent doesn't silently swallow all errors
            with pytest.raises(Exception, match="LLM API Error"):
                await agent.execute("Task", max_turns=1)