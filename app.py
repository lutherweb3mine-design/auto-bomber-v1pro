import streamlit as st
import sqlite3
import json
import os
import re
import time
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import requests

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LeadGen Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.05);
    }

    .metric-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 20px;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99,102,241,0.3);
        box-shadow: 0 8px 32px rgba(99,102,241,0.15);
    }

    .platform-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
        transition: all 0.3s ease;
    }
    .platform-card:hover {
        border-color: rgba(99,102,241,0.3);
    }

    .chat-message-user {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 12px 16px;
        margin: 6px 0 6px auto;
        max-width: 80%;
        font-size: 14px;
        line-height: 1.5;
    }
    .chat-message-ai {
        background: linear-gradient(145deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        border: 1px solid rgba(255,255,255,0.08);
        color: #e5e7eb;
        border-radius: 18px 18px 18px 4px;
        padding: 12px 16px;
        margin: 6px auto 6px 0;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.6;
    }

    .test-result-success {
        background: rgba(34,197,94,0.1);
        border: 1px solid rgba(34,197,94,0.3);
        border-radius: 10px;
        padding: 14px;
        color: #86efac;
    }
    .test-result-fail {
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.3);
        border-radius: 10px;
        padding: 14px;
        color: #fca5a5;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        color: #9ca3af;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: white !important;
    }

    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99,102,241,0.3);
    }

    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: white !important;
    }
    .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.2) !important;
    }

    .stSelectbox>div>div {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: white !important;
    }

    @media (max-width: 768px) {
        .metric-card { padding: 14px; }
        .platform-card { padding: 12px; }
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DB_PATH = "leadgen.db"
CONFIG_PATH = "config.json"

# Platform definitions
PLATFORMS = {
    "telegram": {
        "name": "Telegram", "icon": "📱", "color": "#0088cc",
        "fields": {
            "api_id": {"label": "API ID", "type": "text", "required": True,
                       "help": "From my.telegram.org → API development tools"},
            "api_hash": {"label": "API Hash", "type": "password", "required": True,
                         "help": "Same page as API ID — long alphanumeric string"},
            "phone": {"label": "Phone Number", "type": "text", "required": True,
                      "help": "Format: +1234567890 (with country code)"},
            "session_name": {"label": "Session Name", "type": "text", "required": False,
                             "help": "Optional custom session name"}
        },
        "setup_url": "https://my.telegram.org/auth",
        "difficulty": "Medium", "time_estimate": "5-10 min", "testable": True,
        "guide": "**Step 1:** Go to my.telegram.org and log in\n**Step 2:** Click 'API development tools'\n**Step 3:** Fill app title/short name\n**Step 4:** Copy API ID and API Hash\n**Step 5:** Paste above and click Save & Test"
    },
    "reddit": {
        "name": "Reddit", "icon": "🤖", "color": "#FF4500",
        "fields": {
            "client_id": {"label": "Client ID", "type": "text", "required": True,
                          "help": "From Reddit App settings — under app name"},
            "client_secret": {"label": "Client Secret", "type": "password", "required": True,
                              "help": "From Reddit App — click 'edit' to reveal"},
            "username": {"label": "Reddit Username", "type": "text", "required": True},
            "password": {"label": "Reddit Password", "type": "password", "required": True},
            "user_agent": {"label": "User Agent", "type": "text", "required": False}
        },
        "setup_url": "https://www.reddit.com/prefs/apps",
        "difficulty": "Easy", "time_estimate": "3-5 min", "testable": True,
        "guide": "**Step 1:** Go to reddit.com/prefs/apps\n**Step 2:** Click 'create another app'\n**Step 3:** Select 'script' type\n**Step 4:** Name it, set redirect to http://localhost:8080\n**Step 5:** Copy Client ID and Client Secret"
    },
    "discord": {
        "name": "Discord", "icon": "💬", "color": "#5865F2",
        "fields": {
            "token": {"label": "Bot Token", "type": "password", "required": True,
                      "help": "Dev Portal → Your App → Bot tab → Reset Token → Copy"},
            "bot_name": {"label": "Bot Name", "type": "text", "required": False}
        },
        "setup_url": "https://discord.com/developers/applications",
        "difficulty": "Easy", "time_estimate": "3-5 min", "testable": True,
        "guide": "**Step 1:** Go to Discord Developer Portal\n**Step 2:** New Application → Name it\n**Step 3:** Click 'Bot' in sidebar\n**Step 4:** Reset Token → Copy immediately\n**Step 5:** Enable Privileged Gateway Intents\n**Step 6:** OAuth2 → URL Generator → invite bot"
    },
    "twitter": {
        "name": "Twitter/X", "icon": "🐦", "color": "#1DA1F2",
        "fields": {
            "bearer_token": {"label": "Bearer Token", "type": "password", "required": True},
            "api_key": {"label": "API Key", "type": "password", "required": True},
            "api_secret": {"label": "API Secret", "type": "password", "required": True},
            "access_token": {"label": "Access Token", "type": "password", "required": True},
            "access_secret": {"label": "Access Token Secret", "type": "password", "required": True}
        },
        "setup_url": "https://developer.twitter.com/en/portal/dashboard",
        "difficulty": "Medium", "time_estimate": "10-15 min", "testable": True,
        "guide": "**Step 1:** Go to developer.twitter.com\n**Step 2:** Create Project + App\n**Step 3:** Keys and Tokens tab\n**Step 4:** Regenerate all 5 tokens\n**Note:** Free tier = 100 reads/24hrs"
    },
    "facebook": {
        "name": "Facebook", "icon": "📘", "color": "#1877F2",
        "fields": {
            "access_token": {"label": "Access Token", "type": "password", "required": True},
            "page_id": {"label": "Page ID", "type": "text", "required": False}
        },
        "setup_url": "https://developers.facebook.com/tools/explorer/",
        "difficulty": "Hard", "time_estimate": "15-20 min", "testable": False,
        "guide": "⚠️ Facebook heavily restricts new accounts.\n**Step 1:** Go to developers.facebook.com\n**Step 2:** Create Business app\n**Step 3:** Graph API Explorer → generate token\n**Alternative:** Buy aged accounts (~$10-30)"
    },
    "instagram": {
        "name": "Instagram", "icon": "📷", "color": "#E4405F",
        "fields": {
            "username": {"label": "Username", "type": "text", "required": True},
            "password": {"label": "Password", "type": "password", "required": True},
            "session_id": {"label": "Session ID (Optional)", "type": "text", "required": False}
        },
        "setup_url": "https://www.instagram.com/",
        "difficulty": "Hard", "time_estimate": "10-15 min", "testable": False,
        "guide": "⚠️ Instagram blocks automation aggressively.\n**Use aged account (6+ months)**\n**Step 1:** Enter username/password\n**Alternative:** Use Instagram Graph API (requires FB Business verification)"
    },
    "tiktok": {
        "name": "TikTok", "icon": "🎵", "color": "#000000",
        "fields": {
            "api_key": {"label": "API Key", "type": "password", "required": True},
            "api_secret": {"label": "API Secret", "type": "password", "required": True},
            "access_token": {"label": "Access Token", "type": "password", "required": True}
        },
        "setup_url": "https://developers.tiktok.com/",
        "difficulty": "Very Hard", "time_estimate": "20-30 min", "testable": False,
        "guide": "⚠️ Requires business verification (3-7 days).\n**Step 1:** Apply at developers.tiktok.com\n**Step 2:** Submit business documents\n**Step 3:** Create app, get approved"
    }
}

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, niche TEXT,
        keywords TEXT, indicators TEXT, platforms TEXT, pitches TEXT,
        status TEXT DEFAULT 'paused', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        leads_count INTEGER DEFAULT 0, messages_sent INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, platform TEXT,
        username TEXT, message TEXT, status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, responded INTEGER DEFAULT 0, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER, platform TEXT,
        content TEXT, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'sent'
    )""")
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_PATH)

init_db()

# ── Config Manager ────────────────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {"platforms": {}, "settings": {}, "campaigns": []}

def save_config(cfg: dict):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)

def get_platform_config(platform: str) -> dict:
    return load_config().get("platforms", {}).get(platform, {})

def set_platform_config(platform: str, data: dict):
    cfg = load_config()
    cfg.setdefault("platforms", {})[platform] = data
    save_config(cfg)

def is_platform_configured(platform: str) -> bool:
    cfg = get_platform_config(platform)
    if not cfg:
        return False
    p = PLATFORMS.get(platform, {})
    required = [k for k, v in p.get("fields", {}).items() if v.get("required")]
    return all(cfg.get(k) for k in required)

# ── AI Configuration ──────────────────────────────────────────────────────────
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

LEADGEN_SYSTEM_PROMPT = """You are LeadGen Pro AI, a helpful assistant for lead generation automation.

CAPABILITIES:
- Platform setup guides (Telegram, Reddit, Discord, Twitter, Facebook, Instagram, TikTok)
- Campaign creation for any niche with keywords, indicators, pitches
- Troubleshooting API errors (401, 403, 429, connection issues)
- Status checks and analytics

PLATFORM KNOWLEDGE:
- Telegram: my.telegram.org → API ID + Hash + phone number
- Reddit: reddit.com/prefs/apps → script app → Client ID + Secret
- Discord: discord.com/developers → Bot tab → Token + enable intents
- Twitter: developer.twitter.com → 5 tokens (Bearer, API Key/Secret, Access Token/Secret)
- Facebook: developers.facebook.com → Graph API Explorer token
- Instagram: aged account + username/password (aggressive bot detection)
- TikTok: developers.tiktok.com → business verification required

TONE: Professional, conversational, concise. Use formatting for readability.
When user has an error, explain what it means and exact fix steps."""

# ── Persistent AI Engine ─────────────────────────────────────────────────────
def get_api_key() -> str:
    """Get API key from config or env."""
    cfg = load_config()
    key = cfg.get("settings", {}).get("groq_api_key", "")
    if key and key.startswith("gsk_"):
        return key
    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key and env_key.startswith("gsk_"):
        return env_key
    return ""

def chat_with_groq(messages: list, api_key: str) -> Tuple[bool, str]:
    """Call Groq API. Returns (success, response_text)."""
    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 2048},
            timeout=30
        )
        if resp.status_code == 200:
            return True, resp.json()["choices"][0]["message"]["content"]
        elif resp.status_code == 429:
            return False, "⏳ Rate limit hit. Please wait 30 seconds and try again."
        elif resp.status_code == 401:
            return False, "❌ Invalid API key. Check Settings → AI Configuration."
        else:
            return False, f"⚠️ API Error {resp.status_code}: {resp.text[:100]}"
    except requests.exceptions.Timeout:
        return False, "⏱️ Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return False, "🌐 Connection error. Check your internet."
    except Exception as e:
        return False, f"❌ Error: {str(e)[:100]}"

def build_ai_messages(user_input: str, history: list, context: dict = None) -> list:
    """Build message array for Groq API."""
    messages = [{"role": "system", "content": LEADGEN_SYSTEM_PROMPT}]

    # Add context about app state
    if context:
        ctx_parts = []
        platforms = context.get("platforms", {})
        configured = [p for p, s in platforms.items() if s.get("configured")]
        if configured:
            ctx_parts.append(f"Configured platforms: {', '.join(configured)}")
        campaigns = context.get("campaigns", [])
        if campaigns:
            ctx_parts.append(f"Active campaigns: {len([c for c in campaigns if c.get('status')=='active'])}")
        if ctx_parts:
            messages.append({"role": "system", "content": "App state: " + "; ".join(ctx_parts)})

    # Add history (last 6 exchanges max to stay within limits)
    for entry in history[-6:]:
        messages.append({"role": "user", "content": entry["user"]})
        messages.append({"role": "assistant", "content": entry["ai"]})

    messages.append({"role": "user", "content": user_input})
    return messages

# ── Platform Testing ──────────────────────────────────────────────────────────
class PlatformTester:
    @staticmethod
    def test_telegram(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}
        for field in ["api_id", "api_hash", "phone"]:
            if not cfg.get(field):
                results["errors"].append(f"Missing: {field}")
                return results
        try:
            int(cfg["api_id"])
            results["steps"].append(("✅", "API ID valid"))
        except:
            results["errors"].append("API ID must be numeric")
            return results
        if not cfg.get("phone", "").startswith("+"):
            results["errors"].append("Phone needs country code (+)")
        else:
            results["success"] = True
            results["steps"].append(("✅", "Ready for authentication"))
        return results

    @staticmethod
    def test_reddit(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}
        for field in ["client_id", "client_secret", "username", "password"]:
            if not cfg.get(field):
                results["errors"].append(f"Missing: {field}")
                return results
        try:
            import praw
            reddit = praw.Reddit(
                client_id=cfg["client_id"], client_secret=cfg["client_secret"],
                username=cfg["username"], password=cfg["password"],
                user_agent=cfg.get("user_agent", "LeadGenPro/1.0")
            )
            me = reddit.user.me()
            results["steps"].append(("✅", f"Connected as u/{me.name}"))
            results["success"] = True
        except Exception as e:
            results["errors"].append(f"Connection failed: {str(e)[:100]}")
        return results

    @staticmethod
    def test_discord(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}
        if not cfg.get("token"):
            results["errors"].append("Missing Bot Token")
            return results
        try:
            import discord
            import asyncio
            async def test():
                intents = discord.Intents.default()
                intents.message_content = True
                client = discord.Client(intents=intents)
                @client.event
                async def on_ready():
                    results["steps"].append(("✅", f"Connected as {client.user}"))
                    results["success"] = True
                    await client.close()
                try:
                    await client.start(cfg["token"])
                except discord.LoginFailure:
                    results["errors"].append("Invalid token — get it from Bot tab, not Application ID")
                except Exception as e:
                    results["errors"].append(str(e)[:100])
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.wait_for(test(), timeout=10))
            loop.close()
        except Exception as e:
            results["errors"].append(f"Test error: {str(e)[:100]}")
        return results

    @staticmethod
    def test_twitter(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}
        for field in ["bearer_token", "api_key", "api_secret", "access_token", "access_secret"]:
            if not cfg.get(field):
                results["errors"].append(f"Missing: {field}")
                return results
        try:
            import tweepy
            client = tweepy.Client(
                bearer_token=cfg["bearer_token"], consumer_key=cfg["api_key"],
                consumer_secret=cfg["api_secret"], access_token=cfg["access_token"],
                access_token_secret=cfg["access_secret"]
            )
            me = client.get_me()
            if me.data:
                results["steps"].append(("✅", f"Connected as @{me.data.username}"))
                results["success"] = True
        except Exception as e:
            results["errors"].append(f"Failed: {str(e)[:100]}")
        return results

    @staticmethod
    def test_platform(platform: str, cfg: dict) -> Dict:
        testers = {
            "telegram": PlatformTester.test_telegram,
            "reddit": PlatformTester.test_reddit,
            "discord": PlatformTester.test_discord,
            "twitter": PlatformTester.test_twitter,
        }
        tester = testers.get(platform)
        if tester:
            return tester(cfg)
        return {"success": False, "steps": [("⚠️", "Manual verification required")], "errors": []}

# ── UI Components ─────────────────────────────────────────────────────────────
def render_metric_card(title, value, subtitle, icon, color):
    st.markdown(f"""
    <div class="metric-card" style="border-left: 3px solid {color};">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
            <span style="font-size:1.5rem;">{icon}</span>
            <span style="color:{color}; font-size:0.7rem; font-weight:600; text-transform:uppercase;">{title}</span>
        </div>
        <div style="font-size:1.8rem; font-weight:700; color:white;">{value}</div>
        <div style="font-size:0.8rem; color:#9ca3af;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def render_platform_card(pid, p):
    cfg = get_platform_config(pid)
    configured = is_platform_configured(pid)
    status_color = "#22c55e" if configured else "#ef4444"
    status_text = "Connected" if configured else "Not Configured"
    status_dot = "status-online" if configured else "status-offline"
    runner_running = os.path.exists(f"{pid}_runner.pid")
    runner_text = "🟢 Running" if runner_running else "⚪ Stopped"

    st.markdown(f"""
    <div class="platform-card" style="border-left: 3px solid {p['color']};">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-size:1.3rem;">{p['icon']}</span>
                <div>
                    <div style="font-weight:600; color:white; font-size:0.95rem;">{p['name']}</div>
                    <div style="font-size:0.75rem; color:#9ca3af;">{runner_text}</div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
                <span style="width:8px; height:8px; border-radius:50%; background:{status_color}; display:inline-block;"></span>
                <span style="color:{status_color}; font-weight:600; font-size:0.8rem;">{status_text}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_test_results(results):
    if results.get("success"):
        st.markdown('<div class="test-result-success">', unsafe_allow_html=True)
        st.markdown("### ✅ Connected")
    else:
        st.markdown('<div class="test-result-fail">', unsafe_allow_html=True)
        st.markdown("### ❌ Failed")
    for icon, step in results.get("steps", []):
        st.markdown(f"{icon} {step}")
    for err in results.get("errors", []):
        st.markdown(f"- {err}")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Main Application ──────────────────────────────────────────────────────────
def main():
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:10px 0 20px 0;">
            <div style="font-size:2rem;">🚀</div>
            <div style="font-weight:700; color:white; font-size:1.1rem;">LeadGen Pro</div>
            <div style="font-size:0.75rem; color:#6b7280;">v1.0</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:10px 0;'>", unsafe_allow_html=True)

        page = st.radio("Navigation",
            ["📊 Dashboard", "🤖 AI Assistant", "📢 Campaigns", "👥 Leads", "⚙️ Account Setup", "📁 Bulk Import", "🔧 Settings"],
            label_visibility="collapsed")

        st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:10px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#9ca3af; margin-bottom:10px;'>Platform Status</div>", unsafe_allow_html=True)
        for pid, p in PLATFORMS.items():
            status = "🟢" if is_platform_configured(pid) else "🔴"
            st.markdown(f"<div style='font-size:0.75rem;'>{status} {p['icon']} {p['name']}</div>", unsafe_allow_html=True)

    # ── DASHBOARD ───────────────────────────────────────────────────────────
    if page == "📊 Dashboard":
        st.markdown("<h2 style='color:white; margin-bottom:24px;'>Dashboard Overview</h2>", unsafe_allow_html=True)

        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM campaigns WHERE status='active'")
            active = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM leads")
            leads = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM messages")
            msgs = c.fetchone()[0]
            conn.close()
        except:
            active = leads = msgs = 0

        col1, col2, col3, col4 = st.columns(4)
        with col1: render_metric_card("Active Campaigns", str(active), "Running now", "📢", "#6366f1")
        with col2: render_metric_card("Total Leads", str(leads), "Captured all time", "👥", "#22c55e")
        with col3: render_metric_card("Messages Sent", str(msgs), "Outreach messages", "💬", "#f59e0b")
        with col4: render_metric_card("Platforms Ready", f"{sum(1 for p in PLATFORMS if is_platform_configured(p))}/7", "Connected", "🔗", "#ec4899")

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:white; margin-bottom:16px;'>Platform Health</h3>", unsafe_allow_html=True)

        # Responsive: 3 cols on desktop, 1 on mobile
        cols = st.columns(3)
        for i, (pid, p) in enumerate(PLATFORMS.items()):
            with cols[i % 3]:
                render_platform_card(pid, p)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:white; margin-bottom:16px;'>Recent Activity</h3>", unsafe_allow_html=True)
        try:
            conn = get_db()
            df = pd.read_sql_query("SELECT name as Campaign, niche as Niche, status as Status, created_at as Created FROM campaigns ORDER BY created_at DESC LIMIT 5", conn)
            conn.close()
            if df.empty:
                st.info("No activity yet. Create your first campaign.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        except:
            st.info("No activity yet.")

    # ── AI ASSISTANT ────────────────────────────────────────────────────────
    elif page == "🤖 AI Assistant":
        st.markdown("<h2 style='color:white; margin-bottom:8px;'>AI Assistant</h2>", unsafe_allow_html=True)

        api_key = get_api_key()
        if not api_key:
            st.warning("⚠️ AI not configured. Add your Groq API key in Settings.")
            col1, col2 = st.columns([1, 2])
            with col1:
                st.link_button("🔑 Get Free API Key", "https://console.groq.com/keys")
            with col2:
                key_input = st.text_input("Paste Groq API Key", type="password", key="quick_key")
                if key_input and st.button("💾 Save Key", key="quick_save"):
                    cfg = load_config()
                    cfg.setdefault("settings", {})["groq_api_key"] = key_input
                    save_config(cfg)
                    st.success("Key saved! The AI is now active.")
                    st.rerun()
            st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:16px 0;'>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#22c55e; font-size:0.9rem;'>✅ AI Active — Powered by Llama 3.3 70B</p>", unsafe_allow_html=True)

        # Chat history stored in session state
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "last_error" not in st.session_state:
            st.session_state.last_error = None

        # Display chat
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-message-user">{msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-message-ai">{msg["content"]}</div>', unsafe_allow_html=True)

        # Show last error if any (non-blocking)
        if st.session_state.last_error:
            st.error(st.session_state.last_error)
            if st.button("🗑️ Dismiss Error"):
                st.session_state.last_error = None
                st.rerun()

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # Suggestion chips
        suggestions = ["How do I setup Telegram?", "Create a plumbing campaign", "What does 401 mean?", "Suggest niches"]
        sug_cols = st.columns(2)
        for i, sug in enumerate(suggestions):
            with sug_cols[i % 2]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.pending_input = sug
                    st.rerun()

        # Input
        pending = st.session_state.get("pending_input", "")
        if pending:
            st.session_state.pending_input = ""

        user_input = st.text_input("Message", value=pending, key="chat_input",
            placeholder="Ask anything...", label_visibility="collapsed")

        if user_input.strip() and api_key:
            # Add user message
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Build context
            context = {}
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT name, niche, status FROM campaigns")
                context["campaigns"] = [{"name": r[0], "niche": r[1], "status": r[2]} for r in c.fetchall()]
                c.execute("SELECT COUNT(*) FROM leads")
                context["leads_count"] = c.fetchone()[0]
                conn.close()
                platforms = {}
                for pid in PLATFORMS:
                    platforms[pid] = {"configured": is_platform_configured(pid)}
                context["platforms"] = platforms
            except:
                pass

            # Build messages and call API
            history = [{"user": h["content"], "ai": st.session_state.chat_history[i+1]["content"]} 
                        for i, h in enumerate(st.session_state.chat_history[:-1]) if h["role"] == "user"]
            messages = build_ai_messages(user_input, history, context)

            with st.spinner("🤖 Thinking..."):
                success, response = chat_with_groq(messages, api_key)

            if success:
                st.session_state.chat_history.append({"role": "ai", "content": response})
                st.session_state.last_error = None
            else:
                st.session_state.last_error = response
                # Remove the user message since we got an error
                st.session_state.chat_history.pop()

            st.rerun()

        if st.session_state.chat_history and st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.last_error = None
            st.rerun()

    # ── CAMPAIGNS ───────────────────────────────────────────────────────────
    elif page == "📢 Campaigns":
        st.markdown("<h2 style='color:white;'>Campaigns</h2>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["➕ Create", "📋 Manage"])

        with tab1:
            niche = st.text_input("Niche / Industry", placeholder="e.g., plumbing, immigration, cybersecurity")
            if st.button("🤖 Auto-Generate", use_container_width=True) and niche:
                st.session_state.generated_niche = niche
                st.rerun()

            if "generated_niche" in st.session_state:
                niche_val = st.session_state.generated_niche
                st.info(f"Campaign for: {niche_val}")
                keywords = st.text_area("Keywords", value=f"{niche_val}\n{niche_val} service\n{niche_val} near me\nbest {niche_val}\nhire {niche_val}", height=80)
                indicators = st.text_area("Indicators", value=f"need {niche_val}\nlooking for {niche_val}\n{niche_val} recommendation\n{niche_val} urgent", height=80)
                pitches = st.text_area("Pitches", value=f"Hi {{name}}, saw you're looking for {niche_val}. We specialize in {niche_val} with proven results. Reply YES for a free consultation.\n\nHey {{name}}, struggling with {niche_val}? Our team has 5+ years experience. Reply INFO for pricing.\n\nHi {{name}}, [Company] here. We provide top-rated {niche_val} services. Reply BOOK to reserve your slot.", height=120)
                platforms_selected = st.multiselect("Platforms", options=list(PLATFORMS.keys()),
                    format_func=lambda x: f"{PLATFORMS[x]['icon']} {PLATFORMS[x]['name']}")

                name = st.text_input("Campaign Name", placeholder=f"{niche_val.title()} Campaign")
                if st.button("💾 Save Campaign", use_container_width=True):
                    if name and niche_val:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("INSERT INTO campaigns (name, niche, keywords, indicators, platforms, pitches, status) VALUES (?,?,?,?,?,?,?)",
                            (name, niche_val, keywords, indicators, json.dumps(platforms_selected), pitches, "paused"))
                        conn.commit()
                        conn.close()
                        del st.session_state.generated_niche
                        st.success(f"Campaign '{name}' saved!")
                        st.rerun()
            else:
                st.info("Enter a niche and click Auto-Generate to create a campaign.")

        with tab2:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
                camps = c.fetchall()
                conn.close()

                if not camps:
                    st.info("No campaigns yet.")
                else:
                    for camp in camps:
                        cid, name, niche, kw, ind, plats, pitches, status, created, leads, msgs = camp
                        with st.expander(f"{'🟢' if status=='active' else '🔴'} {name} — {niche}"):
                            c1, c2, c3 = st.columns([2, 1, 1])
                            with c1:
                                st.markdown(f"**Status:** {status.upper()} | **Leads:** {leads} | **Messages:** {msgs}")
                            with c2:
                                if status == "paused":
                                    if st.button("▶️ Activate", key=f"a_{cid}"):
                                        conn = get_db(); conn.execute("UPDATE campaigns SET status='active' WHERE id=?", (cid,)); conn.commit(); conn.close(); st.rerun()
                                else:
                                    if st.button("⏸️ Pause", key=f"p_{cid}"):
                                        conn = get_db(); conn.execute("UPDATE campaigns SET status='paused' WHERE id=?", (cid,)); conn.commit(); conn.close(); st.rerun()
                            with c3:
                                if st.button("🗑️ Delete", key=f"d_{cid}"):
                                    conn = get_db(); conn.execute("DELETE FROM campaigns WHERE id=?", (cid,)); conn.commit(); conn.close(); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # ── LEADS ───────────────────────────────────────────────────────────────
    elif page == "👥 Leads":
        st.markdown("<h2 style='color:white;'>Leads</h2>", unsafe_allow_html=True)
        try:
            conn = get_db()
            df = pd.read_sql_query("""
                SELECT l.id, c.name as campaign, l.platform, l.username, l.message, l.status, l.created_at
                FROM leads l LEFT JOIN campaigns c ON l.campaign_id = c.id ORDER BY l.created_at DESC
            """, conn)
            conn.close()
            if df.empty:
                st.info("No leads captured yet. Run active campaigns to generate leads.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        except:
            st.info("No leads yet.")

    # ── ACCOUNT SETUP ───────────────────────────────────────────────────────
    elif page == "⚙️ Account Setup":
        st.markdown("<h2 style='color:white;'>Account Setup</h2>", unsafe_allow_html=True)
        tabs = st.tabs([f"{p['icon']} {p['name']}" for p in PLATFORMS.values()])

        for i, (pid, p) in enumerate(PLATFORMS.items()):
            with tabs[i]:
                cfg = get_platform_config(pid)
                configured = is_platform_configured(pid)
                if configured:
                    st.success(f"✅ {p['name']} configured")
                elif cfg:
                    st.warning(f"⚠️ {p['name']} partially configured")
                else:
                    st.info(f"ℹ️ {p['name']} not configured")

                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown(f"### 📖 Setup Guide")
                    st.markdown(p['guide'])
                    st.link_button(f"🔗 Open {p['name']} Portal", p['setup_url'])
                    diff_colors = {"Easy": "#22c55e", "Medium": "#f59e0b", "Hard": "#ef4444", "Very Hard": "#dc2626"}
                    st.markdown(f"<span style='background:{diff_colors.get(p['difficulty'])}; color:white; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:600;'>{p['difficulty']}</span> <span style='color:#9ca3af; font-size:0.8rem;'>~{p['time_estimate']}</span>", unsafe_allow_html=True)

                with col2:
                    st.markdown(f"### 🔑 Credentials")
                    form_data = {}
                    for fk, fi in p["fields"].items():
                        val = cfg.get(fk, "")
                        if fi["type"] == "password":
                            form_data[fk] = st.text_input(fi["label"], value=val, type="password", help=fi.get("help", ""), key=f"{pid}_{fk}")
                        else:
                            form_data[fk] = st.text_input(fi["label"], value=val, help=fi.get("help", ""), key=f"{pid}_{fk}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾 Save", key=f"sv_{pid}", use_container_width=True):
                            set_platform_config(pid, form_data)
                            st.success("Saved!"); st.rerun()
                    with c2:
                        if st.button("🧪 Test", key=f"ts_{pid}", use_container_width=True):
                            if not is_platform_configured(pid):
                                st.error("Fill required fields first")
                            else:
                                with st.spinner("Testing..."):
                                    res = PlatformTester.test_platform(pid, form_data)
                                render_test_results(res)
                    with c3:
                        if st.button("🗑️ Clear", key=f"cl_{pid}", use_container_width=True):
                            set_platform_config(pid, {})
                            st.success("Cleared!"); st.rerun()

    # ── BULK IMPORT ─────────────────────────────────────────────────────────
    elif page == "📁 Bulk Import":
        st.markdown("<h2 style='color:white;'>Bulk Import</h2>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["📄 CSV", "📝 JSON"])

        with t1:
            st.markdown("**Format:** `platform,field,value`")
            st.code("platform,field,value\ntelegram,api_id,12345678\ntelegram,api_hash,abc...")
            f = st.file_uploader("Upload CSV", type=["csv"])
            if f:
                try:
                    df = pd.read_csv(f)
                    st.dataframe(df.head(10), use_container_width=True)
                    if st.button("📥 Import", use_container_width=True):
                        imported = {}
                        for _, r in df.iterrows():
                            plat, field, val = str(r.get("platform","")).strip().lower(), str(r.get("field","")).strip(), str(r.get("value","")).strip()
                            if plat and field and val:
                                imported.setdefault(plat, {})[field] = val
                        cfg = load_config()
                        for plat, data in imported.items():
                            if plat in PLATFORMS:
                                cfg.setdefault("platforms", {})[plat] = data
                        save_config(cfg)
                        st.success(f"Imported {len(imported)} platform(s)!")
                except Exception as e:
                    st.error(f"Error: {e}")

        with t2:
            st.markdown("**Format:** Nested JSON object")
            st.code('{"telegram": {"api_id": "123", "api_hash": "abc"}}')
            j = st.text_area("Paste JSON", height=150)
            if j:
                try:
                    data = json.loads(j)
                    st.json(data)
                    if st.button("📥 Import JSON", use_container_width=True):
                        cfg = load_config()
                        for plat, creds in data.items():
                            if plat in PLATFORMS and isinstance(creds, dict):
                                cfg.setdefault("platforms", {})[plat] = creds
                        save_config(cfg)
                        st.success("Imported!")
                except:
                    st.error("Invalid JSON")

    # ── SETTINGS ────────────────────────────────────────────────────────────
    elif page == "🔧 Settings":
        st.markdown("<h2 style='color:white;'>Settings</h2>", unsafe_allow_html=True)

        # AI Config
        st.markdown("### 🤖 AI Configuration")
        cfg = load_config()
        current_key = cfg.get("settings", {}).get("groq_api_key", "")
        c1, c2 = st.columns([3, 1])
        with c1:
            new_key = st.text_input("Groq API Key", value=current_key, type="password", placeholder="gsk_...")
        with c2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Save Key", use_container_width=True):
                cfg.setdefault("settings", {})["groq_api_key"] = new_key
                save_config(cfg)
                st.success("Saved!"); st.rerun()

        if get_api_key():
            st.success("✅ AI configured and ready")
        else:
            st.error("❌ AI not configured")

        st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:24px 0;'>", unsafe_allow_html=True)

        # Data Management
        st.markdown("### 💾 Data Management")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Export Config**")
            cfg_json = json.dumps(load_config(), indent=2)
            st.download_button("Download config.json", cfg_json, "leadgen_config.json", "application/json", use_container_width=True)
        with c2:
            st.markdown("**Import Config**")
            up = st.file_uploader("Upload JSON", type=["json"], label_visibility="collapsed")
            if up:
                try:
                    save_config(json.load(up))
                    st.success("Imported!"); st.rerun()
                except:
                    st.error("Invalid JSON")

        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

        # Danger Zone
        st.markdown("### ⚠️ Danger Zone")
        if st.button("🗑️ Reset All Data", use_container_width=True):
            if st.checkbox("I understand this deletes everything"):
                for f in [CONFIG_PATH, DB_PATH]:
                    if os.path.exists(f): os.remove(f)
                init_db()
                st.success("Reset complete."); st.rerun()

if __name__ == "__main__":
    main()
