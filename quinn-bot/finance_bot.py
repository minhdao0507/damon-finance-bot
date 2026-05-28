"""
Quinn's Personal Finance Telegram Bot — v2
==========================================
- Multi-transaction input in one message
- Persistent money sources with currency (VND/USD)
- Per-transaction source selection
- Edit category inline before saving
- Auto-learn keywords from manual edits
- English + Vietnamese keywords
"""

import json
import logging
import os
import re
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from google import genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import gspread
from google.oauth2.service_account import Credentials

# ── Config ──────────────────────────────────────────────────────
BOT_TOKEN      = os.environ["BOT_TOKEN"]
SHEET_ID       = os.environ["SHEET_ID"]
YOUR_CHAT_ID   = int(os.environ["YOUR_CHAT_ID"])
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

BASE_DIR      = Path(__file__).parent
SOURCES_FILE  = BASE_DIR / "user_sources.json"
LEARNED_FILE  = BASE_DIR / "learned_keywords.json"

# ── Conversation states ─────────────────────────────────────────
(COLLECT_TX, ASK_SOURCE, CONFIRM_ALL,
 EDIT_CAT, EDIT_CAT_CUSTOM,
 ADD_SOURCE_NAME, ADD_SOURCE_CURRENCY,
 ANALYZE_CHAT) = range(8)

# ── Default sources ─────────────────────────────────────────────
DEFAULT_SOURCES = [
    {"name": "VIB",        "currency": "VND", "uses": 0},
    {"name": "MB Bank",    "currency": "VND", "uses": 0},
    {"name": "MoMo",       "currency": "VND", "uses": 0},
    {"name": "Chase",      "currency": "USD", "uses": 0},
    {"name": "Apple Card", "currency": "USD", "uses": 0},
]

# ── Categories ──────────────────────────────────────────────────
CATEGORIES = {
    "Ăn uống ngoài":    ["ăn sáng", "ăn trưa", "ăn tối", "café", "cafe", "coffee", "trà sữa",
                         "nước uống", "cơm", "phở", "bún", "bánh", "mì", "ramen", "lẩu", "sushi",
                         "cháo", "gà", "pasta", "cold cut", "bánh bao", "đồ ăn", "tiền ăn",
                         "circle k", "gs25", "family mart", "ăn ngoài", "ăn",
                         "lunch", "dinner", "breakfast", "brunch", "meal", "food", "eat",
                         "drink", "boba", "bubble tea", "restaurant", "snack", "juice"],
    "Đi chợ":           ["đi chợ", "chợ", "đậu phụ", "market"],
    "Đi siêu thị":      ["siêu thị", "mega market", "genshai", "gensha", "kingfood", "king food",
                         "kinh food", "winmart", "e market", "đồ ăn vặt", "supermarket", "grocery"],
    "Di chuyển":        ["grab", "xăng", "xe", "bus", "taxi", "gửi xe", "xanh sm",
                         "di chuyển", "giao thông", "transport", "commute", "parking", "uber", "lyft"],
    "Du lịch":          ["du lịch", "thuê xe", "đặt phòng", "cao tốc", "phí cao tốc",
                         "khách sạn", "resort", "travel", "hotel", "flight", "trip", "vacation", "tour", "airbnb"],
    "Phí sinh hoạt":    ["giặt đồ", "youtube", "google", "chatgpt", "chat gpt", "cloud",
                         "premium", "internet", "wifi", "điện", "nước", "gas", "sinh hoạt",
                         "subscription", "sub", "bill", "utility", "service", "streaming", "spotify", "apple music"],
    "Tiền nhà":         ["thuê nhà", "tiền nhà", "cọc", "nhà trọ", "phòng trọ", "rent"],
    "Tín dụng":         ["tín dụng", "credit", "thanh toán tín dụng", "credit card", "pay bill"],
    "Trải nghiệm":      ["rượu", "wine", "rượu vang", "trải nghiệm", "beer", "alcohol", "cocktail"],
    "Giải trí":         ["xem phim", "cgv", "bhd", "lotte cinema", "rạp", "netflix", "game",
                         "karaoke", "concert", "nhạc", "bar", "pub", "billiards", "bowling",
                         "movie", "cinema", "theater", "gaming", "event", "show"],
    "Chăm sóc cá nhân": ["cắt tóc", "tóc", "spa", "nail", "massage", "kem", "sữa tắm",
                         "dầu gội", "mỹ phẩm", "chăm sóc", "dưỡng",
                         "haircut", "hair", "beauty", "skincare", "makeup", "salon", "grooming"],
    "Quà/Tặng":         ["quà", "tặng", "gift", "sinh nhật", "birthday", "biếu", "hoa", "flowers", "present"],
    "Sức khỏe":         ["thuốc", "bệnh viện", "phòng khám", "gym", "khám",
                         "medicine", "hospital", "clinic", "pharmacy", "doctor", "health", "workout", "fitness"],
    "Thiết bị":         ["thiết bị", "nồi chiên", "máy", "đồ dùng", "dụng cụ",
                         "device", "gadget", "equipment", "appliance", "tech", "cable", "charger"],
    "Đặt hàng online":  ["shopee", "lazada", "đặt hàng", "online", "order", "amazon", "delivery"],
    "Học tập":          ["sách", "khóa học", "course", "ielts", "book", "study", "class", "tutor", "udemy"],
    "Minh":             ["minh", "minh dao", "đưa minh", "chuyển cho minh"],
    "Phạt":             ["phạt", "fine", "penalty"],
    "Khác":             []
}

CAT_LIST = list(CATEGORIES.keys())

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

ALLOWED_IDS = {int(x) for x in os.environ.get("ALLOWED_IDS", os.environ["YOUR_CHAT_ID"]).split(",")}


# ── Persistent source storage ───────────────────────────────────

def load_sources():
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return [s.copy() for s in DEFAULT_SOURCES]


def save_sources(sources):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def record_source_use(name):
    sources = load_sources()
    for s in sources:
        if s["name"] == name:
            s["uses"] = s.get("uses", 0) + 1
            break
    sources.sort(key=lambda x: -x.get("uses", 0))
    save_sources(sources)


# ── Auto-learn keywords ─────────────────────────────────────────

def load_learned():
    try:
        with open(LEARNED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def learn_keyword(reason: str, category: str):
    if not reason or category == "Khác":
        return
    learned = load_learned()
    learned[reason.lower().strip()] = category
    with open(LEARNED_FILE, "w", encoding="utf-8") as f:
        json.dump(learned, f, ensure_ascii=False, indent=2)


# ── Categorization ──────────────────────────────────────────────

def auto_categorize(reason: str) -> str:
    r = reason.lower()
    for kw, cat in load_learned().items():
        if kw in r:
            return cat
    for cat, keywords in CATEGORIES.items():
        if any(kw in r for kw in keywords):
            return cat
    return "Khác"


# ── Parsing ─────────────────────────────────────────────────────

def parse_line(text: str):
    """Parse one transaction line → (amount, currency, reason) or (None, None, None)."""
    text = text.strip()
    if not text:
        return None, None, None

    # "$5 netflix" or "$ 5 netflix"
    m = re.match(r"^\$\s*(\d+(?:\.\d+)?)\s+(.+)$", text)
    if m:
        return float(m.group(1)), "USD", m.group(2).strip()

    # "5$ netflix" (dollar after number)
    m = re.match(r"^(\d+(?:\.\d+)?)\$\s+(.+)$", text)
    if m:
        return float(m.group(1)), "USD", m.group(2).strip()

    # "5 usd netflix" / "15k vnd ăn trưa" / "15k ăn trưa"
    m = re.match(
        r"^(\d+(?:\.\d+)?)\s*(k|m|tr)?\s*(vnd|usd)?\s+(.+)$",
        text, re.IGNORECASE
    )
    if not m:
        return None, None, None

    amount = float(m.group(1))
    unit   = (m.group(2) or "").lower()
    curr   = (m.group(3) or "vnd").lower()
    reason = m.group(4).strip()

    if unit == "k":
        amount *= 1_000
    elif unit in ("m", "tr"):
        amount *= 1_000_000

    currency = "USD" if curr == "usd" else "VND"
    return (int(amount) if currency == "VND" else amount), currency, reason


def parse_transactions(text: str):
    txs = []
    for line in text.strip().splitlines():
        amount, currency, reason = parse_line(line.strip())
        if amount is not None and reason:
            txs.append({
                "amount":   amount,
                "currency": currency,
                "reason":   reason,
                "category": auto_categorize(reason),
                "source":   None,
            })
    return txs


# ── Formatting ───────────────────────────────────────────────────

def fmt_amount(amount, currency):
    if currency == "USD":
        return f"${amount:.2f}"
    return f"{int(amount):,}đ".replace(",", ".")


# ── Google Sheets ───────────────────────────────────────────────

EXPECTED_HEADER = ["STT", "Ngày", "Giờ", "Nguồn", "Số tiền", "Tiền tệ", "Category", "Lý do", "Ghi chú"]


def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info  = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client    = gspread.authorize(creds)
    sheet     = client.open_by_key(SHEET_ID)
    month_tab = datetime.now().strftime("%Y-%m")
    try:
        ws = sheet.worksheet(month_tab)
        _ensure_currency_column(ws)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=month_tab, rows=500, cols=10)
        ws.append_row(EXPECTED_HEADER)
        ws.format("A1:I1", {"textFormat": {"bold": True}})
    return ws


def _ensure_currency_column(ws):
    """Insert 'Tiền tệ' column after 'Số tiền' if the sheet was created without it."""
    header = ws.row_values(1)
    if not header or "Tiền tệ" in header:
        return
    # Old header: STT Ngày Giờ Nguồn Số tiền Category Lý do Ghi chú
    # New header: STT Ngày Giờ Nguồn Số tiền Tiền tệ Category Lý do Ghi chú
    try:
        col_idx = header.index("Số tiền") + 2  # 1-based → insert after "Số tiền"
    except ValueError:
        return
    ws.insert_cols([[]], col=col_idx)
    ws.update_cell(1, col_idx, "Tiền tệ")
    # Back-fill existing rows with "VND" (all old data was VND only)
    num_rows = len(ws.get_all_values())
    if num_rows > 1:
        cells = [["VND"]] * (num_rows - 1)
        ws.update(f"{gspread.utils.rowcol_to_a1(2, col_idx)}:{gspread.utils.rowcol_to_a1(num_rows, col_idx)}", cells)
    ws.format(f"A1:{gspread.utils.rowcol_to_a1(1, len(EXPECTED_HEADER))}", {"textFormat": {"bold": True}})


# ── Keyboards ───────────────────────────────────────────────────

def kb_sources(tx_idx: int):
    sources = load_sources()
    rows, row = [], []
    for s in sources:
        label = f"{s['name']} ({s['currency']})"
        row.append(InlineKeyboardButton(label, callback_data=f"src|{tx_idx}|{s['name']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("➕ Thêm nguồn mới", callback_data=f"newsrc|{tx_idx}")])
    return InlineKeyboardMarkup(rows)


def kb_confirm(txs: list):
    rows = []
    for i, tx in enumerate(txs):
        rows.append([InlineKeyboardButton(
            f"✏️ {i+1}. {tx['category']}",
            callback_data=f"editcat|{i}"
        )])
    rows.append([
        InlineKeyboardButton("✅ Lưu tất cả", callback_data="save|all"),
        InlineKeyboardButton("❌ Hủy",         callback_data="cancel|all"),
    ])
    return InlineKeyboardMarkup(rows)


def kb_categories(tx_idx: int):
    rows, row = [], []
    for i, cat in enumerate(CAT_LIST):
        if cat == "Khác":
            continue
        row.append(InlineKeyboardButton(cat, callback_data=f"setcat|{tx_idx}|{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    khac_idx = CAT_LIST.index("Khác")
    rows.append([
        InlineKeyboardButton("Khác", callback_data=f"setcat|{tx_idx}|{khac_idx}"),
        InlineKeyboardButton("📝 Nhập tên khác", callback_data=f"customcat|{tx_idx}"),
    ])
    rows.append([InlineKeyboardButton("◀️ Quay lại", callback_data="backtocfm")])
    return InlineKeyboardMarkup(rows)


def kb_currency():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇻🇳 VND", callback_data="newcurr|VND"),
        InlineKeyboardButton("🇺🇸 USD", callback_data="newcurr|USD"),
    ]])


# ── Helpers ─────────────────────────────────────────────────────

def is_authorized(update: Update) -> bool:
    return update.effective_user.id in ALLOWED_IDS


def confirm_text(txs: list) -> str:
    msg = "✅ *Xác nhận giao dịch:*\n\n"
    for i, tx in enumerate(txs, 1):
        msg += f"{i}. *{tx['source']}* · {fmt_amount(tx['amount'], tx['currency'])}\n"
        msg += f"   📂 {tx['category']} · _{tx['reason']}_\n\n"
    msg += "Nhấn vào category để chỉnh sửa nếu cần nhé em bé 👇"
    return msg


async def show_confirm(query, context):
    txs = context.user_data["txs"]
    await query.edit_message_text(
        confirm_text(txs),
        parse_mode="Markdown",
        reply_markup=kb_confirm(txs)
    )
    return CONFIRM_ALL


# ── Entry: parse transactions ────────────────────────────────────

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "Nhập chi tiêu vào đây em bé 👇\n\n"
        "`15k ăn trưa`\n`5$ netflix`\n`200k grab`\n\n"
        "_(Có thể nhập nhiều dòng cùng lúc)_",
        parse_mode="Markdown"
    )
    return COLLECT_TX


async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return ConversationHandler.END

    txs = parse_transactions(update.message.text)
    if not txs:
        await update.message.reply_text(
            "Em bé ơi, không hiểu ý 😅\n\nNhập theo dạng:\n"
            "`15k ăn trưa`\n`5$ netflix`\n`200k grab`\n\n"
            "Gõ /help để xem danh sách lệnh nhé!",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["txs"]    = txs
    context.user_data["tx_idx"] = 0

    summary = "📝 Em bé nhận được:\n\n"
    for i, tx in enumerate(txs, 1):
        summary += f"{i}. `{fmt_amount(tx['amount'], tx['currency'])}` · {tx['reason']} → _{tx['category']}_\n"
    summary += f"\nChọn nguồn tiền cho giao dịch 1 · _{txs[0]['reason']}_"

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=kb_sources(0)
    )
    return ASK_SOURCE


# ── Source selection ─────────────────────────────────────────────

async def handle_source_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("|")
    action = parts[0]

    if action == "src":
        tx_idx      = int(parts[1])
        source_name = "|".join(parts[2:])  # handle names with |
        context.user_data["txs"][tx_idx]["source"] = source_name
        record_source_use(source_name)

        next_idx = tx_idx + 1
        context.user_data["tx_idx"] = next_idx
        txs = context.user_data["txs"]

        if next_idx < len(txs):
            tx = txs[next_idx]
            await query.edit_message_text(
                f"Chọn nguồn cho giao dịch {next_idx + 1} · _{tx['reason']}_\n"
                f"`{fmt_amount(tx['amount'], tx['currency'])}`",
                parse_mode="Markdown",
                reply_markup=kb_sources(next_idx)
            )
            return ASK_SOURCE
        else:
            return await show_confirm(query, context)

    elif action == "newsrc":
        context.user_data["adding_src_for"] = int(parts[1])
        await query.edit_message_text("Tên nguồn tiền mới là gì em bé? 💳")
        return ADD_SOURCE_NAME


async def add_source_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_src_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"*{context.user_data['new_src_name']}* dùng loại tiền nào?",
        parse_mode="Markdown",
        reply_markup=kb_currency()
    )
    return ADD_SOURCE_CURRENCY


async def add_source_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    currency = query.data.split("|")[1]
    name     = context.user_data["new_src_name"]
    tx_idx   = context.user_data["adding_src_for"]

    sources = load_sources()
    sources.insert(0, {"name": name, "currency": currency, "uses": 1})
    save_sources(sources)

    context.user_data["txs"][tx_idx]["source"] = name
    next_idx = tx_idx + 1
    context.user_data["tx_idx"] = next_idx
    txs = context.user_data["txs"]

    if next_idx < len(txs):
        tx = txs[next_idx]
        await query.edit_message_text(
            f"✅ Đã thêm *{name}* ({currency})!\n\n"
            f"Chọn nguồn cho giao dịch {next_idx + 1} · _{tx['reason']}_",
            parse_mode="Markdown",
            reply_markup=kb_sources(next_idx)
        )
        return ASK_SOURCE
    else:
        return await show_confirm(query, context)


# ── Confirm + Edit ───────────────────────────────────────────────

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("|")
    action = parts[0]

    if action == "save":
        txs = context.user_data["txs"]
        try:
            ws  = get_sheet()
            stt = len(ws.get_all_values())
            now = datetime.now()
            rows = []
            for tx in txs:
                rows.append([
                    stt,
                    now.strftime("%d/%m/%Y"),
                    now.strftime("%H:%M"),
                    tx["source"],
                    tx["amount"],
                    tx["currency"],
                    tx["category"],
                    tx["reason"],
                    ""
                ])
                stt += 1
            ws.append_rows(rows, value_input_option="RAW")

            msg = f"✅ *Đã lưu {len(txs)} giao dịch!*\n\n"
            for tx in txs:
                msg += f"• {tx['source']} · {fmt_amount(tx['amount'], tx['currency'])} · {tx['category']}\n"
            await query.edit_message_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Sheet error: {e}")
            await query.edit_message_text(f"❌ Lỗi khi lưu: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    elif action == "cancel":
        await query.edit_message_text("❌ Đã hủy.")
        context.user_data.clear()
        return ConversationHandler.END

    elif action == "editcat":
        tx_idx = int(parts[1])
        context.user_data["editing_tx"] = tx_idx
        tx = context.user_data["txs"][tx_idx]
        await query.edit_message_text(
            f"Đổi category cho _{tx['reason']}_\nHiện tại: *{tx['category']}*",
            parse_mode="Markdown",
            reply_markup=kb_categories(tx_idx)
        )
        return EDIT_CAT


async def handle_edit_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("|")
    action = parts[0]

    if action == "setcat":
        tx_idx   = int(parts[1])
        cat_idx  = int(parts[2])
        new_cat  = CAT_LIST[cat_idx]
        old_cat  = context.user_data["txs"][tx_idx]["category"]
        context.user_data["txs"][tx_idx]["category"] = new_cat
        if new_cat != old_cat:
            learn_keyword(context.user_data["txs"][tx_idx]["reason"], new_cat)
        return await show_confirm(query, context)

    elif action == "customcat":
        tx_idx = int(parts[1])
        context.user_data["editing_tx"] = tx_idx
        await query.edit_message_text(
            "Nhập tên category mới em bé muốn dùng:"
        )
        return EDIT_CAT_CUSTOM

    elif action == "backtocfm":
        return await show_confirm(query, context)


async def handle_custom_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_cat = update.message.text.strip()
    tx_idx  = context.user_data["editing_tx"]
    old_cat = context.user_data["txs"][tx_idx]["category"]
    context.user_data["txs"][tx_idx]["category"] = new_cat
    if new_cat != old_cat:
        learn_keyword(context.user_data["txs"][tx_idx]["reason"], new_cat)
        # Add to CATEGORIES if truly new
        if new_cat not in CATEGORIES:
            CATEGORIES[new_cat] = []
            CAT_LIST.append(new_cat)

    txs = context.user_data["txs"]
    await update.message.reply_text(
        confirm_text(txs),
        parse_mode="Markdown",
        reply_markup=kb_confirm(txs)
    )
    return CONFIRM_ALL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Đã hủy em bé nhé!")
    return ConversationHandler.END


# ── Summary commands ────────────────────────────────────────────

HELP_TEXT = (
    "*Quinn Finance Bot* 💜\n\n"
    "*Ghi chi tiêu:*\n"
    "Nhập thẳng vào chat, ví dụ:\n"
    "`15k ăn trưa`\n"
    "`5$ netflix`\n"
    "`200k grab` _(nhiều dòng cùng lúc được nhé)_\n\n"
    "*Lệnh:*\n"
    "/today — chi tiêu hôm nay\n"
    "/week — 7 ngày gần nhất\n"
    "/month — tổng tháng này\n"
    "/analyze — AI phân tích chi tiêu\n"
    "/src — quản lý nguồn tiền\n"
    "/cancel — hủy thao tác đang làm"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


def kb_sources_manage():
    sources = load_sources()
    rows = []
    for i, s in enumerate(sources):
        rows.append([
            InlineKeyboardButton(
                f"{s['name']} ({s['currency']}) — {s.get('uses', 0)} lần",
                callback_data="noop"
            ),
            InlineKeyboardButton("🗑️", callback_data=f"delsrc|{i}"),
        ])
    rows.append([InlineKeyboardButton("✅ Xong", callback_data="closesrc")])
    return InlineKeyboardMarkup(rows)


async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sources = load_sources()
    if not sources:
        await update.message.reply_text("Chưa có nguồn tiền nào em bé ơi.")
        return
    await update.message.reply_text(
        "*Nguồn tiền đã lưu:*\nNhấn 🗑️ để xóa",
        parse_mode="Markdown",
        reply_markup=kb_sources_manage()
    )


async def handle_delete_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("|")
    action = parts[0]

    if action == "noop":
        return

    if action == "closesrc":
        await query.delete_message()
        return

    idx     = int(parts[1])
    sources = load_sources()
    if idx < len(sources):
        removed = sources.pop(idx)
        save_sources(sources)
        if sources:
            await query.edit_message_text(
                "*Nguồn tiền đã lưu:*\nNhấn 🗑️ để xóa",
                parse_mode="Markdown",
                reply_markup=kb_sources_manage()
            )
        else:
            await query.edit_message_text(
                f"✅ Đã xóa *{removed['name']}*. Chưa còn nguồn nào.",
                parse_mode="Markdown"
            )


def _get_rows_for_period(rows, days=None):
    today = datetime.now()
    result = []
    for r in rows:
        if len(r) < 8:
            continue
        try:
            if days is None or (today - datetime.strptime(r[1], "%d/%m/%Y")).days <= days - 1:
                result.append(r)
        except Exception:
            continue
    return result


def _summarize(rows, title):
    valid = [r for r in rows if len(r) >= 8 and str(r[4]).replace(".", "").isdigit()]
    if not valid:
        return f"{title}\n\nChưa có giao dịch nào."

    total_vnd, total_usd = 0, 0.0
    by_cat = {}
    for r in valid:
        amt      = float(r[4])
        currency = r[5] if len(r) > 5 and r[5] in ("VND", "USD") else "VND"
        cat      = r[6] if len(r) > 6 else "Khác"
        key      = f"{cat} ({currency})"
        by_cat[key] = by_cat.get(key, 0) + amt
        if currency == "USD":
            total_usd += amt
        else:
            total_vnd += int(amt)

    msg = f"*{title}*\n\n"
    for c, a in sorted(by_cat.items(), key=lambda x: -x[1]):
        if "USD" in c:
            msg += f"• {c}: `${a:.2f}`\n"
        else:
            msg += f"• {c}: `{fmt_amount(int(a), 'VND')}`\n"

    if total_vnd:
        msg += f"\n💰 VND: `{total_vnd:,}đ`".replace(",", ".")
    if total_usd:
        msg += f"\n💵 USD: `${total_usd:.2f}`"
    return msg


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws    = get_sheet()
        rows  = ws.get_all_values()[1:]
        today = datetime.now().strftime("%d/%m/%Y")
        rows  = [r for r in rows if len(r) >= 2 and r[1] == today]
        await update.message.reply_text(
            _summarize(rows, f"Hôm nay ({today})"), parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Lỗi: {e}")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws   = get_sheet()
        rows = _get_rows_for_period(ws.get_all_values()[1:], days=7)
        await update.message.reply_text(
            _summarize(rows, "7 ngày gần nhất"), parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Lỗi: {e}")


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws   = get_sheet()
        rows = ws.get_all_values()[1:]
        month = datetime.now().strftime("%m/%Y")
        await update.message.reply_text(
            _summarize(rows, f"Tháng {month}"), parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"Lỗi: {e}")


# ── AI Analysis ─────────────────────────────────────────────────

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return ConversationHandler.END
    await update.message.reply_text("🤖 Đang phân tích chi tiêu tháng này...")
    try:
        ws   = get_sheet()
        rows = ws.get_all_values()[1:]
        if not rows:
            await update.message.reply_text("Tháng này chưa có giao dịch nào.")
            return ConversationHandler.END

        by_cat = {}
        detail = []
        for r in rows:
            if len(r) < 8 or not str(r[4]).replace(".", "").isdigit():
                continue
            amt      = float(r[4])
            currency = r[5] if len(r) > 5 and r[5] in ("VND", "USD") else "VND"
            cat      = r[6] if len(r) > 6 else "Khác"
            key      = f"{cat} ({currency})"
            by_cat[key] = by_cat.get(key, 0) + amt
            detail.append(f"  {r[1]} | {cat} | {r[7]} | {amt} {currency}")

        month   = datetime.now().strftime("%m/%Y")
        summary = f"Tháng {month}\n\nTheo category:\n"
        for c, a in sorted(by_cat.items(), key=lambda x: -x[1]):
            suffix = f"${a:.2f}" if "USD" in c else f"{int(a):,}đ"
            summary += f"  {c}: {suffix}\n"
        summary += "\nChi tiết:\n" + "\n".join(detail)

        prompt = (
            "You are a personal finance advisor. Here is my spending data:\n\n"
            f"{summary}\n\n"
            "Please provide:\n"
            "1. Analysis of spending patterns (what's good/not good)\n"
            "2. 2-3 specific actionable tips to optimize spending\n"
            "3. Estimated potential savings per month\n\n"
            "Reply in Vietnamese, concise and friendly."
        )

        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        clean    = re.sub(r"\*{1,2}|_{1,2}|`{1,3}", "", response.text)

        context.user_data["analyze_summary"] = summary
        context.user_data["analyze_history"] = [
            {"role": "user", "text": prompt},
            {"role": "model", "text": response.text},
        ]

        await update.message.reply_text(
            f"🤖 Phân tích AI\n\n{clean}\n\n"
            "💬 Hỏi thêm bất cứ điều gì, hoặc /cancel để thoát."
        )
        return ANALYZE_CHAT
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        await update.message.reply_text(f"❌ Lỗi phân tích: {e}")
        return ConversationHandler.END


async def handle_analyze_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return ConversationHandler.END

    user_msg = update.message.text.strip()
    history  = context.user_data.get("analyze_history", [])
    summary  = context.user_data.get("analyze_summary", "")

    conv_text = (
        "You are a personal finance advisor. Here is the user's spending data for context:\n\n"
        f"{summary}\n\nConversation so far:\n"
    )
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        conv_text += f"{role}: {msg['text']}\n\n"
    conv_text += f"User: {user_msg}\n\nReply in Vietnamese, concise and friendly."

    try:
        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=conv_text)
        clean    = re.sub(r"\*{1,2}|_{1,2}|`{1,3}", "", response.text)

        history.append({"role": "user",  "text": user_msg})
        history.append({"role": "model", "text": response.text})
        context.user_data["analyze_history"] = history

        await update.message.reply_text(clean)
        return ANALYZE_CHAT
    except Exception as e:
        logger.error(f"Analyze chat error: {e}")
        await update.message.reply_text(f"❌ Lỗi: {e}")
        return ANALYZE_CHAT


# ── Daily reminder ──────────────────────────────────────────────

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=YOUR_CHAT_ID,
        text="Ngày hôm nay của em bé dài rồi, nhưng đừng quên ghi chép chi tiêu nhé 💜"
    )


# ── Main ────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", cmd_add),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input),
        ],
        states={
            COLLECT_TX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input),
            ],
            ASK_SOURCE: [
                CallbackQueryHandler(handle_source_btn, pattern=r"^(src|newsrc)\|"),
            ],
            ADD_SOURCE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_source_name),
            ],
            ADD_SOURCE_CURRENCY: [
                CallbackQueryHandler(add_source_currency, pattern=r"^newcurr\|"),
            ],
            CONFIRM_ALL: [
                CallbackQueryHandler(handle_confirm, pattern=r"^(save|cancel|editcat)\|"),
            ],
            EDIT_CAT: [
                CallbackQueryHandler(handle_edit_cat, pattern=r"^(setcat|customcat|backtocfm)"),
            ],
            EDIT_CAT_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_cat),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    analyze_conv = ConversationHandler(
        entry_points=[CommandHandler("analyze", cmd_analyze)],
        states={
            ANALYZE_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_analyze_chat),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("today",   cmd_today))
    app.add_handler(CommandHandler("week",    cmd_week))
    app.add_handler(CommandHandler("month",   cmd_month))
    app.add_handler(CommandHandler("src",     cmd_sources))
    app.add_handler(CallbackQueryHandler(handle_delete_source, pattern=r"^(delsrc|noop|closesrc)"))
    app.add_handler(analyze_conv)
    app.add_handler(conv)

    # 23:30 GMT+7 = 16:30 UTC
    app.job_queue.run_daily(daily_reminder, time=dtime(hour=16, minute=30, tzinfo=timezone.utc))

    print("Quinn Finance Bot v2 dang chay...")
    app.run_polling()


if __name__ == "__main__":
    main()
