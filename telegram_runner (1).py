#!/usr/bin/env python3
"""
Telegram Bot Runner - Connected to LeadGen Pro v3.0
Searches groups, joins them, monitors posts, replies with signatures.
Uses unified DB and config paths.
"""

import os
import sys
import asyncio
import sqlite3
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

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


def get_active_campaigns():
    conn = get_db()
    cursor = conn.execute(
        "SELECT * FROM campaigns WHERE status = 'active' AND platforms LIKE '%telegram%'"
    )
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    campaigns = []
    for row in rows:
        camp = dict(zip(columns, row))
        for field in ['keywords', 'platforms', 'niche_indicators', 'pitches', 'target_groups', 'signature']:
            try:
                camp[field] = json.loads(camp[field]) if camp[field] else ([] if field != 'signature' else {})
            except:
                camp[field] = [] if field != 'signature' else {}
        campaigns.append(camp)
    conn.close()
    return campaigns


def log_activity(campaign_id, action, details, status="success"):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO activity_log (campaign_id, platform, action, details, status) VALUES (?, ?, ?, ?, ?)",
            (campaign_id, "telegram", action, details, status)
        )
        conn.commit()
        conn.close()
    except:
        pass


def add_lead(campaign_id, user_id, username, name, source, message):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO leads (campaign_id, platform, user_id, username, name, source, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (campaign_id, "telegram", user_id, username, name, source, message)
        )
        conn.commit()
        conn.close()
        return True
    except:
        return False


def update_campaign_stats(campaign_id, replies=0, posts=0, leads=0):
    try:
        conn = get_db()
        if replies:
            conn.execute("UPDATE campaigns SET replies_sent = replies_sent + ? WHERE id = ?", (replies, campaign_id))
        if posts:
            conn.execute("UPDATE campaigns SET posts_checked = posts_checked + ? WHERE id = ?", (posts, campaign_id))
        if leads:
            conn.execute("UPDATE campaigns SET leads_found = leads_found + ? WHERE id = ?", (leads, campaign_id))
        conn.commit()
        conn.close()
    except:
        pass


def update_runner_status(status, pid=None, stats=None):
    try:
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO runner_status (platform, status, pid, started_at, last_heartbeat, stats)
            VALUES (?, ?, ?, COALESCE((SELECT started_at FROM runner_status WHERE platform = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, ?)
        """, ("telegram", status, pid, "telegram", json.dumps(stats) if stats else '{}'))
        conn.commit()
        conn.close()
    except:
        pass


def analyze_niche(text, indicators):
    text_lower = text.lower()
    matched = []
    score = 0
    for ind in indicators:
        ind_lower = ind.lower()
        if ind_lower in text_lower:
            matched.append(ind)
            score += 2
        else:
            words = ind_lower.split()
            for w in words:
                if len(w) > 3 and w in text_lower:
                    score += 0.5

    help_words = ["help", "need", "looking for", "want", "please", "struggling", "lost", "forgot"]
    if any(hw in text_lower for hw in help_words):
        score += 1

    confidence = min(score / (len(indicators) * 2), 1.0) if indicators else 0
    return confidence >= 0.5, confidence, matched


def build_signature(campaign_sig, global_sig):
    parts = []
    sig = campaign_sig if campaign_sig else global_sig
    if not sig:
        return ""

    if isinstance(sig, dict):
        if sig.get("whatsapp"):
            parts.append(f"📱 WhatsApp: {sig['whatsapp']}")
        if sig.get("website"):
            parts.append(f"🌐 Website: {sig['website']}")
        if sig.get("custom_text"):
            parts.append(sig["custom_text"])

    if parts:
        return "\n\n" + "\n".join(parts)
    return ""


async def init_client(config):
    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError
    except ImportError:
        print(f"{YELLOW}Installing telethon...{RESET}")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "telethon"], capture_output=True)
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError

    tg_config = config.get("platforms", {}).get("telegram", {})
    api_id = tg_config.get("api_id", "")
    api_hash = tg_config.get("api_hash", "")
    phone = tg_config.get("phone", "")

    if not api_id or not api_hash:
        print(f"{RED}ERROR: Telegram API credentials not set. Go to Dashboard > Settings > Platforms.{RESET}")
        return None

    try:
        client = TelegramClient(str(BASE_DIR / "telegram_runner_session"), int(api_id), api_hash)
        await client.start(phone=phone if phone else None)
        me = await client.get_me()
        print(f"{GREEN}Telegram connected: {me.first_name}{RESET}")
        return client
    except Exception as e:
        print(f"{RED}Telegram connection failed: {e}{RESET}")
        return None


async def search_and_join_groups(client, campaign, config):
    from telethon.tl.functions.messages import SearchGlobalRequest
    from telethon.tl.types import InputPeerEmpty, Channel, Chat
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import FloodWaitError

    keywords = campaign.get("keywords", [])
    print(f"{CYAN}Searching groups for: {', '.join(keywords[:3])}...{RESET}")

    for keyword in keywords[:3]:
        try:
            result = await client(SearchGlobalRequest(
                q=keyword,
                offset_rate=0,
                offset_peer=InputPeerEmpty(),
                offset_id=0,
                limit=10
            ))

            for chat in result.chats:
                if isinstance(chat, (Channel, Chat)):
                    if getattr(chat, 'megagroup', False) or isinstance(chat, Chat):
                        group_id = chat.id
                        name = chat.title
                        members = getattr(chat, 'participants_count', 0) or 0

                        conn = get_db()
                        cursor = conn.execute("SELECT 1 FROM communities WHERE platform = 'telegram' AND name = ?", (name,))
                        if cursor.fetchone():
                            conn.close()
                            continue

                        try:
                            entity = await client.get_entity(group_id)
                            messages = await client.get_messages(entity, limit=5)
                            if len(messages) < 2:
                                conn.close()
                                continue

                            await client(JoinChannelRequest(chat))

                            conn.execute(
                                "INSERT INTO communities (platform, name, username, members, activity_score, joined, campaign_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                ("telegram", name, getattr(chat, 'username', '') or '', members, len(messages), 1, campaign['id'])
                            )
                            conn.commit()
                            conn.close()

                            print(f"{GREEN}[+] Joined: {name} ({members} members){RESET}")
                            log_activity(campaign['id'], "join_group", f"Joined {name}")
                            await asyncio.sleep(random.uniform(3, 7))

                        except Exception as e:
                            conn.close()
                            continue

            await asyncio.sleep(random.uniform(5, 10))

        except FloodWaitError as e:
            print(f"{YELLOW}Rate limit: waiting {e.seconds}s{RESET}")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"{RED}Search error: {e}{RESET}")


async def monitor_groups(client, campaign, config):
    conn = get_db()
    cursor = conn.execute(
        "SELECT * FROM communities WHERE platform = 'telegram' AND joined = 1 AND campaign_id = ?",
        (campaign['id'],)
    )
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    groups = [dict(zip(columns, row)) for row in rows]
    conn.close()

    if not groups:
        print(f"{YELLOW}No groups joined yet for this campaign{RESET}")
        return

    global_sig = config.get("signatures", {})
    campaign_sig = campaign.get("signature", {})

    for group in groups:
        try:
            print(f"{BLUE}Checking: {group['name']}{RESET}")
            entity = await client.get_entity(group['name'])
            messages = await client.get_messages(entity, limit=20)

            for msg in messages:
                if not msg or not msg.message:
                    continue

                update_campaign_stats(campaign['id'], posts=1)

                comments = getattr(msg, 'replies', None)
                comment_count = comments.replies if comments else 0

                if comment_count < 3:
                    continue

                is_match, confidence, matched = analyze_niche(msg.message, campaign['niche_indicators'])

                if is_match:
                    print(f"\n{MAGENTA}[MATCH] {confidence:.0%} confidence{RESET}")
                    print(f"{BLUE}Comments: {comment_count}{RESET}")
                    print(f"{BLUE}Message: {msg.message[:200]}...{RESET}")

                    pitch = random.choice(campaign['pitches']) if campaign['pitches'] else "I can help with this. DM me."
                    sig = build_signature(campaign_sig, global_sig)
                    full_message = pitch + sig

                    delay = random.randint(30, 120)
                    print(f"{YELLOW}Waiting {delay}s before reply...{RESET}")
                    await asyncio.sleep(delay)

                    try:
                        await msg.reply(full_message)
                        update_campaign_stats(campaign['id'], replies=1)
                        log_activity(campaign['id'], "reply", f"Replied to post in {group['name']}")
                        print(f"{GREEN}[REPLIED]{RESET}")
                    except Exception as e:
                        print(f"{RED}Reply failed: {e}{RESET}")

                    if comments:
                        try:
                            replies = await client.get_messages(entity, reply_to=msg.id, limit=20)
                            for reply in replies:
                                if reply and reply.sender:
                                    user = reply.sender
                                    if user and not user.bot:
                                        if add_lead(
                                            campaign['id'],
                                            str(user.id),
                                            getattr(user, 'username', '') or '',
                                            getattr(user, 'first_name', '') or '',
                                            group['name'],
                                            reply.message[:200]
                                        ):
                                            update_campaign_stats(campaign['id'], leads=1)
                        except:
                            pass

                    await asyncio.sleep(random.uniform(5, 10))

            await asyncio.sleep(random.uniform(10, 20))

        except Exception as e:
            print(f"{RED}Check error: {e}{RESET}")


async def run_campaign(client, campaign, config):
    print(f"\n{CYAN}=== Running Campaign: {campaign['name']} ==={RESET}")
    await search_and_join_groups(client, campaign, config)
    await monitor_groups(client, campaign, config)


async def main():
    print(f"{CYAN}=== Telegram Runner Started ==={RESET}")

    if not os.path.exists(DB_PATH):
        print(f"{RED}ERROR: Database not found. Run dashboard first.{RESET}")
        return

    config = load_config()
    client = await init_client(config)
    if not client:
        return

    stats = {"groups_joined": 0, "posts_checked": 0, "replies_sent": 0, "leads_found": 0}

    try:
        while True:
            campaigns = get_active_campaigns()

            if not campaigns:
                print(f"{YELLOW}No active Telegram campaigns. Waiting...{RESET}")
                update_runner_status("waiting", stats=stats)
                await asyncio.sleep(60)
                continue

            for campaign in campaigns:
                await run_campaign(client, campaign, config)
                await asyncio.sleep(random.uniform(30, 60))

            print(f"\n{YELLOW}=== Telegram Stats ==={RESET}")
            print(f"  Groups joined: {stats['groups_joined']}")
            print(f"  Posts checked: {stats['posts_checked']}")
            print(f"  Replies sent: {stats['replies_sent']}")
            print(f"  Leads found: {stats['leads_found']}")
            print(f"{YELLOW}Sleeping 15 minutes...{RESET}\n")

            update_runner_status("running", stats=stats)
            await asyncio.sleep(900)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping...{RESET}")
    finally:
        update_runner_status("stopped")
        await client.disconnect()
        print(f"{GREEN}Telegram runner stopped.{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopped.{RESET}")
