#!/usr/bin/env python3
"""
Instagram Bot Runner - Connected to LeadGen Pro v3.0
Placeholder - Instagram has strict API restrictions.
Uses unified DB and config paths.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "leadgen.db"
CONFIG_PATH = BASE_DIR / "config.json"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def get_db():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def update_runner_status(status, pid=None, stats=None):
    try:
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO runner_status (platform, status, pid, started_at, last_heartbeat, stats)
            VALUES (?, ?, ?, COALESCE((SELECT started_at FROM runner_status WHERE platform = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, ?)
        """, ("instagram", status, pid, "instagram", json.dumps(stats) if stats else '{}'))
        conn.commit()
        conn.close()
    except:
        pass


class InstagramRunner:
    def __init__(self):
        self.running = True

    def get_active_campaigns(self):
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%instagram%'"
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        campaigns = []
        for row in rows:
            camp = dict(zip(columns, row))
            camp['keywords'] = json.loads(camp['keywords']) if camp['keywords'] else []
            camp['niche_indicators'] = json.loads(camp['niche_indicators']) if camp['niche_indicators'] else []
            camp['pitches'] = json.loads(camp['pitches']) if camp['pitches'] else []
            campaigns.append(camp)
        conn.close()
        return campaigns

    def run(self):
        print(f"{CYAN}=== Instagram Runner ==={RESET}")
        print(f"{YELLOW}NOTE: Instagram automation is heavily restricted.{RESET}")
        print(f"{YELLOW}Options:{RESET}")
        print(f"  1. Instagram Basic Display API (limited)")
        print(f"  2. Instagram Graph API (requires business account)")
        print(f"  3. instagrapi library (unofficial, risk of ban)")
        print(f"{YELLOW}For now, use other platforms (Telegram, Reddit, Twitter).{RESET}")

        update_runner_status("stopped")


if __name__ == "__main__":
    runner = InstagramRunner()
    runner.run()
