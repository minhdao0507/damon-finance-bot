"""
market_digest.py — Daily 5:45 AM market summary.

Verified sources:
  World gold   : yfinance GC=F (no key needed)
  Vietnam gold : yfinance estimate (world price × USD/VND × 1.02) — reference only
  Khối ngoại   : vnstock VN30 price_board, sorted by foreign buy/sell value
  Tự doanh     : no public API available → skipped
  BĐS          : cafef.vn/bat-dong-san.chn top headlines
  Keywords     : cafef.vn homepage top finance/business headlines
"""

import re
import warnings
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

_H = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9",
}
_T = 12


def _get(url: str, **kwargs) -> requests.Response:
    return requests.get(url, headers=_H, timeout=_T, **kwargs)


# ── 1. World gold & Vietnam gold estimate ────────────────────────

def fetch_gold() -> tuple[str, str]:
    """
    Returns (world_str, vietnam_str).
    Vietnam price is estimated from world price + USD/VND rate, not exact SJC retail.
    """
    try:
        import yfinance as yf
        gold_usd = yf.Ticker("GC=F").fast_info.last_price
        usd_vnd  = yf.Ticker("USDVND=X").fast_info.last_price
        world_str = f"${gold_usd:,.1f}/oz"
        # 1 lượng = 37.5g, 1 troy oz = 31.1035g → 1 lượng ≈ 1.2057 troy oz
        # +2% retail/premium buffer
        vnd_per_luong = gold_usd * (37.5 / 31.1035) * usd_vnd * 1.02
        vn_str = f"~{vnd_per_luong / 1_000_000:.1f}M đ/lượng \\(tham chiếu\\)"
        return world_str, vn_str
    except Exception:
        return "N/A", "N/A"


# ── 2. Khối ngoại (foreign investor) ────────────────────────────

def fetch_foreign_trading(top_n: int = 10) -> dict[str, list[str]]:
    """
    Uses vnstock VN30 price_board to find top foreign buy/sell stocks.
    Scope is VN30 only (most liquid stocks where foreigners are active).
    """
    try:
        from vnstock.api.listing import Listing
        from vnstock.api.trading import Trading

        vn30 = Listing(source="VCI").symbols_by_group(group="VN30").tolist()
        t    = Trading(symbol=vn30[0], source="VCI")
        df   = t.price_board(symbols_list=vn30)

        df.columns = ["_".join(c) for c in df.columns]
        sym = "listing_symbol"
        fbv = "match_foreign_buy_value"
        fsv = "match_foreign_sell_value"

        buy_top  = df.nlargest(top_n, fbv)[sym].tolist()
        sell_top = df.nlargest(top_n, fsv)[sym].tolist()
        return {"buy": buy_top, "sell": sell_top}
    except Exception:
        return {"buy": [], "sell": []}


# ── 3. BĐS hot headlines ─────────────────────────────────────────

def fetch_bds_headlines(top_n: int = 5) -> list[str]:
    """Top headlines from cafef.vn real estate section."""
    try:
        r    = _get("https://cafef.vn/bat-dong-san.chn")
        soup = BeautifulSoup(r.text, "lxml")
        results = []
        for tag in soup.find_all(["h2", "h3"]):
            title = tag.get_text(strip=True)
            if title and len(title) > 20 and title not in results:
                results.append(title)
            if len(results) >= top_n:
                break
        return results
    except Exception:
        return []


# ── 4. Business/investment keywords ─────────────────────────────

_FINANCE_WORDS = {
    "vàng", "chứng khoán", "cổ phiếu", "đầu tư", "ngân hàng", "lãi suất",
    "bất động sản", "tỷ giá", "lạm phát", "gdp", "tăng trưởng", "thị trường",
    "kinh doanh", "doanh nghiệp", "xuất khẩu", "nhập khẩu", "fdi", "ipo",
    "quỹ", "trái phiếu", "crypto", "bitcoin", "fintech",
}


def fetch_keywords(top_n: int = 3) -> list[str]:
    """Top finance/business headlines from cafef.vn homepage."""
    try:
        r    = _get("https://cafef.vn/")
        soup = BeautifulSoup(r.text, "lxml")
        scored = []
        for tag in soup.find_all(["h2", "h3"]):
            title = tag.get_text(strip=True)
            if not title or len(title) < 20:
                continue
            score = sum(1 for w in _FINANCE_WORDS if w in title.lower())
            if score > 0:
                scored.append((score, title))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Deduplicate and take top_n
        seen, results = set(), []
        for _, title in scored:
            key = title[:40]
            if key not in seen:
                seen.add(key)
                results.append(title)
            if len(results) >= top_n:
                break
        return results
    except Exception:
        return []


# ── Escape MarkdownV2 special chars ──────────────────────────────

_MDV2_SPECIAL = re.compile(r"([_\*\[\]()~`>#+\-=|{}.!\\])")


def _esc(text: str) -> str:
    return _MDV2_SPECIAL.sub(r"\\\1", text)


# ── Assemble digest ──────────────────────────────────────────────

def build_digest() -> str:
    world_gold, vn_gold = fetch_gold()
    foreign   = fetch_foreign_trading()
    bds       = fetch_bds_headlines()
    keywords  = fetch_keywords()

    buy_str  = ", ".join(foreign["buy"])  or "N/A"
    sell_str = ", ".join(foreign["sell"]) or "N/A"

    parts = [
        "📊 *Tổng quan thị trường sáng nay*\n",

        "🥇 *Giá vàng*",
        f"  • Thế giới \\(bán\\): {_esc(world_gold)}",
        f"  • Việt Nam \\(tham chiếu\\): {vn_gold}",

        "",
        "🌏 *Khối ngoại — VN30*",
        f"  Mua nhiều nhất: {_esc(buy_str)}",
        f"  Bán nhiều nhất: {_esc(sell_str)}",

        "",
        "🏠 *BĐS — tin nổi bật*",
    ]
    for i, h in enumerate(bds, 1):
        parts.append(f"  {i}\\. {_esc(h)}")
    if not bds:
        parts.append("  N/A")

    parts += ["", "🔍 *Chủ đề kinh doanh/đầu tư hôm nay*"]
    for i, kw in enumerate(keywords, 1):
        parts.append(f"  {i}\\. {_esc(kw)}")
    if not keywords:
        parts.append("  N/A")

    return "\n".join(parts)
