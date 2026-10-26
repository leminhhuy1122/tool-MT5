# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Tests for Paper Trading & Virtual Wallet Engine.
"""

from datetime import datetime, timezone
import pytest

from app.database.connection import DatabaseManager
from app.database.migrations import run_migrations
from app.simulator.models import PaperPosition, PaperTradeHistory, PaperWallet
from app.simulator.paper_engine import PaperTradingEngine
from app.strategy.signal_models import SignalDirection, TradingSignal


@pytest.fixture
def memory_db():
    """Tạo database in-memory và chạy migrations v2."""
    db = DatabaseManager(db_path=":memory:")
    run_migrations(db)
    return db


@pytest.fixture
def paper_engine(memory_db):
    """Khởi tạo PaperTradingEngine với memory db."""
    return PaperTradingEngine(db_manager=memory_db)


@pytest.fixture
def sample_buy_signal():
    """Tín hiệu MUA mẫu."""
    return TradingSignal(
        signal_id="SIG-BUY-001",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.BUY,
        entry_price=2700.0,
        stop_loss=2692.0,
        take_profit_1=2712.0,
        take_profit_2=2720.0,
        score=85.0,
    )


@pytest.fixture
def sample_sell_signal():
    """Tín hiệu BÁN mẫu."""
    return TradingSignal(
        signal_id="SIG-SELL-001",
        symbol="XAUUSD",
        timeframe="M5",
        direction=SignalDirection.SELL,
        entry_price=2700.0,
        stop_loss=2708.0,
        take_profit_1=2688.0,
        take_profit_2=2680.0,
        score=82.0,
    )


class TestPaperTradingEngine:
    """Test suite cho toàn bộ chức năng Ví Đầu Tư Ảo & Paper Engine."""

    # 1. Khởi tạo ví ảo mặc định với $50
    def test_default_wallet_initialization(self, paper_engine):
        wallet = paper_engine.get_wallet()
        assert wallet.wallet_id == "default"
        assert wallet.initial_balance == 50.0
        assert wallet.balance == 50.0
        assert wallet.equity == 50.0
        assert wallet.default_lot == 0.01
        assert wallet.leverage == 500
        assert wallet.is_auto_trading is True
        assert wallet.free_margin == 50.0
        assert wallet.used_margin == 0.0
        assert wallet.net_profit_usd == 0.0
        assert wallet.roi_percent == 0.0

    # 2. Người dùng tự nhập số tiền vốn tùy chỉnh (ví dụ nạp $100 hoặc $500)
    def test_setup_custom_balance(self, paper_engine):
        w100 = paper_engine.setup_wallet(initial_balance=100.0, default_lot=0.01)
        assert w100.initial_balance == 100.0
        assert w100.balance == 100.0
        assert w100.equity == 100.0

        w500 = paper_engine.setup_wallet(initial_balance=500.0, default_lot=0.02)
        assert w500.initial_balance == 500.0
        assert w500.default_lot == 0.02

    # 3. Bật/Tắt tự động đi lệnh theo Bot
    def test_toggle_auto_trading(self, paper_engine):
        state1 = paper_engine.toggle_auto_trading(False)
        assert state1 is False
        assert paper_engine.get_wallet().is_auto_trading is False

        state2 = paper_engine.toggle_auto_trading(True)
        assert state2 is True
        assert paper_engine.get_wallet().is_auto_trading is True

    # 4. Tự động mở lệnh MUA 0.01 lot khi có tín hiệu và tính ký quỹ
    def test_open_buy_position_from_signal(self, paper_engine, sample_buy_signal):
        # Giá hiện tại 2700.0, spread 0.2 -> Ask = 2700.10
        pos = paper_engine.open_position_from_signal(
            signal=sample_buy_signal,
            current_price=2700.0,
            spread=0.2,
        )
        assert pos is not None
        assert pos.symbol == "XAUUSD"
        assert pos.direction == "BUY"
        assert pos.volume == 0.01
        assert pos.open_price == 2700.10
        assert pos.stop_loss == 2692.0
        assert pos.take_profit_1 == 2712.0
        assert pos.status == "OPEN"

        # Ký quỹ cho 0.01 lot Vàng tại 2700.10: (2700.10 * 100 * 0.01) / 500 = 5.40 USD
        wallet = paper_engine.get_wallet()
        assert round(wallet.used_margin, 2) == 5.40
        assert round(wallet.free_margin, 2) == round(50.0 - 5.40, 2)

    # 5. Chống trùng lặp lệnh cho cùng 1 tín hiệu
    def test_prevent_duplicate_position_for_same_signal(self, paper_engine, sample_buy_signal):
        pos1 = paper_engine.open_position_from_signal(sample_buy_signal, 2700.0)
        assert pos1 is not None

        pos2 = paper_engine.open_position_from_signal(sample_buy_signal, 2700.0)
        assert pos2 is None  # Đã bị chặn trùng lặp

    # 6. Cập nhật PnL thả nổi theo giá MT5 Live
    def test_floating_pnl_update(self, paper_engine, sample_buy_signal):
        pos = paper_engine.open_position_from_signal(sample_buy_signal, 2700.0, spread=0.2)
        assert pos.open_price == 2700.10

        # Giá Vàng tăng lên: Bid = 2705.10, Ask = 2705.30 (+5.0 giá lãi)
        # Lãi 5 giá với 0.01 lot = +5.00 USD
        paper_engine.update_positions(current_bid=2705.10, current_ask=2705.30)

        open_positions = paper_engine.get_open_positions()
        assert len(open_positions) == 1
        assert open_positions[0]["floating_pnl"] == 5.00
        assert open_positions[0]["current_price"] == 2705.10

        wallet = paper_engine.get_wallet()
        assert wallet.balance == 50.0  # Balance chưa chốt
        assert wallet.equity == 55.0   # Equity đã cộng lãi thả nổi
        assert wallet.floating_pnl == 5.00

    # 7. Tự động Chốt lời (Take Profit) và cộng tiền vào Balance
    def test_auto_take_profit(self, paper_engine, sample_buy_signal):
        paper_engine.open_position_from_signal(sample_buy_signal, 2700.0, spread=0.0)
        # TP1 là 2712.0 (+12 giá = +$12.00)
        closed = paper_engine.update_positions(current_bid=2712.5, current_ask=2712.7)

        assert len(closed) == 1
        trade = closed[0]
        assert trade.close_reason == "TAKE_PROFIT"
        assert trade.pnl_usd == 12.00
        assert trade.pnl_pips == 120.0

        # Kiểm tra danh sách lệnh mở đã trống
        assert len(paper_engine.get_open_positions()) == 0

        # Kiểm tra số dư ví đã tăng từ $50 lên $62
        wallet = paper_engine.get_wallet()
        assert wallet.balance == 62.00
        assert wallet.equity == 62.00
        assert wallet.net_profit_usd == 12.00
        assert wallet.roi_percent == 24.0  # +24.0%
        assert wallet.win_rate == 100.0

    # 8. Tự động Cắt lỗ (Stop Loss) và trừ tiền vào Balance
    def test_auto_stop_loss(self, paper_engine, sample_buy_signal):
        paper_engine.open_position_from_signal(sample_buy_signal, 2700.0, spread=0.0)
        # SL là 2692.0 (-8 giá = -$8.00)
        closed = paper_engine.update_positions(current_bid=2691.5, current_ask=2691.7)

        assert len(closed) == 1
        trade = closed[0]
        assert trade.close_reason == "STOP_LOSS"
        assert trade.pnl_usd == -8.00
        assert trade.pnl_pips == -80.0

        wallet = paper_engine.get_wallet()
        assert wallet.balance == 42.00
        assert wallet.equity == 42.00
        assert wallet.net_profit_usd == -8.00
        assert wallet.roi_percent == -16.0
        assert wallet.losing_trades == 1

    # 9. Đóng lệnh thủ công từ người dùng (Manual Close)
    def test_manual_close_position(self, paper_engine, sample_buy_signal):
        pos = paper_engine.open_position_from_signal(sample_buy_signal, 2700.0, spread=0.0)
        # Người dùng bấm đóng lệnh tại giá 2704.50 (+4.5 giá = +$4.50)
        trade = paper_engine.close_position_manual(
            position_id=pos.position_id,
            current_price=2704.50,
        )
        assert trade is not None
        assert trade.close_reason == "MANUAL"
        assert trade.pnl_usd == 4.50

        wallet = paper_engine.get_wallet()
        assert wallet.balance == 54.50

    # 10. Reset ví về mốc ban đầu
    def test_reset_wallet(self, paper_engine, sample_buy_signal):
        paper_engine.open_position_from_signal(sample_buy_signal, 2700.0, spread=0.0)
        paper_engine.update_positions(current_bid=2712.5, current_ask=2712.7)
        assert paper_engine.get_wallet().balance == 62.0

        # Reset về mốc $50
        reset_w = paper_engine.reset_wallet(50.0)
        assert reset_w.balance == 50.0
        assert reset_w.equity == 50.0
        assert len(paper_engine.get_open_positions()) == 0
        assert len(paper_engine.get_trade_history()) == 0

    # 11. Test REST API Endpoints trực tiếp
    def test_api_paper_wallet_endpoints(self, memory_db, sample_buy_signal):
        import app.api.server as srv
        srv.db_manager = memory_db
        srv.bot_runner = None
        srv.notifier = None

        # 1. Overview
        ov = srv.get_paper_wallet_overview()
        assert "wallet" in ov
        assert ov["wallet"]["balance"] == 50.0

        # 2. Setup custom balance ($150)
        setup_res = srv.setup_paper_wallet(srv.PaperWalletSetupRequest(initial_balance=150.0, default_lot=0.01))
        assert setup_res["ok"] is True
        assert setup_res["wallet"]["balance"] == 150.0

        # 3. Toggle auto trading
        tog = srv.toggle_paper_auto_trading(srv.PaperWalletToggleRequest(enabled=False))
        assert tog["ok"] is True
        assert tog["is_auto_trading"] is False
        srv.toggle_paper_auto_trading(srv.PaperWalletToggleRequest(enabled=True))

        # 4. Open position & check positions API
        engine = srv._get_paper_engine()
        pos = engine.open_position_from_signal(sample_buy_signal, 2700.0)
        assert pos is not None

        positions = srv.get_paper_open_positions()
        assert len(positions) == 1
        assert positions[0]["position_id"] == pos.position_id

        # 5. Close position API
        close_res = srv.close_paper_position_manual(srv.PaperClosePositionRequest(position_id=pos.position_id))
        assert close_res["ok"] is True
        assert "trade" in close_res

        # 6. History API
        history = srv.get_paper_trade_history()
        assert len(history) == 1

        # 7. Equity curve API
        curve = srv.get_paper_equity_curve()
        assert len(curve) >= 1

    # 12. Test tự động đồng bộ tín hiệu active vào ví ảo (sync_active_signals)
    def test_sync_active_signals_and_close_by_signal(self, memory_db, paper_engine):
        # Chèn trực tiếp một signal đang ACTIVE vào bảng signals
        with memory_db.session() as conn:
            conn.execute(
                """
                INSERT INTO signals 
                (signal_id, strategy_version, symbol, timeframe, direction, status, entry_price, 
                 entry_zone_low, entry_zone_high, stop_loss, take_profit_1, take_profit_2, risk_reward_ratio,
                 sl_distance, tp_distance, score, confidence, reasons, invalidation, created_at, expires_at, updated_at)
                VALUES ('SIG-SYNC-001', 'v1.0', 'XAUUSD', 'M5', 'SELL', 'ENTRY_REACHED', 4016.82,
                        4016.0, 4017.0, 4027.82, 4005.82, 3994.82, 2.0, 11.0, 11.0, 90.0, 'HIGH',
                        '["Test sync"]', 'Invalidation test', '2026-10-26T08:00:00Z', '2026-10-26T12:00:00Z', '2026-10-26T08:00:00Z');
                """
            )

        # Chưa có position
        assert len(paper_engine.get_open_positions()) == 0

        # Gọi sync_active_signals
        synced = paper_engine.sync_active_signals()
        assert synced == 1

        # Đã xuất hiện trong paper_positions
        positions = paper_engine.get_open_positions()
        assert len(positions) == 1
        assert positions[0]["signal_id"] == "SIG-SYNC-001"
        assert positions[0]["direction"] == "SELL"
        assert positions[0]["open_price"] == 4016.82

        # Cập nhật giá thị trường (SELL ở 4016.82, giá hiện tại 4014.82 -> Lãi 2 giá = $2.00 USD / 2.00 U)
        closed = paper_engine.update_positions(current_bid=4014.72, current_ask=4014.92)
        assert len(closed) == 0
        w = paper_engine.get_wallet()
        assert w.floating_pnl > 0.0

        # Đóng lệnh theo signal hoàn tất (TP_REACHED)
        trade = paper_engine.close_position_by_signal(
            signal_id="SIG-SYNC-001",
            current_price=4005.82,
            reason="TP_REACHED",
        )
        assert trade is not None
        assert trade.pnl_usd > 0.0
        assert len(paper_engine.get_open_positions()) == 0
        assert len(paper_engine.get_trade_history()) == 1

    # 13. Test Anti-Hedging Guard (Chặn mở đồng thời BUY và SELL trên cùng mã)
    def test_anti_hedging_guard(self, paper_engine, sample_buy_signal, sample_sell_signal):
        # Mở vị thế BUY đầu tiên
        pos1 = paper_engine.open_position_from_signal(sample_buy_signal, current_price=2700.0)
        assert pos1 is not None
        assert pos1.direction == "BUY"
        assert len(paper_engine.get_open_positions()) == 1

        # Cố gắng mở vị thế SELL ngược chiều ngay cùng mức giá 2700.0 -> Phải bị chặn bởi Anti-Hedging Cận Biên (< 5.0 giá)
        pos2 = paper_engine.open_position_from_signal(sample_sell_signal, current_price=2700.0)
        assert pos2 is None
        assert len(paper_engine.get_open_positions()) == 1

        # Cập nhật giá thị trường tăng lên 2708.0 (+7.9 giá -> BUY đang có lời $7.90 nhưng chưa chạm TP1 2712.0)
        paper_engine.update_positions(current_bid=2707.9, current_ask=2708.1)

        # Mở vị thế SELL chiến lược tại 2708.0 (cách lệnh BUY 8 giá >= 5.0 giá và lệnh BUY đã có lời) -> Hợp lệ!
        sample_sell_top = TradingSignal(
            signal_id="SIG-SELL-TOP",
            symbol="XAUUSD",
            timeframe="M5",
            direction=SignalDirection.SELL,
            entry_price=2708.0,
            stop_loss=2716.0,
            take_profit_1=2695.0,
            take_profit_2=2685.0,
            score=95.0,
        )
        pos3 = paper_engine.open_position_from_signal(sample_sell_top, current_price=2708.0)
        assert pos3 is not None
        assert pos3.direction == "SELL"
        assert len(paper_engine.get_open_positions()) == 2



