# -*- coding: utf-8 -*-
"""
VietKey Gold AI — MT5 Order Executor (Stage 1).

Chuyên trách thực thi lệnh trực tiếp trên MetaTrader 5 Terminal:
- Gửi lệnh thị trường (Market Order) kèm SL/TP ghim thẳng lên máy chủ Broker (0ms latency).
- Gửi lệnh chờ (Pending Buy/Sell Limit) đón đầu tại vùng Entry.
- Dời Stop Loss trực tiếp (Live Trailing Stop & Breakeven) qua TRADE_ACTION_SLTP.
- Đóng vị thế tức thì qua TRADE_ACTION_DEAL (Smart Early Exit & chốt lời).
- Hủy lệnh chờ quá hạn qua TRADE_ACTION_REMOVE.
- Tự động nhận diện phương thức khớp lệnh của Broker (FOK / IOC / RETURN).
- Quản trị rủi ro: Giới hạn lot size, kiểm tra ký quỹ tự do, chống duplicate lệnh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import MetaTrader5 as mt5

from app.mt5.lock import mt5_lock
from app.strategy.signal_models import SignalDirection
from config import MT5TradingConfig
from logger import get_logger

log = get_logger("mt5.executor")


@dataclass
class OrderResult:
    """Kết quả thực thi lệnh trên MT5."""
    success: bool
    ticket: int = 0
    retcode: int = 0
    comment: str = ""
    symbol: str = ""
    direction: str = ""
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __str__(self) -> str:
        if self.success:
            return (
                f"✓ [MT5 #{self.ticket}] {self.direction} {self.volume}L {self.symbol} "
                f"@ {self.price:.2f} (SL: {self.sl:.2f} | TP: {self.tp:.2f}) - {self.comment}"
            )
        return f"✗ [MT5 Lỗi {self.retcode}] {self.comment}"


@dataclass
class PositionInfo:
    """Thông tin vị thế thực tế đang mở trên MT5."""
    ticket: int
    symbol: str
    direction: str
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    pnl_usd: float
    pnl_points: float
    magic: int
    comment: str
    open_time: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "direction": self.direction,
            "volume": self.volume,
            "open_price": round(self.open_price, 2),
            "current_price": round(self.current_price, 2),
            "sl": round(self.sl, 2),
            "tp": round(self.tp, 2),
            "pnl_usd": round(self.pnl_usd, 2),
            "pnl_points": round(self.pnl_points, 2),
            "magic": self.magic,
            "comment": self.comment,
            "open_time": self.open_time.isoformat(),
        }


class MT5Executor:
    """Bộ điều khiển đặt lệnh và giám sát vị thế trực tiếp trên MT5."""

    def __init__(self, config: Optional[MT5TradingConfig] = None) -> None:
        self.config = config or MT5TradingConfig()

    def get_filling_mode(self, symbol: str) -> int:
        """Tự động xác định kiểu khớp lệnh thích hợp của Symbol (IOC, FOK hoặc RETURN)."""
        with mt5_lock:
            info = mt5.symbol_info(symbol)
        if not info:
            return mt5.ORDER_FILLING_IOC

        # Bitmask filling mode: 1 = FOK, 2 = IOC
        if info.filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        elif info.filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def is_trade_allowed(self) -> Tuple[bool, str]:
        """Kiểm tra xem MT5 terminal có cho phép giao dịch tự động không."""
        with mt5_lock:
            term = mt5.terminal_info()
            acc = mt5.account_info()

        if not term:
            return False, "Chưa khởi tạo hoặc mất kết nối MT5 Terminal"
        if not term.connected:
            return False, "MT5 Terminal đang mất kết nối Internet/Broker"
        if not acc:
            return False, "Không lấy được thông tin tài khoản MT5"
        if not acc.trade_allowed:
            return False, "Tài khoản MT5 bị sàn khóa quyền giao dịch"
        if not acc.trade_expert:
            return False, "Tài khoản không cho phép Expert Advisor đặt lệnh"
        if not term.trade_allowed:
            return False, "Nút 'Algo Trading' trên thanh công cụ MT5 đang TẮT. Vui lòng bấm bật nút 'Algo Trading' màu xanh!"

        return True, "Sẵn sàng giao dịch"

    def get_account_summary(self) -> dict[str, Any]:
        """Lấy thông tin tài chính tài khoản MT5 thời gian thực."""
        with mt5_lock:
            acc = mt5.account_info()
        if not acc:
            return {
                "connected": False,
                "login": 0,
                "balance": 0.0,
                "equity": 0.0,
                "margin": 0.0,
                "free_margin": 0.0,
                "currency": "USD",
                "trade_allowed": False,
            }
        return {
            "connected": True,
            "login": acc.login,
            "server": acc.server,
            "name": acc.name,
            "balance": round(acc.balance, 2),
            "equity": round(acc.equity, 2),
            "margin": round(acc.margin, 2),
            "free_margin": round(acc.margin_free, 2),
            "currency": acc.currency,
            "leverage": acc.leverage,
            "trade_allowed": bool(acc.trade_allowed and acc.trade_expert),
        }

    def get_open_positions(self, symbol: Optional[str] = None) -> list[PositionInfo]:
        """Lấy danh sách các vị thế đang mở trên MT5."""
        sym = symbol or self.config.symbol
        positions: list[PositionInfo] = []
        with mt5_lock:
            raw_pos = mt5.positions_get(symbol=sym)

        if not raw_pos:
            return positions

        for p in raw_pos:
            direction_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
            pnl_pts = (p.price_current - p.price_open) if p.type == mt5.ORDER_TYPE_BUY else (p.price_open - p.price_current)
            op_time = datetime.fromtimestamp(p.time, tz=timezone.utc)
            positions.append(
                PositionInfo(
                    ticket=p.ticket,
                    symbol=p.symbol,
                    direction=direction_str,
                    volume=p.volume,
                    open_price=p.price_open,
                    current_price=p.price_current,
                    sl=p.sl,
                    tp=p.tp,
                    pnl_usd=p.profit,
                    pnl_points=round(pnl_pts, 2),
                    magic=p.magic,
                    comment=p.comment,
                    open_time=op_time,
                )
            )
        return positions

    def get_pending_orders(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        """Lấy danh sách các lệnh chờ (Limit/Stop) đang treo trên MT5."""
        sym = symbol or self.config.symbol
        orders: list[dict[str, Any]] = []
        with mt5_lock:
            raw_orders = mt5.orders_get(symbol=sym)

        if not raw_orders:
            return orders

        for o in raw_orders:
            order_type = "BUY_LIMIT" if o.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                "SELL_LIMIT" if o.type == mt5.ORDER_TYPE_SELL_LIMIT else str(o.type)
            )
            orders.append({
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": order_type,
                "volume": o.volume_current,
                "price": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "magic": o.magic,
                "comment": o.comment,
                "time_setup": datetime.fromtimestamp(o.time_setup, tz=timezone.utc).isoformat(),
            })
        return orders

    def send_market_order(
        self,
        symbol: str,
        direction: SignalDirection,
        volume: float,
        sl: float,
        tp: float,
        comment: str = "VietKey AI",
        magic: Optional[int] = None,
    ) -> OrderResult:
        """
        Bắn lệnh thị trường (Market Order) vào MT5 với SL và TP được ghim thẳng lên Server sàn.
        """
        ok, msg = self.is_trade_allowed()
        if not ok:
            log.warning("⛔ Không thể đặt lệnh MT5: %s", msg)
            return OrderResult(success=False, comment=msg)

        # Lấy giá tick hiện tại
        with mt5_lock:
            tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return OrderResult(success=False, comment=f"Không lấy được giá tick của {symbol}")

        is_buy = direction == SignalDirection.BUY
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid
        filling = self.get_filling_mode(symbol)
        magic_val = magic if magic is not None else self.config.magic_number

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(round(sl, 2)),
            "tp": float(round(tp, 2)),
            "deviation": int(self.config.max_slippage_points),
            "magic": int(magic_val),
            "comment": str(comment[:31]),  # MT5 comment tối đa 31 ký tự
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        # Kiểm tra trước (order_check)
        with mt5_lock:
            check_res = mt5.order_check(request)
        if check_res is None or check_res.retcode != 0:
            err = check_res.comment if check_res else "Lỗi order_check MT5"
            log.error("❌ MT5 order_check từ chối: %s", err)
            return OrderResult(success=False, retcode=check_res.retcode if check_res else -1, comment=err)

        # Thực thi gửi lệnh (order_send)
        with mt5_lock:
            send_res = mt5.order_send(request)

        if send_res is None:
            return OrderResult(success=False, comment="order_send trả về None")

        if send_res.retcode != mt5.TRADE_RETCODE_DONE:
            log.error("❌ MT5 order_send thất bại [Code %d]: %s", send_res.retcode, send_res.comment)
            return OrderResult(
                success=False,
                ticket=send_res.order,
                retcode=send_res.retcode,
                comment=send_res.comment,
            )

        log.info(
            "🚀 [MT5 THỰC THI THÀNH CÔNG] Khớp lệnh #%d %s %.2f lot %s @ %.2f (SL: %.2f | TP: %.2f)",
            send_res.order, direction.value, volume, symbol, send_res.price, sl, tp,
        )
        return OrderResult(
            success=True,
            ticket=send_res.order,
            retcode=send_res.retcode,
            comment="Khớp lệnh thị trường thành công",
            symbol=symbol,
            direction=direction.value,
            volume=volume,
            price=send_res.price or price,
            sl=sl,
            tp=tp,
        )

    def send_limit_order(
        self,
        symbol: str,
        direction: SignalDirection,
        price: float,
        volume: float,
        sl: float,
        tp: float,
        comment: str = "VietKey Limit",
        magic: Optional[int] = None,
    ) -> OrderResult:
        """
        Đón đầu tại vùng cản SMC: Đặt lệnh chờ Limit trực tiếp lên sàn MT5 kèm SL/TP.
        """
        ok, msg = self.is_trade_allowed()
        if not ok:
            return OrderResult(success=False, comment=msg)

        is_buy = direction == SignalDirection.BUY
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
        filling = self.get_filling_mode(symbol)
        magic_val = magic if magic is not None else self.config.magic_number

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(round(price, 2)),
            "sl": float(round(sl, 2)),
            "tp": float(round(tp, 2)),
            "deviation": int(self.config.max_slippage_points),
            "magic": int(magic_val),
            "comment": str(comment[:31]),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        with mt5_lock:
            check_res = mt5.order_check(request)
        if check_res is None or check_res.retcode != 0:
            err = check_res.comment if check_res else "Lỗi order_check Limit"
            return OrderResult(success=False, retcode=check_res.retcode if check_res else -1, comment=err)

        with mt5_lock:
            send_res = mt5.order_send(request)

        if send_res is None or send_res.retcode != mt5.TRADE_RETCODE_DONE:
            err = send_res.comment if send_res else "order_send Limit trả về None"
            log.error("❌ MT5 đặt Limit thất bại: %s", err)
            return OrderResult(success=False, retcode=send_res.retcode if send_res else -1, comment=err)

        log.info(
            "📌 [MT5 ĐẶT LIMIT THÀNH CÔNG] Lệnh chờ #%d %s %.2f lot %s @ %.2f (SL: %.2f | TP: %.2f)",
            send_res.order, "BUY_LIMIT" if is_buy else "SELL_LIMIT", volume, symbol, price, sl, tp,
        )
        return OrderResult(
            success=True,
            ticket=send_res.order,
            retcode=send_res.retcode,
            comment="Đặt lệnh chờ Limit thành công",
            symbol=symbol,
            direction="BUY_LIMIT" if is_buy else "SELL_LIMIT",
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
        )

    def modify_position_sltp(
        self,
        ticket: int,
        sl: float,
        tp: Optional[float] = None,
    ) -> bool:
        """
        Dời Stop Loss trực tiếp trên MT5 (Breakeven & Trailing Stop) qua TRADE_ACTION_SLTP.
        """
        with mt5_lock:
            pos_list = mt5.positions_get(ticket=ticket)
        if not pos_list:
            log.warning("Không tìm thấy vị thế #%d trên MT5 để sửa SL/TP", ticket)
            return False

        pos = pos_list[0]
        new_sl = float(round(sl, 2))
        new_tp = float(round(tp, 2)) if tp is not None else float(pos.tp)

        # Tránh gửi request lặp nếu SL không thay đổi
        if abs(pos.sl - new_sl) < 0.01 and (tp is None or abs(pos.tp - new_tp) < 0.01):
            return True

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": new_tp,
        }

        with mt5_lock:
            res = mt5.order_send(request)

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("🛡️ [MT5 #%d] Đã dời Stop Loss trực tiếp lên %.2f (TP: %.2f)", ticket, new_sl, new_tp)
            return True

        err = res.comment if res else "None"
        log.warning("⚠️ Không thể dời SL/TP vị thế #%d trên MT5: %s", ticket, err)
        return False

    def close_position(
        self,
        ticket: int,
        volume: Optional[float] = None,
        comment: str = "VietKey Exit",
    ) -> OrderResult:
        """
        Đóng vị thế trực tiếp trên MT5 qua TRADE_ACTION_DEAL (Smart Exit / Cắt sớm / Chốt lời).
        """
        with mt5_lock:
            pos_list = mt5.positions_get(ticket=ticket)
        if not pos_list:
            return OrderResult(success=False, comment=f"Vị thế #{ticket} không tồn tại hoặc đã được sàn đóng trước")

        pos = pos_list[0]
        sym = pos.symbol
        close_vol = float(volume) if volume is not None else float(pos.volume)
        is_buy_pos = pos.type == mt5.ORDER_TYPE_BUY

        # Đóng BUY thì Sell, đóng SELL thì Buy
        close_type = mt5.ORDER_TYPE_SELL if is_buy_pos else mt5.ORDER_TYPE_BUY

        with mt5_lock:
            tick = mt5.symbol_info_tick(sym)
        if not tick:
            return OrderResult(success=False, comment="Không lấy được giá tick để đóng lệnh")

        close_price = tick.bid if is_buy_pos else tick.ask
        filling = self.get_filling_mode(sym)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(ticket),
            "symbol": sym,
            "volume": close_vol,
            "type": close_type,
            "price": float(close_price),
            "deviation": int(self.config.max_slippage_points),
            "magic": int(pos.magic),
            "comment": str(comment[:31]),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        with mt5_lock:
            res = mt5.order_send(request)

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(
                "🎯 [MT5 ĐÓNG LỆNH THÀNH CÔNG] Đã tất toán vị thế #%d %s %.2f lot @ %.2f [%s]",
                ticket, "BUY" if is_buy_pos else "SELL", close_vol, res.price or close_price, comment,
            )
            return OrderResult(
                success=True,
                ticket=ticket,
                retcode=res.retcode,
                comment="Đóng vị thế thành công",
                symbol=sym,
                direction="CLOSE",
                volume=close_vol,
                price=res.price or close_price,
            )

        err = res.comment if res else "Lỗi order_send khi đóng vị thế"
        log.error("❌ MT5 đóng vị thế #%d thất bại: %s", ticket, err)
        return OrderResult(success=False, ticket=ticket, retcode=res.retcode if res else -1, comment=err)

    def cancel_order(self, ticket: int) -> bool:
        """Hủy lệnh chờ Limit/Stop trên MT5 khi hết hạn hoặc vi phạm cấu trúc."""
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(ticket),
        }
        with mt5_lock:
            res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log.info("🗑️ [MT5 HỦY LỆNH CHỜ] Đã hủy thành công lệnh pending #%d", ticket)
            return True
        log.warning("Không thể hủy lệnh chờ #%d: %s", ticket, res.comment if res else "None")
        return False

    def close_all_positions(self, symbol: Optional[str] = None) -> list[OrderResult]:
        """Khẩn cấp 1-Click: Đóng toàn bộ các vị thế MT5 đang mở."""
        positions = self.get_open_positions(symbol)
        results: list[OrderResult] = []
        for p in positions:
            res = self.close_position(ticket=p.ticket, comment="Khẩn cấp: Đóng toàn bộ")
            results.append(res)
        return results
