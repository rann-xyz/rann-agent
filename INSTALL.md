# Installation Guide

## Prerequisites

- Python 3.11 or higher
- pip or uv package manager
- Git

## Quick Install

```bash
# Clone repository
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent

# Install with pip
pip install -e .

# Or with uv (faster)
uv pip install -e .
```

## Install from PyPI (when published)

```bash
pip install rann-agent

# With all extras
pip install rann-agent[all]
```

## Development Install

```bash
# Clone and install with dev dependencies
git clone https://github.com/rann-xyz/rann-agent.git
cd rann-agent

pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Verify Installation

```bash
# Check CLI is available
rann-agent --help

# Show version
rann-agent version

# Show config
rann-agent config-show
```

## API Keys Setup

### Option 1: Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY=sk-ant-xxxxx
# or
export OPENAI_API_KEY=sk-xxxxx
```

### Option 2: .env File

```bash
# In project directory
cp .env.example .env
nano .env  # Add your API keys
```

### Option 3: Config File

```bash
# System-wide config
mkdir -p ~/.rann-agent
cp config.yaml.example ~/.rann-agent/config.yaml
nano ~/.rann-agent/config.yaml
```

## Platform-Specific Notes

### macOS

```bash
# Install Python 3.11+ if needed
brew install python@3.11

# Install Rann Agent
pip3 install -e .
```

### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Install Rann Agent
pip3 install -e .
```

### Windows

```powershell
# Install Python from python.org
# Then in PowerShell:
pip install -e .
```

## Optional Dependencies

### For Vector Memory (Semantic Search)

```bash
pip install chromadb sentence-transformers
```

### For Browser Automation

```bash
pip install playwright
playwright install chromium
```

### For Redis Task Queue

```bash
pip install redis celery
```

## Troubleshooting

### Command Not Found

```bash
# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Or use python -m
python -m rann_agent.cli.main --help
```

### Import Errors

```bash
# Reinstall dependencies
pip install -e . --force-reinstall

# Or clear cache
pip cache purge
pip install -e .
```

### Permission Errors

```bash
# Use user install
pip install --user -e .

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Upgrading

```bash
# Pull latest changes
cd rann-agent
git pull origin main

# Reinstall
pip install -e . --upgrade
```

## Uninstall

```bash
pip uninstall rann-agent
```

## Next Steps

- [Quick Start Guide](QUICKSTART.md)
- [Configuration](README.md#configuration)
- [Examples](examples/)
