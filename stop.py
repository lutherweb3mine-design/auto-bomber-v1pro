#!/usr/bin/env python3
"""
LeadGen Pro - Stop Script
==========================
Stop all background runners:
    python stop.py
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "leadgen.db"

def stop_tmux_sessions():
    """Stop all tmux sessions for LeadGen"""
    result = subprocess.run(["tmux", "ls"], capture_output=True, text=True)
    if result.returncode != 0:
        return

    for line in result.stdout.split("\n"):
        if line.startswith("leadgen_"):
            session = line.split(":")[0]
            subprocess.run(["tmux", "kill-session", "-t", session])
            print(f"   🛑 Killed tmux session: {session}")

def stop_processes():
    """Stop runner processes by checking runner_status table"""
    if not DB_PATH.exists():
        return

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.execute("SELECT platform, pid FROM runner_status WHERE status = 'running'")
        for row in cursor.fetchall():
            platform, pid = row
            if pid:
                try:
                    os.kill(pid, 9)
                    print(f"   🛑 Killed {platform} runner (PID: {pid})")
                except ProcessLookupError:
                    print(f"   ⚠️  {platform} runner already stopped")

        # Update status
        conn.execute("UPDATE runner_status SET status = 'stopped', pid = NULL")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️  Error stopping processes: {e}")

def main():
    print("🛑 Stopping all LeadGen Pro runners...")

    # Try tmux first
    stop_tmux_sessions()

    # Then try process killing
    stop_processes()

    print("\n✅ All runners stopped.")

if __name__ == "__main__":
    main()
