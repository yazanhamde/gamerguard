<div align="center">

<img src="https://img.shields.io/badge/GamerGuard-Discord%20Bot-5766ee?style=for-the-badge&logo=discord&logoColor=white" alt="GamerGuard"/>

# 🛡️ GamerGuard

**AI-powered moderation & community bot built for Arabic-speaking gaming communities.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[Features](#-features) • [Screenshots](#-dashboard) • [Quick Start](#-quick-start) • [Commands](#-slash-commands) • [Configuration](#-configuration) • [Deploy](#-deployment)

</div>

---

## ✨ Features

### 🤖 AI Moderation
- **3-tier analysis pipeline** — OpenAI Moderation API (free) → seed word filter → GPT-4o-mini context judge
- Understands **Arabic dialects**: Levantine, Gulf, Egyptian, and Arabizi
- Distinguishes **friendly banter** from genuine abuse — no over-banning
- First offense → private DM warning. Repeat offense → moderator alert
- **No automatic bans** — humans always make the final call
- Per-guild thresholds (`MOD_LOW` / `MOD_HIGH`) and custom seed words via dashboard

### 🌐 Auto-Translation
- Detects non-Arabic / non-English messages and translates them to **both Arabic and English** in-line
- **Voice message transcription** powered by Whisper AI — converts audio to text and translates
- Per-user language preference with `/setlang`
- Toggle text and voice translation independently per server

### 🎮 LFG (Looking for Group)
- Interactive **multi-step wizard** — game, player count, age group, reputation filter, rank range
- Supports **16+ games** across FPS, MOBA, Battle Royale, Sports, and Co-op categories with full rank systems
- Auto-creates a **temporary voice channel** when a team is complete and moves online members
- Voice channel auto-deletes after 2 hours if empty
- Edit or cancel your LFG post anytime via buttons

### ⭐ Reputation System
- Score **0–100** based on peer ratings, confirmed flags, and reports (30-day window)
- `/rate` — rate a player 1–5 stars after a session (once per day per player)
- `/profile` — view any player's reputation at a glance
- LFG posts can require a minimum reputation to join

### 🖥️ Web Dashboard
- Full **admin panel** built with FastAPI — dark/light mode, RTL Arabic UI
- **Role system**: Admin (full access) and Moderator (flags, reports, player notes)
- Flag management with false-positive marking
- Report queue with open/resolved tracking
- Per-player timeline: flags, reports, ratings, and mod notes in one view
- **Audit log** — every dashboard action recorded with actor and timestamp
- Forced password change on first login, session invalidation on user disable
- Rate-limited login with brute-force protection (5 attempts / 10 min per IP)
- Security headers: CSP, X-Frame-Options, no-store cache

---

## 📸 Dashboard

| Flags | Player Profile | Settings |
|---|---|---|
| *Flag feed with false-positive controls* | *Full player timeline & mod notes* | *Per-guild thresholds & seed words* |

---

## 🚀 Quick Start

### Prerequisites
- Python **3.10+**
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- An OpenAI API key ([platform.openai.com](https://platform.openai.com))

### 1. Clone & install
```bash
git clone https://github.com/yazanhamdi/gamerguard.git
cd gamerguard
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key

# Dashboard
DASH_PASSWORD=YourStrongPassword123
SECRET_KEY=a-random-secret-key-at-least-32-chars

# Optional
OPENAI_MODEL=gpt-4o-mini
MOD_LOW=0.30
MOD_HIGH=0.85
RETENTION_DAYS=30
PORT=8000
HTTPS_ONLY=0
DB_PATH=data.db
DB_POOL_SIZE=5
```

### 3. Discord bot setup
In the [Developer Portal](https://discord.com/developers/applications):
1. Create a new application → **Bot** tab
2. Enable **Message Content Intent** and **Server Members Intent**
3. Invite the bot with scopes: `bot` + `applications.commands`
   - Required permissions: `Send Messages`, `Embed Links`, `Manage Channels`, `Move Members`, `Read Message History`

### 4. Run
```bash
python bot.py
```

On first run:
- Slash commands sync automatically
- Dashboard admin account is created at `http://localhost:8000`
- Run `/setup #your-mod-channel` in your server

---

## 💬 Slash Commands

| Command | Description | Permission |
|---|---|---|
| `/lfg [players]` | Open an LFG wizard to find teammates | Everyone |
| `/report [user] [reason]` | Report a player to moderators | Everyone |
| `/rate [user] [1-5]` | Rate a player after a session | Everyone |
| `/profile [user]` | View a player's reputation score | Everyone |
| `/translate [text]` | Manually translate any text | Everyone |
| `/setlang [code]` | Set your preferred translation language | Everyone |
| `/lfg_list [game]` | Browse open LFG posts (last 24h) | Everyone |
| `/setup [channel]` | Set the mod-alert channel | Manage Server |
| `/stats` | View 7-day moderation stats | Manage Messages |
| `/privacy` | View what data the bot collects | Everyone |

---

## ⚙️ Configuration

### Moderation Thresholds

| Variable | Default | Description |
|---|---|---|
| `MOD_LOW` | `0.30` | Below this score + no seed word → message ignored |
| `MOD_HIGH` | `0.85` | Above this score → abuse flagged without GPT |
| Between LOW and HIGH | — | GPT judges context (banter vs. abuse) |

Tune these per-guild from the dashboard **Settings** tab without restarting.

### Custom Seed Words
Add community-specific words (one per line) in the dashboard. The bot ships with a default Arabic/Arabizi seed list — your additions layer on top.

### Games
Enable or disable games per-server from the dashboard **Games** tab. Supported games:

**FPS / Battle Royale:** Valorant · CS2 · Apex Legends · Warzone · Fortnite  
**MOBA / RPG:** League of Legends · Dota 2 · Genshin Impact · Roblox  
**Sports / Racing:** EA FC 25 · Rocket League  
**Co-op / Survival:** Minecraft · Rust · Lethal Company · Palworld · Among Us

---

## 🏗️ Architecture

```
bot.py          — Discord client, event handlers, slash commands
moderation.py   — 3-tier AI moderation pipeline (cached seed patterns)
translation.py  — Text & voice translation via GPT-4o-mini + Whisper
db.py           — Async SQLite with connection pool (WAL mode) + guild config cache
dashboard.py    — FastAPI web dashboard (auth, flags, reports, settings)
auth.py         — PBKDF2-SHA256 password hashing, session management, audit log
games.py        — Game catalog with rank systems
```

**Tech stack:** `discord.py` · `FastAPI` · `aiosqlite` · `OpenAI Python SDK` · `uvicorn`

### Moderation Pipeline
```
Message received
     │
     ▼
OpenAI Moderation API  ──── score < MOD_LOW + no seed word ──▶  ignore
     │
     ├── score ≥ MOD_HIGH ──────────────────────────────────▶  flag as abuse
     │
     └── score between thresholds or seed word matched
               │
               ▼
         GPT-4o-mini (with last 5 messages for context)
               │
         ┌─────┴─────┐
       banter        abuse
         │              │
       ignore       1st offense → DM warning
                    repeat    → mod channel alert
```

---

## 🚢 Deployment

### Railway (Recommended)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

1. Push your repo to GitHub
2. Connect to Railway → **New Project from GitHub**
3. Add environment variables from `.env`
4. Railway auto-detects Python and runs `bot.py`

### VPS (Ubuntu)
```bash
# Install dependencies
pip install -r requirements.txt

# Run with process manager
pip install supervisor
# or
nohup python bot.py &

# Reverse proxy dashboard (nginx)
# proxy_pass http://127.0.0.1:8000;
# Then set HTTPS_ONLY=1 in .env
```

### Environment Notes
- Set `HTTPS_ONLY=1` before exposing the dashboard publicly
- Set a spending limit in your [OpenAI dashboard](https://platform.openai.com/account/limits) to control costs
- The bot requires 24/7 uptime — shared hosting (cPanel) is not recommended

---

## 💰 Estimated OpenAI Costs

| Usage | Cost |
|---|---|
| Text moderation (100 users × 50 msg/day) | ~$0.20/month |
| Translation per message | ~$0.0004 |
| Voice transcription (Whisper) | ~$0.006/minute |
| Typical active server (100 users) | **~$3–5/month** |

---

## 📁 Project Structure

```
gamerguard/
├── bot.py              # Main bot entry point
├── moderation.py       # AI moderation pipeline
├── translation.py      # Auto-translation & Whisper
├── dashboard.py        # FastAPI web dashboard
├── db.py               # Database layer (pool + cache)
├── auth.py             # Authentication & audit
├── games.py            # Game catalog
├── db_migration.py     # Schema migrations
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

1. Fork the repo
2. Create your branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by [Yazan Hamdi](https://github.com/yazanhamde) · Star ⭐ if you find it useful

</div>
