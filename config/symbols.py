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
