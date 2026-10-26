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
import os
import re
import signal
import sys
import time
from typing import Optional

import pandas as pd

from app.database.connection import DatabaseManager
from app.database.repository import MarketDataRepository, SignalRepository
from app.market.data_manager import MarketDataManager
from app.market.timeframe_manager import Timeframe
from app.ml.filter import MLSignalFilter
from app.ml.model import SignalQualityClassifier
from app.ml.registry import ModelRegistry
from app.mt5.connector import MT5Connector
from app.news.ai_writer import AINewsWriter
from app.news.calendar import NewsManager
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, SignalStatus, TradingSignal
from app.strategy.signal_tracker import SignalTracker, TrackerConfig
from app.telegram.notifier import TelegramNotifier
from config import Settings, get_settings
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

        # 3. Động cơ phân tích & Tín hiệu
        self.signal_engine = SignalEngine(
            strategy_version="v1.0-M5",
            symbol=self.symbol,
            default_timeframe="M5",
        )

        # 4. Tích hợp Machine Learning Filter (Phase 9)
        self.ml_registry = ModelRegistry(self.db)
        latest_model_path = self.ml_registry.get_latest_production_model_path()
        classifier = SignalQualityClassifier.load(latest_model_path) if latest_model_path else None
        self.ml_filter = MLSignalFilter(classifier=classifier)

        # 5. Bộ theo dõi tín hiệu (Khôi phục trạng thái active từ SQLite để chống trùng lặp khi khởi động lại)
        self.tracker = SignalTracker(config=TrackerConfig(cooldown_minutes=45, max_active_signals=3))
        try:
            active_rows = self.signal_repo.get_active_signals(self.symbol)
            if active_rows:
                active_signals = [TradingSignal.from_dict(row) for row in active_rows]
                self.tracker.load_active_signals(active_signals)
        except Exception as e:
            log.warning("Không thể nạp tín hiệu active từ database: %s", e)

        # 6. Telegram Notifier
        self.notifier = notifier or TelegramNotifier(self.settings.telegram)

        # Trạng thái vòng lặp
        self.last_processed_m5_time: Optional[datetime] = None
        self.last_price: float = 0.0

    def start(self) -> None:
        """Khởi động bot và kết nối các dịch vụ."""
        log.info("=" * 60)
        log.info("  VIETKEY GOLD AI — KHỞI ĐỘNG LIVE BOT ENGINE")
        log.info("  Symbol: %s | Timeframe: M5 (Trend: H1/H4)", self.symbol)
        log.info("  Chế độ: FORWARD TESTING / SIGNALS ONLY (KHÔNG AUTO-ORDER)")
        log.info("=" * 60)

        # Kết nối MT5
        if not self.connector.is_connected:
            res = self.connector.connect()
            if not res.success:
                log.error("Không thể kết nối MT5 Terminal: %s", res.error)
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
        log.info("✓ Bot đã dừng an toàn.")

    def run_once(self) -> Optional[TradingSignal]:
        """
        Thực hiện một chu kỳ kiểm tra:
        1. Cập nhật giá thị trường hiện tại và cập nhật trạng thái các lệnh active.
        2. Nếu có nến M5 mới đóng -> Chạy phân tích đa khung thời gian và sinh tín hiệu.
        3. Gửi thông báo và lưu trữ database.
        """
        try:
            # 1. Lấy giá mới nhất từ MT5
            price_info = self.data_mgr.get_latest_price()
            if not price_info:
                return None

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

                # Cập nhật vào SQLite
                self.signal_repo.update_status(sig.signal_id, sig.status)
                if sig.status in (SignalStatus.TP_REACHED, SignalStatus.SL_REACHED):
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

                    self.signal_repo.save_outcome(
                        signal_id=sig.signal_id,
                        final_status=sig.status.value,
                        exit_price=current_price,
                        pnl_points=round(pnl_pts, 2),
                        duration_seconds=diff_sec,
                    )

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

            # 2b. Tự động kiểm tra và phát bài viết Tin Nóng sau khi tin ra 2-3 phút
            try:
                self.check_realtime_news_releases(current_price=current_price, now_utc=now_utc)
            except Exception as e:
                log.debug("Lỗi kiểm tra tin tức thời gian thực: %s", e)

            # 3. Thu thập nến M5 và kiểm tra nến mới
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

            # 6. Tinh chỉnh qua bộ lọc Machine Learning (Phase 9)
            spread = float(price_info.get("spread", 0.3))
            final_signal = self.ml_filter.apply(raw_signal, df_m5, spread=spread)

            # 7. Xử lý tín hiệu BUY hoặc SELL
            if final_signal.direction in (SignalDirection.BUY, SignalDirection.SELL):
                log.info("🔥 PHÁT HIỆN TÍN HIỆU: %s %s @ %.2f (Score: %.1f)",
                         final_signal.direction.value, self.symbol,
                         final_signal.entry_price, final_signal.score)

                # Chống trùng lặp 2 lớp: Kiểm tra trực tiếp cả ở Database SQLite
                active_in_db = self.signal_repo.get_active_signals(self.symbol)
                for s in active_in_db:
                    if s.get("direction") == final_signal.direction.value:
                        log.warning(
                            "⛔ CHẶN TRÙNG LẶP: Đã có lệnh %s [%s] đang %s trong database. Bỏ qua phát thêm để tránh rủi ro chồng lệnh (Double Exposure).",
                            final_signal.direction.value, s.get("signal_id"), s.get("status")
                        )
                        return None

                # Đăng ký vào SignalTracker
                is_reg = self.tracker.register_signal(final_signal)
                if is_reg:
                    # Lưu vào SQLite Database
                    self.signal_repo.save_signal(final_signal)

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
