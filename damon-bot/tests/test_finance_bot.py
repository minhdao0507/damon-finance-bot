"""
Unit tests for pure functions in damon-bot/finance_bot.py.
No Telegram, no Google Sheets, no network required.
"""
import os
import sys
import types
import pytest
from unittest.mock import patch

# ── Set required env vars before import ─────────────────────────
os.environ.setdefault("BOT_TOKEN",      "fake-token")
os.environ.setdefault("SHEET_ID",       "fake-sheet")
os.environ.setdefault("YOUR_CHAT_ID",   "12345678")
os.environ.setdefault("GEMINI_API_KEY", "fake-key")

# ── Stub heavy optional imports ──────────────────────────────────

class _Dummy:
    """Recursive dummy: any attribute access returns another _Dummy."""
    def __getattr__(self, name):
        return _Dummy()
    def __call__(self, *args, **kwargs):
        return _Dummy()
    def __iter__(self):
        return iter([])

_DUMMY = _Dummy()

def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: _DUMMY
    return m

for mod in [
    "telegram", "telegram.ext",
    "gspread", "gspread.utils",
    "google", "google.genai",
    "google.oauth2", "google.oauth2.service_account",
]:
    sys.modules.setdefault(mod, _stub(mod))

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from finance_bot import parse_line, parse_transactions, auto_categorize, fmt


# ── parse_line ───────────────────────────────────────────────────

class TestParseLine:
    def test_raw_number(self):
        amount, reason = parse_line("50000 ăn trưa")
        assert amount == 50_000
        assert reason == "ăn trưa"

    def test_k_unit(self):
        amount, reason = parse_line("50k ăn trưa")
        assert amount == 50_000

    def test_m_unit(self):
        amount, reason = parse_line("1m tiền nhà")
        assert amount == 1_000_000

    def test_tr_unit(self):
        amount, reason = parse_line("2tr tiền nhà")
        assert amount == 2_000_000

    def test_decimal_k(self):
        amount, reason = parse_line("1.5k trà sữa")
        assert amount == 1_500

    def test_multi_word_reason(self):
        amount, reason = parse_line("30k ăn sáng bánh mì")
        assert amount == 30_000
        assert "bánh mì" in reason

    def test_uppercase_unit(self):
        amount, reason = parse_line("100K café")
        assert amount == 100_000

    def test_empty_returns_none(self):
        assert parse_line("") == (None, None)
        assert parse_line("   ") == (None, None)

    def test_no_amount_returns_none(self):
        assert parse_line("ăn trưa") == (None, None)

    def test_text_only_returns_none(self):
        assert parse_line("không phải tiền") == (None, None)


# ── parse_transactions ───────────────────────────────────────────

class TestParseTransactions:
    @patch("finance_bot.load_learned", return_value={})
    def test_single_line(self, _):
        txs = parse_transactions("50k ăn trưa")
        assert len(txs) == 1
        assert txs[0]["amount"] == 50_000
        assert txs[0]["currency"] == "VND"
        assert txs[0]["source"] is None

    @patch("finance_bot.load_learned", return_value={})
    def test_multiline(self, _):
        txs = parse_transactions("50k ăn trưa\n30k café\n20k gửi xe")
        assert len(txs) == 3
        assert txs[1]["amount"] == 30_000

    @patch("finance_bot.load_learned", return_value={})
    def test_invalid_lines_skipped(self, _):
        txs = parse_transactions("50k ăn trưa\nkhông phải tiền\n30k café")
        assert len(txs) == 2

    @patch("finance_bot.load_learned", return_value={})
    def test_empty_string(self, _):
        assert parse_transactions("") == []

    @patch("finance_bot.load_learned", return_value={})
    def test_category_auto_assigned(self, _):
        txs = parse_transactions("50k grab về nhà")
        assert txs[0]["category"] == "Di chuyển"


# ── auto_categorize ──────────────────────────────────────────────

class TestAutoCategorize:
    @patch("finance_bot.load_learned", return_value={})
    def test_food_keyword(self, _):
        assert auto_categorize("ăn trưa cơm gà") == "Ăn uống ngoài"

    @patch("finance_bot.load_learned", return_value={})
    def test_transport_grab(self, _):
        assert auto_categorize("grab về nhà") == "Di chuyển"

    @patch("finance_bot.load_learned", return_value={})
    def test_online_shopping(self, _):
        assert auto_categorize("shopee mua đồ") == "Đặt hàng online"

    @patch("finance_bot.load_learned", return_value={})
    def test_entertainment_karaoke(self, _):
        assert auto_categorize("đi karaoke với bạn") == "Giải trí"

    @patch("finance_bot.load_learned", return_value={})
    def test_unknown_falls_back_to_khac(self, _):
        assert auto_categorize("xyz123 không rõ danh mục") == "Khác"

    def test_learned_keyword_takes_priority(self):
        with patch("finance_bot.load_learned", return_value={"pizza": "Ăn uống ngoài"}):
            assert auto_categorize("pizza hut dinner") == "Ăn uống ngoài"

    @patch("finance_bot.load_learned", return_value={})
    def test_case_insensitive(self, _):
        assert auto_categorize("GRAB bike") == "Di chuyển"


# ── fmt ──────────────────────────────────────────────────────────

class TestFmt:
    def test_thousands(self):
        assert fmt(50_000) == "50.000đ"

    def test_millions(self):
        assert fmt(1_000_000) == "1.000.000đ"

    def test_zero(self):
        assert fmt(0) == "0đ"

    def test_small(self):
        assert fmt(1_000) == "1.000đ"
