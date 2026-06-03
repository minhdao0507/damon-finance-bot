# Finance Bot — Ghi chép dự án

Cập nhật: 2026-06-02

---

## Tổng quan

Hệ thống 2 Telegram bot theo dõi chi tiêu cá nhân, tự động phân loại, lưu vào Google Sheets, và phân tích bằng AI. Bao gồm tính năng **market digest** gửi bản tin thị trường hàng ngày.

**2 bot độc lập:**

| Bot | Người dùng | Tiền tệ | Repo GitHub |
|-----|-----------|---------|-------------|
| Damon Bot | Damon | VND | `damon-finance-bot` |
| Quinn Bot | Quinn + Damon | VND + USD | `quinn-finance-bot` |

> **Lưu ý hạ tầng:** Cả 2 bot chạy trên VM instance `apple-monitor` thuộc **GCP project `apple-monitor`** (us-central1-a, e2-micro). Finance Bot và Apple Procurement Monitor là **2 dự án logic hoàn toàn riêng biệt** — chỉ dùng chung VM để tiết kiệm chi phí (e2-micro Always Free). GCP project `personal-finance-adviser` tồn tại riêng cho service account + Google Sheets, không có VM.

---

## Infrastructure

| Thứ | Chi tiết |
|-----|----------|
| Máy chủ | GCP VM `apple-monitor`, us-central1-a, e2-micro (Always Free) |
| OS | Ubuntu |
| User | `dphm57` |
| Thư mục Damon | `/home/dphm57/finance_bot/` |
| Thư mục Quinn | `/home/dphm57/finance_bot_quinn/` |

---

## Cấu trúc thư mục (local)

```text
M:\Working\financebot\
├── damon-bot\
│   ├── finance_bot.py        ← bot chính v2, bao gồm market digest
│   ├── market_digest.py      ← module thu thập dữ liệu thị trường
│   ├── requirements.txt
│   ├── credentials.json      ← GCP service account (KHÔNG commit)
│   ├── learned_keywords.json ← tự học từ user corrections
│   ├── user_sources.json     ← danh sách nguồn tiền
│   └── .gitignore
├── quinn-bot\
│   ├── finance_bot.py        ← bot v2 (VND + USD)
│   ├── requirements.txt
│   ├── credentials.json
│   ├── learned_keywords.json
│   ├── user_sources.json
│   └── .gitignore
└── keys\
    ├── credentials.json      ← bản gốc service account
    └── ssh-key-2026-05-23.key
```

---

## Config quan trọng

### Damon Bot (`damon-bot/finance_bot.py`)

| Biến | Mô tả |
|------|-------|
| `BOT_TOKEN` | Token từ @BotFather |
| `SHEET_ID` | Google Sheet ID |
| `YOUR_CHAT_ID` | Telegram ID của Damon |
| `ALLOWED_IDS` | `{YOUR_CHAT_ID}` |
| `GEMINI_API_KEY` | Google AI Studio key |

### Quinn Bot (`quinn-bot/finance_bot.py`)

| Biến | Mô tả |
|------|-------|
| `BOT_TOKEN` | Token riêng của Quinn bot |
| `SHEET_ID` | Google Sheet riêng của Quinn |
| `YOUR_CHAT_ID` | Telegram ID của Quinn |
| `ALLOWED_IDS` | `{quinn_id, damon_id}` |
| `GEMINI_API_KEY` | Dùng chung key |

### GCP Service Account

- Project: `personal-finance-adviser`
- Email: `finance-bot@personal-finance-adviser.iam.gserviceaccount.com`
- File local: `M:\Working\financebot\keys\credentials.json`
- Scope: Google Sheets API + Google Drive API

### Gemini API

- SDK: `google-genai` (package mới — `google-generativeai` đã deprecated)
- Model: `gemini-2.5-flash-lite` (free tier, 1,500 req/ngày)

### Google Sheets

| Bot | Sheet link |
|-----|-----------|
| Damon | [Link](https://docs.google.com/spreadsheets/d/1FccOyealfvkLueXOz4ltKmrh_nVqnDxxWYZP_Mcfj7U) |
| Quinn | [Link](https://docs.google.com/spreadsheets/d/1AqcWPlAtlbwPXqd-VGj-VYovq7NnHcgvfujAi848p9Y) |

---

## Systemd Services

| Service | WorkingDir trên VM | Script |
|---------|--------------------|--------|
| `finance-bot.service` | `/home/dphm57/finance_bot/` | `finance_bot.py` |
| `finance-bot-quinn.service` | `/home/dphm57/finance_bot_quinn/` | `finance_bot.py` |

Config không dùng env file — credentials hardcode trực tiếp trong code với `os.environ.get(KEY, default)`.

---

## Lệnh thường dùng trên VM

```bash
# Xem trạng thái
sudo systemctl status finance-bot
sudo systemctl status finance-bot-quinn

# Restart sau khi update code
sudo systemctl restart finance-bot
sudo systemctl restart finance-bot-quinn

# Xem log realtime
sudo journalctl -u finance-bot -f
sudo journalctl -u finance-bot-quinn -f
```

---

## Update code lên VM (chạy trên máy Windows)

```powershell
# Damon bot — cập nhật 1 file
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot/ --zone=us-central1-a --quiet

# Damon bot — cập nhật nhiều file (bao gồm market_digest.py)
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" "M:\Working\financebot\damon-bot\market_digest.py" "M:\Working\financebot\damon-bot\requirements.txt" dphm57@apple-monitor:/home/dphm57/finance_bot/ --zone=us-central1-a --quiet

# Restart sau khi upload
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot"

# Quinn bot
gcloud compute scp "M:\Working\financebot\quinn-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot_quinn/ --zone=us-central1-a --quiet
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot-quinn"
```

---

## Tính năng: Market Digest (Damon Bot)

Module `market_digest.py` thu thập dữ liệu thị trường và gửi vào Telegram 4 lần/ngày.

### Lịch gửi

| Giờ GMT+7 | Giờ UTC | Job |
|-----------|---------|-----|
| 05:45 | 22:45 (hôm trước) | `morning_digest` |
| 09:30 | 02:30 | `morning_digest` |
| 13:00 | 06:00 | `morning_digest` |
| 17:30 | 10:30 | `morning_digest` |

### Nội dung bản tin

| Mục | Nguồn dữ liệu | Ghi chú |
|-----|--------------|---------|
| Giá vàng thế giới | yfinance `GC=F` | Không cần API key |
| Giá vàng Việt Nam | Ước tính từ `GC=F` × `USDVND=X` × (37.5/31.1035) × 1.02 | Tham chiếu, không phải SJC chính thức |
| Khối ngoại mua/bán | vnstock v4 VN30 `price_board()`, cột `match_foreign_buy/sell_value` | Chỉ VN30 |
| Tin BĐS | Scrape `cafef.vn/bat-dong-san.chn` (h2/h3 headlines) | Top 5 |
| Từ khóa kinh doanh | Scrape `cafef.vn` homepage, score theo finance keywords | Top 3 |

### Nguồn đã loại bỏ

| Nguồn | Lý do |
|-------|-------|
| sjc.com.vn | Chặn bởi Cloudflare 403 |
| TCBS / SSI / VNDirect foreign_trade API | 404 / 403 / timeout |
| pytrends (Google Trends) | 404 / 429 rate-limited |
| batdongsan.com.vn | URL thay đổi, tất cả 404 |
| Tự doanh | Không có public API |

---

## Features chi tiêu

### UX Flow v2

```text
Gõ text tự do hoặc /add
  → Bot: "Ghi nhận: 1. 30.000đ · ăn sáng → Ăn uống ngoài"
  → Chọn nguồn tiền cho từng giao dịch

Chọn nguồn (inline keyboard)
  → Bot: Xác nhận toàn bộ + nút ✏️ chỉnh category

Xác nhận / chỉnh category / lưu
  → ✅ Đã lưu X giao dịch
```

### Parser format

```text
<số><đơn vị> <lý do>

k = ×1,000 | tr / m = ×1,000,000
Ví dụ:  30k ăn sáng  →  30,000đ
        1.5m quần áo →  1,500,000đ
        85000 bún bò →  85,000đ

Quinn bot thêm:
  $5 netflix    →  $5.00 USD
  5 usd netflix →  $5.00 USD
```

### Nhắc nhở tự động hàng ngày

| Bot | Giờ (GMT+7) | Nội dung |
|-----|------------|----------|
| Damon | 23:30 | "Ngày hôm nay của đồng chí dài rồi, thương bạn lắm, nhưng đừng quên ghi chép chi tiêu, vì bạn tiêu nhiều vl" |
| Quinn | 23:30 | "Ngày hôm nay của em bé dài rồi, nhưng đừng quên ghi chép chi tiêu nhé 💜" |

---

## Lệnh bot

| Lệnh | Mô tả |
|------|-------|
| `/add` | Ghi chi tiêu mới (có hướng dẫn) |
| `/today` | Tổng chi tiêu hôm nay theo category |
| `/week` | Tổng 7 ngày gần nhất |
| `/month` | Tổng tháng này theo category + nguồn |
| `/analyze` | AI phân tích chi tiêu tháng + chat follow-up |
| `/src` | Quản lý nguồn tiền |
| `/help` | Danh sách lệnh |
| `/cancel` | Hủy thao tác đang làm |

---

## Google Sheets — Cấu trúc cột (v2)

`STT | Ngày | Giờ | Nguồn | Số tiền | Tiền tệ | Category | Lý do | Ghi chú`

Index:  0  ·  1  ·  2  ·  3  ·  4  ·  5  ·  **6**  ·  **7**  ·  8

> ⚠️ Category ở index **6** (không phải 5 như schema cũ). `_ensure_currency_column()` tự migrate tab cũ thiếu cột Tiền tệ.

---

## Nguồn tiền mặc định

| Bot | Nguồn |
|-----|-------|
| Damon | VPBank, Tiền mặt, ZaloPay, MoMo |
| Quinn | VIB (VND), MB Bank (VND), MoMo (VND), Chase (USD), Apple Card (USD) |

---

## Categories

Damon & Quinn dùng chung: Ăn uống ngoài, Đi chợ, Đi siêu thị, Di chuyển, Du lịch, Phí sinh hoạt, Tiền nhà, Tín dụng, Trải nghiệm, Giải trí, Chăm sóc cá nhân, Quà/Tặng, Sức khỏe, Thiết bị, Đặt hàng online, Học tập *(Quinn)*, Phạt, Khác

| Bot | Category riêng |
|-----|---------------|
| Damon | `Quinn` — keywords: quinn, quỳnh anh, quỳnh |
| Quinn | `Minh` — keywords: minh, minh dao, đưa minh, chuyển cho minh |

---

## Dependencies

```
python-telegram-bot[job-queue]>=20.0
gspread>=5.0
google-auth>=2.0
google-genai>=1.0.0
yfinance>=0.2.0          ← market digest: gold + USD/VND rate
beautifulsoup4>=4.12.0   ← market digest: scrape cafef.vn
lxml>=5.0.0              ← market digest: HTML parser
requests>=2.31.0         ← market digest: HTTP calls
vnstock>=4.0.0           ← market digest: VN30 foreign trading
```

---

## Lỗi đã gặp & cách xử lý

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| `Conflict: terminated by other getUpdates` | 2 instance cùng chạy | `taskkill /FI "IMAGENAME eq python.exe" /F` |
| `models/gemini-1.5-flash is not found` | Model cũ | Đổi sang `gemini-2.5-flash-lite` |
| `UnicodeEncodeError` | Windows cp1252 không encode emoji | Dùng ASCII cho `print()`, Telegram vẫn nhận UTF-8 |
| `google-generativeai` FutureWarning | Package deprecated | Đổi sang `google-genai` |
| `can't parse entities` trong /analyze | Gemini trả Markdown không hợp lệ | Bỏ parse_mode + strip `**`, `__`, backtick |
| `KeyError: 'BOT_TOKEN'` | Service không set env vars | Dùng `os.environ.get(KEY, hardcoded_default)` |
| Cột lệch sau thêm Tiền tệ | Tab cũ thiếu cột currency | `_ensure_currency_column()` tự migrate |
| `ModuleNotFoundError: squarify` | vnstock3 dependency lỗi | `pip install squarify` hoặc dùng vnstock v4 |
| `NotImplementedError: foreign_trade` | VCI source không hỗ trợ | Dùng `price_board()` thay thế |
| sjc.com.vn 403 | Cloudflare chặn | Dùng yfinance estimate thay thế |
