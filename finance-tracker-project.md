# 💰 Dự án Quản Lý Chi Tiêu Cá Nhân

> Hệ thống track chi tiêu tự động qua Telegram Bot + Google Sheets + n8n + AI Agent

---

## Tổng quan

Hệ thống gồm 3 phases:

| Phase | Mô tả | Trạng thái |
|-------|-------|-----------|
| Phase 1 | Telegram Bot — thu thập data hàng ngày | ✅ Done |
| Phase 2 | n8n Automation — xử lý, cảnh báo, báo cáo tự động | 🔨 Build tiếp |
| Phase 3 | AI Financial Advisor Agent — tư vấn + dự báo | 📋 Planned |

---

## Phase 1 — Telegram Bot

### Convention nhập chi tiêu

```
nguon - so_tien - ly_do
```

**Ví dụ:**
```
vpbank - 85000 - bun bo an trua
tien mat - 30000 - nuoc lon
zalopay - 350000 - tien dien thang 5
momo - 50k - cafe highland
vpbank - 1.2m - quan ao
```

### Nguồn hỗ trợ

| Nhập | Hiển thị |
|------|---------|
| vpbank, vp | VPBank |
| tien mat, cash, mat | Tien mat |
| zalopay, zalo | ZaloPay |
| momo | MoMo |
| bidv | BIDV |
| acb | ACB |
| techcombank, tcb | Techcombank |

### Đơn vị số tiền

| Nhập | Kết quả |
|------|---------|
| 85000 | 85,000đ |
| 85k | 85,000đ |
| 1.5m | 1,500,000đ |
| 1.5tr | 1,500,000đ |

### Commands

| Command | Mô tả |
|---------|-------|
| /start | Hướng dẫn sử dụng |
| /today | Tổng chi tiêu hôm nay |
| /week | Tổng 7 ngày gần nhất |
| /month | Tổng tháng + breakdown category |
| /help | Xem ví dụ |

### Auto-categorize

| Category | Keywords |
|----------|----------|
| an uong | an sang, an trua, an toi, cafe, tra sua, com, pho... |
| di chuyen | grab, xang, xe, bus, taxi... |
| tien ich | dien, nuoc, internet, wifi, gas |
| mua sam | quan ao, giay, shopee, lazada... |
| suc khoe | thuoc, benh vien, phong kham, gym |
| giai tri | xem phim, cgv, netflix, game |
| hoc tap | sach, khoa hoc, course, ielts |
| tiet kiem | tiet kiem, gui tiet kiem, dau tu |
| gia dinh | gia dinh, bo me, gui ve nha |

### Google Sheets Schema

Mỗi tháng tạo 1 sheet riêng (tên: `2026-05`, `2026-06`...):

| STT | Ngay | Gio | Nguon | So tien | Category | Ly do | Ghi chu |
|-----|------|-----|-------|---------|----------|-------|---------|

---

## Rào cản kỹ thuật — Bank API

Các ngân hàng VN không cung cấp personal transaction API. Workarounds:

| Ngân hàng | Giải pháp |
|-----------|-----------|
| VPBank | Download PDF sao kê hàng tháng → unlock + extract |
| BIDV | Có tính năng gửi email per-transaction (duy nhất) |
| Các ngân hàng khác | SMS forwarding qua app Android |
| ZaloPay | Tự động withdraw từ VPBank → xuất hiện trong sao kê |
| Tiền mặt | Manual note qua Telegram bot |

### Password PDF VPBank
```
DDMMYYYY (ngày sinh)
Ví dụ: 05071999
```

---

## Month-End Validation

Cuối tháng chạy script để validate:

```bash
python validate_month.py --pdf vpbank_may_2026.pdf --month 2026-05
```

Script tự động:
1. Unlock PDF (pikepdf)
2. Extract transactions (pdfplumber)
3. So sánh với bot log trong Google Sheets
4. Report missing transactions
5. Tính tổng bao gồm cả tiền mặt + ví điện tử

---

## Phase 2 — n8n Automation (Build tiếp theo)

### Workflow 1: Weekly Digest

**Trigger:** Mỗi tối Chủ nhật 20:00

**Flow:**
```
Schedule trigger
  → Query Google Sheets (7 ngày gần nhất)
  → Tính tổng theo category
  → Format message
  → Gửi qua Telegram
```

**Output mẫu:**
```
📊 Tuần 19-25/05/2026

• an uong:    850,000đ (38%)
• di chuyen:  320,000đ (14%)
• mua sam:    450,000đ (20%)
• tien ich:   380,000đ (17%)
• khac:       240,000đ (11%)

💰 Tổng: 2,240,000đ
📈 Trung bình/ngày: 320,000đ
```

### Workflow 2: Budget Alert

**Trigger:** Mỗi transaction mới trong Sheets

**Logic:**
```
Nếu tổng category trong tháng > budget limit
  → Gửi cảnh báo qua Telegram
```

**Budget defaults:**
| Category | Limit/tháng |
|----------|-------------|
| an uong | 6,000,000đ |
| di chuyen | 2,000,000đ |
| mua sam | 3,000,000đ |
| giai tri | 1,500,000đ |

### Workflow 3: Monthly PDF Automation

**Trigger:** Ngày 1 hàng tháng

**Flow:**
```
Schedule trigger
  → Nhắc nhở download sao kê (Telegram)
  → Chờ file upload
  → Unlock PDF (Python)
  → Extract transactions
  → So sánh với bot log
  → Gửi validation report
```

---

## Phase 3 — AI Financial Advisor Agent

### Architecture

```
Google Sheets (unified data)
        ↓
AI Agent (smolagents)
  ├── Tool: get_transactions()
  ├── Tool: calculate_metrics()
  └── Tool: forecast_canada_savings()
        ↓
Telegram — trả lời bằng tiếng Việt
```

### Tools cần build

#### `get_transactions(start_date, end_date, category=None, source=None)`
- Query Google Sheets
- Filter theo khoảng thời gian, category, nguồn
- Return JSON array

#### `calculate_metrics(period='month')`
- Tổng chi tiêu theo category
- Savings rate
- Spending trends (so với tháng trước)
- Top merchants/categories
- Average daily spending

#### `forecast_canada_savings(target_date='2027-09-01', target_amount=500_000_000)`
- Dự báo tổng tiết kiệm đến ngày target
- So sánh với target Canada (500Tr tự kiếm)
- Gap analysis
- Recommendation để đạt target

### Ví dụ conversation

**Bạn hỏi:**
```
Tháng này tôi có tiết kiệm đủ để đi Canada không?
```

**Agent trả lời:**
```
📊 Tháng 5/2026 (tính đến hôm nay):

Chi tiêu: 4,820,000đ / 15 ngày
→ Ước tính cả tháng: ~9,640,000đ

Lương Apple: 42,000,000đ (gross)
Còn lại ước tính: ~32,000,000đ

🎯 Target Canada: 500Tr trong 16 tháng = 31.25Tr/tháng
✅ Tháng này đang đúng hướng (+0.75Tr so với target)

Điểm cần chú ý:
• Ăn uống: 2.1Tr/7 ngày → pace cao hơn 15% so với tháng 4
• Mua sắm: 1.2Tr → trong budget

Projection đến 09/2027:
• Nếu giữ pace hiện tại: ~512Tr ✅
• Cần tiết kiệm mỗi tháng: ≥31.25Tr
```

---

## Deploy Setup

### Yêu cầu

- Python 3.11+
- Railway account (free tier đủ dùng)
- Google Cloud account (free)
- Telegram account

### Dependencies

```
python-telegram-bot>=20.0
gspread>=5.0
google-auth>=2.0
pikepdf>=8.0
pdfplumber>=0.9
```

### Files

| File | Mô tả |
|------|-------|
| `finance_bot.py` | Bot của Damon |
| `finance_bot_quinn.py` | Bot của Quinn |
| `validate_month.py` | Validation cuối tháng |
| `requirements.txt` | Python dependencies |
| `credentials.json` | Google Service Account |
| `railway.json` | Railway deploy config |

### Biến môi trường

| Biến | Mô tả |
|------|-------|
| `BOT_TOKEN` | Telegram bot token từ BotFather |
| `SHEET_ID` | Google Spreadsheet ID |
| `YOUR_CHAT_ID` | Telegram user ID |

### Checklist deploy

- [ ] Tạo 2 Telegram bots (@BotFather)
- [ ] Tạo Google Cloud project
- [ ] Enable Google Sheets API + Drive API
- [ ] Tạo Service Account → download `credentials.json`
- [ ] Tạo 2 Google Sheets (Damon + Quinn)
- [ ] Share sheets với service account email
- [ ] Lấy Chat ID của Damon và Quinn (@userinfobot)
- [ ] Điền config vào `finance_bot.py` và `finance_bot_quinn.py`
- [ ] Deploy 2 repos riêng lên Railway
- [ ] Test bot của Damon
- [ ] Hướng dẫn Quinn setup

---

## Quinn's Bot

Bot riêng cho Quinn, hoàn toàn độc lập với Damon:

- Cùng codebase, khác config (token + sheet)
- Data tách biệt — Damon không thấy chi tiêu của Quinn
- Cùng convention nhập liệu
- Deploy trên Railway riêng

**3 giá trị cần điền trong `finance_bot_quinn.py`:**
```python
BOT_TOKEN = "QUINN_BOT_TOKEN_HERE"
SHEET_ID  = "QUINN_SHEET_ID_HERE"
YOUR_CHAT_ID = QUINN_TELEGRAM_ID
```

---

## Roadmap

```
05/2026  ✅ Build Telegram bot (Damon + Quinn)
06/2026  🔨 Deploy lên Railway
07/2026  🔨 Build n8n weekly digest workflow
08/2026  📋 Build n8n budget alert
09/2026  📋 Build monthly PDF automation
10/2026  📋 Build AI agent tools (get_transactions, calculate_metrics)
11/2026  📋 Build forecast_canada tool
12/2026  📋 Launch AI advisor — hỏi đáp tiếng Việt
```

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Data collection | Telegram Bot (python-telegram-bot) |
| Storage | Google Sheets |
| Automation | n8n (self-hosted trên Railway) |
| PDF processing | pikepdf + pdfplumber |
| AI Agent | smolagents (Hugging Face) |
| LLM | Claude API / DeepSeek (cost-effective) |
| Deploy | Railway (free tier) |

---

*Tài liệu cập nhật lần cuối: 05/2026*
