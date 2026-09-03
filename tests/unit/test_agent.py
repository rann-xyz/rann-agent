"""
Unit tests for Agent core functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from rann_agent.core.agent import Agent
from rann_agent.core.config import Config


class TestAgentInitialization:
    """Test agent initialization"""
    
    def test_agent_init_default(self, mock_llm_provider):
        """Test agent initializes with defaults"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent()
            assert agent.config is not None
            assert agent.llm is not None
            assert agent.tools is not None
    
    def test_agent_init_custom_provider(self, mock_llm_provider):
        """Test agent with custom provider"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(provider="openai", model="gpt-4")
            assert agent.config.agent.llm.provider == "openai"
            assert agent.config.agent.llm.model == "gpt-4"
    
    def test_agent_init_custom_tools(self, mock_llm_provider):
        """Test agent with custom tool list"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(tools=["terminal"])
            assert len(agent.tools.get_enabled()) >= 1


class TestAgentExecution:
    """Test agent task execution"""
    
    @pytest.mark.asyncio
    async def test_execute_simple_task(self, mock_llm_provider, mock_config):
        """Test executing a simple task"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Task completed",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            })
            
            result = await agent.execute(goal="test task", max_turns=1)
            
            assert result is not None
            mock_llm_provider.complete_with_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_with_context(self, mock_llm_provider, mock_config):
        """Test execution with additional context"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "Done with context",
                "usage": {},
            })
            
            result = await agent.execute(
                goal="test",
                context="additional info",
                max_turns=1
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_session_id_generation(self, mock_llm_provider, mock_config):
        """Test session ID is generated"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "done",
                "usage": {}
            })
            
            await agent.execute("test", max_turns=1)
            
            assert agent.session_id is not None
            assert isinstance(agent.session_id, str)
            assert len(agent.session_id) > 10


class TestAgentSelfHealing:
    """Test self-healing functionality"""
    
    @pytest.mark.asyncio
    async def test_self_heal_called_on_error(self, mock_llm_provider, mock_config):
        """Test self-healing is triggered on error"""
        mock_config.agent.self_healing.enabled = True
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            with patch.object(agent, '_self_heal', new_callable=AsyncMock) as mock_heal:
                mock_heal.return_value = True
                
                with patch.object(agent, '_execute_turn', new_callable=AsyncMock) as mock_turn:
                    mock_turn.side_effect = [
                        {"error": "test error", "done": False},
                        {"done": True, "output": "fixed"}
                    ]
                    
                    result = await agent.execute("test", max_turns=2)
                    
                    mock_heal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_self_heal_retry_limit(self, mock_llm_provider, mock_config):
        """Test self-healing respects retry limit"""
        mock_config.agent.self_healing.enabled = True
        mock_config.agent.self_healing.max_retries = 2
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            with patch.object(agent, '_self_heal', new_callable=AsyncMock) as mock_heal:
                mock_heal.return_value = False  # Always fail
                
                with pytest.raises(Exception, match="Failed to heal error"):
                    with patch.object(agent, '_execute_turn', new_callable=AsyncMock) as mock_turn:
                        mock_turn.return_value = {"error": "persistent error", "done": False}
                        await agent.execute("test", max_turns=1)


class TestAgentContext:
    """Test context management"""
    
    def test_context_initialization(self, mock_llm_provider):
        """Test context is properly initialized"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent()
            assert agent.context is not None
            assert len(agent.context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_context_updated_during_execution(self, mock_llm_provider, mock_config):
        """Test context is updated during task execution"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            agent.llm = mock_llm_provider
            
            mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                "content": "response",
                "usage": {}
            })
            
            await agent.execute("test goal", max_turns=1)
            
            # Check context has messages
            assert len(agent.context.messages) > 0


class TestAgentMemory:
    """Test memory integration"""
    
    def test_agent_with_memory_enabled(self, mock_llm_provider):
        """Test agent initializes with memory"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(memory=True)
            assert agent.memory is not None
    
    def test_agent_with_memory_disabled(self, mock_llm_provider):
        """Test agent without memory"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(memory=False)
            assert agent.memory is None
    
    @pytest.mark.asyncio
    async def test_memory_context_loaded(self, mock_llm_provider, mock_config):
        """Test memory context is loaded before execution"""
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config, memory=True)
            agent.llm = mock_llm_provider
            
            if agent.memory:
                with patch.object(agent.memory, 'get_relevant_context', new_callable=AsyncMock) as mock_mem:
                    mock_mem.return_value = "relevant memory"
                    
                    mock_llm_provider.complete_with_retry = AsyncMock(return_value={
                        "content": "done",
                        "usage": {}
                    })
                    
                    await agent.execute("test", max_turns=1)
                    
                    mock_mem.assert_called_once()


class TestAgentCoordinator:
    """Test coordinator spawning"""
    
    def test_spawn_coordinator(self, mock_llm_provider, mock_config):
        """Test coordinator can be spawned"""
        mock_config.agent.orchestration.enabled = True
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            coordinator = agent.spawn_coordinator()
            
            assert coordinator is not None
            assert coordinator.parent == agent
    
    def test_coordinator_config_inherited(self, mock_llm_provider, mock_config):
        """Test coordinator inherits config"""
        mock_config.agent.orchestration.enabled = True
        mock_config.agent.orchestration.max_concurrent_agents = 10
        
        with patch("rann_agent.core.agent.LLMProvider", return_value=mock_llm_provider):
            agent = Agent(config=mock_config)
            coordinator = agent.spawn_coordinator()
            
            assert coordinator.max_concurrent == 10