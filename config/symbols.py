"""
FyersGap — Trading universe management.

Symbols are stored as plain NSE ticker strings.
Use `get_all_symbols()` to retrieve the full watchlist and
`to_fyers_format(symbol)` to convert to the Fyers API symbol string.

Fyers symbol format for NSE cash equities: "NSE:<TICKER>-EQ"
Example: "NSE:RELIANCE-EQ"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Watchlist — ~150 liquid NSE stocks grouped by sector
# ---------------------------------------------------------------------------

_WATCHLIST: dict[str, list[str]] = {
    "Energy": [
        "RELIANCE", "ONGC", "IOC", "BPCL", "HPCL",
        "GAIL", "PETRONET", "IGL", "MGL", "GSPL",
    ],
    "Renewables": [
        "ADANIGREEN", "TATAPOWER", "CESC", "TORNTPOWER", "NTPC",
        "POWERGRID", "SJVN", "NHPC", "INOXGREEN",
    ],
    "Defense": [
        "HAL", "BEL", "BEML", "BHEL", "MIDHANI",
        "PARAS", "MTAR", "COCHINSHIP", "GARDENREACH",
    ],
    "Pharma": [
        "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA",
        "LUPIN", "BIOCON", "IPCALAB", "ALKEM", "GLENMARK",
    ],
    "IT": [
        "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
        "LTIM", "MPHASIS", "PERSISTENT", "COFORGE", "KPIT",
    ],
    "Auto": [
        "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT",
        "HEROMOTOCO", "TVSMOTORS", "ASHOKLEY", "TVSMOTOR", "MOTHERSON",
    ],
    "Banking": [
        "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
        "BANKBARODA", "PNB", "CANBK", "FEDERALBNK", "IDFCFIRSTB",
    ],
    "NBFC": [
        "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN",
        "MANAPPURAM", "M&MFIN", "LICHOUSFIN", "HDFCAMC",
    ],
    "FMCG": [
        "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR",
        "MARICO", "GODREJCP", "EMAMILTD", "COLPAL",
    ],
    "Metals": [
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "COALINDIA",
        "NMDC", "MOIL", "NATIONALUM", "SAIL",
    ],
    "Cement": [
        "ULTRACEMCO", "AMBUJACEM", "ACC", "SHREECEM", "RAMCOCEM",
        "JKCEMENT", "HEIDELBERG",
    ],
    "Paints": [
        "ASIANPAINT", "BERGEPAINT", "KANSAINER", "INDIGO",
    ],
    "Chemicals": [
        "PIDILITIND", "AARTIIND", "DEEPAKNTR", "GNFC", "TATACHEMICALS",
        "ALKYLAMINE", "NAVINFLUOR",
    ],
    "Infrastructure": [
        "LT", "ADANIPORTS", "ADANIENTER", "IRB", "KNR",
        "NBCC", "RVNL", "IRFC",
    ],
    "Telecom": [
        "BHARTIARTL", "IDEA",
    ],
    "Consumer_Durables": [
        "HAVELLS", "VOLTAS", "BLUESTAR", "POLYCAB", "KEI",
        "VGUARD", "CROMPTON",
    ],
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_all_symbols() -> list[str]:
    """Return flat list of all symbols in the watchlist."""
    symbols = []
    for sector_symbols in _WATCHLIST.values():
        symbols.extend(sector_symbols)
    return list(dict.fromkeys(symbols))  # deduplicate, preserve order


def get_symbols_by_sector(sector: str) -> list[str]:
    return _WATCHLIST.get(sector, [])


def get_sectors() -> list[str]:
    return list(_WATCHLIST.keys())


def to_fyers_format(symbol: str) -> str:
    """
    Convert a plain NSE ticker to the Fyers API symbol string.

    Fyers uses "NSE:<TICKER>-EQ" for NSE cash equity instruments.
    Example: "RELIANCE" → "NSE:RELIANCE-EQ"
    """
    return f"NSE:{symbol.strip().upper()}-EQ"


def from_fyers_format(fyers_symbol: str) -> str:
    """
    Extract the plain NSE ticker from a Fyers symbol string.
    Example: "NSE:RELIANCE-EQ" → "RELIANCE"
    """
    # Strip "NSE:" prefix and "-EQ" suffix
    ticker = fyers_symbol.upper()
    if ticker.startswith("NSE:"):
        ticker = ticker[4:]
    if ticker.endswith("-EQ"):
        ticker = ticker[:-3]
    return ticker


def normalize(symbol: str) -> str:
    """Uppercase and strip whitespace."""
    return symbol.strip().upper()
