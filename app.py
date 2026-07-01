#!/usr/bin/env python3
"""
LeadGen Pro - Unified App v2.0
================================
Single entry point. Run:
    streamlit run app.py

Everything connects:
- Dashboard UI (campaigns, leads, analytics, settings)
- AI Chat Assistant (campaign creation helper)
- Background Runner Manager (starts/stops platform bots)
- Comment Customization (signatures on all replies)
- All platforms: Telegram, Reddit, Discord, Twitter, Facebook, Instagram

Background mode:
    python start.py --background    # Start all runners
    python stop.py                  # Stop all runners
    python status.py                # Check status
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
from datetime import datetime, timedelta
from pathlib import Path

# ============ OPTIONAL IMPORTS ============
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
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============ CONSTANTS ============
APP_NAME = "LeadGen Pro"
APP_VERSION = "2.0.0"

DEFAULT_CONFIG = {
    "general": {
        "theme": "dark",
        "language": "english",
        "check_interval": 15,
        "max_campaigns": 10,
        "auto_save": True,
    },
    "platforms": {
        "telegram": {"enabled": False, "api_id": "", "api_hash": "", "phone": ""},
        "reddit": {"enabled": False, "client_id": "", "client_secret": "", "username": "", "password": ""},
        "discord": {"enabled": False, "token": "", "bot_name": ""},
        "twitter": {"enabled": False, "api_key": "", "api_secret": "", "access_token": "", "access_secret": ""},
        "facebook": {"enabled": False, "email": "", "password": ""},
        "instagram": {"enabled": False, "username": "", "password": ""},
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
        "model": "rule_based",
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

CAMPAIGN_TEMPLATES = {
    "crypto_recovery": {
        "name": "Crypto Wallet Recovery",
        "description": "Find people who lost access to crypto wallets",
        "keywords": ["lost crypto", "wallet recovery", "forgot seed", "recover bitcoin", "lost wallet", "cant access wallet", "stuck funds"],
        "platforms": ["telegram", "reddit", "twitter"],
        "niche_indicators": ["lost", "recover", "forgot", "stuck", "access", "seed phrase", "private key", "backup"],
        "pitches": [
            "I specialize in wallet recovery. DM me if you need help getting your funds back.",
            "I have helped people recover lost wallets before. Reach out if you need assistance.",
            "If you are still struggling with wallet access, I have tools that might help. DM me.",
        ],
        "target_groups": ["crypto", "bitcoin", "ethereum", "blockchain"],
    },
    "web_design": {
        "name": "Web Design Services",
        "description": "Find people who need websites built",
        "keywords": ["need a website", "web designer", "build my site", "website help", "redesign website", "cheap website"],
        "platforms": ["reddit", "twitter", "facebook"],
        "niche_indicators": ["website", "design", "build", "create", "need", "looking for", "hire"],
        "pitches": [
            "I build professional websites at affordable prices. DM me for portfolio and pricing.",
            "Need a website? I can help. Check my work and let us discuss your project.",
            "Web designer here. I can build what you need. Message me for details.",
        ],
        "target_groups": ["webdev", "webdesign", "smallbusiness", "startups"],
    },
    "app_development": {
        "name": "App Development",
        "description": "Find people who need mobile apps built",
        "keywords": ["need an app", "app developer", "build my app", "mobile app", "app idea", "cheap app developer"],
        "platforms": ["reddit", "twitter", "facebook"],
        "niche_indicators": ["app", "mobile", "developer", "build", "create", "idea", "need"],
        "pitches": [
            "I develop mobile apps. Have an idea? Let us build it together. DM me.",
            "App developer here. I can turn your idea into reality. Message me for details.",
        ],
        "target_groups": ["appdev", "mobileapps", "startups", "entrepreneurs"],
    },
    "custom": {
        "name": "Custom Campaign",
        "description": "Build your own campaign from scratch",
        "keywords": [],
        "platforms": [],
        "niche_indicators": [],
        "pitches": [],
        "target_groups": [],
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

# ============ NICHE DETECTOR ============
class NicheDetector:
    def __init__(self, settings):
        self.settings = settings
        self.confidence_threshold = settings.get("ai", {}).get("confidence_threshold", 0.5)

    def analyze(self, text, campaign_indicators):
        text_lower = text.lower()
        matched = []
        total_score = 0
        max_score = len(campaign_indicators) * 2

        for indicator in campaign_indicators:
            indicator_lower = indicator.lower()
            if indicator_lower in text_lower:
                matched.append(indicator)
                total_score += 2
                continue
            indicator_words = indicator_lower.split()
            for iw in indicator_words:
                if len(iw) > 3 and iw in text_lower:
                    matched.append(indicator)
                    total_score += 1
                    break
            related = self._get_related_words(indicator_lower)
            for rw in related:
                if rw in text_lower:
                    total_score += 0.5

        help_words = ["help", "need", "looking for", "want", "please", "anyone", "struggling"]
        if any(hw in text_lower for hw in help_words):
            total_score += 1

        confidence = min(total_score / max_score, 1.0) if max_score > 0 else 0
        is_match = confidence >= self.confidence_threshold
        return is_match, confidence, list(set(matched))

    def _get_related_words(self, word):
        related = {
            "wallet": ["account", "funds", "crypto", "bitcoin", "eth"],
            "recover": ["get back", "restore", "retrieve", "access"],
            "lost": ["forgot", "missing", "cant find", "deleted"],
            "website": ["site", "web", "page", "online", "domain"],
            "design": ["build", "create", "make", "develop"],
            "app": ["application", "mobile", "software", "program"],
        }
        return related.get(word, [])

# ============ SIGNATURE MANAGER ============
class SignatureManager:
    def __init__(self, config):
        self.config = config

    def build_signature(self, campaign_signature=None):
        sig_config = self.config.get("signatures", {})
        if not sig_config.get("enabled", False):
            return ""
        parts = []
        sig = campaign_signature if campaign_signature else {}
        if isinstance(sig, dict):
            if sig.get("whatsapp"):
                parts.append("📱 WhatsApp: " + sig['whatsapp'])
            if sig.get("website"):
                parts.append("🌐 Website: " + sig['website'])
            if sig.get("custom_text"):
                parts.append(sig["custom_text"])
        if not parts:
            if sig_config.get("whatsapp"):
                parts.append("📱 WhatsApp: " + sig_config['whatsapp'])
            if sig_config.get("website"):
                parts.append("🌐 Website: " + sig_config['website'])
            if sig_config.get("custom_text"):
                parts.append(sig_config["custom_text"])
        if not parts:
            return ""
        return "\n\n" + "\n".join(parts)

    def apply_to_pitch(self, pitch, campaign_signature=None):
        sig = self.build_signature(campaign_signature)
        if sig:
            return pitch + sig
        return pitch

# ============ AI CHAT ASSISTANT ============
class AIChatAssistant:
    def __init__(self):
        self.history = []

    def generate_campaign_suggestions(self, user_input):
        text = user_input.lower()
        niches = {
            "crypto": ["crypto", "bitcoin", "wallet", "blockchain", "ethereum", "seed phrase", "private key", "lost crypto"],
            "web_design": ["website", "web design", "build site", "need a website", "web developer"],
            "app_dev": ["app", "mobile app", "application", "app developer", "build app"],
            "marketing": ["marketing", "seo", "ads", "promote", "traffic"],
            "writing": ["writer", "content", "blog", "copywriting", "article"],
            "design": ["logo", "graphic design", "branding", "ui", "ux"],
            "seo": ["seo", "ranking", "google", "search", "optimize"],
            "social_media": ["social media", "instagram", "followers", "engagement", "grow"],
            "ecommerce": ["shopify", "dropshipping", "ecommerce", "store", "products"],
            "coaching": ["coach", "mentor", "course", "training", "learn"],
        }
        detected_niche = None
        for niche, keywords in niches.items():
            if any(kw in text for kw in keywords):
                detected_niche = niche
                break

        if detected_niche == "crypto":
            return {
                "name": "Crypto Wallet Recovery",
                "description": "Find people who lost access to crypto wallets and need recovery help.",
                "keywords": ["lost crypto", "wallet recovery", "forgot seed", "recover bitcoin", "lost wallet", "cant access wallet"],
                "niche_indicators": ["lost", "recover", "forgot", "stuck", "access", "seed phrase", "private key"],
                "pitches": [
                    "I specialize in wallet recovery. DM me if you need help getting your funds back.",
                    "I have helped people recover lost wallets before. Reach out if you need assistance.",
                    "If you are still struggling with wallet access, I have tools that might help. DM me.",
                ],
                "platforms": ["telegram", "reddit", "twitter"],
                "target_groups": ["crypto", "bitcoin", "ethereum"],
            }
        elif detected_niche == "web_design":
            return {
                "name": "Web Design Services",
                "description": "Find people who need professional websites built.",
                "keywords": ["need a website", "web designer", "build my site", "website help", "redesign website"],
                "niche_indicators": ["website", "design", "build", "create", "need", "looking for", "hire"],
                "pitches": [
                    "I build professional websites at affordable prices. DM me for portfolio and pricing.",
                    "Need a website? I can help. Check my work and let us discuss your project.",
                    "Web designer here. I can build what you need. Message me for details.",
                ],
                "platforms": ["reddit", "twitter", "facebook"],
                "target_groups": ["webdev", "webdesign", "smallbusiness"],
            }
        elif detected_niche == "app_dev":
            return {
                "name": "App Development",
                "description": "Find people who need mobile apps built.",
                "keywords": ["need an app", "app developer", "build my app", "mobile app", "app idea"],
                "niche_indicators": ["app", "mobile", "developer", "build", "create", "idea", "need"],
                "pitches": [
                    "I develop mobile apps. Have an idea? Let us build it together. DM me.",
                    "App developer here. I can turn your idea into reality. Message me for details.",
                ],
                "platforms": ["reddit", "twitter", "facebook"],
                "target_groups": ["appdev", "mobileapps", "startups"],
            }
        elif detected_niche == "marketing":
            return {
                "name": "Digital Marketing Services",
                "description": "Find businesses that need marketing help.",
                "keywords": ["need marketing", "seo help", "grow my business", "digital marketing", "ads help"],
                "niche_indicators": ["marketing", "seo", "ads", "promote", "traffic", "grow", "clients"],
                "pitches": [
                    "I help businesses grow with proven marketing strategies. DM me for a free audit.",
                    "Need more customers? I specialize in digital marketing. Let us talk.",
                ],
                "platforms": ["reddit", "twitter", "facebook", "instagram"],
                "target_groups": ["marketing", "smallbusiness", "entrepreneurs"],
            }
        elif detected_niche == "writing":
            return {
                "name": "Content Writing Services",
                "description": "Find people who need blog posts, articles, or copywriting.",
                "keywords": ["need a writer", "content writer", "blog writer", "copywriter", "article writer"],
                "niche_indicators": ["writer", "content", "blog", "article", "copy", "write"],
                "pitches": [
                    "Professional writer here. I create engaging content that converts. DM me.",
                    "Need quality content? I write blogs, articles, and sales copy. Let us discuss.",
                ],
                "platforms": ["reddit", "twitter", "facebook"],
                "target_groups": ["writing", "blogging", "startups"],
            }
        elif detected_niche == "social_media":
            return {
                "name": "Social Media Growth",
                "description": "Find people who want to grow their social media presence.",
                "keywords": ["grow instagram", "more followers", "social media help", "engagement", "viral"],
                "niche_indicators": ["followers", "engagement", "grow", "viral", "social media", "instagram"],
                "pitches": [
                    "I help accounts grow organically. DM me for a growth strategy.",
                    "Want more followers and engagement? I have proven methods. Message me.",
                ],
                "platforms": ["reddit", "twitter", "instagram"],
                "target_groups": ["socialmedia", "instagram", "influencers"],
            }
        elif detected_niche == "ecommerce":
            return {
                "name": "E-commerce Consulting",
                "description": "Find people who need help with their online store.",
                "keywords": ["shopify help", "dropshipping", "ecommerce store", "online store", "product sourcing"],
                "niche_indicators": ["shopify", "dropshipping", "ecommerce", "store", "products", "sales"],
                "pitches": [
                    "I help e-commerce stores scale. DM me for a free strategy call.",
                    "Struggling with your online store? I can help optimize and grow sales.",
                ],
                "platforms": ["reddit", "twitter", "facebook"],
                "target_groups": ["ecommerce", "shopify", "dropshipping"],
            }
        elif detected_niche == "coaching":
            return {
                "name": "Online Coaching & Courses",
                "description": "Find people looking for coaching or online courses.",
                "keywords": ["need a coach", "online course", "learn", "mentor", "training"],
                "niche_indicators": ["coach", "mentor", "course", "training", "learn", "teach"],
                "pitches": [
                    "I offer 1-on-1 coaching to help you reach your goals. DM me for details.",
                    "Looking to learn? I have courses and coaching programs. Message me.",
                ],
                "platforms": ["reddit", "twitter", "facebook", "instagram"],
                "target_groups": ["coaching", "selfimprovement", "entrepreneurs"],
            }
        else:
            return {
                "name": "Custom Campaign",
                "description": user_input,
                "keywords": [user_input],
                "niche_indicators": [user_input],
                "pitches": ["I can help with this. DM me for details."],
                "platforms": ["reddit", "twitter"],
                "target_groups": [],
            }

    def chat(self, user_message, context=None):
        text = user_message.lower()
        if any(word in text for word in ["create", "make", "build", "start", "want to find", "looking for", "need", "help me find"]):
            suggestions = self.generate_campaign_suggestions(user_message)
            response = "Great! I will help you create a campaign for: **" + suggestions['name'] + "**\n\n"
            response += "**Description:** " + suggestions['description'] + "\n\n"
            response += "**Suggested Keywords:**\n" + "\n".join(["- " + k for k in suggestions['keywords'][:5]]) + "\n\n"
            response += "**Suggested Platforms:** " + ", ".join(suggestions['platforms']) + "\n\n"
            response += "**Sample Pitch:**\n> " + suggestions['pitches'][0] + "\n\n"
            response += "Click **Use These Settings** below to auto-fill the campaign builder!"
            return response, suggestions
        elif any(word in text for word in ["help", "how", "what", "?"]):
            return "I can help you create campaigns! Just tell me what kind of leads you want to find. For example:\n- \"I want to find people who lost crypto wallets\"\n- \"I need web design clients\"\n- \"Looking for app development leads\"\n- \"Help me find ecommerce store owners\"", None
        elif any(word in text for word in ["hi", "hello", "hey", "sup"]):
            return "Hey! I am your AI Campaign Assistant. Tell me what kind of leads you want to find, and I will build a campaign for you!", None
        else:
            return "I am not sure I understand. Try telling me what kind of leads you want to find, like \"I want to find people who need websites\" or \"help me find crypto wallet recovery leads\".", None

# ============ BACKGROUND RUNNER MANAGER ============
class RunnerManager:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.processes = {}

    def start_runner(self, platform):
        if platform in self.processes and self.processes[platform].poll() is None:
            return False, "Already running"
        script_map = {
            "telegram": "telegram_runner.py",
            "reddit": "reddit_runner.py",
            "discord": "discord_runner.py",
            "twitter": "twitter_runner.py",
            "facebook": "facebook_runner.py",
            "instagram": "instagram_runner.py",
        }
        script = BASE_DIR / script_map.get(platform, "")
        if not script.exists():
            return False, "Runner script not found: " + str(script)
        try:
            log_file = LOGS_DIR / (platform + ".log")
            with open(log_file, "a") as log:
                proc = subprocess.Popen(
                    [sys.executable, str(script)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=BASE_DIR
                )
            self.processes[platform] = proc
            self.db.update_runner_status(platform, "running", pid=proc.pid)
            return True, "Started " + platform + " runner (PID: " + str(proc.pid) + ")"
        except Exception as e:
            return False, str(e)

    def stop_runner(self, platform):
        if platform in self.processes:
            try:
                self.processes[platform].terminate()
                del self.processes[platform]
            except:
                pass
        self.db.update_runner_status(platform, "stopped", pid=None)
        return True, "Stopped " + platform + " runner"

    def stop_all(self):
        for platform in list(self.processes.keys()):
            self.stop_runner(platform)

    def get_status(self):
        status = {}
        for platform, proc in list(self.processes.items()):
            if proc.poll() is not None:
                self.db.update_runner_status(platform, "stopped", pid=None)
                del self.processes[platform]
                status[platform] = "stopped"
            else:
                status[platform] = "running"
        db_status = self.db.get_runner_status()
        for platform, info in db_status.items():
            if platform not in status:
                status[platform] = info.get("status", "stopped")
        return status

    def start_all_enabled(self):
        platforms_config = self.config.get("platforms", {})
        campaigns = self.db.get_campaigns("active")
        enabled_platforms = set()
        for camp in campaigns:
            for p in camp.get("platforms", []):
                if platforms_config.get(p, {}).get("enabled", False):
                    enabled_platforms.add(p)
        results = {}
        for platform in enabled_platforms:
            success, msg = self.start_runner(platform)
            results[platform] = {"success": success, "message": msg}
        return results
