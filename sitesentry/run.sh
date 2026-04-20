#!/bin/bash

# SiteSentry Launcher Script
# Activates venv and runs the application with environment variables

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/.venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Set environment variables (replace with real values before deployment)
export GROQ_API_KEY="${GROQ_API_KEY:-test_key}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-test_token}"
export TELEGRAM_ADMIN_CHAT_ID="${TELEGRAM_ADMIN_CHAT_ID:-123456}"

echo "=========================================="
echo "  SiteSentry - Autonomous Inspector"
echo "=========================================="
echo ""
echo "Environment:"
echo "  Python: $(python3 --version)"
echo "  GROQ_API_KEY: ${GROQ_API_KEY:0:10}..."
echo "  TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:0:10}..."
echo "  TELEGRAM_ADMIN_CHAT_ID: $TELEGRAM_ADMIN_CHAT_ID"
echo ""

# Parse arguments
case "${1:-help}" in
    test)
        echo "Running test suite..."
        python3 test_standalone.py
        ;;
    telegram)
        echo "Starting Telegram Bot..."
        python3 brain/telegram_bot.py
        ;;
    brain)
        echo "Starting Robot Brain..."
        python3 brain/robot_brain.py
        ;;
    cad)
        echo "CAD Parser - Usage: ./run.sh cad <dxf_file>"
        if [ -z "$2" ]; then
            echo "  Error: No DXF file specified"
            exit 1
        fi
        python3 brain/cad_to_json.py "$2"
        ;;
    help|--help|-h)
        echo "Usage: ./run.sh [command]"
        echo ""
        echo "Commands:"
        echo "  test              Run test suite"
        echo "  telegram          Start Telegram Bot listener"
        echo "  brain             Start Robot Brain AI inspector"
        echo "  cad <file.dxf>    Parse CAD file to mission.json"
        echo "  help              Show this help message"
        echo ""
        echo "Environment variables (optional):"
        echo "  GROQ_API_KEY              Groq API key for vision"
        echo "  TELEGRAM_BOT_TOKEN        Telegram bot token"
        echo "  TELEGRAM_ADMIN_CHAT_ID    Your Telegram chat ID"
        echo ""
        echo "Example with real credentials:"
        echo "  export GROQ_API_KEY='gsk_...'"
        echo "  export TELEGRAM_BOT_TOKEN='123:ABC...'"
        echo "  export TELEGRAM_ADMIN_CHAT_ID='987654321'"
        echo "  ./run.sh telegram"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run './run.sh help' for available commands"
        exit 1
        ;;
esac

deactivate
