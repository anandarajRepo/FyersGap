"""
FyersGap — Fyers API v3 data service.

Wraps fyers-apiv3 to provide:
  - Historical OHLC data (daily candles via fyers.history())
  - Live quotes (LTP polling via fyers.quotes())
  - Previous day close price lookup

Fyers API response shapes
--------------------------
history()  → {"s": "ok", "candles": [[epoch, open, high, low, close, volume], ...]}
quotes()   → {"s": "ok", "d": [{"n": "NSE:X-EQ", "v": {"lp": ..., "vol": ...,
                                                          "ask": ..., "bid": ...}}]}

All methods return plain Python objects / dataclasses — no raw API dicts
leak into the rest of the system.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

from config.settings import settings
from config.symbols import to_fyers_format, from_fyers_format
from models.trading_models import DayOHLC, LiveQuote
from utils.logger import get_logger

logger = get_logger("fyers_data_service", settings.ops.log_level, settings.ops.log_file)

# Fyers quotes API accepts up to 50 symbols per request
_QUOTE_BATCH_SIZE = 50

# Retry parameters
_MAX_RETRIES = 4
_BASE_BACKOFF = 2  # seconds


def _retry(func, *args, **kwargs):
    """Synchronous retry with exponential backoff."""
    backoff = _BASE_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise
            logger.warning("Attempt %d failed (%s). Retrying in %ds…", attempt, exc, backoff)
            time.sleep(backoff)
            backoff *= 2


class FyersDataService:
    """
    Thin wrapper around fyers-apiv3 for price/quote data.

    Parameters
    ----------
    fyers_client : authenticated fyersModel.FyersModel instance
    """

    def __init__(self, fyers_client) -> None:
        self._client = fyers_client

    # ------------------------------------------------------------------
    # Historical OHLC
    # ------------------------------------------------------------------

    def get_historical_ohlc(
        self,
        symbol: str,
        days: int = 30,
    ) -> list[DayOHLC]:
        """
        Fetch `days` trading days of daily OHLC for *symbol*.

        Uses fyers.history() with resolution "D" (daily).
        Returns a list sorted oldest → newest.
        """
        to_date = datetime.now()
        # Add buffer for weekends/holidays so we always get enough trading days
        from_date = to_date - timedelta(days=days * 2)

        fyers_symbol = to_fyers_format(symbol)
        logger.debug("Fetching %d-day OHLC for %s (%s)", days, symbol, fyers_symbol)

        data = {
            "symbol": fyers_symbol,
            "resolution": "D",
            "date_format": "1",                        # epoch timestamps
            "range_from": int(from_date.timestamp()),
            "range_to": int(to_date.timestamp()),
            "cont_flag": "1",                          # continuous data
        }

        try:
            def _fetch():
                resp = self._client.history(data=data)
                if not isinstance(resp, dict):
                    raise ValueError(f"Unexpected response type: {type(resp)}")
                if resp.get("s") != "ok":
                    raise ValueError(f"Fyers history error: {resp.get('message', resp)}")
                return resp

            raw = _retry(_fetch)
        except Exception as exc:
            logger.error("get_historical_ohlc failed for %s: %s", symbol, exc)
            return []

        # candles: [[epoch, open, high, low, close, volume], ...]
        candles = raw.get("candles", [])
        bars: list[DayOHLC] = []
        for candle in candles:
            try:
                epoch, o, h, l, c, v = candle
                bars.append(DayOHLC(
                    symbol=symbol,
                    date=datetime.fromtimestamp(int(epoch)),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=int(v),
                ))
            except Exception as exc:
                logger.debug("Skipping malformed candle for %s: %s", symbol, exc)
                continue

        bars.sort(key=lambda b: b.date)
        return bars[-days:]  # return at most `days` bars

    # ------------------------------------------------------------------
    # Live quotes
    # ------------------------------------------------------------------

    def get_live_quote(self, symbol: str) -> Optional[LiveQuote]:
        """Fetch a single live quote for *symbol*."""
        fyers_symbol = to_fyers_format(symbol)
        try:
            def _fetch():
                resp = self._client.quotes(data={"symbols": fyers_symbol})
                if not isinstance(resp, dict):
                    raise ValueError(f"Unexpected response type: {type(resp)}")
                if resp.get("s") != "ok":
                    raise ValueError(f"Fyers quotes error: {resp.get('message', resp)}")
                return resp

            raw = _retry(_fetch)
            items = raw.get("d", [])
            if not items:
                return None
            v = items[0].get("v", {})
            return LiveQuote(
                symbol=symbol,
                ltp=float(v.get("lp", 0) or 0),
                bid=float(v.get("bid", 0) or 0),
                ask=float(v.get("ask", 0) or 0),
                volume=int(v.get("vol", 0) or v.get("volume", 0) or 0),
                timestamp=datetime.now(),
            )
        except Exception as exc:
            logger.error("get_live_quote failed for %s: %s", symbol, exc)
            return None

    def get_live_quotes(self, symbols: list[str]) -> dict[str, LiveQuote]:
        """
        Batch fetch LTP for multiple symbols.

        Fyers accepts up to 50 symbols per quotes() call, comma-separated.
        Returns {plain_ticker: LiveQuote}.
        """
        result: dict[str, LiveQuote] = {}

        for i in range(0, len(symbols), _QUOTE_BATCH_SIZE):
            batch = symbols[i: i + _QUOTE_BATCH_SIZE]
            fyers_symbols = ",".join(to_fyers_format(s) for s in batch)
            try:
                def _fetch(syms=fyers_symbols):
                    resp = self._client.quotes(data={"symbols": syms})
                    if not isinstance(resp, dict):
                        raise ValueError(f"Unexpected response type: {type(resp)}")
                    if resp.get("s") != "ok":
                        raise ValueError(f"Fyers quotes error: {resp.get('message', resp)}")
                    return resp

                raw = _retry(_fetch)
                for item in raw.get("d", []):
                    fyers_sym = item.get("n", "")
                    v = item.get("v", {})
                    plain_sym = from_fyers_format(fyers_sym)
                    if plain_sym:
                        result[plain_sym] = LiveQuote(
                            symbol=plain_sym,
                            ltp=float(v.get("lp", 0) or 0),
                            bid=float(v.get("bid", 0) or 0),
                            ask=float(v.get("ask", 0) or 0),
                            volume=int(v.get("vol", 0) or v.get("volume", 0) or 0),
                            timestamp=datetime.now(),
                        )
            except Exception as exc:
                logger.error("Batch quote failed for %s: %s", batch, exc)

        return result

    # ------------------------------------------------------------------
    # Convenience: previous day close
    # ------------------------------------------------------------------

    def get_prev_close(self, symbol: str) -> Optional[float]:
        bars = self.get_historical_ohlc(symbol, days=5)
        if len(bars) >= 2:
            return bars[-2].close  # yesterday's close
        elif len(bars) == 1:
            return bars[0].close
        return None

    def get_prev_closes(self, symbols: list[str]) -> dict[str, float]:
        """Fetch previous close for all symbols. Returns {symbol: prev_close}."""
        result = {}
        for sym in symbols:
            prev_close = self.get_prev_close(sym)
            if prev_close:
                result[sym] = prev_close
        return result
