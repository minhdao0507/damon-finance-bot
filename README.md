# Personal Finance Tracker Bots

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20-blue)
![Google Sheets](https://img.shields.io/badge/Database-Google%20Sheets-34A853?logo=google-sheets&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-4285F4?logo=google&logoColor=white)
![GCP](https://img.shields.io/badge/Deploy-GCP%20e2--micro-orange?logo=google-cloud&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

Two Telegram bots for personal expense tracking — **Damon bot** (VND, single user) and **Quinn bot** (VND + USD, two users). Users log transactions in natural language, the bot categorizes them automatically, persists records to Google Sheets, and offers Gemini-powered monthly analysis with interactive follow-up Q&A.

---

## Features

- **Natural language transaction input** — `300k cafe`, `1.5tr grab`, `500 usd rent`; no rigid format required
- **Multi-line batch logging** — submit several transactions in one message
- **Smart auto-categorization** — keyword mapping that learns from user corrections over time
- **Google Sheets as database** — one tab per month, auto-created; human-readable and exportable
- **Gemini 1.5 Flash analysis** — AI-generated spending pattern analysis with multi-turn conversational follow-up
- **Income source management** — track and label income sources alongside expenses
- **Multi-currency support** (Quinn bot) — seamlessly handles both VND and USD entries
- **Persistent learning** — `learned_keywords.json` retains user-taught category corrections across restarts
- **Secure by default** — `ALLOWED_IDS` whitelist; secrets in environment variables only

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/add` | Log one or more transactions (multi-line supported) |
| `/summary` | Spending summary for the current month, grouped by category |
| `/analyze` | Gemini AI analysis of spending patterns; enters conversation mode for follow-up Q&A |
| `/src` | Manage income sources (add / edit / delete) |
| `/help` | Full command reference |

---

## Transaction Format

```
<amount><unit> <description>
```

| Input | Parsed As |
|-------|-----------|
| `300k cafe` | 300,000 VND — Food & Drink |
| `1.5tr grab` | 1,500,000 VND — Transport |
| `500 usd rent` | 500 USD — Housing *(Quinn bot only)* |
| `200k lunch\n50k coffee` | Two transactions in one message |

**VND shortcuts:** `k` = ×1,000 &nbsp;|&nbsp; `tr` / `m` = ×1,000,000

---

## Architecture

### Conversation State Machine

```
User sends message
        |
        v
+-------+--------+
|   Dispatcher   |
| (PTB v20 async)|
+-------+--------+
        |
        +---> /analyze --> [ analyze_conv ]
        |                        |
        |         +--------------+--------------+
        |         |              |              |
        |    ANALYZE_WAIT   FOLLOWUP_Q&A   END/CANCEL
        |    (Gemini call)  (multi-turn)
        |
        +---> /add, /summary, /src --> [ main conv ]
                         |
        +----------------+-----------------+
        |        |        |        |        |
     ADD_Q  CONFIRM_Q  SRC_MENU  SRC_ADD  SRC_EDIT
        |        |
     (parse) (save to
     (categ)  Sheets)
        |
   CORRECT_CAT? --> update learned_keywords.json
```

`analyze_conv` is registered **before** `main conv` in the dispatcher to ensure `/analyze` is intercepted correctly even when another conversation is active.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Bot framework | python-telegram-bot v20 (async, `Application` builder) |
| Database | Google Sheets via `gspread` (service account auth) |
| AI analysis | Google Gemini 1.5 Flash (`google-generativeai`) |
| Hosting | GCP e2-micro VM, Ubuntu, `systemd` (one service per bot) |
| Language | Python 3.10+ |
| Persistence | `user_sources.json`, `learned_keywords.json` (local flat files) |

---

## Tech Highlights

- **Async-first design** — built on PTB v20's native `asyncio` support; no threading workarounds
- **ConversationHandler state machine** — 7–8 states per flow, cleanly separated `entry_points`, `states`, and `fallbacks`
- **Handler registration order** — `analyze_conv` registered ahead of `main conv` to prevent state collision on `/analyze`
- **Gemini multi-turn Q&A** — full conversation history stored in `context.user_data`; each follow-up sends the accumulated history to the model for coherent dialogue
- **Self-learning categorization** — when a user corrects a category, the keyword is written to `learned_keywords.json` and reloaded on the fly; no restart needed
- **Zero-schema database** — Google Sheets tabs are auto-created per month (`YYYY-MM` naming); no migration scripts ever needed
- **Dual-persona deployment** — identical codebase pattern, different configs; each bot runs as an isolated `systemd` service with its own virtual environment and environment file

---

## Project Structure

```
financebot/
├── damon-bot/
│   ├── finance_bot.py        # Full bot logic (VND only)
│   ├── learned_keywords.json # Persisted category corrections
│   └── user_sources.json     # Income source definitions
├── quinn-bot/
│   ├── finance_bot.py        # Full bot logic (VND + USD variant)
│   ├── learned_keywords.json
│   └── user_sources.json
├── requirements.txt
└── DEPLOY_GUIDE.md
```

---

## Setup — Local Development

### Prerequisites

- Python 3.10+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A GCP service account with Google Sheets API and Google Drive API enabled
- A Google Gemini API key

### Install

```bash
git clone <repo-url>
cd financebot/damon-bot   # or quinn-bot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r ../requirements.txt
```

### Configure environment

Create a `.env` file (never commit this):

```env
BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEY=your_gemini_api_key
SPREADSHEET_ID=your_google_sheet_id
ALLOWED_IDS=123456789,987654321
GOOGLE_CREDENTIALS_JSON=/path/to/service_account.json
```

### Run

```bash
python finance_bot.py
```

---

## Deployment — GCP e2-micro VM

Full steps are documented in [`DEPLOY_GUIDE.md`](DEPLOY_GUIDE.md). Summary:

1. SSH into your VM and clone the repo.
2. Create a virtual environment and install dependencies for each bot directory.
3. Place your service account JSON and set up `/etc/systemd/system/damon-bot.service` (and `quinn-bot.service`):

```ini
[Unit]
Description=Damon Finance Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/financebot/damon-bot
EnvironmentFile=/home/ubuntu/financebot/damon-bot/.env
ExecStart=/home/ubuntu/financebot/damon-bot/.venv/bin/python finance_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

4. Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable damon-bot quinn-bot
sudo systemctl start damon-bot quinn-bot
```

5. Check logs:

```bash
journalctl -u damon-bot -f
```

---

## Security

- Bot tokens, Gemini API keys, and spreadsheet IDs are loaded from environment variables — never hard-coded or committed.
- Each bot enforces an `ALLOWED_IDS` whitelist; all messages from unknown users are silently ignored.
- The GCP service account is scoped to the minimum required APIs (Sheets + Drive).

---

## Two Bots, Two Personas

| | Damon Bot | Quinn Bot |
|-|-----------|-----------|
| Currency | VND only | VND + USD |
| Users | Single user | Quinn + Damon |
| Tone | Vietnamese, military ("đồng chí") | Vietnamese, friendly |
| Spreadsheet | Separate | Separate |

---

## License

MIT — see [LICENSE](LICENSE) for details.
