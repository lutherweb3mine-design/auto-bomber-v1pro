import streamlit as st
import sqlite3
import json
import os
import re
import time
import random
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

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

    /* Dark theme base */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.05);
    }

    /* Cards */
    .metric-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99,102,241,0.3);
        box-shadow: 0 8px 32px rgba(99,102,241,0.15);
    }

    .status-indicator {
        width: 10px; height: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        box-shadow: 0 0 8px currentColor;
    }
    .status-online { background: #22c55e; color: #22c55e; }
    .status-offline { background: #ef4444; color: #ef4444; }
    .status-warning { background: #f59e0b; color: #f59e0b; }
    .status-pending { background: #6b7280; color: #6b7280; }

    .platform-card {
        background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: all 0.3s ease;
    }
    .platform-card:hover {
        border-color: rgba(99,102,241,0.3);
    }

    .chat-message-user {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 14px 18px;
        margin: 8px 0 8px auto;
        max-width: 80%;
        font-size: 14px;
        line-height: 1.5;
    }
    .chat-message-ai {
        background: linear-gradient(145deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        border: 1px solid rgba(255,255,255,0.08);
        color: #e5e7eb;
        border-radius: 18px 18px 18px 4px;
        padding: 14px 18px;
        margin: 8px auto 8px 0;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.6;
    }

    .setup-step {
        background: rgba(255,255,255,0.03);
        border-left: 3px solid #6366f1;
        padding: 16px 20px;
        margin: 12px 0;
        border-radius: 0 12px 12px 0;
    }

    .test-result-success {
        background: rgba(34,197,94,0.1);
        border: 1px solid rgba(34,197,94,0.3);
        border-radius: 10px;
        padding: 16px;
        color: #86efac;
    }
    .test-result-fail {
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.3);
        border-radius: 10px;
        padding: 16px;
        color: #fca5a5;
    }
    .test-result-pending {
        background: rgba(245,158,11,0.1);
        border: 1px solid rgba(245,158,11,0.3);
        border-radius: 10px;
        padding: 16px;
        color: #fcd34d;
    }

    /* Streamlit branding visible — no hiding */

    /* Tabs */
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

    /* Buttons */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99,102,241,0.3);
    }

    /* Inputs */
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

    /* Selectbox */
    .stSelectbox>div>div {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: white !important;
    }

    /* Progress bars */
    .stProgress>div>div>div {
        background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%) !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DB_PATH = "leadgen.db"
CONFIG_PATH = "config.json"

# Platform definitions with EXACT required fields
PLATFORMS = {
    "telegram": {
        "name": "Telegram",
        "icon": "📱",
        "color": "#0088cc",
        "fields": {
            "api_id": {"label": "API ID", "type": "text", "required": True, 
                       "help": "Get from my.telegram.org → API development tools → Create application"},
            "api_hash": {"label": "API Hash", "type": "password", "required": True,
                         "help": "Same page as API ID — long alphanumeric string"},
            "phone": {"label": "Phone Number", "type": "text", "required": True,
                      "help": "Format: +1234567890 (with country code)"},
            "session_name": {"label": "Session Name", "type": "text", "required": False,
                             "help": "Optional custom session name (default: leadgen_session)"}
        },
        "setup_url": "https://my.telegram.org/auth",
        "difficulty": "Medium",
        "time_estimate": "5-10 min",
        "testable": True,
        "guide": """
        **Step 1:** Go to [my.telegram.org](https://my.telegram.org/auth) and log in with your phone number
        **Step 2:** Click "API development tools"
        **Step 3:** Fill in any app title/short name (e.g., "LeadGen Bot")
        **Step 4:** Copy the **API ID** (numbers only) and **API Hash** (long string)
        **Step 5:** Paste them above and click "Save & Test"
        **Step 6:** You'll receive an SMS code on first run — enter it when prompted
        """
    },
    "reddit": {
        "name": "Reddit",
        "icon": "🤖",
        "color": "#FF4500",
        "fields": {
            "client_id": {"label": "Client ID", "type": "text", "required": True,
                          "help": "From Reddit App settings — the string under your app name"},
            "client_secret": {"label": "Client Secret", "type": "password", "required": True,
                              "help": "From Reddit App settings — click 'edit' to reveal"},
            "username": {"label": "Reddit Username", "type": "text", "required": True,
                         "help": "Your Reddit username (without u/)"},
            "password": {"label": "Reddit Password", "type": "password", "required": True,
                         "help": "Your Reddit account password"},
            "user_agent": {"label": "User Agent", "type": "text", "required": False,
                           "help": "Optional custom user agent string"}
        },
        "setup_url": "https://www.reddit.com/prefs/apps",
        "difficulty": "Easy",
        "time_estimate": "3-5 min",
        "testable": True,
        "guide": """
        **Step 1:** Go to [Reddit Apps](https://www.reddit.com/prefs/apps) while logged in
        **Step 2:** Scroll down and click "create another app..."
        **Step 3:** Select "script" as the app type
        **Step 4:** Name it "LeadGen" and set redirect URI to `http://localhost:8080`
        **Step 5:** Click "create app"
        **Step 6:** Copy the **Client ID** (under the app name) and **Client Secret** (labeled "secret")
        **Step 7:** Paste them above with your Reddit username and password
        """
    },
    "discord": {
        "name": "Discord",
        "icon": "💬",
        "color": "#5865F2",
        "fields": {
            "token": {"label": "Bot Token", "type": "password", "required": True,
                      "help": "From Discord Developer Portal → Your App → Bot tab → Reset Token → Copy"},
            "bot_name": {"label": "Bot Name", "type": "text", "required": False,
                         "help": "Optional display name for the bot"}
        },
        "setup_url": "https://discord.com/developers/applications",
        "difficulty": "Easy",
        "time_estimate": "3-5 min",
        "testable": True,
        "guide": """
        **Step 1:** Go to [Discord Developer Portal](https://discord.com/developers/applications)
        **Step 2:** Click "New Application" → Name it "LeadGen Bot" → Create
        **Step 3:** In the left sidebar, click **"Bot"** (NOT the main page)
        **Step 4:** Click "Reset Token" → **Copy the token immediately** (it won't show again)
        **Step 5:** Scroll down and enable these Privileged Gateway Intents:
        - ✓ Presence Intent
        - ✓ Server Members Intent  
        - ✓ Message Content Intent
        **Step 6:** Click "Save Changes"
        **Step 7:** Go to OAuth2 → URL Generator
        **Step 8:** Select scope: `bot`
        **Step 9:** Select permissions: `Send Messages`, `Read Message History`, `View Channels`
        **Step 10:** Copy the generated URL, open it in browser, and invite the bot to your server
        **Step 11:** Paste the token above and click "Save & Test"
        """
    },
    "twitter": {
        "name": "Twitter/X",
        "icon": "🐦",
        "color": "#1DA1F2",
        "fields": {
            "bearer_token": {"label": "Bearer Token", "type": "password", "required": True,
                             "help": "From Twitter Developer Portal → Projects & Apps → Keys and Tokens"},
            "api_key": {"label": "API Key", "type": "password", "required": True,
                        "help": "Also called Consumer Key"},
            "api_secret": {"label": "API Secret", "type": "password", "required": True,
                           "help": "Also called Consumer Secret"},
            "access_token": {"label": "Access Token", "type": "password", "required": True,
                             "help": "From same page — user-specific token"},
            "access_secret": {"label": "Access Token Secret", "type": "password", "required": True,
                              "help": "From same page — paired with Access Token"}
        },
        "setup_url": "https://developer.twitter.com/en/portal/dashboard",
        "difficulty": "Medium",
        "time_estimate": "10-15 min",
        "testable": True,
        "guide": """
        **Step 1:** Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
        **Step 2:** Create a Project, then an App within it
        **Step 3:** Go to "Keys and Tokens" tab
        **Step 4:** Under "Consumer Keys", click "Regenerate" → copy **API Key** and **API Secret**
        **Step 5:** Under "Authentication Tokens", click "Generate" → copy **Access Token** and **Access Secret**
        **Step 6:** Under "Bearer Token", click "Regenerate" → copy **Bearer Token**
        **Step 7:** Paste all 5 tokens above
        **Note:** Free tier has strict rate limits (100 reads/24hrs). Consider Basic ($100/mo) for production.
        """
    },
    "facebook": {
        "name": "Facebook",
        "icon": "📘",
        "color": "#1877F2",
        "fields": {
            "access_token": {"label": "Access Token", "type": "password", "required": True,
                             "help": "From Facebook Developer → Graph API Explorer → Generate User Token"},
            "page_id": {"label": "Page ID", "type": "text", "required": False,
                        "help": "Optional — if targeting a specific Facebook Page"}
        },
        "setup_url": "https://developers.facebook.com/tools/explorer/",
        "difficulty": "Hard",
        "time_estimate": "15-20 min",
        "testable": False,
        "guide": """
        **⚠️ Facebook is heavily restricted.** New accounts often require photo ID verification.

        **Step 1:** Go to [Facebook Developer](https://developers.facebook.com/tools/explorer/)
        **Step 2:** Create an app (Business type recommended)
        **Step 3:** Go to Graph API Explorer
        **Step 4:** Select your app, generate a User Access Token
        **Step 5:** Add permissions: `pages_read_engagement`, `pages_messaging`
        **Step 6:** Copy the access token

        **Alternative:** Buy aged Facebook accounts from marketplaces (~$10-30 each) to avoid verification.
        """
    },
    "instagram": {
        "name": "Instagram",
        "icon": "📷",
        "color": "#E4405F",
        "fields": {
            "username": {"label": "Instagram Username", "type": "text", "required": True,
                         "help": "Your Instagram username (without @)"},
            "password": {"label": "Instagram Password", "type": "password", "required": True,
                         "help": "Your Instagram password"},
            "session_id": {"label": "Session ID (Optional)", "type": "text", "required": False,
                           "help": "Advanced: session ID for persistent login"}
        },
        "setup_url": "https://www.instagram.com/",
        "difficulty": "Hard",
        "time_estimate": "10-15 min",
        "testable": False,
        "guide": """
        **⚠️ Instagram aggressively blocks automation.** Expect frequent login challenges.

        **Step 1:** Use an aged account (6+ months old) — new accounts get banned instantly
        **Step 2:** Enable 2FA and generate backup codes
        **Step 3:** Use the same IP/device consistently
        **Step 4:** Enter username/password above

        **Alternative:** Use the Instagram Graph API (requires Facebook Business verification)
        or buy aged accounts (~$15-40 each).
        """
    },
    "tiktok": {
        "name": "TikTok",
        "icon": "🎵",
        "color": "#000000",
        "fields": {
            "api_key": {"label": "API Key", "type": "password", "required": True,
                        "help": "From TikTok for Developers → My Apps → App details"},
            "api_secret": {"label": "API Secret", "type": "password", "required": True,
                           "help": "From same page"},
            "access_token": {"label": "Access Token", "type": "password", "required": True,
                             "help": "Generated after app approval"}
        },
        "setup_url": "https://developers.tiktok.com/",
        "difficulty": "Very Hard",
        "time_estimate": "20-30 min",
        "testable": False,
        "guide": """
        **⚠️ TikTok requires business verification.** Very difficult for new accounts.

        **Step 1:** Apply at [TikTok for Developers](https://developers.tiktok.com/)
        **Step 2:** Submit business documents (takes 3-7 days)
        **Step 3:** Create an app, get approved
        **Step 4:** Copy API Key, Secret, and Access Token

        **Alternative:** Use unofficial APIs (risky, can break anytime) or buy verified accounts.
        """
    }
}

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, niche TEXT, keywords TEXT, indicators TEXT,
        platforms TEXT, pitches TEXT, status TEXT DEFAULT 'paused',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        leads_count INTEGER DEFAULT 0, messages_sent INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER, platform TEXT, username TEXT,
        message TEXT, status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        responded INTEGER DEFAULT 0, notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER, platform TEXT, content TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'sent'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS platform_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT, event TEXT, details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    cfg = load_config()
    return cfg.get("platforms", {}).get(platform, {})

def set_platform_config(platform: str, data: dict):
    cfg = load_config()
    if "platforms" not in cfg:
        cfg["platforms"] = {}
    cfg["platforms"][platform] = data
    save_config(cfg)

def is_platform_configured(platform: str) -> bool:
    cfg = get_platform_config(platform)
    if not cfg:
        return False
    p = PLATFORMS.get(platform, {})
    required = [k for k, v in p.get("fields", {}).items() if v.get("required")]
    return all(cfg.get(k) for k in required)


# ── AI Configuration ──────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Fast, capable, generous free tier
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# System prompt that gives the AI knowledge about LeadGen Pro
LEADGEN_SYSTEM_PROMPT = """You are LeadGen Pro AI, a helpful and knowledgeable assistant for a lead generation automation platform.

YOUR CAPABILITIES:
- Help users set up social media platform accounts (Telegram, Reddit, Discord, Twitter/X, Facebook, Instagram, TikTok)
- Guide users through API credential creation on each platform
- Create lead generation campaigns for ANY niche/industry dynamically
- Suggest keywords, lead indicators, and outreach pitches
- Check platform connection status and campaign performance
- Help with bulk account imports via CSV/JSON
- Troubleshoot connection errors and API issues

PLATFORM SETUP KNOWLEDGE:
- Telegram: Go to my.telegram.org → API development tools → create app → copy API ID (numbers) and API Hash (long string). Also need phone number with country code.
- Reddit: Go to reddit.com/prefs/apps → create "script" app → copy Client ID (under app name) and Client Secret.
- Discord: Go to discord.com/developers/applications → New Application → Bot tab → Reset Token → copy token. Must enable Privileged Gateway Intents (Presence, Server Members, Message Content).
- Twitter/X: Go to developer.twitter.com → create Project + App → Keys and Tokens → copy Bearer Token, API Key, API Secret, Access Token, Access Token Secret. Free tier = 100 reads/day.
- Facebook: Go to developers.facebook.com → Graph API Explorer → generate User Access Token. Very strict, often requires business verification.
- Instagram: Use aged account (6+ months) with username/password. New accounts get banned instantly.
- TikTok: Go to developers.tiktok.com → apply for developer account (requires business verification, 3-7 days).

CAMPAIGN CREATION:
When user wants a campaign, ask for their niche if not provided, then generate:
1. 5-10 targeted keywords
2. 5-10 lead indicators (phrases that signal buying intent)
3. 3 personalized outreach pitches (use {name} placeholder for username)
4. Recommended platforms based on niche type

TONE: Professional but conversational. Be concise but thorough. Use formatting (bullet points, bold text) for readability. If you don't know something, say so honestly.

IMPORTANT: If the user asks about a specific platform setup, give EXACT step-by-step instructions with URLs. If they have an error code (401, 403, 429), explain what it means and how to fix it."""

# ── Real AI Chat Engine (Groq API) ───────────────────────────────────────────
class AIChatEngine:
    """Real conversational AI using Groq's free LLM API."""

    def __init__(self, api_key: str = None):
        # Priority: 1) passed directly, 2) from config.json, 3) from env var
        if api_key:
            self.api_key = api_key
        else:
            # Try config.json first (where Settings saves it)
            try:
                cfg = load_config()
                config_key = cfg.get("settings", {}).get("groq_api_key", "")
                if config_key and len(config_key) > 20:
                    self.api_key = config_key
                else:
                    self.api_key = GROQ_API_KEY  # fallback to env
            except:
                self.api_key = GROQ_API_KEY

        self.conversation_history = []  # Per-session memory
        self.max_history = 10  # Keep last 10 exchanges for context

    def is_configured(self) -> bool:
        return bool(self.api_key) and len(self.api_key) > 30 and self.api_key.startswith("gsk_")

    def chat(self, user_message: str, context_data: Dict = None) -> str:
        """Send message to Groq API and return response."""
        if not self.is_configured():
            return self._fallback_response(user_message, context_data)

        import requests

        # Build messages with system prompt + history + current message
        messages = [{"role": "system", "content": LEADGEN_SYSTEM_PROMPT}]

        # Add conversation history for context
        for entry in self.conversation_history[-self.max_history:]:
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["ai"]})

        # Add current platform/campaign context if available
        context_msg = self._build_context_message(context_data)
        if context_msg:
            messages.append({"role": "system", "content": context_msg})

        messages.append({"role": "user", "content": user_message})

        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "top_p": 0.9
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                ai_reply = result["choices"][0]["message"]["content"]

                # Store in history
                self.conversation_history.append({"user": user_message, "ai": ai_reply})

                return ai_reply

            elif response.status_code == 401:
                return "❌ **Invalid API Key.** Your Groq API key appears to be incorrect or expired. Go to [console.groq.com/keys](https://console.groq.com/keys) to generate a new one, then paste it in Settings."

            elif response.status_code == 429:
                return "⏳ **Rate limit hit.** Groq free tier allows 30 requests/minute and ~1,000/day. Wait a few seconds and try again. If this happens often, consider upgrading at [console.groq.com](https://console.groq.com)."

            else:
                return f"⚠️ **API Error ({response.status_code}):** {response.text[:200]}\n\nIf this persists, check your API key in Settings or try again later."

        except requests.exceptions.Timeout:
            return "⏱️ **Request timed out.** Groq's servers may be busy. Try again in a few seconds."

        except requests.exceptions.ConnectionError:
            return "🌐 **Connection error.** Check your internet connection and try again."

        except Exception as e:
            return f"❌ **Unexpected error:** {str(e)}\n\nPlease check your API key in Settings → AI Configuration."

    def _build_context_message(self, context_data: Dict) -> str:
        """Build a context message from current app state."""
        if not context_data:
            return ""

        parts = []

        # Platform status
        platforms = context_data.get("platforms", {})
        configured = [p for p, c in platforms.items() if c.get("configured")]
        if configured:
            parts.append(f"Currently configured platforms: {', '.join(configured)}")

        # Active campaigns
        campaigns = context_data.get("campaigns", [])
        active = [c for c in campaigns if c.get("status") == "active"]
        if active:
            parts.append(f"Active campaigns: {len(active)}")
            for c in active[:3]:
                parts.append(f"  - {c.get('name')} ({c.get('niche')})")

        # Recent leads
        leads = context_data.get("leads_count", 0)
        if leads:
            parts.append(f"Total leads captured: {leads}")

        if parts:
            return "Current app state:\n" + "\n".join(parts)
        return ""

    def _fallback_response(self, user_message: str, context_data: Dict = None) -> str:
        """Fallback when no API key is set — gives setup instructions."""
        return """🤖 **AI Assistant Setup Required**

To enable the real AI assistant, you need a **free Groq API key**:

1. Go to [console.groq.com/keys](https://console.groq.com/keys)
2. Sign up (free, no credit card)
3. Click "Create API Key"
4. Copy the key and paste it in **Settings → AI Configuration**

**What you get (free forever):**
- Llama 3.3 70B — 1,000 requests/day, 30/minute
- Real conversational AI that remembers context
- Campaign creation for ANY niche
- Platform setup troubleshooting
- Error code explanations

**Without the API key**, I can only show you basic info. With it, I become a real AI assistant that understands follow-ups, context, and gives nuanced advice.

Want to set it up now? Go to the **Settings** tab → **AI Configuration**."""

    def clear_history(self):
        """Clear conversation memory."""
        self.conversation_history = []

# ── Keep the old intent engine as a lightweight helper for UI actions ──────────
class AIIntentEngine:
    """Lightweight intent detection for UI routing (buttons, navigation)."""

    PLATFORM_ALIASES = {
        "telegram": ["telegram", "tg", "tele"],
        "reddit": ["reddit", "red", "subreddit"],
        "discord": ["discord", "dc"],
        "twitter": ["twitter", "x", "tweet"],
        "facebook": ["facebook", "fb", "meta"],
        "instagram": ["instagram", "ig", "insta"],
        "tiktok": ["tiktok", "tt"],
    }

    def extract_platform(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for platform, aliases in self.PLATFORM_ALIASES.items():
            for alias in aliases:
                if alias in text_lower:
                    return platform
        return None

    def extract_niche(self, text: str) -> Optional[str]:
        # Simple niche extraction for UI routing
        text_lower = text.lower()
        known = ["immigration", "plumbing", "cybersecurity", "marketing", "accounting", 
                 "lawyer", "dentist", "realtor", "coach", "seo", "web design", "tax"]
        for niche in known:
            if niche in text_lower:
                return niche
        return None

    def detect_action(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        if any(w in text_lower for w in ["setup", "set up", "configure", "connect"]):
            return "setup"
        if any(w in text_lower for w in ["create", "make", "start", "launch"]):
            return "create"
        if any(w in text_lower for w in ["status", "show", "check", "how many"]):
            return "status"
        return None

# ── Platform Connection Testing ─────────────────────────────────────────────
class PlatformTester:
    """Test platform connections with detailed diagnostics."""

    @staticmethod
    def test_telegram(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}

        # Step 1: Check required fields
        required = ["api_id", "api_hash", "phone"]
        for field in required:
            if not cfg.get(field):
                results["errors"].append(f"Missing required field: {field}")
                results["steps"].append(("❌", f"API ID/Hash/Phone check — {field} missing"))
                return results

        results["steps"].append(("✅", "Required fields present"))

        # Step 2: Validate API ID is numeric
        try:
            int(cfg["api_id"])
            results["steps"].append(("✅", "API ID is valid (numeric)"))
        except ValueError:
            results["errors"].append("API ID must be a number")
            results["steps"].append(("❌", "API ID validation — not numeric"))
            return results

        # Step 3: Check API Hash length
        if len(cfg.get("api_hash", "")) < 20:
            results["errors"].append("API Hash looks too short (should be 32 chars)")
            results["steps"].append(("⚠️", "API Hash length check — suspiciously short"))
        else:
            results["steps"].append(("✅", "API Hash length looks good"))

        # Step 4: Validate phone format
        phone = cfg.get("phone", "")
        if not phone.startswith("+"):
            results["errors"].append("Phone number must include country code (e.g., +1234567890)")
            results["steps"].append(("❌", "Phone format — missing + prefix"))
        else:
            results["steps"].append(("✅", "Phone format includes country code"))

        # Step 5: Try import (lightweight check)
        try:
            import telethon
            results["steps"].append(("✅", "Telethon library installed"))
        except ImportError:
            results["errors"].append("Telethon not installed. Run: pip install telethon")
            results["steps"].append(("❌", "Telethon library — not installed"))
            return results

        # Step 6: Attempt connection (without full auth)
        try:
            from telethon import TelegramClient
            client = TelegramClient(
                cfg.get("session_name", "test_session"),
                int(cfg["api_id"]),
                cfg["api_hash"]
            )
            # We can't fully connect without auth, but we can validate the API creds
            results["steps"].append(("✅", "API credentials format valid — ready for authentication"))
            results["success"] = True
            results["next_step"] = "Run the Telegram runner. You'll receive an SMS code on first connection."
        except Exception as e:
            results["errors"].append(f"Connection test failed: {str(e)}")
            results["steps"].append(("❌", f"Connection attempt — {str(e)}"))

        return results

    @staticmethod
    def test_reddit(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}

        required = ["client_id", "client_secret", "username", "password"]
        for field in required:
            if not cfg.get(field):
                results["errors"].append(f"Missing required field: {field}")
                results["steps"].append(("❌", f"{field} — missing"))
                return results

        results["steps"].append(("✅", "All required fields present"))

        try:
            import praw
            results["steps"].append(("✅", "PRAW library installed"))
        except ImportError:
            results["errors"].append("PRAW not installed. Run: pip install praw")
            results["steps"].append(("❌", "PRAW library — not installed"))
            return results

        try:
            reddit = praw.Reddit(
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                username=cfg["username"],
                password=cfg["password"],
                user_agent=cfg.get("user_agent", "LeadGenPro/1.0")
            )
            me = reddit.user.me()
            results["steps"].append(("✅", f"Connected as u/{me.name}"))
            results["steps"].append(("✅", f"Karma: {me.link_karma} link / {me.comment_karma} comment"))
            results["success"] = True
            results["next_step"] = "Reddit is ready! Create a campaign targeting subreddits."
        except Exception as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthorized" in err_str:
                results["errors"].append("Invalid credentials — check Client ID, Secret, Username, and Password")
                results["steps"].append(("❌", "Authentication failed — 401 Unauthorized"))
            elif "403" in err_str:
                results["errors"].append("Account may be suspended or API access restricted")
                results["steps"].append(("❌", "Authentication failed — 403 Forbidden"))
            else:
                results["errors"].append(f"Connection error: {str(e)}")
                results["steps"].append(("❌", f"Connection failed — {str(e)[:100]}"))

        return results

    @staticmethod
    def test_discord(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}

        if not cfg.get("token"):
            results["errors"].append("Missing Bot Token")
            results["steps"].append(("❌", "Bot Token — missing"))
            return results

        results["steps"].append(("✅", "Bot Token present"))

        # Check token format (Discord tokens are ~70 chars with dots)
        token = cfg["token"]
        if len(token) < 50 or "." not in token:
            results["errors"].append("Token format looks invalid (should be ~70 chars with dots)")
            results["steps"].append(("⚠️", "Token format — suspicious (may be wrong token type)"))
        else:
            results["steps"].append(("✅", "Token format looks valid"))

        try:
            import discord
            results["steps"].append(("✅", "Discord.py library installed"))
        except ImportError:
            results["errors"].append("discord.py not installed. Run: pip install discord.py")
            results["steps"].append(("❌", "Discord.py library — not installed"))
            return results

        try:
            import asyncio

            async def test_bot():
                intents = discord.Intents.default()
                intents.message_content = True
                client = discord.Client(intents=intents)

                @client.event
                async def on_ready():
                    results["steps"].append(("✅", f"Connected as {client.user.name}#{client.user.discriminator}"))
                    results["steps"].append(("✅", f"Bot ID: {client.user.id}"))
                    results["steps"].append(("✅", f"Guilds connected: {len(client.guilds)}"))
                    results["success"] = True
                    results["next_step"] = "Discord bot is live! Invite it to servers and create campaigns."
                    await client.close()

                try:
                    await client.start(token)
                except discord.LoginFailure:
                    results["errors"].append("Invalid Bot Token — check you copied the token from the Bot tab, NOT the Application ID")
                    results["steps"].append(("❌", "Authentication failed — Invalid token"))
                    results["steps"].append(("💡", "Make sure you got the token from: Developer Portal → Your App → Bot tab → Reset Token"))
                except Exception as e:
                    results["errors"].append(f"Connection error: {str(e)}")
                    results["steps"].append(("❌", f"Connection failed — {str(e)[:100]}"))

            # Run async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.wait_for(test_bot(), timeout=10))
            loop.close()

        except asyncio.TimeoutError:
            results["errors"].append("Connection timed out — Discord may be rate limiting")
            results["steps"].append(("⚠️", "Connection timeout — try again in 30 seconds"))
        except Exception as e:
            results["errors"].append(f"Test error: {str(e)}")
            results["steps"].append(("❌", f"Test failed — {str(e)[:100]}"))

        return results

    @staticmethod
    def test_twitter(cfg: dict) -> Dict:
        results = {"success": False, "steps": [], "errors": []}

        required = ["bearer_token", "api_key", "api_secret", "access_token", "access_secret"]
        for field in required:
            if not cfg.get(field):
                results["errors"].append(f"Missing required field: {field}")
                results["steps"].append(("❌", f"{field} — missing"))
                return results

        results["steps"].append(("✅", "All 5 tokens present"))

        try:
            import tweepy
            results["steps"].append(("✅", "Tweepy library installed"))
        except ImportError:
            results["errors"].append("Tweepy not installed. Run: pip install tweepy")
            results["steps"].append(("❌", "Tweepy library — not installed"))
            return results

        try:
            client = tweepy.Client(
                bearer_token=cfg["bearer_token"],
                consumer_key=cfg["api_key"],
                consumer_secret=cfg["api_secret"],
                access_token=cfg["access_token"],
                access_token_secret=cfg["access_secret"]
            )
            me = client.get_me()
            if me.data:
                results["steps"].append(("✅", f"Connected as @{me.data.username}"))
                results["steps"].append(("✅", f"User ID: {me.data.id}"))
                results["success"] = True
                results["next_step"] = "Twitter is ready! Note: Free tier = 100 reads/24hrs. Consider Basic tier for production."
            else:
                results["errors"].append("Could not verify user — token may be invalid")
                results["steps"].append(("❌", "User verification failed"))
        except tweepy.TweepyException as e:
            err_str = str(e).lower()
            if "401" in err_str:
                results["errors"].append("Invalid credentials — regenerate all tokens")
                results["steps"].append(("❌", "Authentication failed — 401 Unauthorized"))
            elif "403" in err_str:
                results["errors"].append("API access restricted — may need elevated tier")
                results["steps"].append(("❌", "Authentication failed — 403 Forbidden (check API tier)"))
            else:
                results["errors"].append(f"Twitter API error: {str(e)}")
                results["steps"].append(("❌", f"API error — {str(e)[:100]}"))
        except Exception as e:
            results["errors"].append(f"Connection error: {str(e)}")
            results["steps"].append(("❌", f"Connection failed — {str(e)[:100]}"))

        return results

    @staticmethod
    def test_platform(platform: str, cfg: dict) -> Dict:
        """Route to correct tester."""
        testers = {
            "telegram": PlatformTester.test_telegram,
            "reddit": PlatformTester.test_reddit,
            "discord": PlatformTester.test_discord,
            "twitter": PlatformTester.test_twitter,
        }
        tester = testers.get(platform)
        if tester:
            return tester(cfg)
        return {
            "success": False,
            "steps": [("⚠️", f"{PLATFORMS[platform]['name']} testing not available — manual verification required")],
            "errors": ["This platform requires manual verification. Check the setup guide."],
            "next_step": "Follow the setup guide and test by running the platform runner."
        }

# ── Dashboard UI Components ───────────────────────────────────────────────────
def render_header():
    st.markdown("""
    <div style="text-align: center; padding: 20px 0 30px 0;">
        <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px;">
            🚀 LeadGen Pro
        </h1>
        <p style="color: #9ca3af; font-size: 1.1rem; font-weight: 400;">
            AI-Powered Lead Generation Across All Platforms
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(title: str, value: str, subtitle: str, icon: str, color: str):
    st.markdown(f"""
    <div class="metric-card" style="border-left: 3px solid {color};">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <span style="font-size: 1.8rem;">{icon}</span>
            <span style="color: {color}; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">{title}</span>
        </div>
        <div style="font-size: 2rem; font-weight: 700; color: white; margin-bottom: 4px;">{value}</div>
        <div style="font-size: 0.85rem; color: #9ca3af;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def render_platform_status_card(pid: str, p: dict):
    cfg = get_platform_config(pid)
    is_configured = is_platform_configured(pid)
    has_partial = bool(cfg) and not is_configured

    if is_configured:
        status_color = "#22c55e"
        status_text = "Connected"
        status_dot = "status-online"
    elif has_partial:
        status_color = "#f59e0b"
        status_text = "Setup Needed"
        status_dot = "status-warning"
    else:
        status_color = "#ef4444"
        status_text = "Not Configured"
        status_dot = "status-offline"

    # Check runner status
    runner_running = os.path.exists(f"{pid}_runner.pid")
    runner_text = "🟢 Running" if runner_running else "⚪ Stopped"

    st.markdown(f"""
    <div class="platform-card" style="border-left: 3px solid {p['color']};">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.5rem;">{p['icon']}</span>
                <div>
                    <div style="font-weight: 600; color: white; font-size: 1rem;">{p['name']}</div>
                    <div style="font-size: 0.8rem; color: #9ca3af;">{runner_text}</div>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span class="status-indicator {status_dot}"></span>
                    <span style="color: {status_color}; font-weight: 600; font-size: 0.85rem;">{status_text}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_test_results(results: Dict):
    if results.get("success"):
        st.markdown('<div class="test-result-success">', unsafe_allow_html=True)
        st.markdown("### ✅ Connection Successful")
    elif results.get("errors"):
        st.markdown('<div class="test-result-fail">', unsafe_allow_html=True)
        st.markdown("### ❌ Connection Failed")
    else:
        st.markdown('<div class="test-result-pending">', unsafe_allow_html=True)
        st.markdown("### ⚠️ Partial Results")

    for icon, step in results.get("steps", []):
        st.markdown(f"{icon} {step}")

    if results.get("errors"):
        st.markdown("**Errors:**")
        for err in results["errors"]:
            st.markdown(f"- {err}")

    if results.get("next_step"):
        st.markdown(f"\n**Next Step:** {results['next_step']}")

    st.markdown('</div>', unsafe_allow_html=True)

# ── Main Application ──────────────────────────────────────────────────────────
def main():
    render_header()

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 10px 0 20px 0;">
            <div style="font-size: 2rem; margin-bottom: 4px;">🚀</div>
            <div style="font-weight: 700; color: white; font-size: 1.1rem;">LeadGen Pro</div>
            <div style="font-size: 0.75rem; color: #6b7280;">v1.0</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 10px 0;'>", unsafe_allow_html=True)

        page = st.radio(
            "Navigation",
            ["📊 Dashboard", "🤖 AI Assistant", "📢 Campaigns", "👥 Leads", "⚙️ Account Setup", "📁 Bulk Import", "🔧 Settings"],
            label_visibility="collapsed"
        )

        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 10px 0;'>", unsafe_allow_html=True)

        # Quick platform status in sidebar
        st.markdown("<div style='font-size: 0.8rem; color: #9ca3af; margin-bottom: 10px;'>Platform Status</div>", unsafe_allow_html=True)
        for pid, p in PLATFORMS.items():
            if is_platform_configured(pid):
                st.markdown(f"<div style='font-size: 0.75rem;'>🟢 {p['icon']} {p['name']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='font-size: 0.75rem; color: #6b7280;'>🔴 {p['icon']} {p['name']}</div>", unsafe_allow_html=True)

    # ── DASHBOARD ───────────────────────────────────────────────────────────
    if page == "📊 Dashboard":
        st.markdown("<h2 style='color: white; margin-bottom: 24px;'>Dashboard Overview</h2>", unsafe_allow_html=True)

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM campaigns WHERE status='active'")
                active_campaigns = c.fetchone()[0]
                conn.close()
            except:
                active_campaigns = 0
            render_metric_card("Active Campaigns", str(active_campaigns), "Running now", "📢", "#6366f1")

        with col2:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM leads")
                total_leads = c.fetchone()[0]
                conn.close()
            except:
                total_leads = 0
            render_metric_card("Total Leads", str(total_leads), "Captured all time", "👥", "#22c55e")

        with col3:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM messages")
                messages_sent = c.fetchone()[0]
                conn.close()
            except:
                messages_sent = 0
            render_metric_card("Messages Sent", str(messages_sent), "Outreach messages", "💬", "#f59e0b")

        with col4:
            configured = sum(1 for pid in PLATFORMS if is_platform_configured(pid))
            render_metric_card("Platforms Ready", f"{configured}/7", "Connected accounts", "🔗", "#ec4899")

        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

        # Platform health grid
        st.markdown("<h3 style='color: white; margin-bottom: 16px;'>Platform Health</h3>", unsafe_allow_html=True)

        cols = st.columns(3)
        for i, (pid, p) in enumerate(PLATFORMS.items()):
            with cols[i % 3]:
                render_platform_status_card(pid, p)

        # Recent activity
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        st.markdown("<h3 style='color: white; margin-bottom: 16px;'>Recent Activity</h3>", unsafe_allow_html=True)

        try:
            conn = get_db()
            df = pd.read_sql_query("""
                SELECT 'Campaign' as type, name as item, status, created_at as time
                FROM campaigns ORDER BY created_at DESC LIMIT 5
            """, conn)
            conn.close()

            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No activity yet. Create your first campaign in the AI Assistant or Campaigns tab.")
        except:
            st.info("No activity yet. Create your first campaign in the AI Assistant or Campaigns tab.")

    # ── AI ASSISTANT ────────────────────────────────────────────────────────
    elif page == "🤖 AI Assistant":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>AI Assistant</h2>", unsafe_allow_html=True)

        # Check if API key is configured
        ai_engine = AIChatEngine()
        if not ai_engine.is_configured():
            st.warning("⚠️ **AI not configured.** Get a free Groq API key to enable real conversational AI.")
            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("🔑 Get Free API Key", use_container_width=True):
                    st.markdown("[Open console.groq.com/keys](https://console.groq.com/keys)")
            with col2:
                api_key_input = st.text_input("Paste your Groq API Key", type="password", key="groq_key_input")
                if api_key_input and st.button("💾 Save Key", use_container_width=True):
                    cfg = load_config()
                    cfg["settings"] = cfg.get("settings", {})
                    cfg["settings"]["groq_api_key"] = api_key_input
                    save_config(cfg)
                    # Update running engine immediately
                    if "ai_engine" in st.session_state:
                        st.session_state.ai_engine = AIChatEngine(api_key=api_key_input)
                    st.success("API key saved and activated!")
                    st.rerun()
            st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 16px 0;'>", unsafe_allow_html=True)

        st.markdown("<p style='color: #9ca3af; margin-bottom: 16px;'>Ask me anything — I'm powered by Llama 3.3 70B via Groq. I understand context, follow-ups, and can help with setup, campaigns, troubleshooting, and more.</p>", unsafe_allow_html=True)

        # Initialize chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        if "ai_engine" not in st.session_state:
            st.session_state.ai_engine = AIChatEngine()  # auto-loads from config

        ai = st.session_state.ai_engine

        # Display chat
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-message-user">{msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-message-ai">{msg["content"]}</div>', unsafe_allow_html=True)

        # Input area
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Quick suggestion chips
        suggestions = [
            "How do I setup Telegram?",
            "How do I get my Reddit API?",
            "Create a plumbing campaign",
            "What does a 401 error mean?",
            "Suggest niches for me",
            "How does bulk import work?"
        ]

        sug_cols = st.columns(3)
        for i, sug in enumerate(suggestions):
            with sug_cols[i % 3]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.chat_input_value = sug
                    st.rerun()

        # Text input
        user_input = st.text_input(
            "Your message",
            value=st.session_state.get("chat_input_value", ""),
            key="chat_input",
            placeholder="Ask me anything... (e.g., 'How do I setup Telegram?', 'Create immigration campaign', 'What does 429 error mean?')",
            label_visibility="collapsed"
        )

        if st.session_state.get("chat_input_value"):
            st.session_state["chat_input_value"] = ""

        if user_input.strip():
            # Add user message to history
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Build context from current app state
            context = {}
            try:
                conn = get_db()
                c = conn.cursor()

                # Platform configs
                cfg = load_config()
                platforms_status = {}
                for pid in PLATFORMS:
                    platforms_status[pid] = {
                        "configured": is_platform_configured(pid),
                        "has_partial": bool(get_platform_config(pid)) and not is_platform_configured(pid)
                    }
                context["platforms"] = platforms_status

                # Campaigns
                c.execute("SELECT name, niche, status FROM campaigns ORDER BY created_at DESC")
                campaigns = [{"name": r[0], "niche": r[1], "status": r[2]} for r in c.fetchall()]
                context["campaigns"] = campaigns

                # Leads count
                c.execute("SELECT COUNT(*) FROM leads")
                context["leads_count"] = c.fetchone()[0]

                conn.close()
            except:
                pass

            # Get AI response
            with st.spinner("🤖 Thinking..."):
                ai_reply = ai.chat(user_input, context)

            # Add AI response to history
            st.session_state.chat_history.append({"role": "ai", "content": ai_reply})

            st.rerun()

        # Clear chat button
        if st.session_state.chat_history and st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            ai.clear_history()
            st.rerun()
    # ── CAMPAIGNS ───────────────────────────────────────────────────────────
    elif page == "📢 Campaigns":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>Campaigns</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #9ca3af; margin-bottom: 24px;'>Create and manage your lead generation campaigns.</p>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["➕ Create Campaign", "📋 Manage Campaigns"])

        with tab1:
            # Check for draft from AI
            draft = st.session_state.get("draft_campaign")

            col1, col2 = st.columns([2, 1])
            with col1:
                niche = st.text_input(
                    "Niche / Industry",
                    value=draft["niche"] if draft else "",
                    placeholder="e.g., plumbing, immigration, cybersecurity, marketing..."
                )
            with col2:
                if st.button("🤖 Auto-Generate", use_container_width=True):
                    if niche:
                        ai = AIIntentEngine()
                        campaign = ai.generate_dynamic_campaign(niche)
                        st.session_state["generated_campaign"] = campaign
                        st.success(f"Generated campaign for '{niche}'!")
                        st.rerun()

            # Show generated data
            gen = st.session_state.get("generated_campaign") or draft
            if gen:
                st.markdown("<div style='background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.3); border-radius: 12px; padding: 20px; margin: 16px 0;'>", unsafe_allow_html=True)
                st.markdown(f"**Generated for:** {gen['niche'].title()}")
                st.markdown(f"**Category:** {gen.get('category', 'custom')}")
                st.markdown(f"**Source:** {gen.get('source', 'manual')}")

                st.markdown("**Keywords:**")
                st.text_area("Keywords (one per line)", value="\n".join(gen["keywords"]), height=100, key="gen_keywords")

                st.markdown("**Indicators:**")
                st.text_area("Lead Indicators (one per line)", value="\n".join(gen["indicators"]), height=100, key="gen_indicators")

                st.markdown("**Pitches:**")
                for i, pitch in enumerate(gen["pitches"]):
                    st.text_area(f"Pitch {i+1}", value=pitch, key=f"gen_pitch_{i}")

                st.markdown("**Recommended Platforms:**")
                platforms_selected = st.multiselect(
                    "Select platforms",
                    options=list(PLATFORMS.keys()),
                    default=gen.get("platforms", []),
                    format_func=lambda x: f"{PLATFORMS[x]['icon']} {PLATFORMS[x]['name']}"
                )
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                # Manual input
                keywords = st.text_area("Keywords (one per line)", placeholder="plumber\nleak\nemergency plumbing", height=100)
                indicators = st.text_area("Lead Indicators (one per line)", placeholder="need plumber\npipe broken", height=100)
                pitches = st.text_area("Pitches (one per line, use {name} for username)", placeholder="Hi {name}, we offer 24/7 plumbing...", height=120)
                platforms_selected = st.multiselect(
                    "Platforms",
                    options=list(PLATFORMS.keys()),
                    format_func=lambda x: f"{PLATFORMS[x]['icon']} {PLATFORMS[x]['name']}"
                )

            campaign_name = st.text_input("Campaign Name", placeholder="e.g., Plumbing Emergency NYC")

            if st.button("💾 Save Campaign", use_container_width=True):
                if not campaign_name:
                    st.error("Campaign name is required")
                elif not niche:
                    st.error("Niche is required")
                else:
                    try:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("""INSERT INTO campaigns 
                            (name, niche, keywords, indicators, platforms, pitches, status)
                            VALUES (?, ?, ?, ?, ?, ?, 'paused')""", (
                            campaign_name,
                            niche,
                            "\n".join(gen["keywords"]) if gen else keywords,
                            "\n".join(gen["indicators"]) if gen else indicators,
                            json.dumps(platforms_selected),
                            "\n---\n".join(gen["pitches"]) if gen else pitches
                        ))
                        conn.commit()
                        conn.close()
                        st.success(f"Campaign '{campaign_name}' saved! Go to Manage Campaigns to activate it.")
                        st.session_state["generated_campaign"] = None
                        st.session_state["draft_campaign"] = None
                    except Exception as e:
                        st.error(f"Error saving campaign: {e}")

        with tab2:
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
                campaigns = c.fetchall()
                conn.close()

                if not campaigns:
                    st.info("No campaigns yet. Create one in the 'Create Campaign' tab.")
                else:
                    for camp in campaigns:
                        camp_id, name, niche, keywords, indicators, platforms, pitches, status, created_at, leads_count, messages_sent = camp

                        with st.expander(f"{'🟢' if status == 'active' else '🔴'} {name} — {niche}"):
                            col1, col2, col3 = st.columns([2, 1, 1])
                            with col1:
                                st.markdown(f"**Niche:** {niche}")
                                st.markdown(f"**Status:** {status.upper()}")
                                st.markdown(f"**Created:** {created_at}")
                                st.markdown(f"**Leads:** {leads_count} | **Messages:** {messages_sent}")
                            with col2:
                                if status == "paused":
                                    if st.button("▶️ Activate", key=f"act_{camp_id}"):
                                        conn = get_db()
                                        c = conn.cursor()
                                        c.execute("UPDATE campaigns SET status='active' WHERE id=?", (camp_id,))
                                        conn.commit()
                                        conn.close()
                                        st.success("Campaign activated!")
                                        st.rerun()
                                else:
                                    if st.button("⏸️ Pause", key=f"pause_{camp_id}"):
                                        conn = get_db()
                                        c = conn.cursor()
                                        c.execute("UPDATE campaigns SET status='paused' WHERE id=?", (camp_id,))
                                        conn.commit()
                                        conn.close()
                                        st.success("Campaign paused!")
                                        st.rerun()
                            with col3:
                                if st.button("🗑️ Delete", key=f"del_{camp_id}"):
                                    conn = get_db()
                                    c = conn.cursor()
                                    c.execute("DELETE FROM campaigns WHERE id=?", (camp_id,))
                                    conn.commit()
                                    conn.close()
                                    st.success("Campaign deleted!")
                                    st.rerun()

                            with st.popover("View Details"):
                                st.markdown("**Keywords:**")
                                st.code(keywords or "None")
                                st.markdown("**Indicators:**")
                                st.code(indicators or "None")
                                st.markdown("**Platforms:**")
                                st.code(platforms or "None")
                                st.markdown("**Pitches:**")
                                st.code(pitches or "None")
            except Exception as e:
                st.error(f"Error loading campaigns: {e}")

    # ── LEADS ───────────────────────────────────────────────────────────────
    elif page == "👥 Leads":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>Leads</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #9ca3af; margin-bottom: 24px;'>View and manage captured leads.</p>", unsafe_allow_html=True)

        try:
            conn = get_db()
            df = pd.read_sql_query("""
                SELECT l.id, c.name as campaign, l.platform, l.username, 
                       l.message, l.status, l.created_at, l.responded
                FROM leads l
                LEFT JOIN campaigns c ON l.campaign_id = c.id
                ORDER BY l.created_at DESC
            """, conn)
            conn.close()

            if df.empty:
                st.info("No leads captured yet. Run active campaigns to start generating leads.")
            else:
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    platform_filter = st.multiselect(
                        "Filter by Platform",
                        options=df["platform"].unique().tolist(),
                        default=[]
                    )
                with col2:
                    status_filter = st.multiselect(
                        "Filter by Status",
                        options=df["status"].unique().tolist(),
                        default=[]
                    )

                if platform_filter:
                    df = df[df["platform"].isin(platform_filter)]
                if status_filter:
                    df = df[df["status"].isin(status_filter)]

                st.dataframe(df, use_container_width=True, hide_index=True)

                # Export
                if st.button("📥 Export to CSV"):
                    csv = df.to_csv(index=False)
                    st.download_button("Download CSV", csv, "leads.csv", "text/csv")
        except Exception as e:
            st.error(f"Error loading leads: {e}")

    # ── ACCOUNT SETUP ───────────────────────────────────────────────────────
    elif page == "⚙️ Account Setup":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>Account Setup</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #9ca3af; margin-bottom: 24px;'>Configure your platform credentials with step-by-step guides and live connection testing.</p>", unsafe_allow_html=True)

        # Platform selector
        platform_tabs = st.tabs([f"{p['icon']} {p['name']}" for p in PLATFORMS.values()])

        for i, (pid, p) in enumerate(PLATFORMS.items()):
            with platform_tabs[i]:
                cfg = get_platform_config(pid)
                is_configured = is_platform_configured(pid)

                # Status banner
                if is_configured:
                    st.success(f"✅ {p['name']} is configured and ready")
                elif cfg:
                    st.warning(f"⚠️ {p['name']} is partially configured — complete the required fields below")
                else:
                    st.info(f"ℹ️ {p['name']} not configured yet — follow the guide below")

                col1, col2 = st.columns([1, 1])

                with col1:
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.03); border-radius: 12px; padding: 20px;">
                        <h4 style="color: white; margin-bottom: 12px;">📖 Setup Guide</h4>
                        <div style="color: #d1d5db; font-size: 0.9rem; line-height: 1.6;">
                        {p['guide']}
                        </div>
                        <div style="margin-top: 16px;">
                            <a href="{p['setup_url']}" target="_blank" style="color: #6366f1; text-decoration: none; font-weight: 600;">
                                🔗 Open {p['name']} Developer Portal →
                            </a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Difficulty badge
                    diff_color = {"Easy": "#22c55e", "Medium": "#f59e0b", "Hard": "#ef4444", "Very Hard": "#dc2626"}
                    st.markdown(f"""
                    <div style="margin-top: 12px;">
                        <span style="background: {diff_color.get(p['difficulty'], '#6b7280')}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600;">
                            {p['difficulty']}
                        </span>
                        <span style="color: #9ca3af; font-size: 0.8rem; margin-left: 8px;">
                            Est. time: {p['time_estimate']}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                with col2:
                    st.markdown(f"<h4 style='color: white; margin-bottom: 16px;'>🔑 Credentials</h4>", unsafe_allow_html=True)

                    form_data = {}
                    for field_key, field_info in p["fields"].items():
                        current_val = cfg.get(field_key, "")
                        if field_info["type"] == "password":
                            form_data[field_key] = st.text_input(
                                field_info["label"],
                                value=current_val,
                                type="password",
                                help=field_info["help"],
                                key=f"{pid}_{field_key}"
                            )
                        else:
                            form_data[field_key] = st.text_input(
                                field_info["label"],
                                value=current_val,
                                help=field_info["help"],
                                key=f"{pid}_{field_key}"
                            )

                    col_save, col_test, col_clear = st.columns(3)

                    with col_save:
                        if st.button("💾 Save", use_container_width=True, key=f"save_{pid}"):
                            set_platform_config(pid, form_data)
                            st.success("Credentials saved!")
                            st.rerun()

                    with col_test:
                        if st.button("🧪 Test", use_container_width=True, key=f"test_{pid}"):
                            if not is_platform_configured(pid):
                                st.error("Fill in all required fields first")
                            else:
                                with st.spinner(f"Testing {p['name']} connection..."):
                                    results = PlatformTester.test_platform(pid, form_data)
                                render_test_results(results)

                    with col_clear:
                        if st.button("🗑️ Clear", use_container_width=True, key=f"clear_{pid}"):
                            set_platform_config(pid, {})
                            st.success("Credentials cleared!")
                            st.rerun()

    # ── BULK IMPORT ─────────────────────────────────────────────────────────
    elif page == "📁 Bulk Import":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>Bulk Account Import</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #9ca3af; margin-bottom: 24px;'>Import multiple platform credentials at once via CSV or JSON.</p>", unsafe_allow_html=True)

        tab_csv, tab_json = st.tabs(["📄 CSV Import", "📝 JSON Import"])

        with tab_csv:
            st.markdown("""
            **CSV Format:**
            ```
            platform,field,value
            telegram,api_id,12345678
            telegram,api_hash,abc123def456
            telegram,phone,+1234567890
            reddit,client_id,xyz789
            reddit,client_secret,secret123
            reddit,username,myuser
            reddit,password,mypass
            ```
            """)

            uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

            if uploaded_file:
                try:
                    df = pd.read_csv(uploaded_file)
                    st.markdown("**Preview:**")
                    st.dataframe(df.head(20), use_container_width=True)

                    if st.button("📥 Import CSV", use_container_width=True):
                        imported = {}
                        for _, row in df.iterrows():
                            platform = str(row.get("platform", "")).strip().lower()
                            field = str(row.get("field", "")).strip()
                            value = str(row.get("value", "")).strip()

                            if platform and field and value:
                                if platform not in imported:
                                    imported[platform] = {}
                                imported[platform][field] = value

                        # Save to config
                        cfg = load_config()
                        for platform, data in imported.items():
                            if platform in PLATFORMS:
                                cfg.setdefault("platforms", {})[platform] = data

                        save_config(cfg)
                        st.success(f"Imported credentials for {len(imported)} platform(s)!")

                        # Show results
                        for platform, data in imported.items():
                            p = PLATFORMS.get(platform)
                            if p:
                                is_ok = is_platform_configured(platform)
                                status = "✅ Complete" if is_ok else "⚠️ Partial"
                                st.markdown(f"{p['icon']} **{p['name']}** — {status}")
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")

        with tab_json:
            st.markdown("""
            **JSON Format:**
            ```json
            {
              "telegram": {
                "api_id": "12345678",
                "api_hash": "abc123...",
                "phone": "+1234567890"
              },
              "reddit": {
                "client_id": "xyz...",
                "client_secret": "...",
                "username": "myuser",
                "password": "mypass"
              }
            }
            ```
            """)

            json_input = st.text_area("Paste JSON here", height=200, placeholder='{"telegram": {"api_id": "..."}}')

            if json_input:
                try:
                    data = json.loads(json_input)
                    st.markdown("**Preview:**")
                    st.json(data)

                    if st.button("📥 Import JSON", use_container_width=True):
                        cfg = load_config()
                        imported = 0
                        for platform, creds in data.items():
                            if platform in PLATFORMS and isinstance(creds, dict):
                                cfg.setdefault("platforms", {})[platform] = creds
                                imported += 1

                        save_config(cfg)
                        st.success(f"Imported credentials for {imported} platform(s)!")
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")

    # ── SETTINGS ────────────────────────────────────────────────────────────
    elif page == "🔧 Settings":
        st.markdown("<h2 style='color: white; margin-bottom: 8px;'>Settings</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #9ca3af; margin-bottom: 24px;'>Configure AI, export/import data, and manage your setup.</p>", unsafe_allow_html=True)

        # AI Configuration
        st.markdown("<h3 style='color: white; margin-bottom: 16px;'>🤖 AI Configuration</h3>", unsafe_allow_html=True)

        cfg = load_config()
        current_key = cfg.get("settings", {}).get("groq_api_key", "")

        col1, col2 = st.columns([3, 1])
        with col1:
            new_key = st.text_input(
                "Groq API Key",
                value=current_key,
                type="password",
                help="Get free key at console.groq.com/keys — no credit card required",
                placeholder="gsk_..."
            )
        with col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Save Key", use_container_width=True):
                cfg["settings"] = cfg.get("settings", {})
                cfg["settings"]["groq_api_key"] = new_key
                save_config(cfg)
                # Update the running AI engine immediately
                if "ai_engine" in st.session_state:
                    st.session_state.ai_engine = AIChatEngine(api_key=new_key)
                st.success("API key saved and activated!")
                st.rerun()

        # Show AI status
        ai_check = AIChatEngine(api_key=new_key)
        if ai_check.is_configured():
            st.success("✅ AI is configured and ready")
            st.markdown(f"**Model:** {GROQ_MODEL}  |  **Provider:** Groq (free tier)")
            st.markdown("**Limits:** 30 requests/min, ~1,000/day")
        else:
            st.error("❌ AI not configured — add your Groq API key above")

        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 24px 0;'>", unsafe_allow_html=True)

        # Data Management
        st.markdown("<h3 style='color: white; margin-bottom: 16px;'>💾 Data Management</h3>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<h4 style='color: white;'>📤 Export Config</h4>", unsafe_allow_html=True)
            cfg = load_config()
            cfg_json = json.dumps(cfg, indent=2)
            st.download_button(
                "Download config.json",
                cfg_json,
                "leadgen_config_backup.json",
                "application/json",
                use_container_width=True
            )

        with col2:
            st.markdown("<h4 style='color: white;'>📥 Import Config</h4>", unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload config JSON", type=["json"], label_visibility="collapsed")
            if uploaded:
                try:
                    new_cfg = json.load(uploaded)
                    save_config(new_cfg)
                    st.success("Config imported successfully!")
                except Exception as e:
                    st.error(f"Error importing config: {e}")

        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

        # Danger zone
        st.markdown("<h4 style='color: #ef4444;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)

        if st.button("🗑️ Reset All Data", use_container_width=True):
            confirm = st.checkbox("I understand this will delete all campaigns, leads, and config")
            if confirm:
                if os.path.exists(CONFIG_PATH):
                    os.remove(CONFIG_PATH)
                if os.path.exists(DB_PATH):
                    os.remove(DB_PATH)
                init_db()
                st.success("All data reset. The app will restart.")
                st.rerun()
if __name__ == "__main__":
    main()
