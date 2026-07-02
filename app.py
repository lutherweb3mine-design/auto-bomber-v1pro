#!/usr/bin/env python3
"""
LeadGen Pro - Unified App v4.0
================================
Dynamic AI - Works with ANY niche without hardcoded templates
Auto-campaign generation from any user input
Enhanced account setup wizard + bulk import

Run: streamlit run app.py
"""

import os
import sys
import json
import time
import random
import sqlite3
import threading
import subprocess
import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    print("ERROR: streamlit not installed. Run: pip install streamlit")
    sys.exit(1)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ============ PATHS ============
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "leadgen.db"
CONFIG_PATH = BASE_DIR / "config.json"
ACCOUNTS_PATH = BASE_DIR / "accounts.json"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

APP_NAME = "LeadGen Pro"
APP_VERSION = "4.0.0"

DEFAULT_CONFIG = {
    "general": {
        "theme": "dark",
        "language": "english",
        "check_interval": 15,
        "max_campaigns": 10,
        "auto_save": True,
    },
    "platforms": {
        "telegram": {"enabled": False, "api_id": "", "api_hash": "", "phone": "", "connected": False},
        "reddit": {"enabled": False, "client_id": "", "client_secret": "", "username": "", "password": "", "connected": False},
        "discord": {"enabled": False, "token": "", "bot_name": "", "connected": False},
        "twitter": {"enabled": False, "api_key": "", "api_secret": "", "access_token": "", "access_secret": "", "connected": False},
        "facebook": {"enabled": False, "email": "", "password": "", "connected": False},
        "instagram": {"enabled": False, "username": "", "password": "", "connected": False},
        "tiktok": {"enabled": False, "note": "TikTok automation is heavily restricted. Manual import mode available.", "connected": False},
    },
    "engagement": {
        "min_comments": 3,
        "reply_delay_min": 30,
        "reply_delay_max": 120,
        "max_groups_per_platform": 50,
        "max_replies_per_hour": 5,
        "max_joins_per_day": 10,
        "human_like": True,
    },
    "ai": {
        "enabled": True,
        "model": "dynamic",
        "confidence_threshold": 0.5,
        "analyze_comments": True,
        "context_window": 500,
    },
    "signatures": {
        "enabled": False,
        "whatsapp": "",
        "website": "",
        "custom_text": "",
        "randomize": False,
        "signatures_list": [],
    }
}

# ============ DATABASE ============
class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.conn = None
        self.init()

    def init(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                template TEXT,
                keywords TEXT,
                platforms TEXT,
                niche_indicators TEXT,
                pitches TEXT,
                target_groups TEXT,
                signature TEXT,
                status TEXT DEFAULT 'paused',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP,
                replies_sent INTEGER DEFAULT 0,
                leads_found INTEGER DEFAULT 0,
                posts_checked INTEGER DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                platform TEXT,
                user_id TEXT,
                username TEXT,
                name TEXT,
                email TEXT,
                phone TEXT,
                source TEXT,
                message TEXT,
                context TEXT,
                contacted INTEGER DEFAULT 0,
                converted INTEGER DEFAULT 0,
                notes TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                platform TEXT,
                action TEXT,
                details TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                name TEXT,
                username TEXT,
                url TEXT,
                members INTEGER,
                activity_score REAL,
                joined INTEGER DEFAULT 0,
                campaign_id INTEGER,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS runner_status (
                platform TEXT PRIMARY KEY,
                status TEXT DEFAULT 'stopped',
                pid INTEGER,
                started_at TIMESTAMP,
                last_heartbeat TIMESTAMP,
                stats TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                suggestions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def add_campaign(self, campaign_data):
        cursor = self.conn.execute("""
            INSERT INTO campaigns (name, description, template, keywords, platforms, niche_indicators, pitches, target_groups, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign_data["name"],
            campaign_data["description"],
            campaign_data.get("template", "custom"),
            json.dumps(campaign_data.get("keywords", [])),
            json.dumps(campaign_data.get("platforms", [])),
            json.dumps(campaign_data.get("niche_indicators", [])),
            json.dumps(campaign_data.get("pitches", [])),
            json.dumps(campaign_data.get("target_groups", [])),
            json.dumps(campaign_data.get("signature", {}))
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_campaigns(self, status=None):
        if status:
            cursor = self.conn.execute("SELECT * FROM campaigns WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor = self.conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        rows = cursor.fetchall()
        campaigns = []
        for row in rows:
            camp = dict(row)
            for field in ['keywords', 'platforms', 'niche_indicators', 'pitches', 'target_groups', 'signature']:
                try:
                    camp[field] = json.loads(camp[field]) if camp[field] else ([] if field != 'signature' else {})
                except:
                    camp[field] = [] if field != 'signature' else {}
            campaigns.append(camp)
        return campaigns

    def get_campaign(self, campaign_id):
        cursor = self.conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = cursor.fetchone()
        if not row:
            return None
        camp = dict(row)
        for field in ['keywords', 'platforms', 'niche_indicators', 'pitches', 'target_groups', 'signature']:
            try:
                camp[field] = json.loads(camp[field]) if camp[field] else ([] if field != 'signature' else {})
            except:
                camp[field] = [] if field != 'signature' else {}
        return camp

    def update_campaign_status(self, campaign_id, status):
        self.conn.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))
        self.conn.commit()

    def delete_campaign(self, campaign_id):
        self.conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        self.conn.commit()

    def update_campaign_stats(self, campaign_id, replies=0, posts=0, leads=0):
        if replies:
            self.conn.execute("UPDATE campaigns SET replies_sent = replies_sent + ? WHERE id = ?", (replies, campaign_id))
        if posts:
            self.conn.execute("UPDATE campaigns SET posts_checked = posts_checked + ? WHERE id = ?", (posts, campaign_id))
        if leads:
            self.conn.execute("UPDATE campaigns SET leads_found = leads_found + ? WHERE id = ?", (leads, campaign_id))
        self.conn.commit()

    def add_lead(self, lead_data):
        self.conn.execute("""
            INSERT INTO leads (campaign_id, platform, user_id, username, name, email, phone, source, message, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_data.get("campaign_id"),
            lead_data.get("platform"),
            lead_data.get("user_id"),
            lead_data.get("username"),
            lead_data.get("name"),
            lead_data.get("email"),
            lead_data.get("phone"),
            lead_data.get("source"),
            lead_data.get("message"),
            lead_data.get("context")
        ))
        self.conn.commit()

    def get_leads(self, campaign_id=None, platform=None):
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        if campaign_id:
            query += " AND campaign_id = ?"
            params.append(campaign_id)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY found_at DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self):
        cursor = self.conn.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = cursor.fetchone()[0]
        cursor = self.conn.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = cursor.fetchone()[0]
        cursor = self.conn.execute("SELECT COUNT(*) FROM leads")
        total_leads = cursor.fetchone()[0]
        cursor = self.conn.execute("SELECT SUM(replies_sent) FROM campaigns")
        total_replies = cursor.fetchone()[0] or 0
        cursor = self.conn.execute("SELECT SUM(posts_checked) FROM campaigns")
        total_posts = cursor.fetchone()[0] or 0
        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_leads": total_leads,
            "total_replies": total_replies,
            "total_posts": total_posts
        }

    def log_activity(self, campaign_id, platform, action, details, status="success"):
        self.conn.execute("""
            INSERT INTO activity_log (campaign_id, platform, action, details, status)
            VALUES (?, ?, ?, ?, ?)
        """, (campaign_id, platform, action, details, status))
        self.conn.commit()

    def get_recent_activity(self, limit=20):
        cursor = self.conn.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def update_runner_status(self, platform, status, pid=None, stats=None):
        self.conn.execute("""
            INSERT OR REPLACE INTO runner_status (platform, status, pid, started_at, last_heartbeat, stats)
            VALUES (?, ?, ?, COALESCE((SELECT started_at FROM runner_status WHERE platform = ?), CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, ?)
        """, (platform, status, pid, platform, json.dumps(stats) if stats else '{}'))
        self.conn.commit()

    def get_runner_status(self):
        cursor = self.conn.execute("SELECT * FROM runner_status")
        return {row['platform']: dict(row) for row in cursor.fetchall()}

    def save_chat_message(self, role, content, suggestions=None):
        self.conn.execute(
            "INSERT INTO chat_history (role, content, suggestions) VALUES (?, ?, ?)",
            (role, content, json.dumps(suggestions) if suggestions else None)
        )
        self.conn.commit()

    def get_chat_history(self, limit=50):
        cursor = self.conn.execute(
            "SELECT * FROM chat_history ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        history = []
        for row in rows:
            entry = dict(row)
            try:
                entry['suggestions'] = json.loads(entry['suggestions']) if entry['suggestions'] else None
            except:
                entry['suggestions'] = None
            history.append(entry)
        return list(reversed(history))

    def clear_chat_history(self):
        self.conn.execute("DELETE FROM chat_history")
        self.conn.commit()


# ============ CONFIG MANAGER ============
class ConfigManager:
    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = str(config_path)
        self.config = self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, section, key=None):
        if key:
            return self.config.get(section, {}).get(key)
        return self.config.get(section, {})

    def set(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save()

    def reset(self):
        self.config = DEFAULT_CONFIG.copy()
        self.save()


# ============ DYNAMIC AI CHAT ASSISTANT ============
class AIChatAssistant:
    """Real AI with intent detection, entity extraction, and contextual responses."""

    def __init__(self):
        self.niche_knowledge = {
            "crypto": {"category": "tech", "keywords": ["crypto", "bitcoin", "wallet", "blockchain", "ethereum"]},
            "web_design": {"category": "tech", "keywords": ["website", "web design", "web developer", "landing page"]},
            "app_dev": {"category": "tech", "keywords": ["app", "mobile app", "application", "ios", "android"]},
            "real_estate": {"category": "home", "keywords": ["house", "apartment", "property", "realtor", "mortgage"]},
            "marketing": {"category": "business", "keywords": ["marketing", "seo", "ads", "promote", "traffic"]},
            "writing": {"category": "creative", "keywords": ["writer", "content", "blog", "article", "copywriting"]},
            "social_media": {"category": "creative", "keywords": ["followers", "engagement", "instagram", "social media"]},
            "ecommerce": {"category": "business", "keywords": ["shopify", "dropshipping", "ecommerce", "online store"]},
            "coaching": {"category": "business", "keywords": ["coach", "mentor", "course", "training"]},
            "design": {"category": "creative", "keywords": ["logo", "branding", "graphic design", "ui ux"]},
            "video": {"category": "creative", "keywords": ["video editor", "editing", "youtube", "video production"]},
            "va": {"category": "business", "keywords": ["virtual assistant", "admin", "personal assistant"]},
            "tax": {"category": "business", "keywords": ["tax", "accountant", "accounting", "bookkeeping"]},
            "fitness": {"category": "health", "keywords": ["fitness", "trainer", "workout", "gym"]},
            "language": {"category": "education", "keywords": ["learn english", "language tutor", "spanish"]},
            "career": {"category": "education", "keywords": ["resume", "career", "job", "interview"]},
            "tickets": {"category": "entertainment", "keywords": ["concert", "tickets", "festival", "gig"]},
            "travel": {"category": "travel", "keywords": ["travel", "trip", "vacation", "flight", "hotel"]},
            "food": {"category": "local_service", "keywords": ["catering", "chef", "meal prep", "food"]},
            "pet": {"category": "local_service", "keywords": ["dog walker", "pet sitter", "grooming"]},
            "photo": {"category": "creative", "keywords": ["photographer", "wedding photo", "portrait"]},
            "music": {"category": "creative", "keywords": ["music producer", "mixing", "mastering"]},
            "car": {"category": "automotive", "keywords": ["rent a car", "buy car", "car dealer"]},
            "immigration": {"category": "business", "keywords": ["immigration", "visa", "green card", "citizenship"]},
            "plumbing": {"category": "local_service", "keywords": ["plumber", "plumbing", "leak", "pipe"]},
            "electrician": {"category": "local_service", "keywords": ["electrician", "electrical", "wiring"]},
            "cleaning": {"category": "local_service", "keywords": ["cleaning", "house cleaner", "maid"]},
            "moving": {"category": "local_service", "keywords": ["moving company", "movers", "relocation"]},
            "security": {"category": "local_service", "keywords": ["security guard", "alarm system", "cctv"]},
            "insurance": {"category": "business", "keywords": ["insurance", "health insurance", "car insurance"]},
            "legal": {"category": "business", "keywords": ["lawyer", "attorney", "legal help"]},
            "therapy": {"category": "health", "keywords": ["therapist", "counseling", "mental health"]},
            "dental": {"category": "health", "keywords": ["dentist", "dental", "braces"]},
            "medical": {"category": "health", "keywords": ["doctor", "physician", "specialist"]},
            "roofing": {"category": "local_service", "keywords": ["roofing", "roof repair", "shingles"]},
            "landscaping": {"category": "local_service", "keywords": ["landscaping", "lawn care"]},
            "hvac": {"category": "local_service", "keywords": ["hvac", "air conditioning", "heating"]},
            "pest_control": {"category": "local_service", "keywords": ["pest control", "exterminator"]},
            "locksmith": {"category": "local_service", "keywords": ["locksmith", "lock out", "rekey"]},
            "tutoring": {"category": "education", "keywords": ["tutor", "math tutor", "homework help"]},
            "wedding": {"category": "entertainment", "keywords": ["wedding planner", "wedding venue"]},
            "event_planning": {"category": "entertainment", "keywords": ["event planner", "party planner"]},
            "interior_design": {"category": "home", "keywords": ["interior design", "home decor"]},
            "cybersecurity": {"category": "tech", "keywords": ["cybersecurity", "hacker", "penetration test"]},
            "data_recovery": {"category": "tech", "keywords": ["data recovery", "hard drive"]},
            "translation": {"category": "business", "keywords": ["translator", "translation"]},
            "notary": {"category": "business", "keywords": ["notary", "notary public"]},
            "limo": {"category": "entertainment", "keywords": ["limo", "limousine"]},
            "dj": {"category": "entertainment", "keywords": ["dj", "wedding dj"]},
            "bartending": {"category": "entertainment", "keywords": ["bartender", "bartending"]},
            "florist": {"category": "entertainment", "keywords": ["florist", "flowers"]},
            "tailor": {"category": "local_service", "keywords": ["tailor", "alterations"]},
            "nanny": {"category": "local_service", "keywords": ["nanny", "babysitter"]},
            "senior_care": {"category": "health", "keywords": ["senior care", "elderly care"]},
            "handyman": {"category": "local_service", "keywords": ["handyman", "home repair"]},
            "solar": {"category": "local_service", "keywords": ["solar panels", "solar installation"]},
            "garage_door": {"category": "local_service", "keywords": ["garage door"]},
            "window": {"category": "local_service", "keywords": ["window repair"]},
            "foundation": {"category": "local_service", "keywords": ["foundation repair"]},
            "mold": {"category": "local_service", "keywords": ["mold removal"]},
            "water_damage": {"category": "local_service", "keywords": ["water damage"]},
            "fire_damage": {"category": "local_service", "keywords": ["fire damage"]},
        }

        self.platform_knowledge = {
            "telegram": {
                "name": "Telegram",
                "icon": "✈️",
                "difficulty": "Easy",
                "time": "5 min",
                "credentials": ["api_id", "api_hash", "phone"],
                "setup_url": "my.telegram.org",
                "setup_steps": [
                    "Go to my.telegram.org and log in with your phone number",
                    "Click 'API development tools'",
                    "Create a new app (any name works)",
                    "Copy the api_id (numbers) and api_hash (long string)",
                    "Paste them in the Account Setup tab + your phone number",
                    "Click Test Connection to verify"
                ],
                "capabilities": ["Search groups", "Join groups", "Monitor messages", "Reply to posts", "DM users"],
                "testable": True,
                "api_docs": "https://core.telegram.org/api",
            },
            "reddit": {
                "name": "Reddit",
                "icon": "🔴",
                "difficulty": "Easy",
                "time": "5 min",
                "credentials": ["client_id", "client_secret", "username", "password"],
                "setup_url": "reddit.com/prefs/apps",
                "setup_steps": [
                    "Go to reddit.com/prefs/apps",
                    "Click 'create another app...'",
                    "Select 'script' type, name it 'LeadGen', redirect URI: http://localhost:8080",
                    "Copy client_id (under the app name) and client_secret",
                    "Enter your Reddit username and password",
                    "Click Test Connection to verify"
                ],
                "capabilities": ["Search subreddits", "Monitor posts", "Reply to posts", "Read comments", "Extract user data"],
                "testable": True,
                "api_docs": "https://www.reddit.com/dev/api/",
            },
            "discord": {
                "name": "Discord",
                "icon": "💬",
                "difficulty": "Easy",
                "time": "5 min",
                "credentials": ["token", "application_id", "public_key"],
                "setup_url": "discord.com/developers/applications",
                "setup_steps": [
                    "Go to discord.com/developers/applications",
                    "Click 'New Application' and name it (e.g., 'LeadGenBot')",
                    "Copy the Application ID and Public Key from the General Information tab",
                    "Go to the 'Bot' tab on the left sidebar",
                    "Click 'Add Bot' then 'Reset Token' and copy the token",
                    "Paste the token, Application ID, and Public Key in Account Setup",
                    "Click Test Connection to verify"
                ],
                "capabilities": ["Monitor servers", "Read messages", "Reply to messages", "Join servers", "DM users"],
                "testable": True,
                "api_docs": "https://discord.com/developers/docs",
            },
            "twitter": {
                "name": "Twitter/X",
                "icon": "🐦",
                "difficulty": "Medium",
                "time": "10 min + approval",
                "credentials": ["api_key", "api_secret", "access_token", "access_secret"],
                "setup_url": "developer.twitter.com",
                "setup_steps": [
                    "Go to developer.twitter.com and sign in",
                    "Apply for a developer account (Elevated access, free)",
                    "Create a Project, then add an App inside it",
                    "Go to 'Keys and Tokens' tab",
                    "Copy API Key, API Secret, Access Token, and Access Token Secret",
                    "Paste all four in Account Setup and click Test Connection"
                ],
                "capabilities": ["Search tweets", "Monitor hashtags", "Reply to tweets", "DM users", "Follow users"],
                "testable": True,
                "api_docs": "https://developer.twitter.com/en/docs",
            },
            "facebook": {
                "name": "Facebook",
                "icon": "📘",
                "difficulty": "Hard",
                "time": "20+ min",
                "credentials": ["email", "password", "access_token"],
                "setup_url": "developers.facebook.com",
                "setup_steps": [
                    "⚠️ Facebook automation is heavily restricted and risky",
                    "Option A: Use Facebook Graph API (requires Business Verification)",
                    "Option B: Use Selenium automation (advanced, high ban risk)",
                    "For Graph API: Go to developers.facebook.com",
                    "Create an app → get User Access Token with pages_read_engagement permission",
                    "Enter email and access token in Account Setup",
                    "Password is only needed if using Selenium mode"
                ],
                "capabilities": ["Read group posts", "Reply to posts", "Search groups", "Limited messaging"],
                "testable": False,
                "warning": "Facebook aggressively bans automation. Use aged accounts or Graph API only.",
            },
            "instagram": {
                "name": "Instagram",
                "icon": "📸",
                "difficulty": "Hard",
                "time": "20+ min",
                "credentials": ["username", "password"],
                "setup_url": "developers.facebook.com",
                "setup_steps": [
                    "⚠️ Instagram automation is heavily restricted",
                    "Option A: Instagram Basic Display API (read-only, limited)",
                    "Option B: Instagram Graph API (requires FB Business account)",
                    "Option C: instagrapi library (unofficial, very high ban risk)",
                    "For Graph API: Link IG to FB Business → get token from developers.facebook.com",
                    "Enter username and access token in Account Setup"
                ],
                "capabilities": ["Read comments", "Limited posting", "Search hashtags", "Profile data"],
                "testable": False,
                "warning": "Instagram aggressively bans automation. Use aged accounts or official API only.",
            },
            "tiktok": {
                "name": "TikTok",
                "icon": "🎵",
                "difficulty": "Very Hard",
                "time": "N/A",
                "credentials": [],
                "setup_url": "N/A",
                "setup_steps": [
                    "❌ TikTok has no public API for messaging or automation",
                    "TikTok Research API exists but is read-only and requires approval",
                    "For now, TikTok is NOT recommended for lead generation",
                    "Alternative: Monitor TikTok comments manually, then reach out via other platforms",
                ],
                "capabilities": [],
                "testable": False,
                "warning": "TikTok automation is practically impossible without violating ToS.",
            },
        }

        self.category_platforms = {
            "local_service": ["reddit", "facebook"],
            "creative": ["reddit", "instagram", "twitter"],
            "tech": ["reddit", "twitter", "discord"],
            "business": ["reddit", "twitter", "facebook"],
            "health": ["reddit", "facebook", "instagram"],
            "education": ["reddit", "discord", "telegram"],
            "entertainment": ["reddit", "twitter", "discord"],
            "travel": ["reddit", "facebook", "twitter"],
            "home": ["reddit", "facebook"],
            "automotive": ["reddit", "facebook"],
        }

        self.intent_patterns = {
            "greeting": {
                "patterns": [
                    r"^(hi|hello|hey|sup|yo|hola|greetings)\b",
                    r"^(good\s+(morning|afternoon|evening|night))\b",
                    r"^(what\s*'\s*up|howdy|how\s+are\s+you|how\s+you\s+doing|how\s+r\s*u|how\s+is\s+it\s+going)\b",
                ],
                "weight": 1.0,
            },
            "platform_setup_help": {
                "patterns": [
                    r"(how\s+(do|can|to)\s+(i|you)\s+(setup|set\s+up|configure|connect|link))\b",
                    r"(how\s+(do|can)\s+i\s+(get|find|create)\s+(my|a|an)?\s*(api|token|key|credential|account))\b",
                    r"(where\s+(do|can)\s+i\s+(get|find)\s+(my|the)?\s*(api|token|key|credential))\b",
                    r"(setup|configure|connect)\s+(my|the)?\s*(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\b",
                    r"(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\s+(setup|config|credential|api|token)\b",
                    r"(what\s+(do|does)\s+i\s+need\s+for)\s+(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\b",
                    r"(how\s+to\s+get)\s+(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\s+(api|token|key)\b",
                ],
                "weight": 1.0,
            },
            "platform_status": {
                "patterns": [
                    r"(is|are)\s+(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\s+(connected|working|setup|ready)\b",
                    r"(status\s+of)\s+(telegram|reddit|discord|twitter|facebook|instagram|tiktok)\b",
                    r"(show|check)\s+(my|the)?\s*(account|platform)\s*status\b",
                    r"(which\s+platforms)\s+(are\s+connected|work)\b",
                ],
                "weight": 1.0,
            },
            "campaign_creation": {
                "patterns": [
                    r"(i\s+(want|need|looking\s+for))\b",
                    r"(find\s+(me|people|clients|leads))\b",
                    r"(get\s+me)\s+(leads|clients|customers)\b",
                    r"(create|make|start|build)\s+(a\s+)?campaign\b",
                    r"(generate)\s+(leads|campaign)\b",
                    r"(help\s+me\s+find)\b",
                ],
                "weight": 0.9,
            },
            "suggestion_request": {
                "patterns": [
                    r"(suggest|recommend|idea|what\s+should|what\s+kind|options|examples|show\s+me|list)\b",
                    r"(what\s+niches|what\s+can\s+i)\b",
                    r"(give\s+me\s+(some\s+)?(ideas|options|examples))\b",
                ],
                "weight": 1.0,
            },
            "general_help": {
                "patterns": [
                    r"(how\s+does\s+(this|it)\s+work)\b",
                    r"(what\s+can\s+you\s+do)\b",
                    r"(how\s+to\s+use)\b",
                    r"(explain)\b",
                    r"(help\s+me)\b",
                ],
                "weight": 0.8,
            },
            "status_query": {
                "patterns": [
                    r"(how\s+many)\s+(leads|campaigns|replies)\b",
                    r"(show\s+me)\s+(my\s+)?(campaigns|leads|stats)\b",
                    r"(what\s+are)\s+(my\s+)?(stats|numbers|results)\b",
                    r"(dashboard|overview|summary)\b",
                ],
                "weight": 1.0,
            },
        }

    def _detect_intent(self, text):
        text_lower = text.lower().strip()
        scores = {}
        entities = {"platforms": [], "niche": None, "topic": None}

        for intent_name, intent_data in self.intent_patterns.items():
            score = 0
            for pattern in intent_data["patterns"]:
                if re.search(pattern, text_lower):
                    score += intent_data["weight"]
            scores[intent_name] = score

        for plat_name in self.platform_knowledge:
            if plat_name in text_lower:
                entities["platforms"].append(plat_name)

        best_niche = None
        best_score = 0
        for niche, data in self.niche_knowledge.items():
            score = 0
            for keyword in data["keywords"]:
                if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower):
                    score += 3
                elif keyword.lower() in text_lower:
                    score += 1
            if score > best_score:
                best_score = score
                best_niche = niche

        if best_niche and best_score >= 3:
            entities["niche"] = best_niche
            entities["topic"] = best_niche.replace("_", " ")
        else:
            fillers = {"i", "want", "need", "looking", "for", "help", "me", "find", "people", "who", "get", "some", "a", "an", "the", "my", "with", "to", "and", "or", "but", "in", "on", "at", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can", "how", "what", "where", "when", "why"}
            words = [w for w in text_lower.split() if w not in fillers and len(w) > 2]
            if words:
                entities["topic"] = " ".join(words[:3])

        best_intent = max(scores, key=scores.get)
        best_confidence = scores[best_intent]

        if best_confidence < 0.5 and entities["topic"]:
            best_intent = "campaign_creation"
            best_confidence = 0.5

        if best_confidence < 0.3:
            best_intent = "general_help"
            best_confidence = 0.3

        return best_intent, best_confidence, entities

    def _generate_campaign(self, topic, niche=None):
        if niche and niche in self.niche_knowledge:
            data = self.niche_knowledge[niche]
            category = data["category"]
        else:
            category = "business"

        platforms = self.category_platforms.get(category, ["reddit", "twitter", "facebook"])

        keywords = [
            f"need {topic}", f"looking for {topic}", f"{topic} help",
            f"{topic} service", f"best {topic}", f"cheap {topic}",
            f"{topic} near me", f"{topic} recommendation",
            f"emergency {topic}", f"{topic} asap",
        ]

        indicators = [
            topic, f"need {topic}", f"looking for {topic}",
            f"{topic} help", f"{topic} service",
            "help", "need", "looking for", "please", "struggling", "recommendation",
            "emergency", "urgent", "asap", "repair", "fix", "broken",
        ]

        pitches = [
            f"I provide professional {topic} services. DM me for a free quote and fast response.",
            f"Need {topic} help? I am experienced and available. Message me for details!",
            f"I specialize in {topic}. DM me if you need help or have questions!",
            f"Looking for {topic}? I can help. Reach out and let us discuss your needs.",
            f"🚨 {topic} emergency? I offer fast response times. DM me immediately!",
        ]

        return {
            "name": f"{topic.title()} Leads",
            "description": f"Find people who need {topic} services or products",
            "template": niche or "custom",
            "keywords": keywords[:10],
            "platforms": platforms,
            "niche_indicators": indicators[:15],
            "pitches": pitches[:5],
            "target_groups": [topic.replace(" ", ""), f"{topic}help", f"{topic}services", "help", "recommendations", "local"],
            "confidence": 0.7 if niche else 0.4,
            "topic": topic,
            "category": category,
        }

    def _build_setup_response(self, platform_name, config=None):
        plat = platform_name.lower()
        if plat not in self.platform_knowledge:
            return f"I don't have setup information for '{platform_name}'. Try one of: Telegram, Reddit, Discord, Twitter, Facebook, Instagram."

        pk = self.platform_knowledge[plat]
        response = f"## {pk['icon']} Setting up {pk['name']}\n\n"
        response += f"**Difficulty:** {pk['difficulty']} | **Time:** {pk['time']}\n\n"

        if pk.get("warning"):
            response += f"⚠️ **{pk['warning']}**\n\n"

        response += "### Step-by-step:\n"
        for i, step in enumerate(pk["setup_steps"], 1):
            response += f"{i}. {step}\n"

        response += f"\n### Credentials needed:\n"
        for cred in pk["credentials"]:
            response += f"- `{cred}`\n"

        response += f"\n### What it can do:\n"
        for cap in pk["capabilities"]:
            response += f"- {cap}\n"

        if pk["testable"]:
            response += f"\n✅ After entering credentials, click **Test Connection** in Account Setup to verify everything works."
        else:
            response += f"\n⚠️ This platform doesn't support automated testing. You'll need to verify manually."

        if config and plat in config.get("platforms", {}):
            plat_cfg = config["platforms"][plat]
            has_creds = any(plat_cfg.get(c, "") for c in pk["credentials"] if c in plat_cfg)
            if has_creds:
                response += f"\n\n📋 **Your status:** Credentials saved. {'Connected!' if plat_cfg.get('connected') else 'Click Test Connection to verify.'}"
            else:
                response += f"\n\n📋 **Your status:** No credentials entered yet."

        return response

    def _build_status_response(self, config, db_stats, runner_status):
        response = "## 📊 System Status\n\n"
        response += "### Campaigns\n"
        response += f"- Total: {db_stats.get('total_campaigns', 0)}\n"
        response += f"- Active: {db_stats.get('active_campaigns', 0)}\n"
        response += f"- Leads captured: {db_stats.get('total_leads', 0)}\n"
        response += f"- Replies sent: {db_stats.get('total_replies', 0)}\n\n"

        response += "### Platform Connections\n"
        for plat, pk in self.platform_knowledge.items():
            plat_cfg = config.get("platforms", {}).get(plat, {})
            connected = plat_cfg.get("connected", False)
            enabled = plat_cfg.get("enabled", False)
            status = "🟢 Connected" if connected else ("🟡 Setup" if enabled else "🔴 Not configured")
            runner = runner_status.get(plat, {}).get("status", "stopped")
            runner_emoji = "🟢" if runner == "running" else "⚪"
            response += f"- {pk['icon']} **{pk['name']}**: {status} | Runner: {runner_emoji} {runner}\n"

        response += "\n💡 **Tip:** Go to **Account Setup** to connect platforms, or **Dashboard** for the full view."
        return response

    def chat(self, user_message, config=None, db_stats=None, runner_status=None):
        text = user_message.strip()
        intent, confidence, entities = self._detect_intent(text)

        if intent == "greeting":
            return {
                "type": "greeting",
                "message": """Hey! 👋 I am your AI Campaign Assistant.

I can help you with:
• **Create campaigns** for any niche — just describe what you need
• **Setup accounts** — I'll guide you through connecting Telegram, Reddit, Discord, etc.
• **Check status** — Ask me about your campaigns, leads, or platform connections
• **Get suggestions** — Type "suggest" to see popular niches

**Examples:**
- "I want people who need plumbers"
- "How do I setup Telegram?"
- "Show me my stats"
- "What platforms are connected?"

What would you like to do?""",
                "suggestions": None,
                "follow_up": None
            }

        if intent == "platform_setup_help":
            if entities["platforms"]:
                plat = entities["platforms"][0]
                response = self._build_setup_response(plat, config)
                return {
                    "type": "platform_setup",
                    "message": response,
                    "suggestions": {"platform": plat, "action": "setup"},
                    "follow_up": f"Need help with anything else about {plat}?"
                }
            else:
                response = "## 🔧 Platform Setup Help\n\nI can guide you through setting up any platform. Which one do you need help with?\n\n"
                for plat, pk in self.platform_knowledge.items():
                    response += f"{pk['icon']} **{pk['name']}** — {pk['difficulty']}, ~{pk['time']}\n"
                return {
                    "type": "platform_setup",
                    "message": response,
                    "suggestions": None,
                    "follow_up": "Which platform do you want to setup?"
                }

        if intent == "platform_status":
            if config and db_stats is not None and runner_status is not None:
                response = self._build_status_response(config, db_stats, runner_status)
                return {
                    "type": "status",
                    "message": response,
                    "suggestions": None,
                    "follow_up": None
                }
            else:
                return {
                    "type": "status",
                    "message": "I can show you your full system status. Go to the **Dashboard** tab to see everything at a glance, or ask me something specific like 'Is Telegram connected?'",
                    "suggestions": None,
                    "follow_up": None
                }

        if intent == "status_query":
            if db_stats:
                response = f"## 📈 Your Stats\n\n"
                response += f"- **Campaigns:** {db_stats.get('total_campaigns', 0)} total, {db_stats.get('active_campaigns', 0)} active\n"
                response += f"- **Leads:** {db_stats.get('total_leads', 0)} captured\n"
                response += f"- **Replies sent:** {db_stats.get('total_replies', 0)}\n"
                response += f"- **Posts checked:** {db_stats.get('total_posts', 0)}\n\n"
                response += "Go to the **Dashboard** or **Leads** tab for full details."
                return {
                    "type": "status",
                    "message": response,
                    "suggestions": None,
                    "follow_up": None
                }
            else:
                return {
                    "type": "status",
                    "message": "Your stats will appear here once you create campaigns and start generating leads. Try creating your first campaign!",
                    "suggestions": None,
                    "follow_up": "Want me to help you create a campaign?"
                }

        if intent == "suggestion_request":
            suggestions = [
                "🏠 **Real Estate** — Buyers, sellers, renters",
                "🔧 **Home Services** — Plumbers, electricians, HVAC, cleaning",
                "💰 **Crypto Recovery** — Lost wallets, stuck funds",
                "🎨 **Creative** — Web design, graphic design, photography, video editing",
                "📱 **Tech** — App development, cybersecurity, data recovery",
                "💼 **Business** — Marketing, VA, coaching, accounting",
                "💪 **Health & Fitness** — Personal trainers, therapists, dentists",
                "🎓 **Education** — Tutors, language teachers, career coaches",
                "🎫 **Entertainment** — Concert tickets, event planning, DJs",
                "✈️ **Travel** — Vacation planners, hotel booking, tours",
                "🐕 **Pet Services** — Dog walkers, groomers, pet sitters",
                "🚗 **Automotive** — Car rental, repair, sales",
                "🌍 **Immigration** — Visa help, green cards, citizenship",
                "⚖️ **Legal** — Lawyers, attorneys, notary services",
                "🏠 **Home Improvement** — Roofing, landscaping, interior design",
                "🎵 **Music** — Producers, mixing, mastering, beat makers",
            ]
            return {
                "type": "suggestions",
                "message": "Here are some popular campaign niches:\n\n" + "\n".join(suggestions) + "\n\nJust tell me which one interests you, or describe your own niche!",
                "suggestions": None,
                "follow_up": "Which niche would you like to explore?"
            }

        if intent == "general_help":
            return {
                "type": "help",
                "message": """Here's what I can do for you:

**1. Create Campaigns**
Just describe your niche — e.g., "I want plumbing leads" or "immigration visa help" — and I'll generate keywords, platforms, and pitches automatically.

**2. Setup Accounts**
Ask me "How do I setup Telegram?" or "What do I need for Reddit?" and I'll give you step-by-step instructions.

**3. Check Status**
Ask "Show me my stats" or "Is Discord connected?" and I'll tell you what's working.

**4. Get Ideas**
Type "suggest" to see popular niches, or just describe what you're looking for.

**Quick start:** Tell me what kind of leads you want to find!""",
                "suggestions": None,
                "follow_up": "What kind of leads do you want to find?"
            }

        topic = entities.get("topic", "")
        niche = entities.get("niche")

        if not topic:
            return {
                "type": "clarification",
                "message": "I'd love to help, but I need a bit more detail. What kind of leads are you looking for?\n\n**Examples:**\n- \"People who need plumbers\"\n- \"Immigration visa clients\"\n- \"Wedding photographer bookings\"\n- \"Cybersecurity audit prospects\"\n\nOr type **'suggest'** to see popular options.",
                "suggestions": None,
                "follow_up": "What niche do you want to target?"
            }

        campaign = self._generate_campaign(topic, niche)

        response = f"## 🎯 {campaign['name']}\n\n"
        response += f"**Topic:** {campaign['topic'].title()}\n"
        response += f"**Category:** {campaign['category'].replace('_', ' ').title()}\n"
        response += f"**Best Platforms:** {', '.join(campaign['platforms'])}\n\n"
        response += f"**Keywords:**\n"
        for kw in campaign['keywords'][:5]:
            response += f"- {kw}\n"
        response += f"\n**Sample Pitch:**\n> {campaign['pitches'][0]}\n\n"

        if campaign['confidence'] < 0.6:
            response += "⚠️ This is based on your input — you can adjust everything in the campaign form.\n\n"

        response += "Click **Use These Settings** to auto-fill the campaign form, or tell me more to refine it!"

        return {
            "type": "campaign",
            "message": response,
            "suggestions": campaign,
            "follow_up": None
        }


# ============ PLATFORM UI DATA ============
PLATFORM_UI_DATA = {
    "telegram": {
        "icon": "✈️",
        "color": "#0088cc",
        "fields": [
            {"key": "api_id", "label": "API ID", "type": "text", "help": "Numbers only. From my.telegram.org → API Development Tools"},
            {"key": "api_hash", "label": "API Hash", "type": "password", "help": "Long string. From my.telegram.org → API Development Tools"},
            {"key": "phone", "label": "Phone Number", "type": "text", "help": "Your Telegram phone number with country code, e.g. +1234567890"},
        ],
        "testable": True,
    },
    "reddit": {
        "icon": "🔴",
        "color": "#FF4500",
        "fields": [
            {"key": "client_id", "label": "Client ID", "type": "text", "help": "From reddit.com/prefs/apps — shown under your app name"},
            {"key": "client_secret", "label": "Client Secret", "type": "password", "help": "From reddit.com/prefs/apps — the secret string"},
            {"key": "username", "label": "Reddit Username", "type": "text", "help": "Your Reddit username (without u/)"},
            {"key": "password", "label": "Reddit Password", "type": "password", "help": "Your Reddit account password"},
        ],
        "testable": True,
    },
    "discord": {
        "icon": "💬",
        "color": "#5865F2",
        "fields": [
            {"key": "token", "label": "Bot Token", "type": "password", "help": "From discord.com/developers → Your App → Bot tab → Reset Token"},
            {"key": "application_id", "label": "Application ID", "type": "text", "help": "From discord.com/developers → Your App → General Information tab"},
            {"key": "public_key", "label": "Public Key", "type": "text", "help": "From discord.com/developers → Your App → General Information tab"},
            {"key": "bot_name", "label": "Bot Name", "type": "text", "help": "Optional display name for your bot"},
        ],
        "testable": True,
    },
    "twitter": {
        "icon": "🐦",
        "color": "#1DA1F2",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "text", "help": "From developer.twitter.com → Project → App → Keys and Tokens"},
            {"key": "api_secret", "label": "API Secret", "type": "password", "help": "From developer.twitter.com → Project → App → Keys and Tokens"},
            {"key": "access_token", "label": "Access Token", "type": "text", "help": "From developer.twitter.com → Project → App → Keys and Tokens"},
            {"key": "access_secret", "label": "Access Token Secret", "type": "password", "help": "From developer.twitter.com → Project → App → Keys and Tokens"},
        ],
        "testable": True,
    },
    "facebook": {
        "icon": "📘",
        "color": "#1877F2",
        "fields": [
            {"key": "email", "label": "Email / Username", "type": "text", "help": "Your Facebook login email (for Selenium mode) or app ID (for Graph API)"},
            {"key": "password", "label": "Password / Access Token", "type": "password", "help": "Password for Selenium mode, or Access Token for Graph API mode"},
        ],
        "testable": False,
    },
    "instagram": {
        "icon": "📸",
        "color": "#E4405F",
        "fields": [
            {"key": "username", "label": "Instagram Username", "type": "text", "help": "Your Instagram username"},
            {"key": "password", "label": "Password / Access Token", "type": "password", "help": "Password for direct login, or Access Token for Graph API"},
        ],
        "testable": False,
    },
    "tiktok": {
        "icon": "🎵",
        "color": "#000000",
        "fields": [],
        "testable": False,
    },
}

ACCOUNT_BUYING_GUIDE = """
### Where to Buy Aged Accounts

| Marketplace | Platform | Price Range | Notes |
|-------------|----------|-------------|-------|
| **AccsMarket** | Reddit, Twitter, Discord | $3-15 | Aged accounts with karma/followers |
| **PlayerUp** | All platforms | $5-50 | Middleman service, safer |
| **RedditBay** (r/redditbay) | Reddit | $5-20 | Check seller reputation |
| **Telegram groups** | Telegram | $2-10 | Search 'account seller' groups |
| **EpicNPC** | All platforms | $5-30 | Gaming-focused but has social accounts |

**⚠️ Risks:**
- Accounts can still be banned
- Some sellers are scams — use escrow when possible
- Aged accounts work better than fresh ones
- Never use your main personal account for automation
"""

# ============ CSS ============
CUSTOM_CSS = """
<style>
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .metric-value { font-size: 32px; font-weight: 700; }
    .metric-label { font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }
    .platform-card {
        background: #1a1a2e;
        border: 1px solid #2a2a4a;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        transition: all 0.2s;
    }
    .platform-card:hover { border-color: #3a3a6a; }
    .platform-card.connected { border-left: 3px solid #00ff88; }
    .platform-card.setup { border-left: 3px solid #ffaa00; }
    .platform-card.offline { border-left: 3px solid #ff4444; }
    .chat-user {
        background: #2a2a4a;
        border-radius: 12px 12px 12px 2px;
        padding: 12px 16px;
        margin: 8px 0;
        max-width: 80%;
    }
    .chat-assistant {
        background: linear-gradient(135deg, #1a3a4a 0%, #1a2a3a 100%);
        border-radius: 12px 12px 2px 12px;
        padding: 12px 16px;
        margin: 8px 0 8px auto;
        max-width: 80%;
        border: 1px solid #2a4a5a;
    }
    .setup-step {
        background: #1a1a2e;
        border-left: 3px solid #00d4ff;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
    }
    .setup-step-number {
        display: inline-block;
        width: 24px;
        height: 24px;
        background: #00d4ff;
        color: #000;
        border-radius: 50%;
        text-align: center;
        line-height: 24px;
        font-weight: bold;
        font-size: 12px;
        margin-right: 10px;
    }
    [data-testid="stSidebar"] { background: #0f0f1a; }
    [data-testid="stSidebar"] .stButton button {
        background: transparent;
        border: 1px solid #2a2a4a;
        color: #ccc;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: #1a1a3e;
        border-color: #3a3a7a;
        color: #fff;
    }
    h1, h2, h3 { color: #e0e0e0 !important; }
</style>
"""

# ============ UI FUNCTIONS ============
def init_session_state():
    defaults = {
        "db": None,
        "config": None,
        "ai": None,
        "chat_history": [],
        "last_ai_suggestion": None,
        "active_tab": "Dashboard",
        "campaign_draft": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 10px 0;">
            <div style="font-size: 28px; font-weight: 800; color: #00d4ff; letter-spacing: 2px;">🔥 LEADGEN PRO</div>
            <div style="font-size: 11px; color: #666; letter-spacing: 3px; text-transform: uppercase; margin-top: 4px;">Dynamic AI v4.1</div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()

        pages = [
            ("📊", "Dashboard", "Overview & status"),
            ("🤖", "AI Assistant", "Chat & create campaigns"),
            ("🚀", "Campaigns", "Manage campaigns"),
            ("👥", "Leads", "View captured leads"),
            ("🔌", "Account Setup", "Connect platforms"),
            ("📥", "Bulk Import", "Import credentials"),
            ("⚙️", "Settings", "Configuration"),
        ]

        for icon, page, desc in pages:
            is_active = st.session_state.active_tab == page
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{icon} {page}", use_container_width=True, type=btn_type, help=desc):
                st.session_state.active_tab = page
                st.rerun()

        st.divider()
        st.markdown("""
        <div style="font-size: 11px; color: #555; padding: 10px; border: 1px solid #2a2a4a; border-radius: 8px;">
            💡 <b>Tip:</b> Use the AI Assistant to create campaigns for ANY niche instantly.
        </div>
        """, unsafe_allow_html=True)


def render_dashboard():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>📊 Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Real-time overview of your lead generation system</p>", unsafe_allow_html=True)

    db = st.session_state.db
    stats = db.get_stats()
    runner_status = db.get_runner_status()
    config = st.session_state.config.config

    # Metric cards
    cols = st.columns(5)
    metrics = [
        ("📁", "Campaigns", stats["total_campaigns"], "#00d4ff"),
        ("▶️", "Active", stats["active_campaigns"], "#00ff88"),
        ("👥", "Leads", stats["total_leads"], "#ff6b6b"),
        ("💬", "Replies", stats["total_replies"], "#ffd93d"),
        ("🔍", "Posts", stats["total_posts"], "#a855f7"),
    ]
    for col, (icon, label, value, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div style="font-size: 20px; margin-bottom: 5px;">{icon}</div>
                <div class="metric-value" style="color: {color};">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)

    # Platform health
    st.markdown("<h2 style='font-size: 18px; font-weight: 600; margin-bottom: 15px;'>🔌 Platform Health</h2>", unsafe_allow_html=True)

    platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]
    plat_cols = st.columns(4)

    for i, plat in enumerate(platforms):
        with plat_cols[i % 4]:
            plat_cfg = config.get("platforms", {}).get(plat, {})
            connected = plat_cfg.get("connected", False)
            enabled = plat_cfg.get("enabled", False)
            last_error = plat_cfg.get("last_error", "")
            last_tested = plat_cfg.get("last_tested", "")

            pk = AIChatAssistant().platform_knowledge.get(plat, {})
            icon = pk.get("icon", "📱")
            name = pk.get("name", plat.title())

            if connected:
                status_class = "connected"
                status_dot = "🟢"
                status_text = "Connected"
                status_color = "#00ff88"
            elif enabled:
                status_class = "setup"
                status_dot = "🟡"
                status_text = "Setup"
                status_color = "#ffaa00"
            else:
                status_class = "offline"
                status_dot = "🔴"
                status_text = "Offline"
                status_color = "#ff4444"

            runner = runner_status.get(plat, {})
            runner_state = runner.get("status", "stopped")
            runner_running = runner_state == "running"

            st.markdown(f"""
            <div class="platform-card {status_class}">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-size: 16px; font-weight: 600;">{icon} {name}</div>
                    <div style="font-size: 11px; color: {status_color}; display: flex; align-items: center;">
                        <span style="margin-right: 6px;">{status_dot}</span>{status_text}
                    </div>
                </div>
                <div style="font-size: 11px; color: #666; margin-top: 8px;">
                    🤖 Runner: <span style="color: {'#00ff88' if runner_running else '#666'}">{runner_state.title()}</span>
                </div>
                {f'<div style="font-size: 10px; color: #ff4444; margin-top: 4px;">❌ {last_error[:50]}</div>' if last_error else ''}
                {f'<div style="font-size: 10px; color: #444; margin-top: 4px;">🕐 Tested: {last_tested}</div>' if last_tested else ''}
            </div>
            """, unsafe_allow_html=True)

            if not connected:
                if st.button(f"Setup {name}", key=f"dash_setup_{plat}", use_container_width=True, type="secondary"):
                    st.session_state.active_tab = "Account Setup"
                    st.session_state["setup_platform"] = plat
                    st.rerun()

    st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)

    # Quick actions
    st.markdown("<h2 style='font-size: 18px; font-weight: 600; margin-bottom: 15px;'>⚡ Quick Actions</h2>", unsafe_allow_html=True)
    qa_cols = st.columns(4)
    actions = [
        ("🤖", "Ask AI", "AI Assistant", "Get campaign ideas from AI"),
        ("🚀", "New Campaign", "Campaigns", "Create a new lead campaign"),
        ("🔌", "Connect", "Account Setup", "Link your social accounts"),
        ("📥", "Import", "Bulk Import", "Bulk import credentials"),
    ]
    for col, (icon, label, tab, help_text) in zip(qa_cols, actions):
        with col:
            if st.button(f"{icon} {label}", use_container_width=True, help=help_text):
                st.session_state.active_tab = tab
                st.rerun()

    st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)

    # Recent activity
    st.markdown("<h2 style='font-size: 18px; font-weight: 600; margin-bottom: 15px;'>📋 Recent Activity</h2>", unsafe_allow_html=True)
    activities = db.get_recent_activity(10)
    if activities:
        for act in activities:
            emoji = "✅" if act["status"] == "success" else "❌"
            border_color = "#00ff88" if act["status"] == "success" else "#ff4444"
            st.markdown(f"""
            <div style="background: #1a1a2e; border-radius: 8px; padding: 10px 15px; margin: 5px 0; border-left: 3px solid {border_color};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span>{emoji} <b>{act['platform'].title()}</b> — {act['action']}</span>
                    <span style="font-size: 11px; color: #555;">{act['created_at']}</span>
                </div>
                <div style="font-size: 12px; color: #888; margin-top: 3px;">{act['details'][:80]}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No activity yet. Start a campaign to see activity here.")


def render_ai_assistant():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>🤖 AI Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Describe ANY niche and I'll generate a complete campaign. Ask me about setup, status, anything.</p>", unsafe_allow_html=True)

    ai = st.session_state.ai
    db = st.session_state.db
    config = st.session_state.config.config
    stats = db.get_stats()
    runner_status = db.get_runner_status()

    # Chat display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start;">
                    <div class="chat-user">{msg['content']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-end;">
                    <div class="chat-assistant">{msg['content']}</div>
                </div>
                """, unsafe_allow_html=True)
                if msg.get("suggestions"):
                    st.session_state.last_ai_suggestion = msg["suggestions"]
                    if st.button("Use These Settings", key=f"use_suggestion_{msg.get('id', 0)}"):
                        st.session_state.campaign_draft = msg["suggestions"]
                        st.session_state.active_tab = "Campaigns"
                        st.rerun()

    # Input
    user_input = st.chat_input("Ask me anything... (e.g., 'How do I setup Telegram?', 'I need plumbing leads', 'Show my stats')")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        db.save_chat_message("user", user_input)

        response = ai.chat(user_input, config=config, db_stats=stats, runner_status=runner_status)
        msg_entry = {
            "role": "assistant",
            "content": response["message"],
            "suggestions": response.get("suggestions"),
            "id": len(st.session_state.chat_history)
        }
        st.session_state.chat_history.append(msg_entry)
        db.save_chat_message("assistant", response["message"], response.get("suggestions"))
        st.rerun()

    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

    # Quick prompts
    st.markdown("<p style='color: #666; font-size: 12px;'>💡 Try asking:</p>", unsafe_allow_html=True)
    prompt_cols = st.columns(3)
    quick_prompts = [
        "How do I setup Telegram?",
        "I need plumbing leads",
        "Show me my stats",
        "How do I get Reddit API?",
        "Immigration lawyer clients",
        "What platforms are connected?",
    ]
    for i, prompt in enumerate(quick_prompts):
        with prompt_cols[i % 3]:
            if st.button(prompt, key=f"prompt_{i}", use_container_width=True, type="secondary"):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                db.save_chat_message("user", prompt)
                response = ai.chat(prompt, config=config, db_stats=stats, runner_status=runner_status)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response["message"],
                    "suggestions": response.get("suggestions"),
                    "id": len(st.session_state.chat_history)
                })
                db.save_chat_message("assistant", response["message"], response.get("suggestions"))
                st.rerun()


def render_campaigns():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>🚀 Campaigns</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Create and manage your lead generation campaigns</p>", unsafe_allow_html=True)

    db = st.session_state.db
    ai = st.session_state.ai

    tab_list = ["📋 All Campaigns", "➕ Create New"]
    tabs = st.tabs(tab_list)

    with tabs[0]:
        campaigns = db.get_campaigns()
        if not campaigns:
            st.info("No campaigns yet. Go to AI Assistant or click Create New.")
        else:
            for camp in campaigns:
                status_color = "#00ff88" if camp['status'] == 'active' else "#ffaa00"
                status_icon = "🟢" if camp['status'] == 'active' else "⏸️"
                with st.expander(f"{status_icon} {camp['name']} (ID: {camp['id']})"):
                    st.markdown(f"""
                    <div style="display: flex; gap: 20px;">
                        <div style="flex: 2;">
                            <p><b>Description:</b> {camp['description']}</p>
                            <p><b>Platforms:</b> {', '.join(camp['platforms'])}</p>
                            <p><b>Keywords:</b> {', '.join(camp['keywords'][:5])}{'...' if len(camp['keywords']) > 5 else ''}</p>
                        </div>
                        <div style="flex: 1; text-align: center;">
                            <div style="font-size: 24px; font-weight: 700; color: #00d4ff;">{camp['replies_sent']}</div>
                            <div style="font-size: 11px; color: #666;">REPLIES</div>
                            <div style="font-size: 24px; font-weight: 700; color: #ff6b6b; margin-top: 10px;">{camp['leads_found']}</div>
                            <div style="font-size: 11px; color: #666;">LEADS</div>
                            <div style="font-size: 24px; font-weight: 700; color: #a855f7; margin-top: 10px;">{camp['posts_checked']}</div>
                            <div style="font-size: 11px; color: #666;">POSTS</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        if camp["status"] == "active":
                            if st.button("⏸️ Pause Campaign", key=f"pause_{camp['id']}", use_container_width=True):
                                db.update_campaign_status(camp["id"], "paused")
                                st.rerun()
                        else:
                            if st.button("▶️ Activate Campaign", key=f"activate_{camp['id']}", use_container_width=True):
                                db.update_campaign_status(camp["id"], "active")
                                st.rerun()
                    with c2:
                        if st.button("🗑️ Delete", key=f"del_{camp['id']}", use_container_width=True, type="secondary"):
                            db.delete_campaign(camp["id"])
                            st.rerun()

    with tabs[1]:
        draft = st.session_state.get("campaign_draft")

        with st.form("create_campaign"):
            st.markdown("<h3>Create New Campaign</h3>", unsafe_allow_html=True)
            name = st.text_input("Campaign Name *", value=draft["name"] if draft else "")
            description = st.text_input("Description", value=draft["description"] if draft else "")

            col1, col2 = st.columns(2)
            with col1:
                all_platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]
                default_platforms = draft["platforms"] if draft else ["reddit"]
                platforms = st.multiselect("Platforms *", all_platforms, default=default_platforms)
            with col2:
                all_templates = ["custom"] + list(ai.niche_knowledge.keys())
                default_template = draft.get("template", "custom") if draft else "custom"
                try:
                    template_idx = all_templates.index(default_template)
                except ValueError:
                    template_idx = 0
                template = st.selectbox("Template", all_templates, index=template_idx)

            keywords = st.text_area("Keywords (one per line)", value="\n".join(draft["keywords"]) if draft else "", height=100)
            indicators = st.text_area("Niche Indicators (one per line)", value="\n".join(draft["niche_indicators"]) if draft else "", height=100)
            pitches = st.text_area("Pitches (one per line)", value="\n".join(draft["pitches"]) if draft else "", height=100)

            submitted = st.form_submit_button("💾 Create Campaign", use_container_width=True)
            if submitted:
                if not name:
                    st.error("Campaign name is required")
                elif not platforms:
                    st.error("Select at least one platform")
                else:
                    campaign_data = {
                        "name": name,
                        "description": description,
                        "template": template,
                        "platforms": platforms,
                        "keywords": [k.strip() for k in keywords.split("\n") if k.strip()],
                        "niche_indicators": [i.strip() for i in indicators.split("\n") if i.strip()],
                        "pitches": [p.strip() for p in pitches.split("\n") if p.strip()],
                        "target_groups": [],
                        "signature": {},
                    }
                    db.add_campaign(campaign_data)
                    st.session_state.campaign_draft = None
                    st.success("✅ Campaign created successfully!")
                    st.rerun()


def render_leads():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>👥 Leads</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>All captured leads from your campaigns</p>", unsafe_allow_html=True)

    db = st.session_state.db
    leads = db.get_leads()

    if not leads:
        st.info("No leads captured yet. Start an active campaign to collect leads.")
        return

    st.markdown(f"<p style='color: #888; margin-bottom: 15px;'>Total leads: <b>{len(leads)}</b></p>", unsafe_allow_html=True)

    if HAS_PANDAS:
        df = pd.DataFrame(leads)
        st.dataframe(df, use_container_width=True)
    else:
        for lead in leads[:50]:
            with st.expander(f"{lead['platform'].title()} — {lead['username'] or lead['user_id']}"):
                st.write(f"**Message:** {lead['message']}")
                st.write(f"**Source:** {lead['source']}")
                st.write(f"**Found:** {lead['found_at']}")

def render_account_setup():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>🔌 Account Setup</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Connect your social media accounts with step-by-step guidance</p>", unsafe_allow_html=True)

    config = st.session_state.config
    preselected = st.session_state.get("setup_platform", None)

    platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]

    if preselected and preselected in platforms:
        idx = platforms.index(preselected)
        st.session_state.pop("setup_platform", None)
    else:
        idx = 0

    plat = st.selectbox("Select Platform", platforms, index=idx,
                        format_func=lambda x: f"{PLATFORM_UI_DATA[x]['icon']} {x.title()}")

    ui_data = PLATFORM_UI_DATA[plat]
    pk = AIChatAssistant().platform_knowledge[plat]
    cfg_section = config.config.get("platforms", {}).get(plat, {})

    # Status banner
    connected = cfg_section.get("connected", False)
    enabled = cfg_section.get("enabled", False)
    last_error = cfg_section.get("last_error", "")
    last_tested = cfg_section.get("last_tested", "")

    if connected:
        st.success(f"✅ {pk['name']} is connected and ready to use!")
    elif enabled:
        st.warning(f"⚠️ {pk['name']} has credentials saved but hasn't been verified. Click Test Connection below.")
    else:
        st.info(f"ℹ️ {pk['name']} not configured yet. Follow the steps below to connect.")

    # Setup guide
    st.markdown(f"<h3>{pk['icon']} Setup Guide</h3>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #888;'>Difficulty: <b>{pk['difficulty']}</b> | Time: <b>{pk['time']}</b> | Docs: <a href='{pk['api_docs']}' target='_blank'>{pk['api_docs']}</a></p>", unsafe_allow_html=True)

    if pk.get("warning"):
        st.error(f"⚠️ {pk['warning']}")

    for i, step in enumerate(pk["setup_steps"], 1):
        st.markdown(f"""
        <div class="setup-step">
            <span class="setup-step-number">{i}</span>{step}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

    # Credential inputs
    st.markdown("<h3>🔑 Enter Credentials</h3>", unsafe_allow_html=True)

    updated = {}
    for field in ui_data["fields"]:
        label = field["label"]
        key = field["key"]
        help_text = field.get("help", "")
        current_val = cfg_section.get(key, "")

        if field["type"] == "password":
            val = st.text_input(label, value=current_val, type="password", key=f"{plat}_{key}", help=help_text)
        else:
            val = st.text_input(label, value=current_val, key=f"{plat}_{key}", help=help_text)
        updated[key] = val

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Save Credentials", use_container_width=True, type="primary"):
            for field_key, val in updated.items():
                config.set("platforms", f"{plat}.{field_key}", val)
            has_any = any(v.strip() for v in updated.values())
            config.set("platforms", f"{plat}.enabled", has_any)
            if not has_any:
                config.set("platforms", f"{plat}.connected", False)
            st.success("✅ Credentials saved!")
            st.rerun()

    with col2:
        if ui_data.get("testable"):
            if st.button("🧪 Test Connection", use_container_width=True):
                with st.spinner("Testing connection... This may take a few seconds."):
                    result, diagnostics = test_platform_connection_detailed(plat, updated)
                    config.set("platforms", f"{plat}.connected", result)
                    config.set("platforms", f"{plat}.last_tested", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    if not result:
                        config.set("platforms", f"{plat}.last_error", diagnostics.get("error", "Unknown error"))
                    else:
                        config.set("platforms", f"{plat}.last_error", "")

                # Show detailed results
                st.markdown("<h4>📊 Test Results</h4>", unsafe_allow_html=True)
                for check, status in diagnostics.items():
                    if check == "error":
                        continue
                    icon = "✅" if status else "❌"
                    color = "#00ff88" if status else "#ff4444"
                    st.markdown(f"<p style='color: {color};'>{icon} {check}</p>", unsafe_allow_html=True)

                if result:
                    st.success(f"🎉 {pk['name']} connection successful!")
                else:
                    st.error(f"❌ Connection failed: {diagnostics.get('error', 'Check your credentials')}")
                st.rerun()
        else:
            st.button("🧪 Test Connection", disabled=True, use_container_width=True,
                     help="This platform doesn't support automated testing.")

    with col3:
        if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
            for field in ui_data["fields"]:
                config.set("platforms", f"{plat}.{field['key']}", "")
            config.set("platforms", f"{plat}.enabled", False)
            config.set("platforms", f"{plat}.connected", False)
            config.set("platforms", f"{plat}.last_error", "")
            st.success("✅ Credentials cleared!")
            st.rerun()

    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

    # Diagnostics panel
    with st.expander("🔍 Connection Diagnostics"):
        st.markdown("<h4>What this platform can do:</h4>", unsafe_allow_html=True)
        for cap in pk.get("capabilities", []):
            st.markdown(f"- {cap}")

        st.markdown("<h4>Required credentials:</h4>", unsafe_allow_html=True)
        for cred in pk.get("credentials", []):
            has_it = bool(cfg_section.get(cred, ""))
            icon = "✅" if has_it else "❌"
            st.markdown(f"{icon} `{cred}`")

        if last_tested:
            st.markdown(f"<p style='color: #666; font-size: 12px;'>Last tested: {last_tested}</p>", unsafe_allow_html=True)
        if last_error:
            st.markdown(f"<p style='color: #ff4444; font-size: 12px;'>Last error: {last_error}</p>", unsafe_allow_html=True)

    # Buy accounts guide
    with st.expander("💰 Don't want to create accounts? Buy aged accounts"):
        st.markdown(ACCOUNT_BUYING_GUIDE)


def test_platform_connection_detailed(platform, credentials):
    """Test connection with detailed diagnostics. Returns (success_bool, diagnostics_dict)."""
    diagnostics = {}

    try:
        if platform == "telegram":
            api_id = credentials.get("api_id", "").strip()
            api_hash = credentials.get("api_hash", "").strip()

            diagnostics["API ID provided"] = bool(api_id)
            diagnostics["API Hash provided"] = bool(api_hash)

            if not api_id or not api_hash:
                return False, {**diagnostics, "error": "API ID and API Hash are required"}

            try:
                from telethon import TelegramClient
                import asyncio

                async def _test():
                    client = TelegramClient("test_session", int(api_id), api_hash)
                    await client.connect()
                    is_auth = await client.is_user_authorized()
                    me = await client.get_me() if is_auth else None
                    await client.disconnect()
                    return is_auth, me

                is_auth, me = asyncio.run(_test())
                diagnostics["Connected to Telegram"] = True
                diagnostics["User authorized"] = is_auth
                if me:
                    diagnostics[f"Logged in as @{me.username or me.first_name}"] = True
                return is_auth, diagnostics
            except Exception as e:
                diagnostics["Connected to Telegram"] = False
                return False, {**diagnostics, "error": str(e)}

        elif platform == "reddit":
            client_id = credentials.get("client_id", "").strip()
            client_secret = credentials.get("client_secret", "").strip()
            username = credentials.get("username", "").strip()
            password = credentials.get("password", "").strip()

            diagnostics["Client ID provided"] = bool(client_id)
            diagnostics["Client Secret provided"] = bool(client_secret)
            diagnostics["Username provided"] = bool(username)
            diagnostics["Password provided"] = bool(password)

            if not all([client_id, client_secret, username, password]):
                return False, {**diagnostics, "error": "All four credentials are required"}

            try:
                import praw
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                    user_agent="LeadGenPro/4.1"
                )
                me = reddit.user.me()
                diagnostics["Authenticated"] = True
                diagnostics[f"Logged in as u/{me.name}"] = True
                diagnostics["Can read posts"] = True
                return True, diagnostics
            except Exception as e:
                diagnostics["Authenticated"] = False
                return False, {**diagnostics, "error": str(e)}

        elif platform == "discord":
            token = credentials.get("token", "").strip()
            app_id = credentials.get("application_id", "").strip()

            diagnostics["Bot Token provided"] = bool(token)
            diagnostics["Application ID provided"] = bool(app_id)

            if not token:
                return False, {**diagnostics, "error": "Bot Token is required"}

            try:
                import discord
                import asyncio

                client = discord.Client(intents=discord.Intents.default())
                result = {"ok": False, "user": None}

                @client.event
                async def on_ready():
                    result["ok"] = True
                    result["user"] = f"{client.user.name}#{client.user.discriminator}"
                    await client.close()

                async def _test():
                    try:
                        await asyncio.wait_for(client.start(token), timeout=8)
                    except asyncio.TimeoutError:
                        result["error"] = "Connection timeout"
                    except discord.LoginFailure:
                        result["error"] = "Invalid token"
                    except Exception as e:
                        result["error"] = str(e)

                asyncio.run(_test())

                diagnostics["Connected to Discord"] = result["ok"]
                if result.get("user"):
                    diagnostics[f"Bot: {result['user']}"] = True
                return result["ok"], {**diagnostics, "error": result.get("error", "")}
            except Exception as e:
                diagnostics["Connected to Discord"] = False
                return False, {**diagnostics, "error": str(e)}

        elif platform == "twitter":
            api_key = credentials.get("api_key", "").strip()
            api_secret = credentials.get("api_secret", "").strip()
            access_token = credentials.get("access_token", "").strip()
            access_secret = credentials.get("access_secret", "").strip()

            diagnostics["API Key provided"] = bool(api_key)
            diagnostics["API Secret provided"] = bool(api_secret)
            diagnostics["Access Token provided"] = bool(access_token)
            diagnostics["Access Secret provided"] = bool(access_secret)

            if not all([api_key, api_secret, access_token, access_secret]):
                return False, {**diagnostics, "error": "All four credentials are required"}

            try:
                import tweepy
                auth = tweepy.OAuthHandler(api_key, api_secret)
                auth.set_access_token(access_token, access_secret)
                api = tweepy.API(auth)
                me = api.verify_credentials()
                diagnostics["Authenticated"] = True
                diagnostics[f"Logged in as @{me.screen_name}"] = True
                diagnostics["Can read tweets"] = True
                return True, diagnostics
            except Exception as e:
                diagnostics["Authenticated"] = False
                return False, {**diagnostics, "error": str(e)}

        return False, {"error": "Platform not supported for testing"}
    except Exception as e:
        return False, {"error": f"Test failed: {str(e)}"}

def render_bulk_import():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>📥 Bulk Import</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Import multiple account credentials at once</p>", unsafe_allow_html=True)

    config = st.session_state.config

    tab1, tab2 = st.tabs(["📄 CSV Import", "📋 JSON Import"])

    with tab1:
        st.markdown("""
        **Expected CSV format:**
        ```csv
        platform,field,value
        telegram,api_id,12345678
        telegram,api_hash,abc123...
        telegram,phone,+1234567890
        reddit,client_id,abc...
        reddit,client_secret,xyz...
        reddit,username,myuser
        reddit,password,mypass
        discord,token,BotTokenHere...
        discord,application_id,123456789
        discord,public_key,abc...
        ```
        Each row sets one field for one platform.
        """)

        csv_file = st.file_uploader("Upload CSV", type=["csv"], key="csv_upload")
        if csv_file:
            try:
                content = csv_file.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)

                if not rows:
                    st.error("CSV is empty or invalid format.")
                else:
                    st.write(f"Found {len(rows)} rows to import.")
                    preview = {}
                    for row in rows:
                        plat = row.get("platform", "").strip().lower()
                        field = row.get("field", "").strip().lower()
                        value = row.get("value", "").strip()
                        if plat and field and value:
                            if plat not in preview:
                                preview[plat] = {}
                            preview[plat][field] = value

                    with st.expander("Preview Import"):
                        for plat, fields in preview.items():
                            st.write(f"**{plat.title()}:** {fields}")

                    if st.button("✅ Import from CSV", use_container_width=True, type="primary"):
                        imported = 0
                        for plat, fields in preview.items():
                            for field, value in fields.items():
                                config.set("platforms", f"{plat}.{field}", value)
                            config.set("platforms", f"{plat}.enabled", True)
                            imported += 1
                        st.success(f"✅ Imported credentials for {imported} platform(s)!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    with tab2:
        st.markdown("""
        **Expected JSON format:**
        ```json
        {
          "telegram": {
            "api_id": "12345678",
            "api_hash": "abc123...",
            "phone": "+1234567890"
          },
          "reddit": {
            "client_id": "abc...",
            "client_secret": "xyz...",
            "username": "myuser",
            "password": "mypass"
          },
          "discord": {
            "token": "BotTokenHere...",
            "application_id": "123456789",
            "public_key": "abc..."
          }
        }
        ```
        Each top-level key is a platform. Each nested key is a field.
        """)

        json_text = st.text_area("Paste JSON here", height=200, key="json_paste")
        if json_text:
            try:
                data = json.loads(json_text)
                if not isinstance(data, dict):
                    st.error("JSON must be an object (dictionary) with platform names as keys.")
                else:
                    with st.expander("Preview Import"):
                        for plat, fields in data.items():
                            st.write(f"**{plat.title()}:** {fields}")

                    if st.button("✅ Import from JSON", use_container_width=True, type="primary"):
                        imported = 0
                        for plat, fields in data.items():
                            if isinstance(fields, dict):
                                for field, value in fields.items():
                                    config.set("platforms", f"{plat}.{field}", str(value))
                                config.set("platforms", f"{plat}.enabled", True)
                                imported += 1
                        st.success(f"✅ Imported credentials for {imported} platform(s)!")
                        st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    st.markdown("""
    <div style="margin-top: 20px; padding: 15px; background: #1a1a2e; border-radius: 8px; border-left: 3px solid #00d4ff;">
        <p style="margin: 0; font-size: 13px; color: #888;">
        💡 <b>Tips:</b><br>
        • You can export your current config from the Settings tab<br>
        • Keep your credential files secure — never commit them to git<br>
        • After importing, go to Account Setup to test each connection
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_settings():
    st.markdown("<h1 style='font-size: 28px; font-weight: 700; margin-bottom: 5px;'>⚙️ Settings</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; margin-bottom: 20px;'>Configure your LeadGen Pro system</p>", unsafe_allow_html=True)

    config = st.session_state.config

    with st.form("general_settings"):
        st.markdown("<h3>General</h3>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            theme = st.selectbox("Theme", ["dark", "light"], index=0 if config.get("general", "theme") == "dark" else 1)
        with col2:
            check_interval = st.slider("Check Interval (minutes)", 5, 60, config.get("general", "check_interval"))
        max_campaigns = st.slider("Max Campaigns", 1, 50, config.get("general", "max_campaigns"))

        st.markdown("<h3>Engagement</h3>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            min_comments = st.number_input("Min Comments", 0, 100, config.get("engagement", "min_comments"))
            reply_delay_min = st.number_input("Reply Delay Min (sec)", 10, 300, config.get("engagement", "reply_delay_min"))
        with col2:
            reply_delay_max = st.number_input("Reply Delay Max (sec)", 30, 600, config.get("engagement", "reply_delay_max"))
            max_replies = st.number_input("Max Replies Per Hour", 1, 50, config.get("engagement", "max_replies_per_hour"))

        st.markdown("<h3>Signatures</h3>", unsafe_allow_html=True)
        sig_enabled = st.checkbox("Enable Signatures", value=config.get("signatures", "enabled"))
        col1, col2 = st.columns(2)
        with col1:
            whatsapp = st.text_input("WhatsApp Number", value=config.get("signatures", "whatsapp"))
        with col2:
            website = st.text_input("Website URL", value=config.get("signatures", "website"))
        custom_text = st.text_area("Custom Signature Text", value=config.get("signatures", "custom_text"))

        if st.form_submit_button("💾 Save Settings", use_container_width=True):
            config.set("general", "theme", theme)
            config.set("general", "check_interval", check_interval)
            config.set("general", "max_campaigns", max_campaigns)
            config.set("engagement", "min_comments", min_comments)
            config.set("engagement", "reply_delay_min", reply_delay_min)
            config.set("engagement", "reply_delay_max", reply_delay_max)
            config.set("engagement", "max_replies_per_hour", max_replies)
            config.set("signatures", "enabled", sig_enabled)
            config.set("signatures", "whatsapp", whatsapp)
            config.set("signatures", "website", website)
            config.set("signatures", "custom_text", custom_text)
            st.success("✅ Settings saved!")
            st.rerun()

    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

    st.markdown("<h3>Export / Import Config</h3>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📤 Export Config to JSON",
            data=json.dumps(config.config, indent=2),
            file_name="config.json",
            mime="application/json",
            use_container_width=True
        )
    with col2:
        uploaded = st.file_uploader("Import Config JSON", type=["json"], key="config_import")
        if uploaded:
            try:
                new_config = json.loads(uploaded.read().decode("utf-8"))
                config.config = new_config
                config.save()
                st.success("✅ Config imported! Restart the app to apply.")
                st.rerun()
            except Exception as e:
                st.error(f"Error importing config: {e}")

    st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

    if st.button("🗑️ Reset All Settings to Default", use_container_width=True, type="secondary"):
        config.reset()
        st.success("✅ Settings reset to defaults!")
        st.rerun()


# ============ MAIN ============
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} v{APP_VERSION}",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    init_session_state()

    if st.session_state.db is None:
        st.session_state.db = Database()
    if st.session_state.config is None:
        st.session_state.config = ConfigManager()
    if st.session_state.ai is None:
        st.session_state.ai = AIChatAssistant()

    render_sidebar()

    tab = st.session_state.active_tab
    if tab == "Dashboard":
        render_dashboard()
    elif tab == "AI Assistant":
        render_ai_assistant()
    elif tab == "Campaigns":
        render_campaigns()
    elif tab == "Leads":
        render_leads()
    elif tab == "Account Setup":
        render_account_setup()
    elif tab == "Bulk Import":
        render_bulk_import()
    elif tab == "Settings":
        render_settings()


if __name__ == "__main__":
    main()
