#!/usr/bin/env python3
"""
Twitter/X Bot Runner - Connected to LeadGen Pro v3.0
Monitors tweets, engages with replies.
Uses unified DB and config paths.
"""

import os
import sys
import asyncio
import sqlite3
import json
import random
import time
from datetime import datetime
from pathlib import Path

try:
    import tweepy
except ImportError:
    print("Installing tweepy...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "tweepy"], capture_output=True)
    import tweepy

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "leadgen.db"
CONFIG_PATH = BASE_DIR / "config.json"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def get_db():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


class TwitterRunner:
    def __init__(self):
        self.api = None
        self.client = None
        self.running = True
        self.stats = {"tweets_checked": 0, "replies_sent": 0, "leads_found": 0}

    def get_active_campaigns(self):
        conn = get_db()
        cursor = conn.execute(
            "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%twitter%'"
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
            conn = get_db()
            conn.execute(
                "INSERT INTO activity_log (campaign_id, platform, action, details, status) VALUES (?, ?, ?, ?, ?)",
                (campaign_id, "twitter", action, details, status)
            )
            conn.commit()
            conn.close()
        except:
            pass

    def add_lead(self, campaign_id, user_id, username, name, source, message):
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO leads (campaign_id, platform, user_id, username, name, source, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, "twitter", user_id, username, name, source, message)
            )
            conn.commit()
            conn.close()
            self.stats["leads_found"] += 1
        except:
            pass

    def update_campaign_stats(self, campaign_id, replies=0, posts=0):
        try:
            conn = get_db()
            if replies:
                conn.execute("UPDATE campaigns SET replies_sent = replies_sent + ? WHERE id = ?", (replies, campaign_id))
            if posts:
                conn.execute("UPDATE campaigns SET posts_checked = posts_checked + ? WHERE id = ?", (posts, campaign_id))
            conn.commit()
            conn.close()
        except:
            pass

    def update_runner_status(self, status, pid=None, stats=None):
        try:
            conn = get_db()
            conn.execute("""
                INSERT OR REPLACE INTO runner_status (platform, status, pid, started_at, last_heartbeat, stats)
                VALUES (?, ?, ?, COALESCE((SELECT started_at FROM runner_status WHERE platform = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, ?)
            """, ("twitter", status, pid, "twitter", json.dumps(stats) if stats else '{}'))
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

    def init_twitter(self):
        config = load_config()
        tw_config = config.get("platforms", {}).get("twitter", {})
        api_key = tw_config.get("api_key", "")
        api_secret = tw_config.get("api_secret", "")
        access_token = tw_config.get("access_token", "")
        access_secret = tw_config.get("access_secret", "")

        if not all([api_key, api_secret, access_token, access_secret]):
            print(f"{RED}ERROR: Twitter credentials incomplete. Go to Dashboard > Settings > Platforms.{RESET}")
            return False

        try:
            auth = tweepy.OAuthHandler(api_key, api_secret)
            auth.set_access_token(access_token, access_secret)
            self.api = tweepy.API(auth, wait_on_rate_limit=True)

            me = self.api.verify_credentials()
            print(f"{GREEN}Twitter connected: @{me.screen_name}{RESET}")
            return True
        except Exception as e:
            print(f"{RED}Twitter connection failed: {e}{RESET}")
            return False

    def search_tweets(self, campaign):
        keywords = campaign.get("keywords", [])

        for keyword in keywords[:3]:
            try:
                print(f"{CYAN}Searching: {keyword}{RESET}")
                tweets = tweepy.Cursor(
                    self.api.search_tweets,
                    q=keyword,
                    lang="en",
                    tweet_mode="extended",
                    result_type="recent"
                ).items(20)

                for tweet in tweets:
                    self.stats["tweets_checked"] += 1
                    self.update_campaign_stats(campaign['id'], posts=1)

                    if tweet.user.screen_name == self.api.verify_credentials().screen_name:
                        continue

                    if tweet.reply_count and tweet.reply_count < 2:
                        continue

                    full_text = tweet.full_text if hasattr(tweet, 'full_text') else tweet.text
                    is_match, confidence, matched = self.analyze_niche(full_text, campaign['niche_indicators'])

                    if is_match:
                        print(f"\n{MAGENTA}[MATCH] @{tweet.user.screen_name} - {confidence:.0%}{RESET}")
                        print(f"{BLUE}Tweet: {full_text[:200]}...{RESET}")

                        pitch = random.choice(campaign['pitches']) if campaign['pitches'] else "I can help with this. DM me for details."

                        delay = random.randint(30, 120)
                        print(f"{YELLOW}Waiting {delay}s...{RESET}")
                        time.sleep(delay)

                        try:
                            self.api.update_status(
                                status=pitch,
                                in_reply_to_status_id=tweet.id,
                                auto_populate_reply_metadata=True
                            )
                            self.stats["replies_sent"] += 1
                            self.update_campaign_stats(campaign['id'], replies=1)
                            self.log_activity(campaign['id'], "reply", f"Replied to @{tweet.user.screen_name}")
                            print(f"{GREEN}[REPLIED]{RESET}")
                        except Exception as e:
                            print(f"{RED}Reply failed: {e}{RESET}")

                        self.add_lead(
                            campaign['id'],
                            str(tweet.user.id),
                            tweet.user.screen_name,
                            tweet.user.name,
                            "twitter_search",
                            full_text[:200]
                        )

                        time.sleep(random.uniform(5, 10))

                time.sleep(random.uniform(10, 20))

            except Exception as e:
                print(f"{RED}Search error: {e}{RESET}")

    def run_campaign(self, campaign):
        print(f"\n{CYAN}=== Twitter Campaign: {campaign['name']} ==={RESET}")
        self.search_tweets(campaign)

    def run(self):
        print(f"{CYAN}=== Twitter Runner Started ==={RESET}")

        if not os.path.exists(DB_PATH):
            print(f"{RED}ERROR: Dashboard database not found. Run dashboard first.{RESET}")
            return

        if not self.init_twitter():
            return

        try:
            while self.running:
                campaigns = self.get_active_campaigns()

                if not campaigns:
                    print(f"{YELLOW}No active Twitter campaigns. Waiting...{RESET}")
                    self.update_runner_status("waiting", stats=self.stats)
                    time.sleep(60)
                    continue

                for campaign in campaigns:
                    self.run_campaign(campaign)
                    time.sleep(random.uniform(30, 60))

                print(f"\n{YELLOW}=== Twitter Stats ==={RESET}")
                print(f"  Tweets checked: {self.stats['tweets_checked']}")
                print(f"  Replies sent: {self.stats['replies_sent']}")
                print(f"  Leads found: {self.stats['leads_found']}")
                print(f"{YELLOW}Sleeping 15 minutes...{RESET}\n")

                self.update_runner_status("running", stats=self.stats)
                time.sleep(900)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Stopping...{RESET}")
        finally:
            self.update_runner_status("stopped")
            print(f"{GREEN}Twitter runner stopped.{RESET}")


if __name__ == "__main__":
    runner = TwitterRunner()
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped.{RESET}")
