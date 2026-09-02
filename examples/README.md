# Rann Agent Examples

Example scripts demonstrating Rann Agent capabilities.

## Running Examples

```bash
# Make sure Rann Agent is installed
cd /path/to/rann-agent
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-xxxxx

# Run examples
cd examples
python example_basic.py
python example_streaming.py
python example_multi_agent.py
python example_custom_tool.py
```

## Examples

### 1. Basic Usage (`example_basic.py`)
Simple task execution with result handling.

### 2. Streaming (`example_streaming.py`)
Real-time token streaming for better UX.

### 3. Multi-Agent (`example_multi_agent.py`)
Parallel task execution with multiple agents.

### 4. Custom Tool (`example_custom_tool.py`)
Creating and registering custom tools.

## More Examples

Check out the [documentation](https://github.com/rann-xyz/rann-agent) for:
- Self-healing error recovery
- Session management
- Memory and context
- API server integration
- Production deployment

## Need Help?

Open an issue: https://github.com/rann-xyz/rann-agent/issues
