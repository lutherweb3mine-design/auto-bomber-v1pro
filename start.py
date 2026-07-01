#!/usr/bin/env python3
"""
LeadGen Pro - Start Script
===========================
Single command to start everything:
    python start.py

Options:
    python start.py --dashboard    # Start dashboard only
    python start.py --background   # Start runners in background
    python start.py --all          # Start dashboard + background runners (default)
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent

def start_dashboard():
    """Start the Streamlit dashboard"""
    print("🚀 Starting LeadGen Pro Dashboard...")
    print("   Open your browser to the URL shown below")
    print("   Press Ctrl+C to stop\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(BASE_DIR / "app.py")])

def start_background():
    """Start all enabled runners in background"""
    print("🤖 Starting background runners...")

    # Check if tmux is available (Termux)
    tmux_available = subprocess.run(["which", "tmux"], capture_output=True).returncode == 0

    runners = ["telegram", "reddit", "twitter", "discord", "facebook", "instagram"]

    for runner in runners:
        script = BASE_DIR / f"{runner}_runner.py"
        if not script.exists():
            print(f"   ⚠️  {runner}_runner.py not found, skipping")
            continue

        if tmux_available:
            # Use tmux for background (persists after closing Termux)
            session_name = f"leadgen_{runner}"
            # Kill existing session if exists
            subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
            # Create new detached session
            subprocess.run([
                "tmux", "new-session", "-d", "-s", session_name,
                f"cd {BASE_DIR} && {sys.executable} {script}"
            ])
            print(f"   ✅ {runner.title()} runner started in tmux session: {session_name}")
        else:
            # Use nohup as fallback
            log_file = BASE_DIR / "logs" / f"{runner}.log"
            log_file.parent.mkdir(exist_ok=True)
            with open(log_file, "w") as log:
                subprocess.Popen(
                    [sys.executable, str(script)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=BASE_DIR
                )
            print(f"   ✅ {runner.title()} runner started (nohup, log: {log_file})")

    print("\n📊 View status: python status.py")
    print("🛑 Stop all: python stop.py")

def main():
    parser = argparse.ArgumentParser(description="LeadGen Pro Starter")
    parser.add_argument("--dashboard", action="store_true", help="Start dashboard only")
    parser.add_argument("--background", action="store_true", help="Start background runners only")
    parser.add_argument("--all", action="store_true", help="Start everything (default)")
    args = parser.parse_args()

    if args.dashboard:
        start_dashboard()
    elif args.background:
        start_background()
    else:
        # Default: start dashboard (runners can be started from UI)
        start_dashboard()

if __name__ == "__main__":
    main()
