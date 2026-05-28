"""
Unit tests for pure functions in quinn-bot/finance_bot.py.
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
from finance_bot import parse_line, parse_transactions, auto_categorize, fmt_amount


# ── parse_line ───────────────────────────────────────────────────

class TestParseLine:
    def test_vnd_raw_number(self):
        amount, currency, reason = parse_line("50000 ăn trưa")
        assert amount == 50_000
        assert currency == "VND"
        assert reason == "ăn trưa"

    def test_vnd_k_unit(self):
        amount, currency, reason = parse_line("50k ăn trưa")
        assert amount == 50_000
        assert currency == "VND"

    def test_vnd_m_unit(self):
        amount, currency, reason = parse_line("1m tiền nhà")
        assert amount == 1_000_000
        assert currency == "VND"

    def test_vnd_explicit_currency(self):
        amount, currency, reason = parse_line("15k vnd ăn trưa")
        assert amount == 15_000
        assert currency == "VND"

    def test_usd_dollar_prefix(self):
        amount, currency, reason = parse_line("$5 netflix")
        assert amount == 5.0
        assert currency == "USD"
        assert reason == "netflix"

    def test_usd_dollar_suffix(self):
        amount, currency, reason = parse_line("5$ netflix")
        assert amount == 5.0
        assert currency == "USD"

    def test_usd_explicit_currency(self):
        amount, currency, reason = parse_line("10 usd chatgpt")
        assert amount == 10
        assert currency == "USD"

    def test_decimal_usd(self):
        amount, currency, reason = parse_line("$9.99 spotify")
        assert abs(amount - 9.99) < 0.001
        assert currency == "USD"

    def test_empty_returns_none_triple(self):
        assert parse_line("") == (None, None, None)
        assert parse_line("   ") == (None, None, None)

    def test_no_amount_returns_none(self):
        assert parse_line("ăn trưa") == (None, None, None)

    def test_uppercase_unit(self):
        amount, currency, reason = parse_line("100K café")
        assert amount == 100_000
        assert currency == "VND"


# ── parse_transactions ───────────────────────────────────────────

class TestParseTransactions:
    @patch("finance_bot.load_learned", return_value={})
    def test_single_vnd(self, _):
        txs = parse_transactions("50k ăn trưa")
        assert len(txs) == 1
        assert txs[0]["amount"] == 50_000
        assert txs[0]["currency"] == "VND"

    @patch("finance_bot.load_learned", return_value={})
    def test_single_usd(self, _):
        txs = parse_transactions("$5 netflix")
        assert len(txs) == 1
        assert txs[0]["currency"] == "USD"

    @patch("finance_bot.load_learned", return_value={})
    def test_mixed_currencies(self, _):
        txs = parse_transactions("50k ăn trưa\n$5 netflix")
        assert len(txs) == 2
        assert txs[0]["currency"] == "VND"
        assert txs[1]["currency"] == "USD"

    @patch("finance_bot.load_learned", return_value={})
    def test_invalid_lines_skipped(self, _):
        txs = parse_transactions("50k ăn trưa\nkhông phải tiền\n$9 spotify")
        assert len(txs) == 2

    @patch("finance_bot.load_learned", return_value={})
    def test_empty_string(self, _):
        assert parse_transactions("") == []

    @patch("finance_bot.load_learned", return_value={})
    def test_source_is_none(self, _):
        txs = parse_transactions("50k grab")
        assert txs[0]["source"] is None


# ── auto_categorize ──────────────────────────────────────────────

class TestAutoCategorize:
    @patch("finance_bot.load_learned", return_value={})
    def test_food(self, _):
        assert auto_categorize("ăn trưa cơm") == "Ăn uống ngoài"

    @patch("finance_bot.load_learned", return_value={})
    def test_transport(self, _):
        assert auto_categorize("grab bike") == "Di chuyển"

    @patch("finance_bot.load_learned", return_value={})
    def test_entertainment_netflix(self, _):
        assert auto_categorize("netflix tháng này") == "Giải trí"

    @patch("finance_bot.load_learned", return_value={})
    def test_unknown(self, _):
        assert auto_categorize("xyz123 mơ hồ") == "Khác"

    def test_learned_takes_priority(self):
        with patch("finance_bot.load_learned", return_value={"starbucks": "Ăn uống ngoài"}):
            assert auto_categorize("starbucks latte") == "Ăn uống ngoài"

    @patch("finance_bot.load_learned", return_value={})
    def test_chatgpt_subscription(self, _):
        assert auto_categorize("chatgpt plus") == "Phí sinh hoạt"


# ── fmt_amount ────────────────────────────────────────────────────

class TestFmtAmount:
    def test_vnd_thousands(self):
        assert fmt_amount(50_000, "VND") == "50.000đ"

    def test_vnd_millions(self):
        assert fmt_amount(1_000_000, "VND") == "1.000.000đ"

    def test_usd_two_decimals(self):
        assert fmt_amount(5.0, "USD") == "$5.00"

    def test_usd_cents(self):
        assert fmt_amount(9.99, "USD") == "$9.99"

    def test_vnd_zero(self):
        assert fmt_amount(0, "VND") == "0đ"
