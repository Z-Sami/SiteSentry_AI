#!/bin/bash
# SiteSentry Setup Script
# ======================
# Quick setup for development/testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🚀 SiteSentry Setup Script"
echo "=========================="
echo ""

# Create virtual environment
echo "📦 Creating Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "✓ venv created"
else
    echo "✓ venv already exists"
fi

# Activate venv
source "$SCRIPT_DIR/venv/bin/activate"
echo "✓ venv activated"

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"
echo "✓ Dependencies installed"

# Create results directory
mkdir -p "$SCRIPT_DIR/results/captures"
echo "✓ Results directory created"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate venv:  source $SCRIPT_DIR/venv/bin/activate"
echo "  2. Run tests:      python3 $SCRIPT_DIR/test_standalone.py"
echo "  3. Set env vars:   export GROQ_API_KEY='...'"
echo "  4. Deploy to ROS:  See README.md for full instructions"
