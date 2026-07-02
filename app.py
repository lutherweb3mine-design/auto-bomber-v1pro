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



# ============ PLATFORM SETUP WIZARD DATA ============
PLATFORM_SETUP_GUIDES = {
    "telegram": {
        "icon": "✈️",
        "difficulty": "Easy",
        "time": "5 min",
        "steps": [
            "Go to my.telegram.org and log in with your phone number",
            "Click 'API development tools'",
            "Create a new app (any name works)",
            "Copy the api_id (numbers) and api_hash (long string)",
            "Paste them below + your phone number",
            "Click Test Connection to verify"
        ],
        "fields": ["api_id", "api_hash", "phone"],
        "testable": True,
    },
    "reddit": {
        "icon": "🔴",
        "difficulty": "Easy",
        "time": "5 min",
        "steps": [
            "Go to reddit.com/prefs/apps",
            "Click 'create another app...'",
            "Select 'script' type, name it 'LeadGen', redirect URI: http://localhost:8080",
            "Copy client_id (under the app name) and client_secret",
            "Enter your Reddit username and password below",
            "Click Test Connection to verify"
        ],
        "fields": ["client_id", "client_secret", "username", "password"],
        "testable": True,
    },
    "discord": {
        "icon": "💬",
        "difficulty": "Easy",
        "time": "3 min",
        "steps": [
            "Go to discord.com/developers/applications",
            "Click 'New Application' → name it 'LeadGen'",
            "Go to 'Bot' tab → click 'Add Bot'",
            "Under 'Token' click 'Reset Token' then 'Copy'",
            "Paste the token below",
            "Click Test Connection to verify"
        ],
        "fields": ["token", "bot_name"],
        "testable": True,
    },
    "twitter": {
        "icon": "🐦",
        "difficulty": "Medium",
        "time": "10 min",
        "steps": [
            "Go to developer.twitter.com",
            "Apply for Elevated access (free, takes 1-2 days)",
            "Create a project → add an app",
            "Go to 'Keys and Tokens' tab",
            "Copy API Key, API Secret, Access Token, Access Secret",
            "Paste all four below and click Test Connection"
        ],
        "fields": ["api_key", "api_secret", "access_token", "access_secret"],
        "testable": True,
    },
    "facebook": {
        "icon": "📘",
        "difficulty": "Hard",
        "time": "20+ min",
        "steps": [
            "⚠️ Facebook automation is heavily restricted",
            "Option A: Use Facebook Graph API (requires Business Verification)",
            "Option B: Use Selenium automation (advanced, risk of ban)",
            "For Graph API: Go to developers.facebook.com",
            "Create app → get Access Token with pages_read_engagement permission",
            "Enter email + token below (password optional for Selenium mode)"
        ],
        "fields": ["email", "password"],
        "testable": False,
        "warning": "Facebook accounts created recently get banned fast. Buy aged accounts or use Graph API only."
    },
    "instagram": {
        "icon": "📸",
        "difficulty": "Hard",
        "time": "20+ min",
        "steps": [
            "⚠️ Instagram automation is heavily restricted",
            "Option A: Instagram Basic Display API (limited, read-only)",
            "Option B: Instagram Graph API (requires Facebook Business account)",
            "Option C: instagrapi library (unofficial, high ban risk)",
            "For Graph API: Link IG to FB Business → get token from developers.facebook.com",
            "Enter username + access token below"
        ],
        "fields": ["username", "password"],
        "testable": False,
        "warning": "Instagram aggressively bans automation. Use aged accounts or official API only."
    },
    "tiktok": {
        "icon": "🎵",
        "difficulty": "Very Hard",
        "time": "N/A",
        "steps": [
            "❌ TikTok has no public API for messaging/automation",
            "TikTok Research API exists but is read-only and requires approval",
            "For now, TikTok is NOT recommended for lead generation",
            "Alternative: Monitor TikTok comments manually, then reach out via other platforms",
            "If you have a workaround, enter credentials below for future use"
        ],
        "fields": [],
        "testable": False,
        "warning": "TikTok automation is practically impossible without violating ToS."
    },
}

ACCOUNT_BUYING_GUIDE = """
### Where to Buy Aged Accounts (If You Don't Want to Create Them)

| Marketplace | Platform | Price Range | Notes |
|-------------|----------|-------------|-------|
| **AccsMarket** | Reddit, Twitter, Discord | $3-15 | Aged accounts with karma/followers |
| **PlayerUp** | All platforms | $5-50 | Middleman service, safer |
| **RedditBay** (r/redditbay) | Reddit | $5-20 | Check seller reputation |
| **Telegram** groups | Telegram | $2-10 | Search 'account seller' groups |
| **EpicNPC** | All platforms | $5-30 | Gaming-focused but has social accounts |

**⚠️ Risks:**
- Accounts can still be banned
- Some sellers are scams — use escrow when possible
- Aged accounts work better than fresh ones
- Never use your main personal account for automation
"""


# ============ STREAMLIT UI ============
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
        st.title(f"🔥 {APP_NAME}")
        st.caption(f"v{APP_VERSION} — Dynamic AI")
        st.divider()

        pages = [
            ("📊", "Dashboard"),
            ("🤖", "AI Assistant"),
            ("🚀", "Campaigns"),
            ("👥", "Leads"),
            ("🔧", "Account Setup"),
            ("📥", "Bulk Import"),
            ("⚙️", "Settings"),
        ]

        for icon, page in pages:
            if st.button(f"{icon} {page}", use_container_width=True,
                         type="primary" if st.session_state.active_tab == page else "secondary"):
                st.session_state.active_tab = page
                st.rerun()

        st.divider()
        st.caption("💡 Tip: Use the AI Assistant to create campaigns for ANY niche instantly.")


def render_dashboard():
    st.header("📊 Dashboard")

    db = st.session_state.db
    stats = db.get_stats()
    runner_status = db.get_runner_status()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Campaigns", stats["total_campaigns"])
    with col2:
        st.metric("Active", stats["active_campaigns"])
    with col3:
        st.metric("Leads", stats["total_leads"])
    with col4:
        st.metric("Replies", stats["total_replies"])
    with col5:
        st.metric("Posts Checked", stats["total_posts"])

    st.divider()

    # Account Status Dashboard
    st.subheader("🔌 Account Connection Status")
    config = st.session_state.config.config

    plat_cols = st.columns(4)
    platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]
    icons = {"telegram": "✈️", "reddit": "🔴", "discord": "💬", "twitter": "🐦",
             "facebook": "📘", "instagram": "📸", "tiktok": "🎵"}

    for i, plat in enumerate(platforms):
        with plat_cols[i % 4]:
            plat_cfg = config.get("platforms", {}).get(plat, {})
            connected = plat_cfg.get("connected", False)
            enabled = plat_cfg.get("enabled", False)

            if connected:
                status_color = "🟢"
                status_text = "Connected"
            elif enabled:
                status_color = "🟡"
                status_text = "Setup Needed"
            else:
                status_color = "🔴"
                status_text = "Not Configured"

            runner = runner_status.get(plat, {})
            runner_state = runner.get("status", "stopped")
            runner_emoji = "🟢" if runner_state == "running" else "⚪"

            st.markdown(f"""
            <div style="border:1px solid #333; border-radius:8px; padding:10px; margin-bottom:8px;">
                <div style="font-size:18px; font-weight:bold;">{icons.get(plat, "📱")} {plat.title()}</div>
                <div style="font-size:13px;">{status_color} {status_text}</div>
                <div style="font-size:12px; color:#888;">{runner_emoji} Runner: {runner_state.title()}</div>
            </div>
            """, unsafe_allow_html=True)

            if not connected:
                if st.button(f"Setup {plat.title()}", key=f"dash_setup_{plat}", use_container_width=True):
                    st.session_state.active_tab = "Account Setup"
                    st.session_state["setup_platform"] = plat
                    st.rerun()

    st.divider()

    # Quick Actions
    st.subheader("⚡ Quick Actions")
    qa1, qa2, qa3, qa4 = st.columns(4)
    with qa1:
        if st.button("🤖 Ask AI for Campaign", use_container_width=True):
            st.session_state.active_tab = "AI Assistant"
            st.rerun()
    with qa2:
        if st.button("🚀 Create Campaign", use_container_width=True):
            st.session_state.active_tab = "Campaigns"
            st.rerun()
    with qa3:
        if st.button("🔧 Connect Accounts", use_container_width=True):
            st.session_state.active_tab = "Account Setup"
            st.rerun()
    with qa4:
        if st.button("📥 Bulk Import", use_container_width=True):
            st.session_state.active_tab = "Bulk Import"
            st.rerun()

    st.divider()

    # Recent Activity
    st.subheader("📋 Recent Activity")
    activities = db.get_recent_activity(10)
    if activities:
        for act in activities:
            emoji = "✅" if act["status"] == "success" else "❌"
            st.markdown(f"{emoji} **{act['platform'].title()}** — {act['action']} — {act['details'][:60]}... <small>{act['created_at']}</small>", unsafe_allow_html=True)
    else:
        st.info("No activity yet. Start a campaign to see activity here.")


def render_ai_assistant():
    st.header("🤖 AI Campaign Assistant")
    st.caption("Describe ANY niche and I will generate a complete campaign instantly. No templates needed.")

    ai = st.session_state.ai
    db = st.session_state.db

    # Chat display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
                    if msg.get("suggestions"):
                        st.session_state.last_ai_suggestion = msg["suggestions"]
                        if st.button("Use These Settings", key=f"use_suggestion_{msg.get('id', 0)}"):
                            st.session_state.campaign_draft = msg["suggestions"]
                            st.session_state.active_tab = "Campaigns"
                            st.rerun()

    # Input
    user_input = st.chat_input("Describe your niche... (e.g., 'I need plumbing leads', 'immigration visa help', 'cybersecurity audits')")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        db.save_chat_message("user", user_input)

        response = ai.chat(user_input)
        msg_entry = {"role": "assistant", "content": response["message"], "suggestions": response.get("suggestions"), "id": len(st.session_state.chat_history)}
        st.session_state.chat_history.append(msg_entry)
        db.save_chat_message("assistant", response["message"], response.get("suggestions"))
        st.rerun()

    st.divider()
    st.caption("💡 **Try these:** 'plumbing emergency leads', 'immigration lawyer clients', 'wedding photographer bookings', 'cybersecurity audit prospects'")


def render_campaigns():
    st.header("🚀 Campaigns")
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
                with st.expander(f"{'🟢' if camp['status'] == 'active' else '⏸️'} {camp['name']} (ID: {camp['id']})"):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.write(f"**Description:** {camp['description']}")
                        st.write(f"**Platforms:** {', '.join(camp['platforms'])}")
                        st.write(f"**Keywords:** {', '.join(camp['keywords'][:5])}...")
                    with c2:
                        st.write(f"**Replies:** {camp['replies_sent']}")
                        st.write(f"**Leads:** {camp['leads_found']}")
                        st.write(f"**Posts:** {camp['posts_checked']}")
                    with c3:
                        if camp["status"] == "active":
                            if st.button("⏸️ Pause", key=f"pause_{camp['id']}"):
                                db.update_campaign_status(camp["id"], "paused")
                                st.rerun()
                        else:
                            if st.button("▶️ Activate", key=f"activate_{camp['id']}"):
                                db.update_campaign_status(camp["id"], "active")
                                st.rerun()
                        if st.button("🗑️ Delete", key=f"del_{camp['id']}"):
                            db.delete_campaign(camp["id"])
                            st.rerun()

    with tabs[1]:
        draft = st.session_state.get("campaign_draft")

        with st.form("create_campaign"):
            name = st.text_input("Campaign Name", value=draft["name"] if draft else "")
            description = st.text_input("Description", value=draft["description"] if draft else "")

            col1, col2 = st.columns(2)
            with col1:
                all_platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]
                default_platforms = draft["platforms"] if draft else ["reddit"]
                platforms = st.multiselect("Platforms", all_platforms, default=default_platforms)
            with col2:
                all_templates = ["custom"] + list(ai.known_niches.keys())
                default_template = draft.get("template", "custom") if draft else "custom"
                try:
                    template_idx = all_templates.index(default_template)
                except ValueError:
                    template_idx = 0
                template = st.selectbox("Template", all_templates, index=template_idx)

            keywords = st.text_area("Keywords (one per line)", value="\n".join(draft["keywords"]) if draft else "")
            indicators = st.text_area("Niche Indicators (one per line)", value="\n".join(draft["niche_indicators"]) if draft else "")
            pitches = st.text_area("Pitches (one per line)", value="\n".join(draft["pitches"]) if draft else "")

            submitted = st.form_submit_button("💾 Create Campaign")
            if submitted:
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
                st.success("Campaign created!")
                st.rerun()


def render_leads():
    st.header("👥 Leads")
    db = st.session_state.db
    leads = db.get_leads()

    if not leads:
        st.info("No leads captured yet. Start an active campaign to collect leads.")
        return

    if HAS_PANDAS:
        df = pd.DataFrame(leads)
        st.dataframe(df, use_container_width=True)
    else:
        for lead in leads[:50]:
            with st.expander(f"{lead['platform'].title()} — {lead['username'] or lead['user_id']}"):
                st.write(f"**Message:** {lead['message']}")
                st.write(f"**Source:** {lead['source']}")
                st.write(f"**Found:** {lead['found_at']}")
    st.write(f"Total leads: {len(leads)}")


def render_account_setup():
    st.header("🔧 Account Setup Wizard")
    st.caption("Connect your social media accounts manually. Step-by-step guides for each platform.")

    config = st.session_state.config
    preselected = st.session_state.get("setup_platform", None)

    platforms = ["telegram", "reddit", "discord", "twitter", "facebook", "instagram", "tiktok"]

    if preselected and preselected in platforms:
        idx = platforms.index(preselected)
        st.session_state.pop("setup_platform", None)
    else:
        idx = 0

    plat = st.selectbox("Select Platform", platforms, index=idx,
                        format_func=lambda x: f"{PLATFORM_SETUP_GUIDES[x]['icon']} {x.title()}")

    guide = PLATFORM_SETUP_GUIDES[plat]
    cfg_section = config.config.get("platforms", {}).get(plat, {})

    st.divider()

    # Status banner
    connected = cfg_section.get("connected", False)
    enabled = cfg_section.get("enabled", False)
    if connected:
        st.success(f"✅ {plat.title()} is connected and ready!")
    elif enabled:
        st.warning(f"⚠️ {plat.title()} has credentials but connection not verified. Click Test Connection.")
    else:
        st.info(f"ℹ️ {plat.title()} not configured yet. Follow the steps below.")

    # Setup guide
    st.subheader(f"{guide['icon']} Setup Guide — Difficulty: {guide['difficulty']} | Time: {guide['time']}")

    if guide.get("warning"):
        st.error(f"⚠️ **Warning:** {guide['warning']}")

    for i, step in enumerate(guide["steps"], 1):
        st.markdown(f"**{i}.** {step}")

    st.divider()

    # Credential inputs
    st.subheader("🔑 Enter Credentials")

    updated = {}
    for field in guide["fields"]:
        label = field.replace("_", " ").title()
        if "secret" in field or "password" in field or "token" in field or "hash" in field:
            val = st.text_input(label, value=cfg_section.get(field, ""), type="password", key=f"{plat}_{field}")
        else:
            val = st.text_input(label, value=cfg_section.get(field, ""), key=f"{plat}_{field}")
        updated[field] = val

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Save Credentials", use_container_width=True):
            for field, val in updated.items():
                config.set("platforms", f"{plat}.{field}", val)
            if any(updated.values()):
                config.set("platforms", f"{plat}.enabled", True)
            else:
                config.set("platforms", f"{plat}.enabled", False)
            st.success("Credentials saved!")
            st.rerun()

    with col2:
        if guide.get("testable"):
            if st.button("🧪 Test Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    result = test_platform_connection(plat, updated)
                    if result:
                        config.set("platforms", f"{plat}.connected", True)
                        st.success(f"✅ {plat.title()} connection successful!")
                    else:
                        config.set("platforms", f"{plat}.connected", False)
                        st.error(f"❌ {plat.title()} connection failed. Check credentials.")
                st.rerun()
        else:
            st.button("🧪 Test Connection", disabled=True, use_container_width=True,
                     help="This platform does not support automated testing.")

    with col3:
        if st.button("🗑️ Clear Credentials", use_container_width=True):
            for field in guide["fields"]:
                config.set("platforms", f"{plat}.{field}", "")
            config.set("platforms", f"{plat}.enabled", False)
            config.set("platforms", f"{plat}.connected", False)
            st.success("Credentials cleared!")
            st.rerun()

    st.divider()

    # Account buying guide
    with st.expander("💰 Don't want to create accounts? Buy aged accounts instead"):
        st.markdown(ACCOUNT_BUYING_GUIDE)

    st.caption("💡 **Tip:** You can also use Bulk Import to add multiple accounts at once from a CSV/JSON file.")


def test_platform_connection(platform, credentials):
    """Test connection to a platform. Returns True/False."""
    try:
        if platform == "telegram":
            api_id = credentials.get("api_id", "")
            api_hash = credentials.get("api_hash", "")
            if not api_id or not api_hash:
                return False
            try:
                from telethon import TelegramClient
                import asyncio
                async def _test():
                    client = TelegramClient("test_session", int(api_id), api_hash)
                    await client.connect()
                    connected = await client.is_user_authorized()
                    await client.disconnect()
                    return connected
                return asyncio.run(_test())
            except:
                return False

        elif platform == "reddit":
            client_id = credentials.get("client_id", "")
            client_secret = credentials.get("client_secret", "")
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            if not all([client_id, client_secret, username, password]):
                return False
            try:
                import praw
                reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    username=username,
                    password=password,
                    user_agent="LeadGenPro/4.0"
                )
                me = reddit.user.me()
                return me is not None
            except:
                return False

        elif platform == "discord":
            token = credentials.get("token", "")
            if not token:
                return False
            try:
                import discord
                import asyncio
                client = discord.Client(intents=discord.Intents.default())
                result = {"ok": False}
                @client.event
                async def on_ready():
                    result["ok"] = True
                    await client.close()
                async def _test():
                    try:
                        await asyncio.wait_for(client.start(token), timeout=5)
                    except:
                        pass
                asyncio.run(_test())
                return result["ok"]
            except:
                return False

        elif platform == "twitter":
            api_key = credentials.get("api_key", "")
            api_secret = credentials.get("api_secret", "")
            access_token = credentials.get("access_token", "")
            access_secret = credentials.get("access_secret", "")
            if not all([api_key, api_secret, access_token, access_secret]):
                return False
            try:
                import tweepy
                auth = tweepy.OAuthHandler(api_key, api_secret)
                auth.set_access_token(access_token, access_secret)
                api = tweepy.API(auth)
                api.verify_credentials()
                return True
            except:
                return False

        return False
    except Exception as e:
        return False


def render_bulk_import():
    st.header("📥 Bulk Account Import")
    st.caption("Import multiple account credentials at once from CSV or JSON.")

    config = st.session_state.config

    tab1, tab2 = st.tabs(["📄 CSV Import", "📋 JSON Import"])

    with tab1:
        st.subheader("CSV Import")
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

                    if st.button("✅ Import from CSV", use_container_width=True):
                        imported = 0
                        for plat, fields in preview.items():
                            for field, value in fields.items():
                                config.set("platforms", f"{plat}.{field}", value)
                            config.set("platforms", f"{plat}.enabled", True)
                            imported += 1
                        st.success(f"Imported credentials for {imported} platform(s)!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    with tab2:
        st.subheader("JSON Import")
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
            "bot_name": "LeadGenBot"
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

                    if st.button("✅ Import from JSON", use_container_width=True):
                        imported = 0
                        for plat, fields in data.items():
                            if isinstance(fields, dict):
                                for field, value in fields.items():
                                    config.set("platforms", f"{plat}.{field}", str(value))
                                config.set("platforms", f"{plat}.enabled", True)
                                imported += 1
                        st.success(f"Imported credentials for {imported} platform(s)!")
                        st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    st.divider()
    st.markdown("""
    **💡 Tips:**
    - You can export your current config from the Settings tab
    - Keep your credential files secure — never commit them to git
    - After importing, go to Account Setup to test each connection
    """)


def render_settings():
    st.header("⚙️ Settings")
    config = st.session_state.config

    with st.form("general_settings"):
        st.subheader("General")
        theme = st.selectbox("Theme", ["dark", "light"], index=0 if config.get("general", "theme") == "dark" else 1)
        check_interval = st.slider("Check Interval (minutes)", 5, 60, config.get("general", "check_interval"))
        max_campaigns = st.slider("Max Campaigns", 1, 50, config.get("general", "max_campaigns"))

        st.subheader("Engagement")
        min_comments = st.number_input("Min Comments", 0, 100, config.get("engagement", "min_comments"))
        reply_delay_min = st.number_input("Reply Delay Min (sec)", 10, 300, config.get("engagement", "reply_delay_min"))
        reply_delay_max = st.number_input("Reply Delay Max (sec)", 30, 600, config.get("engagement", "reply_delay_max"))
        max_replies = st.number_input("Max Replies Per Hour", 1, 50, config.get("engagement", "max_replies_per_hour"))

        st.subheader("Signatures")
        sig_enabled = st.checkbox("Enable Signatures", value=config.get("signatures", "enabled"))
        whatsapp = st.text_input("WhatsApp Number", value=config.get("signatures", "whatsapp"))
        website = st.text_input("Website URL", value=config.get("signatures", "website"))
        custom_text = st.text_area("Custom Signature Text", value=config.get("signatures", "custom_text"))

        if st.form_submit_button("💾 Save Settings"):
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
            st.success("Settings saved!")
            st.rerun()

    st.divider()

    st.subheader("Export / Import Config")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Export Config to JSON", use_container_width=True):
            st.download_button(
                label="Download config.json",
                data=json.dumps(config.config, indent=2),
                file_name="config.json",
                mime="application/json"
            )
    with col2:
        uploaded = st.file_uploader("Import Config JSON", type=["json"], key="config_import")
        if uploaded:
            try:
                new_config = json.loads(uploaded.read().decode("utf-8"))
                config.config = new_config
                config.save()
                st.success("Config imported! Restart the app to apply.")
                st.rerun()
            except Exception as e:
                st.error(f"Error importing config: {e}")

    st.divider()
    if st.button("🗑️ Reset All Settings", type="secondary"):
        config.reset()
        st.success("Settings reset to defaults!")
        st.rerun()


# ============ MAIN ============
def main():
    st.set_page_config(
        page_title=f"{APP_NAME} v{APP_VERSION}",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="expanded"
    )

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
