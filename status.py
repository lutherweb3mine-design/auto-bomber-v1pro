#!/usr/bin/env python3
"""
LeadGen Pro - Status Script
============================
Check what's running:
    python status.py
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "leadgen.db"

def main():
    print("📊 LeadGen Pro Status")
    print("=" * 50)

    if not DB_PATH.exists():
        print("❌ Database not found. Run the dashboard first.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Runner status
    print("\n🤖 Runner Status:")
    print("-" * 50)
    cursor = conn.execute("SELECT * FROM runner_status")
    runners = cursor.fetchall()

    if not runners:
        print("   No runners registered yet.")
    else:
        for r in runners:
            status_emoji = "🟢" if r['status'] == 'running' else "🔴" if r['status'] == 'stopped' else "🟡"
            last_beat = r['last_heartbeat'] or "Never"
            print(f"   {status_emoji} {r['platform'].title():12} | {r['status']:8} | Last: {last_beat}")

    # Campaigns
    print("\n🚀 Campaigns:")
    print("-" * 50)
    cursor = conn.execute("SELECT status, COUNT(*) as count FROM campaigns GROUP BY status")
    for row in cursor.fetchall():
        emoji = {"active": "🟢", "paused": "⏸️", "completed": "✅"}.get(row['status'], "⚪")
        print(f"   {emoji} {row['status'].title():10} | {row['count']} campaigns")

    # Stats
    print("\n📈 Overall Stats:")
    print("-" * 50)
    cursor = conn.execute("SELECT COUNT(*) FROM leads")
    total_leads = cursor.fetchone()[0]
    cursor = conn.execute("SELECT SUM(replies_sent) FROM campaigns")
    total_replies = cursor.fetchone()[0] or 0
    cursor = conn.execute("SELECT SUM(posts_checked) FROM campaigns")
    total_posts = cursor.fetchone()[0] or 0

    print(f"   👥 Total Leads:     {total_leads}")
    print(f"   ✉️  Total Replies:   {total_replies}")
    print(f"   📋 Total Posts:     {total_posts}")

    # Recent activity
    print("\n📋 Recent Activity:")
    print("-" * 50)
    cursor = conn.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 5")
    activities = cursor.fetchall()
    if not activities:
        print("   No recent activity.")
    else:
        for act in activities:
            print(f"   [{act['created_at']}] {act['platform']:10} | {act['action']:12} | {act['details'][:40]}")

    conn.close()
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()
