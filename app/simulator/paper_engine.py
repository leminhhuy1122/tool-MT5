# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Paper Trading & Virtual Wallet Engine.

Quản trị toàn bộ chu trình đi lệnh ảo:
- Khởi tạo ví ảo với số vốn tùy chỉnh (ví dụ $50, $100, $500).
- Khớp lệnh ảo tự động theo tín hiệu từ SignalEngine với khối lượng chuẩn (mặc định 0.01 lot).
- Tính toán PnL, Pips, Ký quỹ (Margin), Tỷ lệ ký quỹ (Margin Level) theo chuẩn hợp đồng XAUUSD (100 oz/lot).
- Tích hợp Smart Exit: Tự động dời Stop Loss về hòa vốn (Breakeven cushion) và bám sát Trailing Stop.
- Tự động chốt lời (TP) và cắt lỗ (SL) thời gian thực theo từng tick giá MT5.
- Lưu trữ lịch sử giao dịch và chụp biến động vốn (Equity Snapshots) vẽ biểu đồ.
"""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Optional
import uuid

import pandas as pd

from app.database.connection import DatabaseManager
from app.simulator.models import PaperPosition, PaperTradeHistory, PaperWallet
from app.strategy.signal_models import SignalDirection, TradingSignal
from app.strategy.smart_exit import ExitActionType, SmartExitConfig, SmartExitEngine
from logger import get_logger

log = get_logger("simulator.paper_engine")


class PaperTradingEngine:
    """Động cơ quản lý Ví Đầu Tư Ảo và Mô Phỏng Đi Lệnh Thực Tế."""

    CONTRACT_SIZE: float = 100.0  # 1.0 lot Vàng = 100 ounces (0.01 lot = 1 ounce)
    DEFAULT_WALLET_ID: str = "default"

    def __init__(
        self,
        db_manager: DatabaseManager,
        notifier: Optional[Any] = None,
        smart_exit_engine: Optional[SmartExitEngine] = None,
        notify_telegram: bool = False,
    ):
        self.db = db_manager
        self.notifier = notifier
        self.smart_exit = smart_exit_engine or SmartExitEngine()
        self.notify_telegram = notify_telegram

        # Đảm bảo bảng và ví mặc định đã sẵn sàng
        self._ensure_wallet_initialized()
        try:
            self.sync_active_signals()
        except Exception:
            pass

    def _ensure_wallet_initialized(self) -> None:
        """Kiểm tra và tạo cấu trúc bảng ví ảo nếu chưa tồn tại trong SQLite."""
        try:
            from app.database.schema import MIGRATION_V2_SQL
            with self.db.session() as conn:
                conn.executescript(MIGRATION_V2_SQL)
        except Exception as e:
            log.warning("Khởi tạo bảng ví ảo mặc định: %s", e)

    # =========================================================================
    # QUẢN LÝ THÔNG TIN VÍ (WALLET MANAGEMENT)
    # =========================================================================

    def get_wallet(self, wallet_id: str = DEFAULT_WALLET_ID) -> PaperWallet:
        """Lấy thông tin ví và tính toán số liệu tài sản, ký quỹ, win-rate thời gian thực."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_wallets WHERE wallet_id = ?;",
                (wallet_id,),
            )
            row = cursor.fetchone()
            if not row:
                self._ensure_wallet_initialized()
                cursor.execute(
                    "SELECT * FROM paper_wallets WHERE wallet_id = ?;",
                    (wallet_id,),
                )
                row = cursor.fetchone()

            wallet = PaperWallet(
                wallet_id=row["wallet_id"],
                name=row["name"],
                initial_balance=float(row["initial_balance"]),
                balance=float(row["balance"]),
                equity=float(row["equity"]),
                currency=row["currency"],
                leverage=int(row["leverage"]),
                default_lot=float(row["default_lot"]),
                is_auto_trading=bool(row["is_auto_trading"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            # Tính toán ký quỹ các lệnh đang mở
            cursor.execute(
                "SELECT volume, open_price, floating_pnl FROM paper_positions WHERE wallet_id = ? AND status = 'OPEN';",
                (wallet_id,),
            )
            open_rows = cursor.fetchall()

            total_used_margin = 0.0
            total_floating_pnl = 0.0
            for pos in open_rows:
                vol = float(pos["volume"])
                open_p = float(pos["open_price"])
                pnl = float(pos["floating_pnl"])
                total_used_margin += (open_p * self.CONTRACT_SIZE * vol) / wallet.leverage
                total_floating_pnl += pnl

            wallet.used_margin = round(total_used_margin, 2)
            wallet.equity = round(wallet.balance + total_floating_pnl, 2)
            wallet.free_margin = max(0.0, round(wallet.equity - wallet.used_margin, 2))
            wallet.margin_level = (
                round((wallet.equity / wallet.used_margin) * 100.0, 1)
                if wallet.used_margin > 0
                else 0.0
            )

            # Thống kê hiệu suất lịch sử
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) as profit_sum,
                    SUM(CASE WHEN pnl_usd < 0 THEN ABS(pnl_usd) ELSE 0 END) as loss_sum
                FROM paper_trades_history 
                WHERE wallet_id = ?;
                """,
                (wallet_id,),
            )
            stat = cursor.fetchone()
            if stat and stat["total"] > 0:
                total_t = int(stat["total"])
                wins = int(stat["wins"] or 0)
                losses = int(stat["losses"] or 0)
                p_sum = float(stat["profit_sum"] or 0.0)
                l_sum = float(stat["loss_sum"] or 0.0)

                wallet.total_trades = total_t
                wallet.winning_trades = wins
                wallet.losing_trades = losses
                wallet.win_rate = round((wins / total_t) * 100.0, 1) if total_t > 0 else 0.0
                wallet.profit_factor = round(p_sum / l_sum, 2) if l_sum > 0 else (2.0 if wins > 0 else 0.0)

            return wallet

    def setup_wallet(
        self,
        initial_balance: float,
        default_lot: float = 0.01,
        leverage: int = 500,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> PaperWallet:
        """Thiết lập vốn ban đầu tùy chỉnh (ví dụ nạp $50, $100, $500) và cấu hình lot."""
        initial_balance = max(10.0, float(initial_balance))
        default_lot = max(0.01, round(float(default_lot), 2))
        now_str = datetime.now(timezone.utc).isoformat()

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE paper_wallets 
                SET initial_balance = ?, balance = ?, equity = ?, default_lot = ?, leverage = ?, updated_at = ?
                WHERE wallet_id = ?;
                """,
                (initial_balance, initial_balance, initial_balance, default_lot, leverage, now_str, wallet_id),
            )
            # Ghi snapshot vốn mới
            cursor.execute(
                """
                INSERT INTO paper_equity_snapshots (wallet_id, balance, equity, timestamp)
                VALUES (?, ?, ?, ?);
                """,
                (wallet_id, initial_balance, initial_balance, now_str),
            )

        log.info("✓ Đã cấu hình ví ảo [%s]: Vốn $%.2f | Lot %.2f | Đòn bẩy 1:%d",
                 wallet_id, initial_balance, default_lot, leverage)
        try:
            self.sync_active_signals(wallet_id)
        except Exception:
            pass
        return self.get_wallet(wallet_id)

    def reset_wallet(
        self,
        initial_balance: Optional[float] = None,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> PaperWallet:
        """Reset ví về số vốn ban đầu, xóa toàn bộ lệnh mở và lịch sử lệnh để test lại từ đầu."""
        wallet = self.get_wallet(wallet_id)
        target_balance = initial_balance if initial_balance is not None else wallet.initial_balance
        target_balance = max(10.0, float(target_balance))
        now_str = datetime.now(timezone.utc).isoformat()

        with self.db.session() as conn:
            cursor = conn.cursor()
            # Xóa các lệnh đang mở và lịch sử
            cursor.execute("DELETE FROM paper_positions WHERE wallet_id = ?;", (wallet_id,))
            cursor.execute("DELETE FROM paper_trades_history WHERE wallet_id = ?;", (wallet_id,))
            cursor.execute("DELETE FROM paper_equity_snapshots WHERE wallet_id = ?;", (wallet_id,))

            # Cập nhật số dư
            cursor.execute(
                """
                UPDATE paper_wallets 
                SET initial_balance = ?, balance = ?, equity = ?, updated_at = ?
                WHERE wallet_id = ?;
                """,
                (target_balance, target_balance, target_balance, now_str, wallet_id),
            )
            cursor.execute(
                """
                INSERT INTO paper_equity_snapshots (wallet_id, balance, equity, timestamp)
                VALUES (?, ?, ?, ?);
                """,
                (wallet_id, target_balance, target_balance, now_str),
            )

        log.info("✓ Đã RESET ví ảo [%s] về mốc ban đầu: $%.2f", wallet_id, target_balance)
        return self.get_wallet(wallet_id)

    def toggle_auto_trading(
        self,
        enabled: Optional[bool] = None,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> bool:
        """Bật / Tắt chế độ tự động đi lệnh theo tín hiệu Bot."""
        wallet = self.get_wallet(wallet_id)
        new_state = (not wallet.is_auto_trading) if enabled is None else bool(enabled)
        now_str = datetime.now(timezone.utc).isoformat()

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE paper_wallets SET is_auto_trading = ?, updated_at = ? WHERE wallet_id = ?;",
                (1 if new_state else 0, now_str, wallet_id),
            )

        log.info("✓ Trạng thái tự động đi lệnh Ví ảo [%s]: %s", wallet_id, "BẬT" if new_state else "TẮT")
        if new_state:
            try:
                self.sync_active_signals(wallet_id)
            except Exception:
                pass
        return new_state

    # =========================================================================
    # ĐỒNG BỘ TÍN HIỆU ACTIVE VÀO VÍ ẢO (SYNC ACTIVE SIGNALS)
    # =========================================================================

    def sync_active_signals(self, wallet_id: str = DEFAULT_WALLET_ID) -> int:
        """
        Tự động đồng bộ các tín hiệu đang ACTIVE hoặc ENTRY_REACHED vào ví ảo.
        Đảm bảo khi khởi động bot hoặc khi người dùng nạp vốn/bật ví,
        các lệnh đang chạy thực tế trên thị trường được đưa ngay vào ví ảo để tính PnL live.
        """
        try:
            wallet = self.get_wallet(wallet_id)
        except Exception:
            return 0

        if not wallet.is_auto_trading:
            return 0

        synced_count = 0
        try:
            with self.db.session() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Chỉ lấy các tín hiệu ĐÃ KHỚP THẬT SỰ (ENTRY_REACHED) chưa có trong paper_positions và chưa từng đóng trong paper_trades_history
                cursor.execute(
                    """
                    SELECT s.* FROM signals s
                    WHERE s.status = 'ENTRY_REACHED'
                      AND NOT EXISTS (
                          SELECT 1 FROM paper_positions p 
                          WHERE p.wallet_id = ? AND p.signal_id = s.signal_id
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM paper_trades_history h 
                          WHERE h.wallet_id = ? AND h.signal_id = s.signal_id
                      )
                    ORDER BY s.created_at ASC;
                    """,
                    (wallet_id, wallet_id),
                )
                signals_to_adopt = cursor.fetchall()

                now_str = datetime.now(timezone.utc).isoformat()
                for sig in signals_to_adopt:
                    sig_id = sig["signal_id"]
                    direction = sig["direction"]
                    open_p = float(sig["entry_price"])
                    sl = float(sig["stop_loss"])
                    tp1 = float(sig["take_profit_1"])
                    tp2 = float(sig["take_profit_2"]) if sig["take_profit_2"] is not None else (open_p + 20.0 if direction == "BUY" else open_p - 20.0)
                    vol = wallet.default_lot
                    sym = sig["symbol"]

                    # Anti-Hedging Guard: Kiểm tra xem đã có vị thế ngược chiều đang mở trên cùng symbol hay chưa
                    cursor.execute(
                        "SELECT direction FROM paper_positions WHERE wallet_id = ? AND symbol = ? AND status = 'OPEN';",
                        (wallet_id, sym),
                    )
                    existing_pos = cursor.fetchall()
                    has_opposing = any(
                        (p["direction"] if isinstance(p, sqlite3.Row) else p[0]) != direction
                        for p in existing_pos
                    )
                    if has_opposing:
                        log.warning(
                            "⛔ Anti-Hedging Ví Ảo: Bỏ qua đồng bộ tín hiệu %s %s vì đã có vị thế ngược chiều đang mở.",
                            direction, sig_id,
                        )
                        continue

                    margin_req = (open_p * self.CONTRACT_SIZE * vol) / wallet.leverage
                    if wallet.free_margin < margin_req:
                        log.warning(
                            "Ví ảo không đủ ký quỹ để đồng bộ tín hiệu %s (Cần $%.2f, còn $%.2f)",
                            sig_id, margin_req, wallet.free_margin,
                        )
                        continue

                    pos_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
                    open_time = sig["created_at"] or now_str

                    cursor.execute(
                        """
                        INSERT INTO paper_positions 
                        (position_id, wallet_id, signal_id, symbol, direction, volume, open_price, current_price,
                         stop_loss, take_profit_1, take_profit_2, floating_pnl, floating_pnl_percent, status, open_time, last_update)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, 'OPEN', ?, ?);
                        """,
                        (
                            pos_id,
                            wallet_id,
                            sig_id,
                            sym,
                            direction,
                            vol,
                            open_p,
                            open_p,
                            sl,
                            tp1,
                            tp2,
                            open_time,
                            now_str,
                        ),
                    )
                    synced_count += 1
                    log.info(
                        "✓ [VÍ ẢO %s] Đã tự động đồng bộ lệnh active: %s %s %.2f lot @ %.2f (SL: %.2f | TP: %.2f)",
                        wallet_id, direction, sym, vol, open_p, sl, tp1,
                    )

            if synced_count > 0:
                self._sync_wallet_equity(wallet_id)
        except Exception as e:
            log.debug("Lỗi đồng bộ active signals vào ví ảo: %s", e)

        return synced_count

    # =========================================================================
    # VÀO LỆNH TỰ ĐỘNG THEO TÍN HIỆU (PAPER ORDER EXECUTION)
    # =========================================================================

    def open_position_from_signal(
        self,
        signal: TradingSignal,
        current_price: float,
        spread: float = 0.2,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> Optional[PaperPosition]:
        """
        Khớp lệnh ảo tự động khi có tín hiệu mới từ SignalEngine:
        - Kiểm tra trạng thái is_auto_trading của ví.
        - Kiểm tra chống trùng lặp theo signal_id.
        - Kiểm tra ký quỹ tự do (Free Margin) đủ cho 0.01 lot.
        - Tính giá khớp thực tế (Ask cho BUY, Bid cho SELL).
        - Lưu vị thế vào database.
        """
        wallet = self.get_wallet(wallet_id)
        if not wallet.is_auto_trading:
            log.debug("Ví ảo [%s] đang tắt Auto-Trading. Bỏ qua khớp lệnh.", wallet_id)
            return None

        volume = wallet.default_lot  # Thường là 0.01 lot
        direction_str = signal.direction.value.upper()

        # Kiểm tra chống trùng lặp và Anti-Hedging Guard (Tuân thủ MT5 Netting & Prop Firm)
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT position_id FROM paper_positions WHERE wallet_id = ? AND signal_id = ? AND status = 'OPEN';",
                (wallet_id, signal.signal_id),
            )
            if cursor.fetchone():
                log.debug("Lệnh cho tín hiệu %s đã đang mở trên ví ảo.", signal.signal_id)
                return None

            cursor.execute(
                "SELECT position_id, direction, open_price, floating_pnl FROM paper_positions WHERE wallet_id = ? AND symbol = ? AND status = 'OPEN';",
                (wallet_id, signal.symbol),
            )
            for pos in cursor.fetchall():
                pos_dir = pos["direction"] if isinstance(pos, sqlite3.Row) else pos[1]
                pos_open = float(pos["open_price"] if isinstance(pos, sqlite3.Row) else pos[2])
                pos_pnl = float(pos["floating_pnl"] if isinstance(pos, sqlite3.Row) else (pos[3] if len(pos) > 3 else 0.0))
                if pos_dir != direction_str:
                    price_diff = abs(current_price - pos_open)
                    if price_diff < 5.0:
                        log.warning(
                            "⛔ Anti-Hedging Cận Biên Ví Ảo: Không thể mở vị thế %s vì lệch vị thế %s cũ chỉ %.2f giá (< 5.0 giá). Cấm tuyệt đối BUY/SELL lệch 1-2 giá!",
                            direction_str, pos_dir, price_diff,
                        )
                        return None
                    if pos_pnl <= 0.0:
                        log.warning(
                            "⛔ Anti-Hedging Kẹp Đầu Ví Ảo: Vị thế %s cũ chưa có lợi nhuận an toàn (Floating: $%.2f). Cấm kẹp đầu khi chưa đảm bảo lời!",
                            pos_dir, pos_pnl,
                        )
                        return None

        # Tính giá khớp lệnh có tính spread thị trường
        half_spread = spread / 2.0
        if direction_str == "BUY":
            open_price = round(current_price + half_spread, 2)
        else:
            open_price = round(current_price - half_spread, 2)

        # Tính toán ký quỹ yêu cầu
        margin_req = (open_price * self.CONTRACT_SIZE * volume) / wallet.leverage
        if wallet.free_margin < margin_req:
            log.warning(
                "⚠️ VÍ ẢO KHÔNG ĐỦ KÝ QUỸ: Cần $%.2f nhưng số dư khả dụng chỉ còn $%.2f. Không thể mở lệnh 0.01 lot!",
                margin_req, wallet.free_margin,
            )
            return None

        position_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        position = PaperPosition(
            position_id=position_id,
            wallet_id=wallet_id,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            direction=direction_str,
            volume=volume,
            open_price=open_price,
            current_price=open_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            floating_pnl=0.0,
            floating_pnl_percent=0.0,
            status="OPEN",
            open_time=now_str,
            last_update=now_str,
        )

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO paper_positions 
                (position_id, wallet_id, signal_id, symbol, direction, volume, open_price, current_price,
                 stop_loss, take_profit_1, take_profit_2, floating_pnl, floating_pnl_percent, status, open_time, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, 'OPEN', ?, ?);
                """,
                (
                    position.position_id,
                    position.wallet_id,
                    position.signal_id,
                    position.symbol,
                    position.direction,
                    position.volume,
                    position.open_price,
                    position.current_price,
                    position.stop_loss,
                    position.take_profit_1,
                    position.take_profit_2,
                    position.open_time,
                    position.last_update,
                ),
            )

        log.info(
            "💼 [VÍ ẢO %s] KHỚP LỆNH: %s %.2f lot %s @ %.2f (SL: %.2f | TP1: %.2f) [Margin: $%.2f]",
            wallet_id, direction_str, volume, signal.symbol, open_price,
            position.stop_loss, position.take_profit_1, margin_req,
        )

        # Thông báo qua Telegram nếu được kích hoạt (mặc định tắt để tránh làm phiền kênh)
        if self.notify_telegram and self.notifier and getattr(self.notifier, "is_enabled", False):
            try:
                alert_msg = (
                    f"💼 <b>VÍ ĐẦU TƯ ẢO (VỐN ${wallet.balance:.2f}): KHỚP LỆNH 0.01 LOT</b>\n\n"
                    f"📌 <b>Lệnh:</b> {direction_str} {signal.symbol} <code>#{position_id}</code>\n"
                    f"📊 <b>Khối lượng:</b> <code>{volume} lot</code>\n"
                    f"🎯 <b>Giá vào:</b> <code>{open_price:.2f}</code>\n"
                    f"🛑 <b>Stop Loss:</b> <code>{position.stop_loss:.2f}</code>\n"
                    f"🎯 <b>Take Profit:</b> <code>{position.take_profit_1:.2f}</code>\n"
                    f"💰 <b>Ký quỹ:</b> <code>${margin_req:.2f}</code> (Còn dư: ${wallet.free_margin - margin_req:.2f})\n"
                    f"⏰ <i>{datetime.now().strftime('%H:%M:%S')} (VN) | VietKey Paper Engine</i>"
                )
                self.notifier.send_raw_message(alert_msg)
            except Exception as e:
                log.debug("Lỗi gửi thông báo ví ảo Telegram: %s", e)

        return position

    # =========================================================================
    # THEO DÕI VỊ THẾ & SMART EXIT LIVE (POSITION TRACKING)
    # =========================================================================

    def update_positions(
        self,
        current_bid: float,
        current_ask: float,
        df_m5: Optional[pd.DataFrame] = None,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> list[PaperTradeHistory]:
        """
        Cập nhật từng tick giá cho toàn bộ lệnh đang chạy:
        - Tính PnL thả nổi ($ và %) theo giá Bid/Ask thực tế từ MT5.
        - Kiểm tra chạm SL hoặc TP1.
        - Tích hợp Smart Exit: Tự động nâng Stop Loss hòa vốn (Breakeven) hoặc Trailing Stop.
        - Đóng lệnh và ghi nhận số dư tài khoản khi thỏa điều kiện thoát lệnh.
        """
        closed_trades: list[PaperTradeHistory] = []
        if current_bid <= 0 or current_ask <= 0:
            return closed_trades

        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_positions WHERE wallet_id = ? AND status = 'OPEN';",
                (wallet_id,),
            )
            positions = cursor.fetchall()

        if not positions:
            # Tự động đồng bộ nếu có tín hiệu active mới
            if self.sync_active_signals(wallet_id) > 0:
                with self.db.session() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT * FROM paper_positions WHERE wallet_id = ? AND status = 'OPEN';",
                        (wallet_id,),
                    )
                    positions = cursor.fetchall()
            if not positions:
                return closed_trades

        wallet = self.get_wallet(wallet_id)
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        for pos in positions:
            pos_id = pos["position_id"]
            direction = pos["direction"]
            vol = float(pos["volume"])
            open_p = float(pos["open_price"])
            sl = float(pos["stop_loss"])
            tp1 = float(pos["take_profit_1"])

            # 1. Tính giá hiện tại áp dụng cho vị thế
            if direction == "BUY":
                curr_p = current_bid
                pnl_pts = curr_p - open_p
            else:
                curr_p = current_ask
                pnl_pts = open_p - curr_p

            # PnL USD = points * 100 * lot (với 0.01 lot: 1 giá = $1.00 USD)
            pnl_usd = round(pnl_pts * self.CONTRACT_SIZE * vol, 2)
            pnl_pips = round(pnl_pts * 10.0, 1)
            pnl_pct = round((pnl_usd / wallet.initial_balance) * 100.0, 2) if wallet.initial_balance > 0 else 0.0

            should_close = False
            close_reason = ""
            close_price = curr_p

            # 2. Kiểm tra Chạm Stop Loss
            if direction == "BUY" and curr_p <= sl:
                should_close = True
                close_price = sl
                close_reason = "BREAKEVEN" if sl >= open_p else ("TRAILING_STOP" if sl > (open_p - 1.0) else "STOP_LOSS")
            elif direction == "SELL" and curr_p >= sl:
                should_close = True
                close_price = sl
                close_reason = "BREAKEVEN" if sl <= open_p else ("TRAILING_STOP" if sl < (open_p + 1.0) else "STOP_LOSS")

            # 3. Kiểm tra Chạm Take Profit 1
            elif direction == "BUY" and curr_p >= tp1:
                should_close = True
                close_price = tp1
                close_reason = "TAKE_PROFIT"
            elif direction == "SELL" and curr_p <= tp1:
                should_close = True
                close_price = tp1
                close_reason = "TAKE_PROFIT"

            # 4. Kiểm tra Smart Exit: Trailing Stop & Breakeven Lock nếu chưa đóng lệnh
            if not should_close:
                new_sl = self._evaluate_smart_sl(
                    direction=direction,
                    open_price=open_p,
                    current_price=curr_p,
                    current_sl=sl,
                    df_m5=df_m5,
                )
                if new_sl is not None and new_sl != sl:
                    sl = new_sl
                    with self.db.session() as conn:
                        conn.execute(
                            "UPDATE paper_positions SET stop_loss = ? WHERE position_id = ?;",
                            (sl, pos_id),
                        )
                    log.info("🛡️ [VÍ ẢO %s] Tự động dời Stop Loss lệnh %s lên %.2f để khóa lợi nhuận!",
                             wallet_id, pos_id, sl)

            # 5. Thực hiện đóng lệnh nếu chạm điều kiện
            if should_close:
                trade = self._execute_close_position(
                    pos_id=pos_id,
                    wallet_id=wallet_id,
                    close_price=close_price,
                    close_reason=close_reason,
                    pos_row=pos,
                )
                if trade:
                    closed_trades.append(trade)
            else:
                # Cập nhật PnL thả nổi tức thời
                with self.db.session() as conn:
                    conn.execute(
                        """
                        UPDATE paper_positions 
                        SET current_price = ?, floating_pnl = ?, floating_pnl_percent = ?, last_update = ?
                        WHERE position_id = ?;
                        """,
                        (curr_p, pnl_usd, pnl_pct, now_str, pos_id),
                    )

        # Cập nhật số dư & tài sản tổng của ví
        self._sync_wallet_equity(wallet_id)
        return closed_trades

    def _evaluate_smart_sl(
        self,
        direction: str,
        open_price: float,
        current_price: float,
        current_sl: float,
        df_m5: Optional[pd.DataFrame] = None,
    ) -> Optional[float]:
        """Tính toán dời Stop Loss thích ứng (Breakeven cushion + Trailing Stop) bằng SmartExitEngine."""
        try:
            # Tạo dummy signal để tương thích với SmartExitEngine
            dir_enum = SignalDirection.BUY if direction == "BUY" else SignalDirection.SELL
            dummy_sig = TradingSignal(
                signal_id="dummy",
                symbol="XAUUSD",
                timeframe="M5",
                direction=dir_enum,
                entry_price=open_price,
                stop_loss=current_sl,
                take_profit_1=open_price + 15.0 if direction == "BUY" else open_price - 15.0,
            )

            decisions = self.smart_exit.evaluate_signal(
                signal=dummy_sig,
                current_price=current_price,
                df_m5=df_m5,
                spread=0.2,
            )

            for dec in decisions:
                if dec.action_type in (
                    ExitActionType.BREAKEVEN_PROTECTION,
                    ExitActionType.TRAILING_STOP_UPDATE,
                    ExitActionType.SWING_STRUCTURE_TRAILING,
                ):
                    if dec.new_sl is not None:
                        if direction == "BUY" and dec.new_sl > current_sl:
                            return dec.new_sl
                        elif direction == "SELL" and dec.new_sl < current_sl:
                            return dec.new_sl
        except Exception as e:
            log.debug("Lỗi tính Smart SL ví ảo: %s", e)

        return None

    def _execute_close_position(
        self,
        pos_id: str,
        wallet_id: str,
        close_price: float,
        close_reason: str,
        pos_row: sqlite3.Row,
    ) -> Optional[PaperTradeHistory]:
        """Đóng vị thế, ghi nhận PnL ròng vào số dư ví, lưu lịch sử và chụp snapshot."""
        open_p = float(pos_row["open_price"])
        vol = float(pos_row["volume"])
        direction = pos_row["direction"]
        open_time = pos_row["open_time"]
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()

        # Tính toán PnL cuối cùng
        if direction == "BUY":
            pnl_pts = close_price - open_p
        else:
            pnl_pts = open_p - close_price

        pnl_usd = round(pnl_pts * self.CONTRACT_SIZE * vol, 2)
        pnl_pips = round(pnl_pts * 10.0, 1)

        # Tính thời gian giữ lệnh
        dur_sec = 0
        if open_time:
            try:
                op_dt = datetime.fromisoformat(open_time)
                if not op_dt.tzinfo:
                    op_dt = op_dt.replace(tzinfo=timezone.utc)
                dur_sec = int((now_dt - op_dt).total_seconds())
            except Exception:
                pass

        trade_id = f"TRD-{uuid.uuid4().hex[:8].upper()}"

        with self.db.session() as conn:
            cursor = conn.cursor()

            # 1. Xóa khỏi paper_positions
            cursor.execute("DELETE FROM paper_positions WHERE position_id = ?;", (pos_id,))

            # 2. Thêm vào paper_trades_history
            cursor.execute(
                """
                INSERT INTO paper_trades_history 
                (trade_id, wallet_id, signal_id, symbol, direction, volume, open_price, close_price,
                 stop_loss, take_profit, pnl_usd, pnl_percent, pnl_pips, close_reason, open_time, close_time, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?);
                """,
                (
                    trade_id,
                    wallet_id,
                    pos_row["signal_id"],
                    pos_row["symbol"],
                    direction,
                    vol,
                    open_p,
                    close_price,
                    pos_row["stop_loss"],
                    pos_row["take_profit_1"],
                    pnl_usd,
                    pnl_pips,
                    close_reason,
                    open_time,
                    now_str,
                    dur_sec,
                ),
            )

            # 3. Cập nhật Balance ví
            cursor.execute(
                """
                UPDATE paper_wallets 
                SET balance = balance + ?, updated_at = ?
                WHERE wallet_id = ?;
                """,
                (pnl_usd, now_str, wallet_id),
            )

            # 4. Ghi snapshot vốn
            cursor.execute("SELECT balance FROM paper_wallets WHERE wallet_id = ?;", (wallet_id,))
            new_bal = float(cursor.fetchone()[0])
            cursor.execute(
                """
                INSERT INTO paper_equity_snapshots (wallet_id, balance, equity, timestamp)
                VALUES (?, ?, ?, ?);
                """,
                (wallet_id, new_bal, new_bal, now_str),
            )

        log.info(
            "🎯 [VÍ ẢO %s] ĐÓNG LỆNH: %s %.2f lot %s @ %.2f -> %.2f | PnL: %s$%.2f (%s%.1f pips) [%s]",
            wallet_id, direction, vol, pos_row["symbol"], open_p, close_price,
            "+" if pnl_usd >= 0 else "", pnl_usd,
            "+" if pnl_pips >= 0 else "", pnl_pips, close_reason,
        )

        # Thông báo qua Telegram (mặc định tắt để tránh làm phiền kênh)
        if self.notify_telegram and self.notifier and getattr(self.notifier, "is_enabled", False):
            try:
                status_emoji = "🎯 LÃI" if pnl_usd > 0 else ("🛡️ HÒA VỐN" if pnl_usd == 0 else "🛑 CẮT LỖ")
                dur_min = max(1, dur_sec // 60)
                dur_str = f"{dur_min} phút" if dur_min < 60 else f"{dur_min // 60}h {dur_min % 60}m"
                msg = (
                    f"💼 <b>VÍ ĐẦU TƯ ẢO (0.01 LOT): BÁO CÁO KẾT QUẢ</b>\n\n"
                    f"📌 <b>Lệnh:</b> {direction} {pos_row['symbol']} <code>#{pos_id}</code>\n"
                    f"🏆 <b>Kết quả:</b> {status_emoji} <b>{'+' if pnl_usd >= 0 else ''}${pnl_usd:.2f} USD</b> ({'+' if pnl_pips >= 0 else ''}{pnl_pips:.1f} pips)\n"
                    f"🎯 <b>Giá vào / đóng:</b> <code>{open_p:.2f}</code> ➜ <code>{close_price:.2f}</code>\n"
                    f"🏷️ <b>Lý do đóng:</b> <code>{close_reason}</code> | ⏱️ <b>Thời gian giữ:</b> {dur_str}\n"
                    f"💰 <b>Số dư ví mới:</b> <b>${new_bal:.2f} USD</b>\n"
                    f"⏰ <i>{datetime.now().strftime('%H:%M:%S')} (VN) | VietKey Paper Engine</i>"
                )
                self.notifier.send_raw_message(msg)
            except Exception as e:
                log.debug("Lỗi gửi thông báo đóng lệnh ví ảo: %s", e)

        return PaperTradeHistory(
            trade_id=trade_id,
            wallet_id=wallet_id,
            signal_id=pos_row["signal_id"],
            symbol=pos_row["symbol"],
            direction=direction,
            volume=vol,
            open_price=open_p,
            close_price=close_price,
            stop_loss=pos_row["stop_loss"],
            take_profit=pos_row["take_profit_1"],
            pnl_usd=pnl_usd,
            pnl_percent=round((pnl_usd / new_bal) * 100.0, 2),
            pnl_pips=pnl_pips,
            close_reason=close_reason,
            open_time=open_time,
            close_time=now_str,
            duration_seconds=dur_sec,
        )

    def close_position_manual(
        self,
        position_id: str,
        current_price: float,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> Optional[PaperTradeHistory]:
        """Đóng lệnh thủ công từ nút bấm trên giao diện người dùng (Manual Close)."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_positions WHERE position_id = ? AND wallet_id = ? AND status = 'OPEN';",
                (position_id, wallet_id),
            )
            pos_row = cursor.fetchone()

        if not pos_row:
            log.warning("Không tìm thấy lệnh đang mở %s để đóng thủ công.", position_id)
            return None

        trade = self._execute_close_position(
            pos_id=position_id,
            wallet_id=wallet_id,
            close_price=current_price,
            close_reason="MANUAL",
            pos_row=pos_row,
        )
        self._sync_wallet_equity(wallet_id)
        return trade

    def close_position_by_signal(
        self,
        signal_id: str,
        current_price: float,
        reason: str = "SIGNAL_CLOSED",
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> Optional[PaperTradeHistory]:
        """Đóng lệnh ảo tương ứng với một signal_id khi tín hiệu đạt TP hoặc SL."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_positions WHERE wallet_id = ? AND signal_id = ? AND status = 'OPEN';",
                (wallet_id, signal_id),
            )
            pos_row = cursor.fetchone()

        if not pos_row:
            return None

        trade = self._execute_close_position(
            pos_id=pos_row["position_id"],
            wallet_id=wallet_id,
            close_price=current_price,
            close_reason=reason,
            pos_row=pos_row,
        )
        self._sync_wallet_equity(wallet_id)
        return trade

    def update_position_sl(
        self,
        signal_id: str,
        new_sl: float,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> bool:
        """Đồng bộ mức Stop Loss mới (Breakeven / Trailing Stop) từ tín hiệu vào vị thế ví ảo."""
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE paper_positions SET stop_loss = ?, last_update = ? WHERE wallet_id = ? AND signal_id = ? AND status = 'OPEN';",
                (new_sl, datetime.now(timezone.utc).isoformat(), wallet_id, signal_id),
            )
            return cursor.rowcount > 0

    def _sync_wallet_equity(self, wallet_id: str = DEFAULT_WALLET_ID) -> None:
        """Đồng bộ tài sản Equity = Balance + Floating PnL của ví vào SQLite."""
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT balance FROM paper_wallets WHERE wallet_id = ?;",
                (wallet_id,),
            )
            row = cursor.fetchone()
            if not row:
                return
            bal = float(row[0])

            cursor.execute(
                "SELECT SUM(floating_pnl) FROM paper_positions WHERE wallet_id = ? AND status = 'OPEN';",
                (wallet_id,),
            )
            fl_row = cursor.fetchone()
            fl_pnl = float(fl_row[0] or 0.0)
            equity = round(bal + fl_pnl, 2)
            now_str = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                "UPDATE paper_wallets SET equity = ?, updated_at = ? WHERE wallet_id = ?;",
                (equity, now_str, wallet_id),
            )

    # =========================================================================
    # DANH SÁCH LỆNH VÀ BIỂU ĐỒ (QUERIES)
    # =========================================================================

    def get_open_positions(self, wallet_id: str = DEFAULT_WALLET_ID) -> list[dict]:
        """Lấy danh sách các lệnh đang mở trên ví ảo kèm PnL cập nhật."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_positions WHERE wallet_id = ? AND status = 'OPEN' ORDER BY open_time DESC;",
                (wallet_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_trade_history(
        self,
        limit: int = 50,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> list[dict]:
        """Lấy danh sách các lệnh đã chốt lời / cắt lỗ trên ví ảo."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM paper_trades_history WHERE wallet_id = ? ORDER BY close_time DESC LIMIT ?;",
                (wallet_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_equity_curve(
        self,
        limit: int = 100,
        wallet_id: str = DEFAULT_WALLET_ID,
    ) -> list[dict]:
        """Lấy danh sách các điểm snapshot tăng trưởng tài sản (Balance/Equity) vẽ biểu đồ."""
        with self.db.session() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp, balance, equity FROM paper_equity_snapshots WHERE wallet_id = ? ORDER BY id ASC LIMIT ?;",
                (wallet_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
