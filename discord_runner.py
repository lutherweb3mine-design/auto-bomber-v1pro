#!/usr/bin/env python3
"""
Discord Bot Runner
==================
Monitors Discord servers/channels, engages with messages.
Connects to LeadGen Dashboard.

SETUP:
pip install discord.py aiosqlite

RUN:
python discord_runner.py
"""

import os
import sys
import asyncio
import sqlite3
import json
import random
from datetime import datetime

try:
    import discord
    from discord.ext import tasks, commands
except ImportError:
    print("Installing discord.py...")
    import subprocess
    subprocess.run(["pip", "install", "discord.py"], capture_output=True)
    import discord
    from discord.ext import tasks, commands

DB_PATH = "leadgen_dashboard.db"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


class DiscordRunner(discord.Client):
    """Discord campaign runner"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)

        self.running = True
        self.stats = {"messages_checked": 0, "replies_sent": 0, "leads_found": 0}
        self.active_campaigns = []

    def get_db(self):
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    def get_active_campaigns(self):
        conn = self.get_db()
        cursor = conn.execute(
            "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%discord%'"
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

    def log_activity(self, campaign_id, action, details, status="success"):
        try:
            conn = self.get_db()
            conn.execute(
                "INSERT INTO activity_log (campaign_id, platform, action, details, status) VALUES (?, ?, ?, ?, ?)",
                (campaign_id, "discord", action, details, status)
            )
            conn.commit()
            conn.close()
        except:
            pass

    def add_lead(self, campaign_id, user_id, username, name, source, message):
        try:
            conn = self.get_db()
            conn.execute(
                "INSERT INTO leads (campaign_id, platform, user_id, username, name, source, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, "discord", user_id, username, name, source, message)
            )
            conn.commit()
            conn.close()
            self.stats["leads_found"] += 1
        except:
            pass

    def analyze_niche(self, text, indicators):
        text_lower = text.lower()
        matched = []
        score = 0
        for ind in indicators:
            ind_lower = ind.lower()
            if ind_lower in text_lower:
                matched.append(ind)
                score += 2
            else:
                for w in ind_lower.split():
                    if len(w) > 3 and w in text_lower:
                        score += 0.5

        help_words = ["help", "need", "looking for", "want", "please", "struggling", "lost", "forgot"]
        if any(hw in text_lower for hw in help_words):
            score += 1

        confidence = min(score / (len(indicators) * 2), 1.0) if indicators else 0
        return confidence >= 0.5, confidence, matched

    async def on_ready(self):
        print(f"{GREEN}Discord connected: {self.user}{RESET}")
        self.check_messages.start()

    @tasks.loop(minutes=15)
    async def check_messages(self):
        """Check messages every 15 minutes"""
        self.active_campaigns = self.get_active_campaigns()

        if not self.active_campaigns:
            print(f"{YELLOW}No active Discord campaigns{RESET}")
            return

        for campaign in self.active_campaigns:
            await self.process_campaign(campaign)

    async def process_campaign(self, campaign):
        """Process a single campaign"""
        print(f"\n{CYAN}=== Discord Campaign: {campaign['name']} ==={RESET}")

        keywords = campaign.get('keywords', [])

        # Search for servers/guilds (we can only monitor ones the bot is in)
        for guild in self.guilds:
            print(f"{BLUE}Checking guild: {guild.name}{RESET}")

            for channel in guild.text_channels:
                try:
                    # Get recent messages
                    messages = []
                    async for msg in channel.history(limit=50):
                        messages.append(msg)

                    for msg in messages:
                        if msg.author == self.user:
                            continue

                        self.stats["messages_checked"] += 1

                        # Check niche
                        is_match, confidence, matched = self.analyze_niche(msg.content, campaign['niche_indicators'])

                        if is_match:
                            print(f"\n{MAGENTA}[MATCH] #{channel.name} - {confidence:.0%}{RESET}")
                            print(f"{BLUE}From: {msg.author.name}{RESET}")
                            print(f"{BLUE}Message: {msg.content[:200]}...{RESET}")

                            # Reply
                            pitch = random.choice(campaign['pitches']) if campaign['pitches'] else "I can help. DM me for details."

                            delay = random.randint(30, 120)
                            print(f"{YELLOW}Waiting {delay}s...{RESET}")
                            await asyncio.sleep(delay)

                            try:
                                await msg.reply(pitch)
                                self.stats["replies_sent"] += 1
                                self.log_activity(campaign['id'], "reply", f"Replied in #{channel.name}")
                                print(f"{GREEN}[REPLIED]{RESET}")
                            except Exception as e:
                                print(f"{RED}Reply failed: {e}{RESET}")

                            # Save lead
                            self.add_lead(
                                campaign['id'],
                                str(msg.author.id),
                                str(msg.author.name),
                                str(msg.author.display_name),
                                f"{guild.name}/#{channel.name}",
                                msg.content[:200]
                            )

                            await asyncio.sleep(random.uniform(5, 10))

                except Exception as e:
                    print(f"{RED}Channel error: {e}{RESET}")

    @check_messages.before_loop
    async def before_check(self):
        await self.wait_until_ready()

    def run_bot(self):
        """Start the bot"""
        print(f"{CYAN}=== Discord Runner Started ==={RESET}")

        if not os.path.exists(DB_PATH):
            print(f"{RED}ERROR: Dashboard database not found. Run dashboard first.{RESET}")
            return

        # Get token from config
        config_path = "leadgen_config.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            token = config.get("platforms", {}).get("discord", {}).get("token", "")
        else:
            print(f"{RED}ERROR: No config found. Set Discord token in dashboard first.{RESET}")
            return

        if not token:
            print(f"{RED}ERROR: Discord token not set. Go to Dashboard > Settings > Platforms.{RESET}")
            return

        try:
            self.run(token)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Stopping...{RESET}")
        finally:
            print(f"{GREEN}Discord runner stopped.{RESET}")


if __name__ == "__main__":
    runner = DiscordRunner()
    try:
        runner.run_bot()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped.{RESET}")
