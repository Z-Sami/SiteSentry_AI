#!/usr/bin/env python3
"""
SiteSentry Launcher - Python Version
Cross-platform launcher with environment setup
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    venv_path = script_dir / ".venv"
    
    # Check if venv exists
    if not venv_path.exists():
        print("❌ Virtual environment not found")
        print(f"Run: cd {script_dir} && python3 -m venv .venv && {venv_path}/bin/pip install -r requirements.txt")
        sys.exit(1)
    
    # Determine Python executable
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    
    # Set environment variables
    env = os.environ.copy()
    env["GROQ_API_KEY"] = env.get("GROQ_API_KEY", "test_key")
    env["TELEGRAM_BOT_TOKEN"] = env.get("TELEGRAM_BOT_TOKEN", "test_token")
    env["TELEGRAM_ADMIN_CHAT_ID"] = env.get("TELEGRAM_ADMIN_CHAT_ID", "123456")
    
    print("=" * 42)
    print("  SiteSentry - Autonomous Inspector")
    print("=" * 42)
    print()
    print("Environment:")
    print(f"  Python: {python_exe}")
    print(f"  GROQ_API_KEY: {env['GROQ_API_KEY'][:10]}...")
    print(f"  TELEGRAM_BOT_TOKEN: {env['TELEGRAM_BOT_TOKEN'][:10]}...")
    print(f"  TELEGRAM_ADMIN_CHAT_ID: {env['TELEGRAM_ADMIN_CHAT_ID']}")
    print()
    
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    try:
        if command == "test":
            print("Running test suite...")
            subprocess.run([str(python_exe), "test_standalone.py"], cwd=script_dir, env=env, check=True)
        
        elif command == "telegram":
            print("Starting Telegram Bot...")
            subprocess.run([str(python_exe), "brain/telegram_bot.py"], cwd=script_dir, env=env, check=True)
        
        elif command == "brain":
            print("Starting Robot Brain...")
            subprocess.run([str(python_exe), "brain/robot_brain.py"], cwd=script_dir, env=env, check=True)
        
        elif command == "cad":
            if len(sys.argv) < 3:
                print("❌ CAD file not specified")
                print("Usage: python3 run.py cad <dxf_file>")
                sys.exit(1)
            dxf_file = sys.argv[2]
            subprocess.run([str(python_exe), "brain/cad_to_json.py", dxf_file], cwd=script_dir, env=env, check=True)
        
        else:
            print_help()
    
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

def print_help():
    print("Usage: python3 run.py [command]")
    print()
    print("Commands:")
    print("  test              Run test suite")
    print("  telegram          Start Telegram Bot listener")
    print("  brain             Start Robot Brain AI inspector")
    print("  cad <file.dxf>    Parse CAD file to mission.json")
    print("  help              Show this help message")
    print()
    print("Environment variables (optional):")
    print("  GROQ_API_KEY              Groq API key for vision")
    print("  TELEGRAM_BOT_TOKEN        Telegram bot token")
    print("  TELEGRAM_ADMIN_CHAT_ID    Your Telegram chat ID")
    print()
    print("Example with real credentials:")
    print("  export GROQ_API_KEY='gsk_...'")
    print("  export TELEGRAM_BOT_TOKEN='123:ABC...'")
    print("  export TELEGRAM_ADMIN_CHAT_ID='987654321'")
    print("  python3 run.py telegram")

if __name__ == "__main__":
    main()
