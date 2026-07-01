#!/usr/bin/env python3
"""
Reddit Bot Runner
=================
Monitors subreddits, engages with posts, captures leads.
Connects to LeadGen Dashboard.

SETUP:
pip install praw aiosqlite

RUN:
python reddit_runner.py
"""

import os
import sys
import asyncio
import sqlite3
import json
import random
import time
from datetime import datetime

try:
    import praw
    from praw.models import Submission, Comment
except ImportError:
    print("Installing praw...")
    import subprocess
    subprocess.run(["pip", "install", "praw"], capture_output=True)
    import praw

DB_PATH = "leadgen_dashboard.db"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


class RedditRunner:
    """Reddit campaign runner"""

    def __init__(self):
        self.reddit = None
        self.running = True
        self.stats = {"posts_checked": 0, "replies_sent": 0, "leads_found": 0}

    def get_db(self):
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    def get_active_campaigns(self):
        conn = self.get_db()
        cursor = conn.execute(
            "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%reddit%'"
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        campaigns = []
        for row in rows:
            camp = dict(zip(columns, row))
            camp['keywords'] = json.loads(camp['keywords']) if camp['keywords'] else []
            camp['niche_indicators'] = json.loads(camp['niche_indicators']) if camp['niche_indicators'] else []
            camp['pitches'] = json.loads(camp['pitches']) if camp['pitches'] else []
            camp['target_groups'] = json.loads(camp['target_groups']) if camp['target_groups'] else []
            campaigns.append(camp)
        conn.close()
        return campaigns

    def log_activity(self, campaign_id, action, details, status="success"):
        try:
            conn = self.get_db()
            conn.execute(
                "INSERT INTO activity_log (campaign_id, platform, action, details, status) VALUES (?, ?, ?, ?, ?)",
                (campaign_id, "reddit", action, details, status)
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
                (campaign_id, "reddit", user_id, username, name, source, message)
            )
            conn.commit()
            conn.close()
            self.stats["leads_found"] += 1
        except:
            pass

    def update_campaign_stats(self, campaign_id, replies=0, posts=0):
        try:
            conn = self.get_db()
            if replies:
                conn.execute("UPDATE campaigns SET replies_sent = replies_sent + ? WHERE id = ?", (replies, campaign_id))
            if posts:
                conn.execute("UPDATE campaigns SET posts_checked = posts_checked + ? WHERE id = ?", (posts, campaign_id))
            conn.commit()
            conn.close()
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

    def init_reddit(self):
        """Initialize Reddit client"""
        config_path = "leadgen_config.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            rd_config = config.get("platforms", {}).get("reddit", {})
            client_id = rd_config.get("client_id", "")
            client_secret = rd_config.get("client_secret", "")
            username = rd_config.get("username", "")
            password = rd_config.get("password", "")
        else:
            print(f"{RED}ERROR: No config found. Set Reddit credentials in dashboard first.{RESET}")
            return False

        if not all([client_id, client_secret, username, password]):
            print(f"{RED}ERROR: Reddit credentials incomplete. Go to Dashboard > Settings > Platforms.{RESET}")
            return False

        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                user_agent="LeadGenPro/1.0"
            )
            me = self.reddit.user.me()
            print(f"{GREEN}Reddit connected: u/{me.name}{RESET}")
            return True
        except Exception as e:
            print(f"{RED}Reddit connection failed: {e}{RESET}")
            return False

    def find_subreddits(self, campaign):
        """Find relevant subreddits"""
        keywords = campaign.get("keywords", [])
        target_groups = campaign.get("target_groups", [])

        subreddits = set()

        # Search for subreddits
        for keyword in keywords[:3]:
            try:
                for subreddit in self.reddit.subreddits.search(keyword, limit=5):
                    if subreddit.subscribers and subreddit.subscribers > 1000:
                        subreddits.add(subreddit.display_name)
            except:
                continue

        # Add target groups
        for group in target_groups:
            try:
                sub = self.reddit.subreddit(group)
                if sub.subscribers and sub.subscribers > 500:
                    subreddits.add(group)
            except:
                continue

        return list(subreddits)[:10]  # Limit

    def monitor_subreddit(self, campaign, subreddit_name):
        """Monitor a subreddit for posts"""
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get recent posts
            posts = list(subreddit.new(limit=20))

            for post in posts:
                if not post or not post.selftext:
                    continue

                self.stats["posts_checked"] += 1
                self.update_campaign_stats(campaign['id'], posts=1)

                # Check comments count
                if post.num_comments < 3:
                    continue

                # Combine title + body for analysis
                full_text = f"{post.title} {post.selftext}"

                # Check niche
                is_match, confidence, matched = self.analyze_niche(full_text, campaign['niche_indicators'])

                if is_match:
                    print(f"\n{MAGENTA}[MATCH] r/{subreddit_name} - {confidence:.0%} confidence{RESET}")
                    print(f"{BLUE}Title: {post.title[:100]}{RESET}")
                    print(f"{BLUE}Comments: {post.num_comments}{RESET}")

                    # Reply
                    pitch = random.choice(campaign['pitches']) if campaign['pitches'] else "I can help with this. Feel free to DM me."

                    delay = random.randint(30, 120)
                    print(f"{YELLOW}Waiting {delay}s before reply...{RESET}")
                    time.sleep(delay)

                    try:
                        post.reply(pitch)
                        self.stats["replies_sent"] += 1
                        self.update_campaign_stats(campaign['id'], replies=1)
                        self.log_activity(campaign['id'], "reply", f"Replied to post in r/{subreddit_name}")
                        print(f"{GREEN}[REPLIED]{RESET}")
                    except Exception as e:
                        print(f"{RED}Reply failed: {e}{RESET}")

                    # Extract leads from comments
                    try:
                        post.comments.replace_more(limit=0)
                        for comment in post.comments[:20]:
                            if comment and comment.author:
                                self.add_lead(
                                    campaign['id'],
                                    str(comment.author.id) if hasattr(comment.author, 'id') else '',
                                    str(comment.author.name),
                                    '',
                                    f"r/{subreddit_name}",
                                    comment.body[:200]
                                )
                    except:
                        pass

                    time.sleep(random.uniform(5, 10))

            time.sleep(random.uniform(10, 20))

        except Exception as e:
            print(f"{RED}Subreddit error: {e}{RESET}")

    def run_campaign(self, campaign):
        """Run a single campaign"""
        print(f"\n{CYAN}=== Running Reddit Campaign: {campaign['name']} ==={RESET}")

        # Find subreddits
        subreddits = self.find_subreddits(campaign)
        print(f"{BLUE}Monitoring subreddits: {', '.join(subreddits)}{RESET}")

        for subreddit in subreddits:
            self.monitor_subreddit(campaign, subreddit)
            time.sleep(random.uniform(30, 60))

    def run(self):
        """Main loop"""
        print(f"{CYAN}=== Reddit Runner Started ==={RESET}")

        if not os.path.exists(DB_PATH):
            print(f"{RED}ERROR: Dashboard database not found. Run dashboard first.{RESET}")
            return

        if not self.init_reddit():
            return

        try:
            while self.running:
                campaigns = self.get_active_campaigns()

                if not campaigns:
                    print(f"{YELLOW}No active Reddit campaigns. Waiting...{RESET}")
                    time.sleep(60)
                    continue

                for campaign in campaigns:
                    self.run_campaign(campaign)
                    time.sleep(random.uniform(30, 60))

                print(f"\n{YELLOW}=== Reddit Stats ==={RESET}")
                print(f"  Posts checked: {self.stats['posts_checked']}")
                print(f"  Replies sent: {self.stats['replies_sent']}")
                print(f"  Leads found: {self.stats['leads_found']}")
                print(f"{YELLOW}Sleeping 15 minutes...{RESET}\n")

                time.sleep(900)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Stopping...{RESET}")
        finally:
            print(f"{GREEN}Reddit runner stopped.{RESET}")


if __name__ == "__main__":
    runner = RedditRunner()
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped.{RESET}")
