"""
FyersGap — Order Manager.

Handles all Fyers API v3 order placement, modification, and cancellation.
Abstracts away the raw API so GapStrategy stays clean.

All order calls respect DRY_RUN mode — in dry-run, orders are logged
but NOT sent to the broker.

Fyers order API reference
--------------------------
place_order(data={
    "symbol":        "NSE:RELIANCE-EQ",
    "qty":           10,
    "type":          2,           # 1=LIMIT 2=MARKET 3=SL-M 4=SL
    "side":          1,           # 1=BUY  -1=SELL
    "productType":   "INTRADAY",  # intraday margin product
    "limitPrice":    0,
    "stopPrice":     0,
    "validity":      "DAY",
    "disclosedQty":  0,
    "offlineOrder":  False,
    "orderTag":      "GAP_ENTRY",
})
Response: {"s": "ok", "id": "<order_id>", "message": "..."}

cancel_order(data={"id": "<order_id>"})
orderbook() → {"s": "ok", "orderBook": [...]}
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from config.settings import settings
from config.symbols import to_fyers_format
from models.trading_models import (
    GapSignal,
    OrderSide,
    OrderType,
    Position,
    PositionStatus,
)
from utils.logger import get_logger

logger = get_logger("order_manager", settings.ops.log_level, settings.ops.log_file)

_MAX_RETRIES = 3
_BASE_BACKOFF = 2

# Fyers order type codes
_FYERS_ORDER_TYPE = {
    OrderType.LIMIT:     1,
    OrderType.MARKET:    2,
    OrderType.SL_MARKET: 3,
    OrderType.SL_LIMIT:  4,
}

# Fyers side codes
_FYERS_SIDE = {
    OrderSide.BUY:  1,
    OrderSide.SELL: -1,
}


def _retry_order(func, *args, **kwargs):
    backoff = _BASE_BACKOFF
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise
            logger.warning("Order attempt %d failed: %s. Retrying in %ds…", attempt, exc, backoff)
            time.sleep(backoff)
            backoff *= 2


class OrderManager:

    def __init__(self, fyers_client) -> None:
        self._client = fyers_client
        self._dry_run = settings.ops.dry_run

    # ------------------------------------------------------------------
    # Position entry
    # ------------------------------------------------------------------

    def place_entry_order(self, signal: GapSignal, quantity: int) -> Optional[Position]:
        """
        Place a market entry order for the given signal.

        Returns a Position object on success, None on failure.
        """
        side = OrderSide.BUY if signal.signal_direction.value == "BUY" else OrderSide.SELL
        order_id = self._place_order(
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            price=0,
            tag="GAP_ENTRY",
        )
        if not order_id:
            return None

        position = Position(
            symbol=signal.symbol,
            signal=signal,
            entry_price=signal.entry_price,
            quantity=quantity,
            order_side=side,
            status=PositionStatus.OPEN,
            entry_order_id=order_id,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
            trailing_stop=signal.stop_loss,
            opened_at=datetime.now(),
        )
        logger.info(
            "ENTRY | %s | %s | qty=%d | price=%.2f | sl=%.2f | t1=%.2f | t2=%.2f",
            signal.symbol,
            side.value,
            quantity,
            signal.entry_price,
            signal.stop_loss,
            signal.target_1,
            signal.target_2,
        )
        return position

    # ------------------------------------------------------------------
    # Stop-loss order
    # ------------------------------------------------------------------

    def place_stop_loss_order(self, position: Position) -> str:
        """Place a stop-loss market order. Returns order_id."""
        sl_side = OrderSide.SELL if position.order_side == OrderSide.BUY else OrderSide.BUY
        order_id = self._place_order(
            symbol=position.symbol,
            side=sl_side,
            quantity=position.quantity,
            order_type=OrderType.SL_MARKET,
            price=0,
            trigger_price=position.signal.stop_loss,
            tag="GAP_SL",
        )
        return order_id or ""

    # ------------------------------------------------------------------
    # Partial / full exit
    # ------------------------------------------------------------------

    def place_exit_order(
        self,
        position: Position,
        quantity: int,
        price: float = 0,
        tag: str = "GAP_EXIT",
    ) -> str:
        exit_side = OrderSide.SELL if position.order_side == OrderSide.BUY else OrderSide.BUY
        order_type = OrderType.LIMIT if price > 0 else OrderType.MARKET
        order_id = self._place_order(
            symbol=position.symbol,
            side=exit_side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            tag=tag,
        )
        return order_id or ""

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        if self._dry_run:
            logger.info("[DRY RUN] Cancel order %s for %s", order_id, symbol)
            return True
        try:
            resp = _retry_order(
                self._client.cancel_order,
                data={"id": order_id},
            )
            if isinstance(resp, dict) and resp.get("s") == "ok":
                logger.info("Cancelled order %s for %s", order_id, symbol)
                return True
            logger.error("Cancel order %s returned: %s", order_id, resp)
            return False
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return False

    # ------------------------------------------------------------------
    # Order status / fill price
    # ------------------------------------------------------------------

    def get_order_fill_price(self, order_id: str) -> Optional[float]:
        """Look up the average fill price for a placed order."""
        if self._dry_run:
            return None
        try:
            resp = _retry_order(self._client.orderbook)
            order_book = resp.get("orderBook", []) if isinstance(resp, dict) else []
            for order in order_book:
                if str(order.get("id", "")) == str(order_id):
                    return float(order.get("tradedPrice", 0) or order.get("limitPrice", 0) or 0)
        except Exception as exc:
            logger.error("get_order_fill_price(%s) failed: %s", order_id, exc)
        return None

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        price: float,
        trigger_price: float = 0,
        tag: str = "",
    ) -> Optional[str]:
        if self._dry_run:
            fake_id = f"DRY_{symbol}_{side.value}_{int(time.time())}"
            logger.info(
                "[DRY RUN] %s | %s | qty=%d | type=%s | price=%.2f | sl=%.2f | tag=%s → %s",
                symbol, side.value, quantity, order_type.value, price, trigger_price, tag, fake_id,
            )
            return fake_id

        fyers_symbol = to_fyers_format(symbol)
        order_data = {
            "symbol":       fyers_symbol,
            "qty":          quantity,
            "type":         _FYERS_ORDER_TYPE[order_type],
            "side":         _FYERS_SIDE[side],
            "productType":  "INTRADAY",
            "limitPrice":   price,
            "stopPrice":    trigger_price,
            "validity":     "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag":     tag,
        }

        try:
            resp = _retry_order(self._client.place_order, data=order_data)
            if not isinstance(resp, dict):
                logger.error("Unexpected place_order response type: %s", type(resp))
                return None
            if resp.get("s") != "ok":
                logger.error("place_order failed: %s", resp)
                return None

            order_id = str(resp.get("id", ""))
            if order_id:
                logger.info(
                    "ORDER PLACED | %s | %s | qty=%d | type=%s | price=%.2f | id=%s",
                    symbol, side.value, quantity, order_type.value, price, order_id,
                )
            else:
                logger.error("Order placement returned no order id: %s", resp)
            return order_id or None
        except Exception as exc:
            logger.error("_place_order failed for %s: %s", symbol, exc)
            return None
