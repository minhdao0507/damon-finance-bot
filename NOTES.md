# Finance Bot — Ghi chép dự án

Cập nhật: 2026-05-27

---

## Tổng quan

Hệ thống bot Telegram theo dõi chi tiêu cá nhân, tự động phân loại, lưu vào Google Sheets và phân tích bằng AI (Gemini). Có 2 bot riêng biệt: **Damon** và **Quinn**.

---

## Kiến trúc

```text
Telegram (người dùng)
        ↓
  finance_bot.py   ← chạy trên GCP VM (apple-monitor, us-central1-a)
        ↓
  Google Sheets    ← lưu từng giao dịch theo tab tháng (YYYY-MM)
        ↓
  Gemini API       ← phân tích AI khi dùng /analyze
```

---

## Cấu trúc thư mục

```text
M:\Working\financebot\
├── damon-bot\
│   ├── finance_bot.py       ← bot chính v2 (đã deploy)
│   ├── credentials.json     ← GCP service account (KHÔNG commit git)
│   ├── requirements.txt
│   ├── railway.json
│   └── .gitignore
├── quinn-bot\
│   ├── finance_bot.py       ← bot v2 (đã deploy)
│   ├── credentials.json
│   ├── requirements.txt
│   └── .gitignore
└── keys\
    ├── credentials.json     ← bản gốc service account
    └── ssh-key-2026-05-23.key
```

---

## Config quan trọng

### Damon Bot

| Biến | Giá trị |
| ------ | --------- |
| BOT_TOKEN | `<your_damon_bot_token>` |
| SHEET_ID | `<your_google_sheet_id>` |
| YOUR_CHAT_ID | `<your_telegram_chat_id>` |
| ALLOWED_IDS | `{your_chat_id}` |

### Quinn Bot

| Biến | Giá trị |
| ------ | --------- |
| BOT_TOKEN | `<your_quinn_bot_token>` |
| SHEET_ID | `<your_google_sheet_id>` |
| YOUR_CHAT_ID | `<quinn_telegram_chat_id>` |
| ALLOWED_IDS | `{quinn_id, damon_id}` (cả 2 đều dùng được) |
| GEMINI_API_KEY | dùng chung key với Damon bot |

### GCP Service Account

- Project: `personal-finance-adviser`
- Email: `finance-bot@personal-finance-adviser.iam.gserviceaccount.com`
- File: `M:\Working\financebot\keys\credentials.json`

### Gemini API

- Key: `<your_gemini_api_key>` (dùng chung với Apple monitor)
- Model: `gemini-2.5-flash-lite` (free tier, 1,500 req/ngày)
- SDK: `google-genai` (package mới — `google-generativeai` đã deprecated)

---

## Deployment — GCP VM

Cả 2 bot chạy trên cùng VM với Apple monitor: `apple-monitor` (us-central1-a, e2-micro, Always Free).

### Systemd services

| Service | WorkingDir | Script |
| --------- | ----------- | -------- |
| `finance-bot.service` | `/home/dphm57/finance_bot/` | `finance_bot.py` |
| `finance-bot-quinn.service` | `/home/dphm57/finance_bot_quinn/` | `finance_bot.py` |

Cả 2 service không set env vars — config hardcode trực tiếp trong code (với `os.environ.get(KEY, default)`).

### Lệnh thường dùng trên VM

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

### Update code lên VM (chạy trên máy Windows)

```powershell
# Damon bot
gcloud compute scp "M:\Working\financebot\damon-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot/ --zone=us-central1-a --quiet
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot"

# Quinn bot
gcloud compute scp "M:\Working\financebot\quinn-bot\finance_bot.py" dphm57@apple-monitor:/home/dphm57/finance_bot_quinn/ --zone=us-central1-a --quiet
gcloud compute ssh dphm57@apple-monitor --zone=us-central1-a --quiet --command="sudo systemctl restart finance-bot-quinn"
```

---

## UX Flow v2 — Nhập chi tiêu

```text
Gõ text tự do hoặc /add
  → Bot: "Ghi nhận: 1. 30.000đ · ăn sáng → Ăn uống ngoài"
  → Chọn nguồn tiền cho từng giao dịch

Chọn nguồn (inline keyboard, nhiều tx thì hỏi từng cái)
  → Bot: Xác nhận toàn bộ + nút ✏️ category cho từng tx

Xác nhận / chỉnh category / lưu
  → ✅ Đã lưu X giao dịch
```

### Multi-transaction input

```text
Nhập nhiều dòng cùng lúc:
30k ăn sáng
200k grab
50k cafe
```

### Parser format

```text
<số><đơn vị> <lý do>

Đơn vị: k = ×1,000 | m hoặc tr = ×1,000,000
Ví dụ:  30k ăn sáng  →  30,000đ
        1.5m quần áo →  1,500,000đ
        85000 bún bò →  85,000đ

Quinn bot thêm:
  $5 netflix    →  $5.00 USD
  5$ netflix    →  $5.00 USD
  5 usd netflix →  $5.00 USD
```

---

## Persistent storage (trên VM)

| File | Nội dung |
| ------ | --------- |
| `user_sources.json` | danh sách nguồn tiền + số lần dùng |
| `learned_keywords.json` | keywords tự học từ category edit |

---

## Nguồn tiền mặc định

### Damon (tất cả VND)
VPBank, Tiền mặt, ZaloPay, MoMo

### Quinn (VND + USD)
VIB (VND), MB Bank (VND), MoMo (VND), Chase (USD), Apple Card (USD)

---

## Lệnh bot

| Lệnh | Mô tả |
| ------ | ------- |
| `/add` | Ghi chi tiêu mới (có hướng dẫn) |
| `/today` | Tổng chi tiêu hôm nay theo category |
| `/week` | Tổng 7 ngày gần nhất + % |
| `/month` | Tổng tháng này theo category + nguồn |
| `/analyze` | AI phân tích chi tiêu tháng + lời khuyên |
| `/src` | Quản lý nguồn tiền (xóa, xem số lần dùng) |
| `/help` | Hiển thị danh sách lệnh |
| `/cancel` | Hủy thao tác đang làm |

### Nhắc nhở tự động

Mỗi ngày lúc **23:30 GMT+7** (16:30 UTC) bot tự nhắn:

- **Damon**: "Ngày hôm nay của đồng chí dài rồi, thương bạn lắm, nhưng đừng quên ghi chép chi tiêu, vì bạn tiêu nhiều vl"
- **Quinn**: "Ngày hôm nay của em bé dài rồi, nhưng đừng quên ghi chép chi tiêu nhé 💜"

---

## Google Sheets

### Cấu trúc cột (v2 — có Tiền tệ)

`STT | Ngày | Giờ | Nguồn | Số tiền | Tiền tệ | Category | Lý do | Ghi chú`

Index: 0 · 1 · 2 · 3 · 4 · 5 · **6** · **7** · 8

> ⚠️ Category ở index 6 (không phải 5 như trước). Code đã cập nhật đúng.

### Migration tự động

`_ensure_currency_column()` tự detect tab cũ thiếu cột Tiền tệ → insert + back-fill VND.

- [Sheet Damon](https://docs.google.com/spreadsheets/d/1FccOyealfvkLueXOz4ltKmrh_nVqnDxxWYZP_Mcfj7U)
- [Sheet Quinn](https://docs.google.com/spreadsheets/d/1AqcWPlAtlbwPXqd-VGj-VYovq7NnHcgvfujAi848p9Y)

---

## Categories

### Damon & Quinn (chung)
Ăn uống ngoài, Đi chợ, Đi siêu thị, Di chuyển, Du lịch, Phí sinh hoạt, Tiền nhà, Tín dụng, Trải nghiệm, Giải trí, Chăm sóc cá nhân, Quà/Tặng, Sức khỏe, Thiết bị, Đặt hàng online, Học tập (Quinn), Phạt, Khác

### Khác nhau
| Bot | Category riêng |
| ----- | --------------- |
| Damon | `Quinn` — keywords: quinn, quỳnh anh, quỳnh |
| Quinn | `Minh` — keywords: minh, minh dao, đưa minh, chuyển cho minh |

Quinn bot có thêm English keywords cho tất cả categories.

---

## Lỗi đã gặp & cách xử lý

| Lỗi | Nguyên nhân | Fix |
| ----- | ------------ | ----- |
| `Conflict: terminated by other getUpdates` | 2 instance bot cùng chạy | `taskkill /FI "IMAGENAME eq python.exe" /F` |
| `models/gemini-1.5-flash is not found` | Model cũ không còn | Đổi sang `gemini-2.5-flash-lite` |
| `UnicodeEncodeError` | Windows cp1252 không đọc emoji | Dùng ASCII cho `print()` |
| `google-generativeai` FutureWarning | Package deprecated | Đổi sang `google-genai` |
| `can't parse entities` trong /analyze | Gemini trả về Markdown không hợp lệ | Bỏ parse_mode + strip `**`, `__`, backtick |
| `KeyError: 'BOT_TOKEN'` | Service không set env vars | Dùng `os.environ.get(KEY, hardcoded_default)` |
| Cột lệch sau thêm Tiền tệ | Tab cũ không có cột currency | `_ensure_currency_column()` tự migrate |
