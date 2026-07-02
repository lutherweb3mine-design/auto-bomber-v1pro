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
    """Dynamic AI that generates campaigns for ANY niche without hardcoded templates"""

    def __init__(self):
        # Known niches for quick matching (expanded but not required)
        self.known_niches = {
            "crypto": ["crypto", "bitcoin", "wallet", "blockchain", "ethereum", "seed phrase", "private key", "btc", "eth"],
            "web_design": ["website", "web design", "web developer", "landing page", "wordpress"],
            "app_dev": ["app", "mobile app", "application", "app developer", "ios", "android", "flutter"],
            "real_estate": ["house", "apartment", "property", "realtor", "mortgage", "rent", "buy house"],
            "marketing": ["marketing", "seo", "ads", "promote", "traffic", "digital marketing"],
            "writing": ["writer", "content", "blog", "article", "copywriting", "ghostwriter"],
            "social_media": ["followers", "engagement", "instagram", "social media", "viral", "tiktok"],
            "ecommerce": ["shopify", "dropshipping", "ecommerce", "online store", "amazon fba"],
            "coaching": ["coach", "mentor", "course", "training", "life coach", "business coach"],
            "design": ["logo", "branding", "graphic design", "ui ux", "illustration"],
            "video": ["video editor", "editing", "youtube", "video production", "premiere"],
            "va": ["virtual assistant", "admin", "personal assistant", "data entry"],
            "tax": ["tax", "accountant", "accounting", "bookkeeping", "cpa", "irs"],
            "fitness": ["fitness", "trainer", "workout", "gym", "lose weight", "diet"],
            "language": ["learn english", "language tutor", "spanish", "fluent", "language exchange"],
            "career": ["resume", "career", "job", "interview", "hiring", "cv", "linkedin"],
            "tickets": ["concert", "tickets", "festival", "gig", "venue", "sold out", "ticketmaster"],
            "travel": ["travel", "trip", "vacation", "flight", "hotel", "booking", "itinerary"],
            "food": ["catering", "chef", "meal prep", "food", "cooking", "wedding catering"],
            "pet": ["dog walker", "pet sitter", "grooming", "pet care", "dog training"],
            "photo": ["photographer", "wedding photo", "portrait", "event photography"],
            "music": ["music producer", "mixing", "mastering", "beat maker", "recording studio"],
            "car": ["rent a car", "buy car", "car dealer", "used car", "lease"],
            "immigration": ["immigration", "visa", "green card", "citizenship", "passport", "work permit", "asylum"],
            "plumbing": ["plumber", "plumbing", "leak", "pipe", "drain", "toilet", "faucet", "water heater"],
            "electrician": ["electrician", "electrical", "wiring", "outlet", "circuit", "lighting", "panel"],
            "cleaning": ["cleaning", "house cleaner", "maid", "janitorial", "deep clean", "office cleaning"],
            "moving": ["moving company", "movers", "relocation", "packing", "storage", "furniture"],
            "security": ["security guard", "alarm system", "cctv", "surveillance", "home security"],
            "insurance": ["insurance", "health insurance", "car insurance", "life insurance", "policy"],
            "legal": ["lawyer", "attorney", "legal help", "sue", "contract", "divorce", "dui"],
            "therapy": ["therapist", "counseling", "mental health", "psychologist", "depression", "anxiety"],
            "dental": ["dentist", "dental", "braces", "teeth whitening", "root canal", "orthodontist"],
            "medical": ["doctor", "physician", "specialist", "clinic", "urgent care", "diagnosis"],
            "roofing": ["roofing", "roof repair", "shingles", "leak", "contractor", "gutter"],
            "landscaping": ["landscaping", "lawn care", "gardener", "tree removal", "hardscape"],
            "hvac": ["hvac", "air conditioning", "heating", "furnace", "ac repair", "hvac contractor"],
            "pest_control": ["pest control", "exterminator", "termite", "bed bug", "rodent", "roach"],
            "locksmith": ["locksmith", "lock out", "rekey", "car key", "safe", "broken lock"],
            "tutoring": ["tutor", "math tutor", "science tutor", "homework help", "sat prep", "act prep"],
            "wedding": ["wedding planner", "wedding venue", "wedding photographer", "bridal", "wedding dress"],
            "event_planning": ["event planner", "party planner", "corporate event", "birthday party", "venue"],
            "interior_design": ["interior design", "home decor", "renovation", "kitchen remodel", "bathroom"],
            "cybersecurity": ["cybersecurity", "hacker", "penetration test", "security audit", "malware", "breach"],
            "data_recovery": ["data recovery", "hard drive", "deleted files", "backup", "corrupted"],
            "translation": ["translator", "translation", "interpretation", "document translation", "certified"],
            "notary": ["notary", "notary public", "apostille", "document notarization", "legalization"],
            "limo": ["limo", "limousine", "car service", "airport transfer", "chauffeur", "party bus"],
            "dj": ["dj", "wedding dj", "event dj", "party dj", "sound system", "mc"],
            "bartending": ["bartender", "bartending", "mobile bar", "cocktail", "wedding bar", "event bar"],
            "florist": ["florist", "flowers", "wedding flowers", "bouquet", "floral arrangement"],
            "tailor": ["tailor", "alterations", "suit", "wedding dress alterations", "custom clothing"],
            "nanny": ["nanny", "babysitter", "childcare", "au pair", "daycare", "preschool"],
            "senior_care": ["senior care", "elderly care", "home care", "assisted living", "nurse"],
            "handyman": ["handyman", "home repair", "fix", "maintenance", "drywall", "paint"],
            "solar": ["solar panels", "solar installation", "renewable energy", "solar company", "battery"],
            "garage_door": ["garage door", "garage door repair", "opener", "spring", "roller"],
            "window": ["window repair", "window replacement", "glass", "double pane", "window installation"],
            "foundation": ["foundation repair", "basement", "crack", "waterproofing", "structural"],
            "mold": ["mold removal", "mold remediation", "black mold", "mold inspection", "air quality"],
            "asbestos": ["asbestos removal", "asbestos testing", "abatement", "insulation"],
            "water_damage": ["water damage", "flood damage", "restoration", "mold", "basement flood"],
            "fire_damage": ["fire damage", "smoke damage", "restoration", "soot removal"],
            "biohazard": ["biohazard cleanup", "crime scene", "hoarding cleanup", "trauma cleanup"],
        }

        # Action/intent keywords
        self.intent_keywords = {
            "need_service": ["need", "looking for", "want", "help", "struggling", "cant", "can't", "trouble", "problem", "issue", "broken", "repair", "fix", "install"],
            "want_buy": ["buy", "purchase", "get", "acquire", "shop for", "order"],
            "want_sell": ["sell", "selling", "get rid of", "dispose", "unload"],
            "want_rent": ["rent", "rental", "lease", "hire", "borrow"],
            "want_learn": ["learn", "study", "course", "training", "teach me", "how to"],
            "emergency": ["emergency", "urgent", "asap", "now", "immediately", "critical", "desperate"],
        }

        # Platform recommendations by topic category
        self.platform_recommendations = {
            "local_service": ["reddit", "facebook"],  # plumbing, electrician, etc.
            "creative": ["reddit", "instagram", "twitter"],  # design, photo, video
            "tech": ["reddit", "twitter", "discord"],  # crypto, app dev, cybersecurity
            "business": ["reddit", "twitter", "facebook", "linkedin"],  # marketing, va, consulting
            "health": ["reddit", "facebook", "instagram"],  # fitness, therapy, dental
            "education": ["reddit", "discord", "telegram"],  # tutoring, language, coaching
            "entertainment": ["reddit", "twitter", "discord"],  # tickets, music, events
            "travel": ["reddit", "facebook", "twitter"],  # travel, hotels, flights
            "home": ["reddit", "facebook"],  # real estate, interior, moving
            "automotive": ["reddit", "facebook"],  # car rental, repair
        }

        self.help_phrases = ["help", "how", "what", "?", "explain", "guide", "tutorial", "how to", "how do i", "how can i"]
        self.greeting_phrases = ["hi", "hello", "hey", "sup", "yo", "good morning", "good afternoon", "good evening", "what's up", "howdy", "hola", "greetings"]
        self.suggestion_phrases = ["suggest", "recommend", "idea", "what should", "what niche", "what kind", "options", "examples", "show me", "list"]
        self.create_phrases = ["create", "make", "build", "start", "want to find", "looking for", "need", "help me find", "find people", "get leads", "generate leads", "i want", "i need"]

    def _extract_topic(self, text):
        """Extract the core topic from user input using keyword matching"""
        text_lower = text.lower()
        best_niche = None
        best_score = 0

        for niche, keywords in self.known_niches.items():
            score = 0
            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Whole word match
                if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text_lower):
                    score += 3
                # Partial match for longer phrases
                elif len(keyword_lower) > 5 and keyword_lower in text_lower:
                    score += 1.5

            if score > best_score:
                best_score = score
                best_niche = niche

        return best_niche, best_score

    def _extract_intent(self, text):
        """Extract user intent (need service, want to buy, emergency, etc.)"""
        text_lower = text.lower()
        intents = []
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    intents.append(intent)
                    break
        return list(set(intents))

    def _determine_category(self, niche):
        """Map niche to category for platform recommendations"""
        category_map = {
            "plumbing": "local_service", "electrician": "local_service", "cleaning": "local_service",
            "moving": "local_service", "security": "local_service", "locksmith": "local_service",
            "handyman": "local_service", "hvac": "local_service", "pest_control": "local_service",
            "garage_door": "local_service", "window": "local_service", "foundation": "local_service",
            "mold": "local_service", "asbestos": "local_service", "water_damage": "local_service",
            "fire_damage": "local_service", "biohazard": "local_service", "roofing": "local_service",
            "landscaping": "local_service",

            "crypto": "tech", "web_design": "tech", "app_dev": "tech", "cybersecurity": "tech",
            "data_recovery": "tech",

            "design": "creative", "photo": "creative", "video": "creative", "music": "creative",
            "dj": "creative", "bartending": "creative", "florist": "creative", "tailor": "creative",

            "marketing": "business", "va": "business", "coaching": "business", "tax": "business",
            "insurance": "business", "legal": "business", "notary": "business", "translation": "business",

            "fitness": "health", "therapy": "health", "dental": "health", "medical": "health",
            "senior_care": "health",

            "language": "education", "tutoring": "education", "career": "education",

            "tickets": "entertainment", "event_planning": "entertainment", "wedding": "entertainment",
            "limo": "entertainment",

            "travel": "travel",

            "real_estate": "home", "interior_design": "home",

            "car": "automotive",
        }
        return category_map.get(niche, "business")

    def _generate_keywords(self, topic, intents):
        """Generate search keywords dynamically"""
        keywords = []

        # Base keywords from topic
        keywords.append(f"need {topic}")
        keywords.append(f"looking for {topic}")
        keywords.append(f"{topic} help")
        keywords.append(f"{topic} service")
        keywords.append(f"best {topic}")
        keywords.append(f"cheap {topic}")
        keywords.append(f"{topic} near me")
        keywords.append(f"{topic} recommendation")

        # Add intent-based keywords
        if "emergency" in intents:
            keywords.append(f"emergency {topic}")
            keywords.append(f"urgent {topic}")
            keywords.append(f"{topic} asap")
        if "need_service" in intents:
            keywords.append(f"{topic} repair")
            keywords.append(f"{topic} fix")
            keywords.append(f"{topic} install")
        if "want_buy" in intents:
            keywords.append(f"buy {topic}")
            keywords.append(f"purchase {topic}")
        if "want_rent" in intents:
            keywords.append(f"rent {topic}")
            keywords.append(f"{topic} rental")
        if "want_learn" in intents:
            keywords.append(f"learn {topic}")
            keywords.append(f"{topic} course")
            keywords.append(f"{topic} training")

        return keywords[:10]

    def _generate_indicators(self, topic, intents):
        """Generate niche indicators for matching posts"""
        indicators = [
            topic,
            f"need {topic}",
            f"looking for {topic}",
            f"{topic} help",
            f"{topic} service",
            "help",
            "need",
            "looking for",
            "please",
            "struggling",
            "recommendation",
        ]

        if "emergency" in intents:
            indicators.extend(["emergency", "urgent", "asap", "now", "immediately", "quick"])
        if "need_service" in intents:
            indicators.extend(["repair", "fix", "broken", "install", "replace"])
        if "want_buy" in intents:
            indicators.extend(["buy", "purchase", "get", "price", "cost", "quote"])
        if "want_rent" in intents:
            indicators.extend(["rent", "lease", "hire", "temporary"])
        if "want_learn" in intents:
            indicators.extend(["learn", "study", "course", "training", "beginner", "tutorial"])

        return indicators[:15]

    def _generate_pitches(self, topic, intents):
        """Generate custom pitches based on topic and intent"""
        pitches = []

        # Service-oriented pitch
        if "need_service" in intents or "emergency" in intents:
            pitches.append(f"I provide professional {topic} services. DM me for a free quote and fast response.")
            pitches.append(f"Need {topic} help? I am experienced and available. Message me for details!")

        # General pitch
        pitches.append(f"I specialize in {topic}. DM me if you need help or have questions!")
        pitches.append(f"Looking for {topic}? I can help. Reach out and let us discuss your needs.")

        # Buy/sell pitch
        if "want_buy" in intents:
            pitches.append(f"I can help you find the best {topic} deals. DM me for recommendations!")

        # Learning pitch
        if "want_learn" in intents:
            pitches.append(f"I teach {topic} and offer personalized guidance. DM me to get started!")

        # Emergency pitch
        if "emergency" in intents:
            pitches.append(f"🚨 {topic} emergency? I offer fast response times. DM me immediately!")

        return pitches[:5]

    def _generate_target_groups(self, topic):
        """Generate relevant target groups/communities"""
        # General groups that might discuss the topic
        return [
            topic.replace(" ", ""),
            f"{topic}help",
            f"{topic}services",
            "help",
            "recommendations",
            "local",
        ]

    def generate_campaign(self, user_input):
        """Generate a complete campaign from ANY user input"""
        text = user_input.lower().strip()

        # Extract topic and intent
        niche, score = self._extract_topic(text)
        intents = self._extract_intent(text)

        # Determine the core topic
        if niche and score >= 3:
            # Use known niche name as topic
            topic = niche.replace("_", " ")
            confidence = min(score / 6, 1.0)
            template = niche
        else:
            # Extract topic from user input directly
            # Remove common filler words
            fillers = ["i", "want", "need", "looking", "for", "help", "me", "find", "people", "who", "get", "some", "a", "an", "the", "my", "with", "to", "and", "or", "but", "in", "on", "at", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can"]
            words = [w for w in text.split() if w not in fillers and len(w) > 2]
            topic = " ".join(words[:3]) if words else text
            confidence = 0.4
            template = "custom"

        # Determine category and platforms
        category = self._determine_category(niche) if niche else "business"
        platforms = self.platform_recommendations.get(category, ["reddit", "twitter", "facebook"])

        # Generate campaign components
        keywords = self._generate_keywords(topic, intents)
        indicators = self._generate_indicators(topic, intents)
        pitches = self._generate_pitches(topic, intents)
        target_groups = self._generate_target_groups(topic)

        return {
            "name": f"{topic.title()} Leads",
            "description": f"Find people who need {topic} services or products",
            "template": template,
            "keywords": keywords,
            "platforms": platforms,
            "niche_indicators": indicators,
            "pitches": pitches,
            "target_groups": target_groups,
            "confidence": confidence,
            "topic": topic,
            "intents": intents,
            "category": category,
        }

    def _is_help_request(self, text):
        return any(phrase in text.lower() for phrase in self.help_phrases)

    def _is_greeting(self, text):
        return any(phrase in text.lower() for phrase in self.greeting_phrases)

    def _is_suggestion_request(self, text):
        return any(phrase in text.lower() for phrase in self.suggestion_phrases)

    def _is_create_request(self, text):
        return any(phrase in text.lower() for phrase in self.create_phrases)

    def chat(self, user_message, context=None):
        text = user_message.lower().strip()

        # Handle greetings
        if self._is_greeting(text) and len(text.split()) < 4:
            return {
                "type": "greeting",
                "message": """Hey! 👋 I am your AI Campaign Assistant. I can create lead generation campaigns for **ANY niche** — just tell me what you need!

**Examples:**
- "I want people who need plumbers"
- "Find me immigration leads"
- "Concert ticket buyers"
- "Cybersecurity audit clients"
- "Wedding photographers needed"

Type **'suggest'** to see popular niches, or just describe what you are looking for!""",
                "suggestions": None,
                "follow_up": None
            }

        # Handle help requests
        if self._is_help_request(text):
            return {
                "type": "help",
                "message": """I can help you create campaigns! Here is how it works:

1. **Tell me your niche** — e.g., "I want people who need plumbers" or "immigration visa help"
2. **I will generate a campaign** with keywords, platforms, and pitches automatically
3. **You can customize it** or use it as-is

**I work with ANY topic:** plumbing, immigration, cybersecurity, wedding services, tutoring, and thousands more!

Type **'suggest'** to see popular options.""",
                "suggestions": None,
                "follow_up": "What kind of leads do you want to find?"
            }

        # Handle suggestion requests
        if self._is_suggestion_request(text):
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
                "message": "Here are some popular campaign niches you can choose from:\n\n" + "\n".join(suggestions) + "\n\nJust tell me which one interests you, or describe your own niche!",
                "suggestions": None,
                "follow_up": "Which niche would you like to explore?"
            }

        # Generate dynamic campaign for ANY input
        campaign = self.generate_campaign(user_message)

        # Build rich response
        response = f"Great! I created a **{campaign['name']}** campaign for you.\n\n"
        response += f"**Topic:** {campaign['topic'].title()}\n"
        response += f"**Category:** {campaign['category'].replace('_', ' ').title()}\n"
        response += f"**Best Platforms:** {', '.join(campaign['platforms'])}\n\n"

        if campaign['intents']:
            response += f"**Detected Intent:** {', '.join(campaign['intents'])}\n\n"

        response += f"**Keywords to Monitor:**\n"
        for kw in campaign['keywords'][:5]:
            response += f"- {kw}\n"

        response += f"\n**Niche Indicators:**\n"
        for ind in campaign['niche_indicators'][:5]:
            response += f"- {ind}\n"

        response += f"\n**Sample Pitch:**\n> {campaign['pitches'][0]}\n\n"

        if campaign['confidence'] < 0.6:
            response += "⚠️ I generated this based on your input. You can adjust the settings below.\n\n"

        response += "Click **Use These Settings** to auto-fill the campaign form, or tell me more to refine it!"

        return {
            "type": "campaign",
            "message": response,
            "suggestions": campaign,
            "follow_up": None
        }
