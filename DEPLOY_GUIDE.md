# Deploy Guide — Finance Bots

Cập nhật: 2026-06-02

Cả 2 bot (`finance-bot` và `finance-bot-quinn`) chạy trên VM `apple-monitor` (GCP project `apple-monitor`, us-central1-a, e2-micro Always Free). Mỗi bot là 1 systemd service độc lập.

---

## Cấu trúc trên VM

```
/home/dphm57/
├── finance_bot/            ← Damon bot
│   ├── finance_bot.py
│   ├── market_digest.py
│   ├── requirements.txt
│   ├── credentials.json
│   ├── learned_keywords.json
│   └── user_sources.json
└── finance_bot_quinn/      ← Quinn bot
    ├── finance_bot.py
    ├── requirements.txt
    ├── credentials.json
    ├── learned_keywords.json
    └── user_sources.json
```

---

## Systemd Services

| File | Service name | Bot |
|------|-------------|-----|
| `/etc/systemd/system/finance-bot.service` | `finance-bot` | Damon |
| `/etc/systemd/system/finance-bot-quinn.service` | `finance-bot-quinn` | Quinn |

### Nội dung service file (Damon)

```ini
[Unit]
Description=Damon Finance Telegram Bot
After=network.target

[Service]
Type=simple
User=dphm57
WorkingDirectory=/home/dphm57/finance_bot
ExecStart=/usr/bin/python3 /home/dphm57/finance_bot/finance_bot.py
Restart=always
RestartSec=10
Environment=BOT_TOKEN=<token>
Environment=SHEET_ID=<sheet_id>
Environment=YOUR_CHAT_ID=<chat_id>
Environment=GEMINI_API_KEY=<gemini_key>
Environment=ALLOWED_IDS=<chat_id>

[Install]
WantedBy=multi-user.target
```

---

## Update code lên VM (chạy trên Windows)

### Damon bot

```powershell
# Upload file(s)
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot/ --zone=us-central1-a --quiet

# Upload kèm market_digest.py
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" "M:\Working\financebot\damon-bot\market_digest.py" dphm57@apple-monitor:/home/dphm57/finance_bot/ --zone=us-central1-a --quiet

# Restart
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot"
```

### Quinn bot

```powershell
gcloud compute scp "M:\Working\financebot\quinn-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot_quinn/ --zone=us-central1-a --quiet
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot-quinn"
```

---

## Kiểm tra trạng thái

```bash
# SSH vào VM
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a

# Xem trạng thái
sudo systemctl status finance-bot
sudo systemctl status finance-bot-quinn

# Xem log realtime
sudo journalctl -u finance-bot -f
sudo journalctl -u finance-bot-quinn -f
```

---

## Gửi test market digest thủ công

```bash
cd /home/dphm57/finance_bot && BOT_TOKEN=<token> YOUR_CHAT_ID=<chat_id> python3 -c "
import asyncio, sys, os
sys.path.insert(0, '.')
from market_digest import build_digest
from telegram import Bot

async def send():
    text = await asyncio.to_thread(build_digest)
    async with Bot(token=os.environ['BOT_TOKEN']) as bot:
        await bot.send_message(chat_id=int(os.environ['YOUR_CHAT_ID']), text=text, parse_mode='MarkdownV2')
    print('Sent!')

asyncio.run(send())
"
```

---

## Cài mới từ đầu (nếu cần migrate VM)

```bash
# SSH vào VM mới
gcloud compute ssh dphm57@<vm-name> --zone=<zone>

# Tạo thư mục
mkdir -p ~/finance_bot ~/finance_bot_quinn

# Copy file từ Windows
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" \
    "M:\Working\financebot\damon-bot\market_digest.py" \
    "M:\Working\financebot\damon-bot\requirements.txt" \
    "M:\Working\financebot\keys\credentials.json" \
    dphm57@<vm-name>:~/finance_bot/ --zone=<zone> --quiet

# Cài dependencies
cd ~/finance_bot && pip3 install -r requirements.txt

# Tạo service file và enable
sudo nano /etc/systemd/system/finance-bot.service
sudo systemctl daemon-reload
sudo systemctl enable finance-bot
sudo systemctl start finance-bot
```

---

## Dependencies

```
python-telegram-bot[job-queue]>=20.0
gspread>=5.0
google-auth>=2.0
google-genai>=1.0.0
yfinance>=0.2.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
requests>=2.31.0
vnstock>=4.0.0
```
