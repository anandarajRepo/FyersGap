"""
FyersGap — Simplified symbol manager for Gap strategy.

Manages symbol mappings for gap detection and trading strategy.
Fyers WebSocket format: "NSE:<TICKER>-EQ"
"""

from __future__ import annotations
from typing import Dict


class GapSymbolManager:
    """Simplified symbol manager for Gap strategy — just symbol mappings"""

    def __init__(self):
        # Simple mapping: symbol -> Fyers WebSocket format
        self._symbol_mappings: Dict[str, str] = {
            # Upstream Energy — Clear Winners
            "ONGC": "NSE:ONGC-EQ",
            "OIL": "NSE:OIL-EQ",
            "GAIL": "NSE:GAIL-EQ",

            # Jewellery Retail
            "TITAN": "NSE:TITAN-EQ",
            "KALYANKJIL": "NSE:KALYANKJIL-EQ",
            "PCJEWELLER": "NSE:PCJEWELLER-EQ",
            "PNGBL": "NSE:PNGBL-EQ",
            "THANGAMAYL": "NSE:THANGAMAYL-EQ",

            # Gold-loan NBFCs
            "MUTHOOTFIN": "NSE:MUTHOOTFIN-EQ",      # Muthoot Finance – large gold‑loan NBFC
            "MANAPPURAM": "NSE:MANAPPURAM-EQ",      # Manappuram Finance – big gold‑loan NBFC

            # Favourite Stocks
            "STLTECH": "NSE:STLTECH-EQ",
            "SKYGOLD": "NSE:SKYGOLD-EQ",
            "AXISCADES": "NSE:AXISCADES-EQ",
        }

    def get_all_symbols(self) -> list[str]:
        """Return list of all plain ticker symbols."""
        return list(self._symbol_mappings.keys())

    def get_fyers_symbol(self, ticker: str) -> str:
        """
        Get Fyers WebSocket format for a symbol.

        Args:
            ticker: Plain NSE ticker (e.g., "ONGC")

        Returns:
            Fyers format string (e.g., "NSE:ONGC-EQ")
        """
        ticker = ticker.strip().upper()
        return self._symbol_mappings.get(ticker, f"NSE:{ticker}-EQ")

    def get_all_fyers_symbols(self) -> list[str]:
        """Return list of all Fyers WebSocket format symbols."""
        return list(self._symbol_mappings.values())

    def is_valid_symbol(self, ticker: str) -> bool:
        """Check if a ticker is in the managed symbols list."""
        return ticker.strip().upper() in self._symbol_mappings

    def normalize(self, symbol: str) -> str:
        """Uppercase and strip whitespace."""
        return symbol.strip().upper()


# Module-level convenience instance and functions
_manager = GapSymbolManager()


def get_all_symbols() -> list[str]:
    """Return list of all plain ticker symbols."""
    return _manager.get_all_symbols()


def get_fyers_symbol(ticker: str) -> str:
    """Get Fyers WebSocket format for a symbol."""
    return _manager.get_fyers_symbol(ticker)


def get_all_fyers_symbols() -> list[str]:
    """Return list of all Fyers WebSocket format symbols."""
    return _manager.get_all_fyers_symbols()


def is_valid_symbol(ticker: str) -> bool:
    """Check if a ticker is in the managed symbols list."""
    return _manager.is_valid_symbol(ticker)


def to_fyers_format(ticker: str) -> str:
    """Alias for get_fyers_symbol - convert plain ticker to Fyers format."""
    return _manager.get_fyers_symbol(ticker)


def from_fyers_format(fyers_symbol: str) -> str | None:
    """Extract plain ticker from Fyers format (e.g., 'NSE:ONGC-EQ' → 'ONGC')."""
    if not fyers_symbol:
        return None
    try:
        # Expected format: "NSE:TICKER-EQ"
        parts = fyers_symbol.split(":")
        if len(parts) != 2:
            return None
        ticker_part = parts[1].split("-")
        return ticker_part[0] if ticker_part else None
    except (IndexError, AttributeError):
        return None
