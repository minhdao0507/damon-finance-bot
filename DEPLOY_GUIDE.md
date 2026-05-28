# Deploy Guide — Finance Bots

## Files cần có

### Bot của Damon
- `finance_bot.py` — bot chính
- `credentials.json` — Google service account
- `requirements.txt`
- `railway_damon.json` → đổi tên thành `railway.json`

### Bot của Quinn
- `finance_bot_quinn.py` — bot của Quinn
- `credentials.json` — cùng service account
- `requirements.txt`
- `railway_quinn.json` → đổi tên thành `railway.json`

---

## Bước 1 — Điền config (làm trước khi deploy)

### Damon's bot (`finance_bot.py`)
```python
BOT_TOKEN = "1234567890:AAF..."    # BotFather token của Damon's bot
SHEET_ID = "1PmTMrUEhZqwa3..."     # Google Sheet ID của Damon
YOUR_CHAT_ID = 987654321           # Telegram ID của Damon
```

### Quinn's bot (`finance_bot_quinn.py`)
```python
BOT_TOKEN = "9876543210:BBG..."    # BotFather token của Quinn's bot (tạo bot mới)
SHEET_ID = "2QnUNSfiBkrxb4..."     # Google Sheet ID của Quinn (tạo sheet mới)
YOUR_CHAT_ID = 123456789           # Telegram ID của Quinn
```

### Lấy Telegram chat ID
Quinn nhắn tin cho @userinfobot → bot reply ID ngay

### Tạo bot mới cho Quinn
1. Nhắn @BotFather
2. /newbot
3. Đặt tên: "Quinn Finance Bot"
4. Lấy token

---

## Bước 2 — Deploy lên Railway (free, 24/7)

### Deploy bot Damon
```bash
# Tạo folder riêng
mkdir damon-bot && cd damon-bot

# Copy files vào
cp ../finance_bot.py .
cp ../credentials.json .
cp ../requirements.txt .
cp ../railway_damon.json ./railway.json

# Push lên GitHub
git init
git add .
git commit -m "Damon finance bot"
git remote add origin https://github.com/YOUR_USERNAME/damon-finance-bot
git push -u origin main
```

Vào https://railway.app → New Project → Deploy from GitHub → chọn repo → Add Variables:
- BOT_TOKEN = (token của Damon)
- SHEET_ID = (sheet ID của Damon)

### Deploy bot Quinn
```bash
mkdir quinn-bot && cd quinn-bot

cp ../finance_bot_quinn.py .
cp ../credentials.json .
cp ../requirements.txt .
cp ../railway_quinn.json ./railway.json

git init
git add .
git commit -m "Quinn finance bot"
git remote add origin https://github.com/YOUR_USERNAME/quinn-finance-bot
git push -u origin main
```

Vào Railway → New Project → chọn repo quinn → Add Variables:
- BOT_TOKEN = (token của Quinn)
- SHEET_ID = (sheet ID của Quinn)

---

## Bước 3 — Test

### Damon test bot của mình
Tìm bot trên Telegram → /start → thử nhắn `vpbank - 50000 - test`

### Quinn test bot của cô ấy
Quinn tìm bot theo tên trên Telegram → /start → thử nhắn `vpbank - 50000 - test`

---

## Checklist trước khi deploy

- [ ] Tạo 2 bot riêng trên BotFather (lấy 2 token khác nhau)
- [ ] Tạo 2 Google Sheet riêng
- [ ] Share cả 2 sheet với cùng service account email
- [ ] Lấy Telegram chat ID của Quinn (@userinfobot)
- [ ] Điền đúng config vào từng file
- [ ] Deploy 2 repo riêng lên Railway

---

## Sau khi deploy xong

Cả hai đều chỉ cần mở Telegram và nhắn tin vào bot là xong.
Không cần máy tính, không cần app gì thêm.

Convention nhắn tin:
  vpbank - 85000 - bun bo an trua
  tien mat - 30000 - cafe
  zalopay - 350000 - tien dien thang 5
  momo - 50k - grab
