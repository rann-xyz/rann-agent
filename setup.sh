#!/bin/bash
# Setup script for Rann Agent

set -e

echo "🚀 Rann Agent Setup"
echo "==================="
echo ""

# Check Python version
echo "✓ Checking Python version..."
python3 --version || { echo "❌ Python 3.11+ required"; exit 1; }

# Create virtual environment (optional)
read -p "Create virtual environment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "✓ Virtual environment created and activated"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
if command -v uv &> /dev/null; then
    echo "Using uv (fast installer)..."
    uv pip install -e .
else
    echo "Using pip..."
    pip install -e .
fi

echo "✓ Dependencies installed"

# Setup config
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ Created .env - Please add your API keys"
else
    echo "✓ .env already exists"
fi

if [ ! -f config.yaml ]; then
    echo "Creating config.yaml..."
    cp config.yaml.example config.yaml
    echo "✓ Created config.yaml"
else
    echo "✓ config.yaml already exists"
fi

# Create data directory
echo ""
echo "Creating data directory..."
mkdir -p ~/.rann-agent/{data,logs}
echo "✓ Data directory created at ~/.rann-agent/"

# Verify installation
echo ""
echo "Verifying installation..."
python -m rann_agent.cli.main version || echo "⚠️  CLI not available yet"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API key:"
echo "   ANTHROPIC_API_KEY=sk-ant-xxxxx"
echo ""
echo "2. Run your first task:"
echo "   rann-agent chat 'hello world'"
echo ""
echo "3. Or start the web server:"
echo "   rann-agent serve"
echo ""
echo "4. Check examples:"
echo "   cd examples && python example_basic.py"
echo ""
echo "📖 Read QUICKSTART.md for more information"
