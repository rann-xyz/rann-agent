#!/bin/bash
#
# Rann Agent Installation Script
# Installs all dependencies for the agent and localhost applications
#

set -e

echo "🤖 Installing Rann Agent..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install core dependencies
echo ""
echo "📥 Installing core dependencies..."
pip install -r requirements.txt

# Install app dependencies
echo ""
echo "📥 Installing application dependencies..."
pip install -r requirements-app.txt

# Install package in editable mode
echo ""
echo "📦 Installing rann-agent package..."
pip install -e .

echo ""
echo "✅ Installation complete!"
echo ""
echo "🚀 Run the applications:"
echo "   Terminal: python terminal_app.py"
echo "   Web:      python web_app.py"
echo ""
echo "💡 Don't forget to activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
