#!/usr/bin/env python3
"""
TikTok Bot Runner - Connected to LeadGen Pro v3.0
Placeholder - TikTok does not offer public API for messaging/comment automation.
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
        """, ("tiktok", status, pid, "tiktok", json.dumps(stats) if stats else '{}'))
        conn.commit()
        conn.close()
    except:
        pass


class TikTokRunner:
    def __init__(self):
        self.running = True

    def get_active_campaigns(self):
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%tiktok%'"
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
        print(f"{CYAN}=== TikTok Runner ==={RESET}")
        print(f"{YELLOW}NOTE: TikTok automation is not available.{RESET}")
        print(f"{YELLOW}Why?{RESET}")
        print(f"  - TikTok has no public API for comments or DMs")
        print(f"  - Unofficial scraping constantly breaks")
        print(f"  - Browser automation is detectable and against ToS")
        print(f"{YELLOW}What you CAN do:{RESET}")
        print(f"  - Use the dashboard to manually import TikTok leads")
        print(f"  - Copy-paste comment URLs or usernames")
        print(f"  - The system will categorize them for you")
        print(f"  - Reach out manually via the TikTok app")
        print(f"{YELLOW}Full automation may be added in a future update.{RESET}")

        update_runner_status("stopped")


if __name__ == "__main__":
    runner = TikTokRunner()
    runner.run()
