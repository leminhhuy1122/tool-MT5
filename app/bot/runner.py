# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Live Bot Runner Engine (Phase 10).

Bộ điều phối toàn diện cho việc chạy tự động theo thời gian thực (Real-time Execution Loop):
- Thu thập nến đa khung thời gian từ MT5 Terminal.
- Nhận diện đóng nến M5 (New bar detection) để phân tích setup.
- Phân tích kỹ thuật, cấu trúc thị trường và chấm điểm hợp lưu.
- Lọc tín hiệu qua bộ lọc Machine Learning (Phase 9).
- Quản lý trạng thái lệnh (SignalTracker):
  + Entry zone ±1 giá.
  + Lãi 5 giá kéo SL hòa vốn.
  + Lãi 10 giá chốt 50% TP1, gồng nuôi TP2.
- Gửi thông báo Telegram tức thì (tín hiệu mới và cập nhật trạng thái).
- Lưu vết toàn bộ lịch sử, đặc trưng và kết quả vào SQLite Database.
- Tuyệt đối an toàn: KHÔNG tự động đặt lệnh tiền thật.
"""

from datetime import datetime, timezone
import json
import os
import re
import signal
import sys
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from app.database.connection import DatabaseManager
from app.database.repository import MarketDataRepository, SignalRepository
from app.market.data_manager import MarketDataManager
from app.market.timeframe_manager import Timeframe
from app.ml.features import FeatureExtractor
from app.ml.filter import MLSignalFilter
from app.ml.model import SignalQualityClassifier
from app.ml.registry import ModelRegistry
from app.mt5.connector import MT5Connector
from app.mt5.executor import MT5Executor, OrderResult, PositionInfo
from app.news.ai_writer import AINewsWriter
from app.news.calendar import NewsManager
from app.strategy.feedback_learner import SelfLearningFeedbackEngine, TradeOutcomeAnalyzer
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_tracker import SignalTracker, TrackerConfig
from app.strategy.smart_exit import ExitActionType, SmartExitConfig, SmartExitEngine
from app.simulator.paper_engine import PaperTradingEngine
from app.telegram.notifier import TelegramNotifier
from config import MT5TradingConfig, Settings, get_settings
from logger import get_logger

log = get_logger("bot.runner")


class LiveBotRunner:
    """Động cơ điều phối bot giao dịch thời gian thực."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        db_manager: Optional[DatabaseManager] = None,
        connector: Optional[MT5Connector] = None,
        notifier: Optional[TelegramNotifier] = None,
        news_manager: Optional[NewsManager] = None,
    ):
        self.settings = settings or get_settings()
        self.symbol = self.settings.mt5.symbol
        self.is_running = False

        # 1. Cơ sở dữ liệu SQLite
        self.db = db_manager or DatabaseManager(config=self.settings.database)
        self.signal_repo = SignalRepository(self.db)
        self.market_repo = MarketDataRepository(self.db)

        # 2. Kết nối MT5
        self.connector = connector or MT5Connector(self.settings.mt5)
        self.data_mgr = MarketDataManager(self.symbol)

        # 3. Quản lý Lịch Kinh Tế & Tin Tức Tài Chính
        self.news_mgr = news_manager or NewsManager()
        self.ai_news_writer = AINewsWriter(self.settings.openai)
        self._notified_realtime_news_ids: set[str] = set()

        # 4. Tích hợp Machine Learning Filter & Model Registry (Phase 7 & 10)
        self.ml_registry = ModelRegistry(self.db)
        if getattr(getattr(self.settings, "optimization", None), "enable_ml_filter", True):
            classifier = self.ml_registry.get_active_production_model()
            self.ml_filter = MLSignalFilter(classifier=classifier)
        else:
            log.info("Optimization: ML Signal Filter đã tắt theo cấu hình (Pure Rule-based SMC Mode).")
            self.ml_filter = None

        # 4b. Động cơ tự học từ closed trades (Phase 8 & 10)
        if getattr(getattr(self.settings, "optimization", None), "enable_self_learning", True):
            self.feedback_engine = SelfLearningFeedbackEngine(repository=self.signal_repo)
            try:
                self.feedback_engine.refresh()
            except Exception as e:
                log.debug("Khởi tạo feedback engine: %s", e)
        else:
            log.info("Optimization: Feedback Learning Engine đã tắt theo cấu hình.")
            self.feedback_engine = None

        # 4c. Process Singleton Guard (Phase 10)
        self.singleton_guard = None
        if getattr(getattr(self.settings, "optimization", None), "enable_process_singleton", True):
            from app.system.resource_optimizer import ProcessSingletonGuard
            self.singleton_guard = ProcessSingletonGuard()

        # 4d. Smart Exit & Adaptive Profit Protection Engine (Phase 12)
        exit_cfg = getattr(self.settings, "smart_exit", None)
        self.smart_exit = SmartExitEngine(config=exit_cfg)

        # 4e. Cấu hình Hedging Chiến Lược & Smart DCA Recovery
        from config import HedgingConfig, DCAConfig
        self.hedging_cfg = getattr(self.settings, "hedging", None) or HedgingConfig()
        self.dca_cfg = getattr(self.settings, "dca", None) or DCAConfig()

        # 4f. AI Trading Copilot Companion (Đồng hành đàm đạo thời gian thực)
        from app.strategy.ai_companion import AITradingCopilot
        self.ai_copilot = AITradingCopilot()

        # 3. Động cơ phân tích & Tín hiệu
        self.signal_engine = SignalEngine(
            strategy_version="v1.0-M5",
            symbol=self.symbol,
            default_timeframe="M5",
            ml_filter=self.ml_filter,
            feedback_engine=self.feedback_engine,
        )

        # 5. Bộ theo dõi tín hiệu (Khôi phục trạng thái active từ SQLite để chống trùng lặp khi khởi động lại)
        self.tracker = SignalTracker(config=TrackerConfig(
            cooldown_minutes=45,
            max_active_signals=3,
            max_unfilled_distance_pts=8.0,
            unfilled_expiry_minutes=45,
        ))
        try:
            active_rows = self.signal_repo.get_active_signals(self.symbol)
            if active_rows:
                active_signals = [TradingSignal.from_dict(row) for row in active_rows]
                self.tracker.load_active_signals(active_signals)
        except Exception as e:
            log.warning("Không thể nạp tín hiệu active từ database: %s", e)

        # 6. Telegram Notifier
        self.notifier = notifier or TelegramNotifier(self.settings.telegram)

        # 7. Ví Đầu Tư Ảo & Paper Trading Engine
        self.paper_engine = PaperTradingEngine(
            db_manager=self.db,
            notifier=self.notifier,
            smart_exit_engine=self.smart_exit,
        )

        # 8. MT5 Live Order Executor (Auto-Trading trực tiếp trên sàn MT5)
        self.mt5_trading_config = getattr(self.settings, "mt5_trading", None) or MT5TradingConfig.from_env()
        self.mt5_executor = MT5Executor(config=self.mt5_trading_config)
        self._signal_mt5_tickets: dict[str, int] = {}

        # Trạng thái vòng lặp và tự phục hồi
        self.last_processed_m5_time: Optional[datetime] = None
        self.last_price: float = 0.0
        self._disconnect_count: int = 0
        self._last_reconnect_attempt: float = 0.0
        self._last_cleanup_time: float = 0.0

    def start(self) -> None:
        """Khởi động bot và kết nối các dịch vụ."""
        log.info("=" * 60)
        log.info("  VIETKEY GOLD AI — KHỞI ĐỘNG LIVE BOT ENGINE")
        log.info("  Symbol: %s | Timeframe: M5 (Trend: H1/H4)", self.symbol)
        log.info("  Chế độ: FORWARD TESTING / SIGNALS ONLY (KHÔNG AUTO-ORDER)")
        log.info("=" * 60)

        # Kiểm tra Process Singleton Guard chống trùng lặp instance (Phase 10)
        if self.singleton_guard:
            if not self.singleton_guard.acquire():
                log.error("Không thể khởi động: Đã có instance bot khác đang chạy trên hệ thống.")
                return

        # Kết nối MT5
        if not self.connector.is_connected:
            res = self.connector.connect()
            if not res.success:
                log.error("Không thể kết nối MT5 Terminal: %s", res.error)
                if self.singleton_guard:
                    self.singleton_guard.release()
                return

        # Kiểm tra kết nối Telegram
        if self.notifier.is_enabled:
            log.info("✓ Telegram Notifier đã kích hoạt.")

        self.is_running = True

    def stop(self) -> None:
        """Dừng bot an toàn."""
        log.info("Đang dừng Live Bot Runner...")
        self.is_running = False
        if self.connector.is_connected:
            self.connector.disconnect()
        if self.singleton_guard:
            self.singleton_guard.release()
        log.info("✓ Bot đã dừng an toàn.")

    def run_once(self) -> Optional[TradingSignal]:
        """
        Thực hiện một chu kỳ kiểm tra:
        1. Cập nhật giá thị trường hiện tại và cập nhật trạng thái các lệnh active.
        2. Nếu có nến M5 mới đóng -> Chạy phân tích đa khung thời gian và sinh tín hiệu.
        3. Gửi thông báo và lưu trữ database.
        """
        try:
            # 1. Lấy giá mới nhất từ MT5 (kèm cơ chế Auto-Reconnect)
            price_info = self.data_mgr.get_latest_price()
            if not price_info:
                now_ts = time.time()
                if not self.connector.is_connected and (now_ts - self._last_reconnect_attempt > 10.0):
                    self._last_reconnect_attempt = now_ts
                    self._disconnect_count += 1
                    log.warning(
                        "⚠️ Phát hiện mất kết nối MT5 (lần %d). Đang thử tự động kết nối lại...",
                        self._disconnect_count,
                    )
                    res = self.connector.connect()
                    if res.success:
                        log.info("✓ Tự động kết nối lại MT5 thành công!")
                        self._disconnect_count = 0
                        price_info = self.data_mgr.get_latest_price()
                    else:
                        log.error("❌ Tự động kết nối lại MT5 thất bại: %s", res.message)
                        if self._disconnect_count == 3 and self.notifier.is_enabled:
                            self.notifier.send_system_event(
                                event_type="DISCONNECT",
                                message="⚠️ CẢNH BÁO HỆ THỐNG: Mất kết nối MT5 Terminal liên tiếp 3 lần. Bot tạm dừng phân tích!",
                            )
                if not price_info:
                    return None

            # Reset bộ đếm khi đã có giá thành công
            self._disconnect_count = 0

            # Dọn dẹp định kỳ (mỗi 1 giờ) các tín hiệu đã đóng trong SignalTracker
            if time.time() - self._last_cleanup_time > 3600:
                self._last_cleanup_time = time.time()
                self.tracker.cleanup_old_signals(max_age_hours=48)

            current_price = float(price_info.get("bid", 0.0))
            self.last_price = current_price
            now_utc = datetime.now(timezone.utc)

            # 2. Cập nhật trạng thái các tín hiệu đang ACTIVE
            changed_signals = self.tracker.update_price(
                current_price=current_price,
                current_time=now_utc,
            )

            for sig in changed_signals:
                log.info("⚡ Tín hiệu [%s] thay đổi trạng thái: %s @ %.2f",
                         sig.signal_id, sig.status.value, current_price)

                # Cập nhật vào SQLite kèm lý do nếu bị invalidation
                self.signal_repo.update_status(
                    sig.signal_id,
                    sig.status,
                    invalidation=getattr(sig, "invalidation", None),
                )
                # 1. KHI TÍN HIỆU CHÍNH THỨC KHỚP VÙNG ENTRY -> KHỚP LỆNH VÍ ẢO 1:1 & MT5 LIVE
                if sig.status == SignalStatus.ENTRY_REACHED:
                    try:
                        spread = float(price_info.get("spread", 0.3)) if price_info else 0.3
                        self.paper_engine.open_position_from_signal(
                            signal=sig,
                            current_price=current_price,
                            spread=spread,
                        )
                    except Exception as e:
                        log.debug("Lỗi khớp lệnh Paper Wallet khi ENTRY_REACHED: %s", e)

                    # Bắn lệnh thực thi trực tiếp trên MT5 nếu bật MT5 Auto-Trading
                    if getattr(self.mt5_trading_config, "enabled", False):
                        try:
                            if sig.signal_id not in self._signal_mt5_tickets:
                                order_res = self.mt5_executor.send_market_order(
                                    symbol=sig.symbol,
                                    direction=sig.direction,
                                    volume=self.mt5_trading_config.lot_size,
                                    sl=sig.stop_loss,
                                    tp=sig.take_profit_1,
                                    comment=f"VK_{sig.signal_id[:6]}",
                                    magic=self.mt5_trading_config.magic_number,
                                )
                                if order_res.success:
                                    self._signal_mt5_tickets[sig.signal_id] = order_res.ticket
                                    if self.notifier and self.notifier.is_enabled:
                                        self.notifier.send_raw_message(
                                            f"🚀 <b>MT5 AUTO-TRADING: ĐÃ VÀO LỆNH THÀNH CÔNG!</b>\n\n"
                                            f"📌 <b>Lệnh:</b> {sig.direction.value} {sig.symbol} <code>#{order_res.ticket}</code>\n"
                                            f"📊 <b>Khối lượng:</b> <code>{order_res.volume} lot</code> @ <code>{order_res.price:.2f}</code>\n"
                                            f"🛑 <b>Stop Loss:</b> <code>{order_res.sl:.2f}</code> (Ghim server 0ms)\n"
                                            f"🎯 <b>Take Profit:</b> <code>{order_res.tp:.2f}</code>\n"
                                            f"⚡ <i>Khớp tự động bởi VietKey MT5 Live Executor</i>"
                                        )
                        except Exception as e:
                            log.error("Lỗi đặt lệnh MT5 Live: %s", e)

                # 2. KHI TÍN HIỆU ĐẠT TP HOẶC SL -> ĐÓNG VỊ THẾ VÀ TÍNH PNL THẬT
                elif sig.status in (SignalStatus.TP_REACHED, SignalStatus.SL_REACHED):
                    pnl_pts = (current_price - sig.entry_price) if sig.direction == SignalDirection.BUY else (sig.entry_price - current_price)
                    diff_sec = None
                    duration_str = None
                    if sig.created_at:
                        c_time = sig.created_at if sig.created_at.tzinfo else sig.created_at.replace(tzinfo=timezone.utc)
                        diff_sec = int((now_utc - c_time).total_seconds())
                        mins = max(1, diff_sec // 60)
                        if mins < 60:
                            duration_str = f"{mins} phút"
                        else:
                            duration_str = f"{mins // 60}h {mins % 60}m"

                    # Phân tích chuyên sâu nguyên nhân kết quả lệnh qua TradeOutcomeAnalyzer
                    outcome_analysis = TradeOutcomeAnalyzer.analyze(
                        signal=sig,
                        final_status=sig.status.value,
                        exit_price=current_price,
                        duration_seconds=diff_sec or 0,
                    )
                    notes_json = json.dumps(outcome_analysis.to_dict(), ensure_ascii=False)

                    self.signal_repo.save_outcome(
                        signal_id=sig.signal_id,
                        final_status=sig.status.value,
                        exit_price=current_price,
                        pnl_points=round(pnl_pts, 2),
                        pnl_r=round(outcome_analysis.pnl_r, 2),
                        duration_seconds=diff_sec,
                        notes=notes_json,
                    )

                    # Đóng vị thế tương ứng trên Ví Đầu Tư Ảo (nếu có lệnh đang mở)
                    try:
                        self.paper_engine.close_position_by_signal(
                            signal_id=sig.signal_id,
                            current_price=current_price,
                            reason=sig.status.value,
                        )
                    except Exception as e:
                        log.debug("Lỗi đóng lệnh Paper Wallet theo signal: %s", e)

                    # Đóng vị thế MT5 nếu broker chưa tự cắt
                    if getattr(self.mt5_trading_config, "enabled", False) and sig.signal_id in self._signal_mt5_tickets:
                        ticket = self._signal_mt5_tickets.pop(sig.signal_id, None)
                        if ticket:
                            try:
                                self.mt5_executor.close_position(ticket=ticket, comment=sig.status.value)
                            except Exception as e:
                                log.debug("Lỗi đóng vị thế MT5 theo signal: %s", e)

                    # Xóa trạng thái trong AI Copilot
                    try:
                        self.ai_copilot.clear_signal(sig.signal_id)
                    except Exception:
                        pass

                # 3. KHI TÍN HIỆU BỊ HỦY / HẾT HẠN TRƯỚC HOẶC TRONG KHI KHỚP
                elif sig.status in (SignalStatus.INVALIDATED, SignalStatus.CANCELLED, SignalStatus.EXPIRED):
                    try:
                        self.paper_engine.close_position_by_signal(
                            signal_id=sig.signal_id,
                            current_price=current_price,
                            reason=sig.status.value,
                        )
                    except Exception as e:
                        log.debug("Lỗi đóng/hủy lệnh Paper Wallet khi tín hiệu bị hủy: %s", e)

                    # Đóng hoặc hủy lệnh MT5 nếu bị hủy
                    if getattr(self.mt5_trading_config, "enabled", False) and sig.signal_id in self._signal_mt5_tickets:
                        ticket = self._signal_mt5_tickets.pop(sig.signal_id, None)
                        if ticket:
                            try:
                                self.mt5_executor.close_position(ticket=ticket, comment=sig.status.value)
                            except Exception as e:
                                log.debug("Lỗi đóng vị thế MT5 khi tín hiệu bị hủy: %s", e)

                    # Tự động cập nhật ma trận thích ứng Self-Learning
                    try:
                        self.feedback_engine.refresh()
                    except Exception:
                        pass

                    # Lấy thống kê hiệu suất tích lũy sau lệnh vừa đóng
                    perf_stats = None
                    try:
                        perf_stats = self.signal_repo.get_performance_summary()
                    except Exception as e:
                        log.debug("Lỗi lấy perf stats: %s", e)

                    # Bắn thông báo tổng hợp kết quả (Lời/Lỗ bao nhiêu Pip) lên Telegram
                    if self.notifier and self.notifier.is_enabled:
                        self.notifier.send_trade_outcome_summary(
                            signal_or_data=sig,
                            exit_price=current_price,
                            pnl_points=pnl_pts,
                            duration_str=duration_str,
                            stats=perf_stats,
                        )

                # Gửi thông báo cập nhật qua Telegram
                self.notifier.notify_status_update(sig, current_price)

            # 2a. Tự động kiểm tra và nâng Stop Loss (Risk-Free Breakeven + Dynamic Trailing Stop)
            try:
                self.check_trailing_stop_and_breakeven(current_price=current_price)
            except Exception as e:
                log.debug("Lỗi kiểm tra Trailing Stop / Breakeven: %s", e)

            # 2b. Tự động kiểm tra và phát bài viết Tin Nóng sau khi tin ra 2-3 phút
            try:
                self.check_realtime_news_releases(current_price=current_price, now_utc=now_utc)
            except Exception as e:
                log.debug("Lỗi kiểm tra tin tức thời gian thực: %s", e)

            # 2c. Tự động bám sát giá và quản trị vị thế trên Ví Đầu Tư Ảo (Paper Wallet 0.01 lot)
            try:
                spread = float(price_info.get("spread", 0.3))
                half_sp = spread / 2.0
                self.paper_engine.update_positions(
                    current_bid=round(current_price - half_sp, 2),
                    current_ask=round(current_price + half_sp, 2),
                )
            except Exception as e:
                log.debug("Lỗi cập nhật Paper Engine: %s", e)

            # 2d. AI Trading Copilot: Trò chuyện và đồng hành thời gian thực cùng anh em trader
            try:
                self.check_ai_copilot_companion(current_price=current_price, now_utc=now_utc)
            except Exception as e:
                log.debug("Lỗi AI Copilot Companion: %s", e)

            # 2e. Tự động đồng bộ và khớp lệnh MT5 cho các tín hiệu ENTRY_REACHED chưa có lệnh MT5
            if getattr(self.mt5_trading_config, "enabled", False):
                try:
                    for sig in self.tracker.active_signals:
                        if sig.status == SignalStatus.ENTRY_REACHED and sig.signal_id not in self._signal_mt5_tickets:
                            is_buy = sig.direction == SignalDirection.BUY
                            price_ok = (current_price > sig.stop_loss) if is_buy else (current_price < sig.stop_loss)
                            if price_ok:
                                order_res = self.mt5_executor.send_market_order(
                                    symbol=sig.symbol,
                                    direction=sig.direction,
                                    volume=self.mt5_trading_config.lot_size,
                                    sl=sig.stop_loss,
                                    tp=sig.take_profit_1,
                                    comment=f"VK_{sig.signal_id[:6]}",
                                    magic=self.mt5_trading_config.magic_number,
                                )
                                if order_res.success:
                                    self._signal_mt5_tickets[sig.signal_id] = order_res.ticket
                                    log.info("🚀 [MT5 AUTO] Đã đồng bộ vào lệnh cho tín hiệu %s: Ticket #%d", sig.signal_id, order_res.ticket)
                                    if self.notifier and self.notifier.is_enabled:
                                        self.notifier.send_raw_message(
                                            f"🚀 <b>MT5 AUTO-TRADING: ĐÃ VÀO LỆNH THÀNH CÔNG!</b>\n\n"
                                            f"📌 <b>Lệnh:</b> {sig.direction.value} {sig.symbol} <code>#{order_res.ticket}</code>\n"
                                            f"📊 <b>Khối lượng:</b> <code>{order_res.volume} lot</code> @ <code>{order_res.price:.2f}</code>\n"
                                            f"🛑 <b>Stop Loss:</b> <code>{order_res.sl:.2f}</code> (Ghim server 0ms)\n"
                                            f"🎯 <b>Take Profit:</b> <code>{order_res.tp:.2f}</code>\n"
                                            f"⚡ <i>Khớp tự động bởi VietKey MT5 Live Executor</i>"
                                        )
                except Exception as e:
                    log.debug("Lỗi đồng bộ vào lệnh MT5: %s", e)

            # 3. Thu thập nến M5 và kiểm tra nến mới (Lightweight check 2 bars trước khi tải 100 nến)
            has_new_candle, _ = self.data_mgr.check_new_candle(Timeframe.M5, self.last_processed_m5_time)
            if not has_new_candle:
                return None

            df_m5 = self.data_mgr.get_candles(Timeframe.M5, num_bars=100)
            if df_m5 is None or len(df_m5) < 30:
                return None

            last_bar_time = df_m5["time"].iloc[-1]
            if isinstance(last_bar_time, str):
                last_bar_time = pd.to_datetime(last_bar_time)

            # Chỉ phân tích khi có nến M5 mới xuất hiện
            if self.last_processed_m5_time is not None and last_bar_time <= self.last_processed_m5_time:
                return None

            self.last_processed_m5_time = last_bar_time
            close_price = float(df_m5["close"].iloc[-1])
            log.info("✓ Nhận diện nến M5 mới: %s (Close: %.2f)", last_bar_time, close_price)

            # Kiểm tra Cảnh Báo Thoát Lệnh Sớm (Early Exit Alert) khi nến M5 vi phạm cấu trúc Order Block
            try:
                self.check_early_structural_exit(close_price=close_price)
            except Exception as e:
                log.debug("Lỗi kiểm tra early structural exit: %s", e)

            # Kiểm tra Cảnh Báo Chốt Lời Sớm (Động lượng suy yếu & Lệnh ứ đọng)
            try:
                self.check_momentum_exhaustion_and_stagnation(
                    df_m5=df_m5,
                    current_price=close_price,
                    now_utc=now_utc,
                )
            except Exception as e:
                log.debug("Lỗi kiểm tra momentum exhaustion & stagnation: %s", e)

            # Lưu nến vào database
            try:
                self.market_repo.save_candles(self.symbol, "M5", df_m5.iloc[-2:])
            except Exception as e:
                log.debug("Lưu nến market_data: %s", e)

            # 4. Tải nến các khung lớn: H1 và H4
            df_h1 = self.data_mgr.get_candles(Timeframe.H1, num_bars=100)
            df_h4 = self.data_mgr.get_candles(Timeframe.H4, num_bars=50)

            # 5. Kiểm tra Vùng Cấm Giao Dịch Tin Đỏ (News Blackout Window)
            is_blackout, news_event = self.news_mgr.is_in_blackout_window(
                current_time=now_utc,
                buffer_before_min=30,
                buffer_after_min=20,
            )
            if is_blackout and news_event:
                log.warning(
                    "⚠️ VÙNG CẤM GIAO DỊCH TIN ĐỎ USD: [%s] (%s UTC). Tự động hoãn phát tín hiệu để tránh bão giá quét SL!",
                    news_event.title,
                    news_event.time_utc.strftime("%H:%M"),
                )
                return None

            # 6. Sinh tín hiệu qua SignalEngine
            raw_signal = self.signal_engine.generate_signal(
                df=df_m5,
                h4_df=df_h1,  # Cho khung M5, xu hướng lớn gần nhất là H1
                symbol=self.symbol,
                timeframe="M5",
            )

            # 6. Tinh chỉnh qua bộ lọc Machine Learning nếu được bật
            spread = float(price_info.get("spread", 0.3))
            if self.ml_filter:
                final_signal = self.ml_filter.apply(raw_signal, df_m5, spread=spread)
            else:
                final_signal = raw_signal

            # 7. Xử lý tín hiệu BUY hoặc SELL
            if final_signal.direction in (SignalDirection.BUY, SignalDirection.SELL):
                log.info("🔥 PHÁT HIỆN TÍN HIỆU: %s %s @ %.2f (Score: %.1f)",
                         final_signal.direction.value, self.symbol,
                         final_signal.entry_price, final_signal.score)

                # Chống trùng lặp & Smart DCA Recovery Guard: Kiểm tra trực tiếp cả ở Database SQLite
                active_in_db = self.signal_repo.get_active_signals(self.symbol)
                for s in active_in_db:
                    if s.get("direction") == final_signal.direction.value:
                        # 1. Kiểm tra nếu là tín hiệu Smart DCA hợp lệ đã được gắn cờ
                        if getattr(final_signal, "is_dca", False):
                            log.info(
                                "🎯 CHO PHÉP LỆNH DCA: Lệnh gốc %s [%s] @ %.2f -> Lệnh DCA mới @ %.2f (Hòa vốn: %.2f)",
                                final_signal.direction.value, s.get("signal_id"), float(s.get("entry_price", 0.0)),
                                final_signal.entry_price, getattr(final_signal, "dca_breakeven_price", 0.0),
                            )
                            break

                        # 2. Hoặc kiểm tra điều kiện kích hoạt DCA trực tiếp từ DB
                        if getattr(self.dca_cfg, "enabled", True):
                            existing_entry = float(s.get("entry_price", 0.0))
                            drawdown = (existing_entry - final_signal.entry_price) if final_signal.direction == SignalDirection.BUY else (final_signal.entry_price - existing_entry)
                            min_dist = getattr(self.dca_cfg, "min_drawdown_distance", 3.5)

                            already_has_dca = any(
                                (act.get("parent_signal_id") == s.get("signal_id") or act.get("is_dca") == 1)
                                for act in active_in_db
                            )

                            if drawdown >= min_dist and not already_has_dca:
                                P_be = round((existing_entry + final_signal.entry_price) / 2.0, 2)
                                final_signal.is_dca = True
                                final_signal.parent_signal_id = s.get("signal_id")
                                final_signal.dca_breakeven_price = P_be
                                final_signal.dca_step = 1
                                final_signal.setup_type = f"DCA_{final_signal.setup_type}" if not final_signal.setup_type.startswith("DCA_") else final_signal.setup_type
                                be_buf = 0.5 if final_signal.is_buy else -0.5
                                final_signal.take_profit_1 = round(P_be + be_buf, 2)
                                if float(s.get("take_profit_1", 0.0)) > 0:
                                    final_signal.take_profit_2 = float(s.get("take_profit_1", 0.0))
                                p_id_short = str(s.get("signal_id", ""))[:8]
                                final_signal.reasons.insert(0, f"DCA cứu lệnh #{p_id_short} (Hòa vốn giỏ: {P_be:.2f}, X2 lãi tại TP2)")
                                log.info(
                                    "🔥 KÍCH HOẠT SMART DCA: Lệnh gốc %s [%s] @ %.2f (âm %.1f giá) -> Khớp DCA @ %.2f (Hòa vốn: %.2f | X2 lãi @ %.2f)",
                                    final_signal.direction.value, s.get("signal_id"), existing_entry,
                                    drawdown, final_signal.entry_price, P_be, final_signal.take_profit_2,
                                )
                                break

                        log.warning(
                            "⛔ CHẶN TRÙNG LẶP: Đã có lệnh %s [%s] đang %s trong database. Bỏ qua để tránh rủi ro chồng lệnh (Double Exposure).",
                            final_signal.direction.value, s.get("signal_id"), s.get("status")
                        )
                        return None
                    else:
                        # Kiểm tra chế độ Strategic Zone Hedging
                        if not getattr(self.hedging_cfg, "allow_strategic_hedging", True):
                            log.warning(
                                "⛔ CHẶN HEDGING (Chế độ Single Direction): Đang có lệnh %s [%s] (%s). "
                                "Không mở thêm lệnh %s tuân thủ chuẩn Netting & Prop Firm!",
                                s.get("direction"), s.get("signal_id"), s.get("status"), final_signal.direction.value
                            )
                            return None

                        existing_entry = float(s.get("entry_price", 0.0))
                        price_diff = abs(final_signal.entry_price - existing_entry)
                        min_dist = getattr(self.hedging_cfg, "min_hedging_distance_points", 5.0)

                        # Điều kiện 1: Cấm tuyệt đối BUY và SELL chung 1 điểm hoặc lệch nhau 1-2 giá (< min_dist)
                        if price_diff < min_dist:
                            log.warning(
                                "⛔ CHẶN HEDGING CẬN BIÊN (Proximity Guard): Lệnh mới @ %.2f lệch lệnh cũ %s @ %.2f chỉ %.2f giá (< %.1f giá). "
                                "Cấm tuyệt đối BUY/SELL chung điểm hoặc lệch 1-2 giá để tránh quét Stop Loss 2 đầu và tốn phí vô ích!",
                                final_signal.entry_price, s.get("direction"), existing_entry, price_diff, min_dist
                            )
                            return None

                        # Điều kiện 2: Căn chỉnh sao cho có lời (Lệnh cũ phải đang có lãi bảo vệ rủi ro)
                        if getattr(self.hedging_cfg, "require_breakeven_or_profit", True):
                            s_dir = s.get("direction")
                            existing_gain = (current_price - existing_entry) if s_dir == "BUY" else (existing_entry - current_price)
                            min_gain = getattr(self.hedging_cfg, "min_existing_profit_points", 3.0)
                            if existing_gain < min_gain:
                                log.warning(
                                    "⛔ CHẶN HEDGING KẸP ĐẦU (Risk-Free Guard): Lệnh cũ %s @ %.2f chưa đủ biên độ lời an toàn (Lời: %.2f giá, cần: %.1f giá). "
                                    "Chỉ được mở lệnh ngược chiều khi lệnh cũ đã có lời bảo vệ để đảm bảo tổng vị thế có lời!",
                                    s_dir, existing_entry, existing_gain, min_gain
                                )
                                return None

                        log.info(
                            "✅ CHO PHÉP HEDGING CHIẾN LƯỢC: Lệnh cũ %s @ %.2f (đang lời +%.2f giá), lệnh mới %s @ %.2f (cách %.2f giá). "
                            "Đạt chuẩn đánh 2 đầu độc lập bảo toàn vốn!",
                            s.get("direction"), existing_entry, existing_gain, final_signal.direction.value, final_signal.entry_price, price_diff
                        )

                # Đăng ký vào SignalTracker
                is_reg = self.tracker.register_signal(final_signal)
                if is_reg:
                    # Trích xuất vector 21 đặc trưng kỹ thuật lúc phát tín hiệu
                    extracted_feats = None
                    try:
                        extracted_feats = FeatureExtractor.extract_features(
                            df_exec=df_m5,
                            candle_idx=-1,
                            spread=spread,
                            h4_trend=final_signal.trend_h4,
                            h1_trend=final_signal.trend_h1,
                            swing_high=final_signal.entry_zone_high + 5.0,
                            swing_low=final_signal.entry_zone_low - 5.0,
                            regime=final_signal.market_regime,
                            session_name=final_signal.score_breakdown.get("session_name") if final_signal.score_breakdown else None,
                            volume_surge=final_signal.score_breakdown.get("volume_surge") if final_signal.score_breakdown else None,
                            risk_reward=final_signal.risk_reward_ratio,
                            setup_historical_wr=final_signal.score_breakdown.get("setup_historical_wr") if final_signal.score_breakdown else None,
                        )
                    except Exception as e:
                        log.debug("Lỗi trích xuất features khi lưu signal: %s", e)

                    # Lưu vào SQLite Database kèm đầy đủ 21 features
                    self.signal_repo.save_signal(final_signal, features=extracted_feats)

                    # Gửi tin nhắn Telegram
                    self.notifier.notify_signal(final_signal)

                    return final_signal

            return final_signal

        except Exception as e:
            log.error("Lỗi trong chu kỳ LiveBotRunner: %s", e, exc_info=True)
            return None

    def check_realtime_news_releases(
        self,
        current_price: float,
        now_utc: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Kiểm tra và tự động phát bài viết lên Telegram trong vòng 1-5 phút (chuẩn 2-3 phút) sau khi tin tức ra:
        - Bắt các sự kiện tin Đỏ và Cam (USD / High & Medium impact).
        - Đối chiếu số liệu và đo lường phản ứng giá Vàng thời gian thực.
        - Bắn bài viết vào Telegram, đảm bảo không bắn trùng lặp.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        recent_events = self.news_mgr.get_recently_released_events(
            current_time=now_utc,
            window_min_start=1.0,
            window_min_end=5.0,
            only_high_or_medium=True,
        )

        for ev, mins_ago in recent_events:
            # Ưu tiên các tin liên quan trực tiếp đến đồng USD hoặc tin cực mạnh
            if not ev.is_usd and not ev.is_high_impact:
                continue

            if ev.id not in self._notified_realtime_news_ids:
                self._notified_realtime_news_ids.add(ev.id)
                log.info(
                    "⚡ PHÁT HIỆN TIN KINH TẾ VỪA CÔNG BỐ: [%s] cách đây %.1f phút! Đang biên tập bài viết...",
                    ev.title, mins_ago,
                )

                post_text = self.ai_news_writer.generate_realtime_flash_news_post(
                    event=ev,
                    current_price=current_price,
                    price_before=self.last_price or current_price,
                    minutes_ago=int(round(mins_ago)),
                )

                if self.notifier and self.notifier.is_enabled:
                    self.notifier.send_raw_message(post_text)
                    log.info("✓ ĐÃ BẮN BÀI VIẾT TIN NÓNG THỜI GIAN THỰC LÊN TELEGRAM: [%s]", ev.title)

                return post_text

        return None

    def check_early_structural_exit(self, close_price: float) -> list[str]:
        """
        Kiểm tra nếu nến M5 vừa đóng vi phạm cấu trúc Order Block/FVG để cảnh báo cắt lỗ sớm (Early Exit).
        - Đối với lệnh SELL: Nếu nến M5 Close > đỉnh Order Block.
        - Đối với lệnh BUY: Nếu nến M5 Close < đáy Order Block.
        """
        alerted_ids: list[str] = []
        for sig in self.tracker.active_signals:
            if sig.status != SignalStatus.ENTRY_REACHED or not sig.invalidation:
                continue

            # Trích xuất mức giá vô hiệu hóa từ chuỗi invalidation (vd: 'Close vượt đỉnh Order Block 4000.42')
            match = re.search(r"(\d{3,5}\.?\d*)", sig.invalidation)
            if not match:
                continue

            inval_level = float(match.group(1))

            should_alert = False
            if sig.direction == SignalDirection.SELL and close_price > inval_level:
                should_alert = True
            elif sig.direction == SignalDirection.BUY and close_price < inval_level:
                should_alert = True

            if should_alert:
                log.warning(
                    "⚠️ PHÁT HIỆN VI PHẠM CẤU TRÚC: Lệnh %s [%s] có nến M5 Close (%.2f) vi phạm mức bảo vệ (%.2f). Gửi cảnh báo thoát lệnh sớm!",
                    sig.direction.value, sig.signal_id, close_price, inval_level,
                )
                if self.notifier and self.notifier.is_enabled:
                    sent = self.notifier.send_early_exit_alert(
                        signal=sig,
                        close_price=close_price,
                        invalidation_level=inval_level,
                    )
                    if sent:
                        alerted_ids.append(sig.signal_id)

        return alerted_ids

    def check_trailing_stop_and_breakeven(
        self,
        current_price: float,
        df_m5: Optional[pd.DataFrame] = None,
        market_regime: str = "UNKNOWN",
        current_spread: float = 0.3,
    ) -> None:
        """
        Kiểm tra và tự động dời Stop Loss (Hòa vốn + Trailing Stop) cho các lệnh đang có lãi qua SmartExitEngine:
        1. Lãi >= 0.5R (hoặc 5.0 giá): Tự động dời SL về Entry + 0.5 giá (Risk-Free Breakeven bù spread).
        2. Chốt lời từng phần Tier 1 (50%) & Tier 2 (30%).
        3. Trailing Stop thích ứng (ATR-Dynamic & Swing Structure).
        """
        smart_exit = getattr(self, "smart_exit", None) or SmartExitEngine()

        for sig in self.tracker.active_signals:
            if sig.status != SignalStatus.ENTRY_REACHED or sig.entry_price <= 0:
                continue

            decisions = smart_exit.evaluate_signal(
                signal=sig,
                current_price=current_price,
                df_m5=df_m5,
                market_regime=market_regime,
                current_spread=current_spread,
                now_utc=datetime.now(timezone.utc),
            )

            for d in decisions:
                if d.new_sl is not None:
                    old_sl = d.old_sl or sig.stop_loss
                    sig.stop_loss = d.new_sl
                    self.signal_repo.update_stop_loss(sig.signal_id, d.new_sl)
                    try:
                        self.paper_engine.update_position_sl(sig.signal_id, d.new_sl)
                    except Exception as e:
                        log.debug("Lỗi đồng bộ Stop Loss sang Paper Wallet: %s", e)

                    # Đồng bộ dời Stop Loss trực tiếp trên sàn MT5 Server-side qua TRADE_ACTION_SLTP
                    if getattr(self.mt5_trading_config, "enabled", False) and sig.signal_id in self._signal_mt5_tickets:
                        ticket = self._signal_mt5_tickets.get(sig.signal_id)
                        if ticket:
                            try:
                                self.mt5_executor.modify_position_sltp(ticket=ticket, sl=d.new_sl)
                            except Exception as e:
                                log.debug("Lỗi dời Stop Loss trên MT5: %s", e)

                    log.info(
                        "🛡️ [%s] Cập nhật SL lệnh %s [%s] -> %.2f (%s)",
                        d.action_type.value, sig.direction.value, sig.signal_id, d.new_sl, d.reason,
                    )
                    if self.notifier and self.notifier.is_enabled:
                        self.notifier.send_trailing_stop_update(
                            signal=sig,
                            current_price=current_price,
                            old_sl=old_sl,
                            new_sl=d.new_sl,
                            locked_points=d.locked_points,
                        )

                if d.action_type in (ExitActionType.SCALED_EXIT_TIER1, ExitActionType.SCALED_EXIT_TIER2):
                    log.info(
                        "🎯 [%s] Khuyến nghị chốt lời %s [%s]: %s",
                        d.tier_name, sig.direction.value, sig.signal_id, d.reason,
                    )
                    if self.notifier and self.notifier.is_enabled:
                        self.notifier.send_scaled_exit_alert(
                            signal=sig,
                            current_price=current_price,
                            tier_name=d.tier_name,
                            close_ratio=d.close_ratio,
                            pnl_points=d.pnl_points,
                            pnl_r=d.pnl_r,
                            new_sl=d.new_sl,
                        )

    def check_momentum_exhaustion_and_stagnation(
        self,
        df_m5: pd.DataFrame,
        current_price: float,
        now_utc: datetime,
    ) -> None:
        """
        Kiểm tra 2 kịch bản chốt lời chủ động khi nến M5 mới đóng cửa:
        1. Cảnh báo động lượng suy yếu (Pinbar từ chối / Rejection Wick >= 50% khi đang lãi >= 3 giá).
        2. Cảnh báo lệnh ứ đọng (Time Decay: giữ lệnh > 60 phút mà giá đi ngang, lãi >= 2 giá).
        """
        smart_exit = getattr(self, "smart_exit", None) or SmartExitEngine()

        for sig in self.tracker.active_signals:
            if sig.status != SignalStatus.ENTRY_REACHED or sig.entry_price <= 0:
                continue

            d = smart_exit.evaluate_candle_exhaustion(
                signal=sig,
                df_m5=df_m5,
                current_price=current_price,
                now_utc=now_utc,
            )
            if not d:
                continue

            if d.action_type == ExitActionType.MOMENTUM_EXHAUSTION:
                candle_time = str(df_m5.iloc[-1].get("time", ""))
                log.warning(
                    "⚡ [Exhaustion Alert] Lệnh %s [%s] gặp cản suy yếu @ %.2f (Lãi +%.2f giá)",
                    sig.direction.value, sig.signal_id, current_price, d.pnl_points,
                )
                if self.notifier and self.notifier.is_enabled:
                    self.notifier.send_momentum_exhaustion_alert(
                        signal=sig,
                        current_price=current_price,
                        pnl_points=d.pnl_points,
                        exhaustion_reason=d.reason,
                        candle_time_str=candle_time[:16],
                    )
            elif d.action_type == ExitActionType.TIME_STAGNATION:
                diff_minutes = int(
                    (now_utc - (sig.created_at if sig.created_at.tzinfo else sig.created_at.replace(tzinfo=timezone.utc))).total_seconds() / 60.0
                )
                log.info(
                    "⏳ [Stagnation Alert] Lệnh %s [%s] ngâm %d phút quanh mức lãi +%.2f giá",
                    sig.direction.value, sig.signal_id, diff_minutes, d.pnl_points,
                )
                if self.notifier and self.notifier.is_enabled:
                    self.notifier.send_time_stagnation_alert(
                        signal=sig,
                        current_price=current_price,
                        pnl_points=d.pnl_points,
                        minutes_open=diff_minutes,
                    )

    def check_ai_copilot_companion(
        self,
        current_price: float,
        now_utc: Optional[datetime] = None,
    ) -> None:
        """
        AI Trading Copilot: Đánh giá trạng thái lệnh đang chạy và gửi tin nhắn đàm đạo,
        động viên hoặc khuyên cắt lệnh tới anh em trader với phong cách gần gũi và chuyên nghiệp.
        """
        if not self.notifier or not self.notifier.is_enabled:
            return

        for sig in self.tracker.active_signals:
            if sig.status != SignalStatus.ENTRY_REACHED or sig.entry_price <= 0:
                continue

            msg = self.ai_copilot.evaluate(
                signal=sig,
                current_price=current_price,
                now_utc=now_utc,
            )
            if msg:
                try:
                    self.notifier.client.send_message(msg)
                except Exception as e:
                    log.debug("Lỗi gửi tin nhắn AI Copilot: %s", e)

    def run_forever(self, poll_interval_sec: float = 5.0) -> None:
        """
        Vòng lặp chạy liên tục theo thời gian thực:
        - Thăm dò giá mỗi poll_interval_sec giây.
        - Tự động bắt sự kiện nến mới và cập nhật trạng thái.
        - Dừng an toàn khi nhận tín hiệu ngắt (Ctrl+C / SIGINT).
        """
        self.start()

        def handle_signal(sig, frame):
            log.info("Nhận tín hiệu dừng (Signal %s)...", sig)
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except Exception:
            pass

        log.info("Bắt đầu vòng lặp giám sát thời gian thực (Chu kỳ kiểm tra: %.1fs)...", poll_interval_sec)

        try:
            while self.is_running:
                self.run_once()
                time.sleep(poll_interval_sec)
        except KeyboardInterrupt:
            log.info("Người dùng ngắt tiến trình (KeyboardInterrupt).")
        finally:
            self.stop()

    def toggle_mt5_auto_trading(self, enabled: Optional[bool] = None) -> bool:
        """Bật/Tắt tính năng tự động đặt lệnh thật trên MT5."""
        if enabled is None:
            self.mt5_trading_config.enabled = not self.mt5_trading_config.enabled
        else:
            self.mt5_trading_config.enabled = bool(enabled)
        state_str = "BẬT" if self.mt5_trading_config.enabled else "TẮT"
        log.info("⚙️ MT5 Auto-Trading đã chuyển sang trạng thái: %s", state_str)
        return self.mt5_trading_config.enabled

    def set_mt5_lot_size(self, lot_size: float) -> float:
        """Thiết lập khối lượng lot giao dịch cho MT5 Auto-Trading."""
        vol = max(0.01, min(round(float(lot_size), 2), 10.0))
        self.mt5_trading_config.lot_size = vol
        log.info("⚙️ MT5 Auto-Trading đã cập nhật Lot Size: %.2f", vol)
        return vol

    def close_all_mt5_positions(self) -> list[Any]:
        """Khẩn cấp 1-Click: Đóng toàn bộ các vị thế đang mở trên MT5."""
        res = self.mt5_executor.close_all_positions(self.mt5_trading_config.symbol)
        self._signal_mt5_tickets.clear()
        return res

    def get_mt5_trading_status(self) -> dict[str, Any]:
        """Lấy toàn bộ trạng thái MT5 Auto-Trading và các vị thế thực tế."""
        allowed, msg = self.mt5_executor.is_trade_allowed()
        account = self.mt5_executor.get_account_summary()
        positions = [p.to_dict() for p in self.mt5_executor.get_open_positions(self.mt5_trading_config.symbol)]
        pending = self.mt5_executor.get_pending_orders(self.mt5_trading_config.symbol)

        return {
            "enabled": self.mt5_trading_config.enabled,
            "trade_allowed": allowed,
            "trade_allowed_message": msg,
            "symbol": self.mt5_trading_config.symbol,
            "lot_size": self.mt5_trading_config.lot_size,
            "max_open_positions": self.mt5_trading_config.max_open_positions,
            "magic_number": self.mt5_trading_config.magic_number,
            "fast_tick_interval_ms": self.mt5_trading_config.fast_tick_interval_ms,
            "account": account,
            "open_positions": positions,
            "open_positions_count": len(positions),
            "pending_orders": pending,
            "active_signal_tickets": dict(self._signal_mt5_tickets),
        }
