# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Backtest Simulation Engine.

Động cơ mô phỏng giao dịch thanh nến tuần tự (Bar-by-bar):
- Tuyệt đối KHÔNG có look-ahead bias (tại nến i chỉ nhìn nến 0..i).
- Khớp lệnh chân thực: tính toán Spread, Trượt giá (Slippage), kiểm tra khoảng giá High-Low.
- Áp dụng chuẩn quy tắc quản lý vốn theo yêu cầu:
  + Lãi 5 giá (hoặc cấu hình) ➔ Tự động kéo SL về hòa vốn (Breakeven).
  + Chạm TP1 (10 giá) ➔ Chốt 50% khối lượng, dời SL dương để gồng TP2.
- Ghi nhận nhật ký MFE (Max Favorable Excursion) và MAE (Max Adverse Excursion).
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

import pandas as pd

from app.backtest.historical_loader import HistoricalLoader
from app.backtest.metrics import calculate_metrics
from app.backtest.models import BacktestConfig, BacktestResult, TradeRecord, TradeStatus
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import SignalDirection, TradingSignal
from logger import get_logger

log = get_logger("backtest.engine")


class BacktestEngine:
    """
    Động cơ thực thi Backtest đa khung thời gian.
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        signal_engine: Optional[SignalEngine] = None,
    ):
        self.config = config or BacktestConfig()
        self.signal_engine = signal_engine or SignalEngine(
            strategy_version="Backtest-v1.0",
            symbol=self.config.symbol,
            default_timeframe="M5",
        )

    def run(
        self,
        df_exec: pd.DataFrame,
        df_macro: Optional[pd.DataFrame] = None,
        min_warmup_bars: int = 30,
    ) -> BacktestResult:
        """
        Thực thi backtest từng nến trên DataFrame lịch sử.

        Args:
            df_exec: DataFrame nến khung thực thi (vd: M5).
            df_macro: DataFrame nến khung xu hướng lớn (vd: H1 hoặc H4).
            min_warmup_bars: Số nến tối thiểu để khởi tạo indicators trước khi quét setup.

        Returns:
            BacktestResult chứa toàn bộ phân tích hiệu suất và danh sách lệnh.
        """
        # Làm sạch và tính indicators
        df_exec_clean = HistoricalLoader.clean_and_prepare(df_exec)
        df_macro_clean = HistoricalLoader.clean_and_prepare(df_macro) if df_macro is not None else None

        if len(df_exec_clean) < min_warmup_bars:
            log.warning("Dữ liệu nến quá ngắn (%d < %d)", len(df_exec_clean), min_warmup_bars)
            return calculate_metrics([], self.config.initial_balance, self.config.symbol)

        completed_trades: list[TradeRecord] = []
        active_trades: list[TradeRecord] = []

        # Point value cho 0.1 lot XAUUSD = $10 / 1 giá (100 oz * 0.1 lot = 10 oz)
        cash_per_point = self.config.contract_size * self.config.lot_size

        log.info(
            "Bắt đầu Backtest trên %d nến (%s, Min bars: %d, Spread: %.1f, Slip: %.1f)",
            len(df_exec_clean), self.config.symbol, min_warmup_bars,
            self.config.spread_points, self.config.slippage_points,
        )

        for i in range(min_warmup_bars, len(df_exec_clean)):
            candle = df_exec_clean.iloc[i]
            c_time = candle["time"]
            c_open = float(candle["open"])
            c_high = float(candle["high"])
            c_low = float(candle["low"])
            c_close = float(candle["close"])

            # ─────────────────────────────────────────────────────────────
            # 1. CẬP NHẬT CÁC LỆNH ĐANG MỞ HOẶC CHỜ KHỚP (ACTIVE TRADES)
            # ─────────────────────────────────────────────────────────────
            still_active: list[TradeRecord] = []

            for trade in active_trades:
                is_buy = (trade.direction == "BUY")

                # 1a. Xử lý lệnh đang chờ khớp (PENDING)
                if trade.status == TradeStatus.PENDING:
                    # Kiểm tra giá chạm Entry Zone
                    in_zone = (c_low <= trade.entry_zone_high and c_high >= trade.entry_zone_low)
                    if in_zone:
                        trade.status = TradeStatus.OPEN
                        trade.entry_time = c_time
                        if is_buy:
                            trade.actual_entry_price = round(
                                trade.planned_entry + self.config.slippage_points + self.config.spread_points, 2
                            )
                        else:
                            trade.actual_entry_price = round(
                                trade.planned_entry - self.config.slippage_points, 2
                            )
                        still_active.append(trade)
                    else:
                        # Kiểm tra xem có bị vi phạm SL trước khi khớp không -> HỦY
                        if is_buy and c_low <= trade.stop_loss:
                            trade.status = TradeStatus.INVALIDATED
                            completed_trades.append(trade)
                        elif not is_buy and c_high >= trade.stop_loss:
                            trade.status = TradeStatus.INVALIDATED
                            completed_trades.append(trade)
                        else:
                            still_active.append(trade)
                    continue

                # 1b. Xử lý lệnh ĐÃ KHỚP (OPEN)
                if trade.status == TradeStatus.OPEN:
                    entry = trade.actual_entry_price

                    # Đo biến động MFE và MAE
                    if is_buy:
                        cur_favorable = max(0.0, c_high - entry)
                        cur_adverse = max(0.0, entry - c_low)
                    else:
                        cur_favorable = max(0.0, entry - c_low)
                        cur_adverse = max(0.0, c_high - entry)

                    trade.mfe_points = max(trade.mfe_points, cur_favorable)
                    trade.mae_points = max(trade.mae_points, cur_adverse)

                    # Quy tắc 1: Lãi >= 5 giá ➔ Kéo SL về hòa vốn (Breakeven)
                    if not trade.is_breakeven_triggered and cur_favorable >= self.config.breakeven_trigger_points:
                        trade.is_breakeven_triggered = True
                        trade.stop_loss = entry  # Dời SL về giá vào lệnh
                        log.debug("Trade [%s] đã dời SL về hòa vốn (BE)", trade.trade_id)

                    # Quy tắc 2: Chạm TP1 ➔ Chốt 50% khối lượng, dời SL dương nuôi TP2
                    tp1_hit = (c_high >= trade.take_profit_1) if is_buy else (c_low <= trade.take_profit_1)
                    if not trade.partial_closed and tp1_hit:
                        trade.partial_closed = True
                        # Dời SL lên điểm dương (bảo toàn thêm 1 giá)
                        trade.stop_loss = entry + 1.0 if is_buy else entry - 1.0
                        log.debug("Trade [%s] đã chốt 50%% tại TP1, dời SL dương", trade.trade_id)

                    # Quy tắc 3: Chạm TP2 ➔ Chốt toàn bộ lệnh
                    tp2_hit = (c_high >= trade.take_profit_2) if is_buy else (c_low <= trade.take_profit_2)
                    if trade.take_profit_2 > 0 and tp2_hit:
                        trade.status = TradeStatus.CLOSED_TP2
                        trade.actual_exit_price = trade.take_profit_2
                        trade.exit_time = c_time
                        
                        # Tính PnL kết hợp (50% tại TP1 + 50% tại TP2 nếu partial, hoặc 100% TP2)
                        pnl_tp1 = abs(trade.take_profit_1 - entry)
                        pnl_tp2 = abs(trade.take_profit_2 - entry)
                        if trade.partial_closed:
                            trade.pnl_points = round((pnl_tp1 * self.config.partial_tp_ratio) + (pnl_tp2 * (1 - self.config.partial_tp_ratio)), 2)
                        else:
                            trade.pnl_points = round(pnl_tp2, 2)

                        trade.pnl_cash = round(trade.pnl_points * cash_per_point, 2)
                        trade.risk_reward_achieved = round(trade.pnl_points / abs(trade.planned_entry - trade.stop_loss), 2) if abs(trade.planned_entry - trade.stop_loss) > 0 else 0.0
                        completed_trades.append(trade)
                        continue

                    # Quy tắc 4: Chạm Stop Loss (hoặc BE nếu đã dời)
                    sl_hit = (c_low <= trade.stop_loss) if is_buy else (c_high >= trade.stop_loss)
                    if sl_hit:
                        trade.actual_exit_price = trade.stop_loss
                        trade.exit_time = c_time

                        if trade.is_breakeven_triggered and abs(trade.stop_loss - entry) <= 0.1:
                            trade.status = TradeStatus.CLOSED_BE
                            trade.pnl_points = 0.0
                        elif trade.partial_closed:
                            # Đã chốt 50% ở TP1, phần còn lại bị dính SL dương
                            trade.status = TradeStatus.CLOSED_TP1
                            pnl_tp1 = abs(trade.take_profit_1 - entry)
                            pnl_rem = 1.0  # SL dương 1 giá
                            trade.pnl_points = round((pnl_tp1 * self.config.partial_tp_ratio) + (pnl_rem * (1 - self.config.partial_tp_ratio)), 2)
                        else:
                            trade.status = TradeStatus.CLOSED_SL
                            trade.pnl_points = round(-abs(entry - trade.stop_loss), 2)

                        trade.pnl_cash = round(trade.pnl_points * cash_per_point, 2)
                        trade.risk_reward_achieved = round(trade.pnl_points / abs(trade.planned_entry - trade.stop_loss), 2) if abs(trade.planned_entry - trade.stop_loss) > 0 else -1.0
                        completed_trades.append(trade)
                        continue

                    # Nếu chưa chạm gì thì giữ tiếp
                    still_active.append(trade)

            active_trades = still_active

            # ─────────────────────────────────────────────────────────────
            # 2. PHÁT TÍN HIỆU MỚI (NO LOOK-AHEAD: CHỈ DÙNG DỮ LIỆU TỚI i)
            # ─────────────────────────────────────────────────────────────
            if len(active_trades) < self.config.max_active_trades:
                current_exec_slice = df_exec_clean.iloc[: i + 1]

                # Lọc nến macro đã đóng trước thời điểm hiện tại
                macro_slice = None
                if df_macro_clean is not None and not df_macro_clean.empty:
                    macro_slice = df_macro_clean[df_macro_clean["time"] < c_time]

                # Sinh tín hiệu từ SignalEngine
                sig: TradingSignal = self.signal_engine.generate_signal(
                    df=current_exec_slice,
                    h4_df=macro_slice,
                    symbol=self.config.symbol,
                    timeframe="M5",
                )

                if sig.direction in (SignalDirection.BUY, SignalDirection.SELL):
                    trade_record = TradeRecord(
                        trade_id=f"BT_{len(completed_trades) + len(active_trades) + 1:04d}",
                        signal_id=sig.signal_id,
                        direction=sig.direction.value,
                        timeframe="M5",
                        planned_entry=sig.entry_price,
                        entry_zone_low=sig.entry_zone_low,
                        entry_zone_high=sig.entry_zone_high,
                        stop_loss=sig.stop_loss,
                        take_profit_1=sig.take_profit_1,
                        take_profit_2=sig.take_profit_2,
                        status=TradeStatus.PENDING,
                    )
                    active_trades.append(trade_record)
                    log.debug("Tạo lệnh chờ mới [%s] %s @ %.2f", trade_record.trade_id, trade_record.direction, trade_record.planned_entry)

        # Đóng các lệnh còn dang dở tại nến cuối cùng
        last_candle = df_exec_clean.iloc[-1]
        last_close = float(last_candle["close"])
        last_time = last_candle["time"]

        for trade in active_trades:
            if trade.status == TradeStatus.OPEN:
                entry = trade.actual_entry_price
                is_buy = (trade.direction == "BUY")
                pnl = (last_close - entry) if is_buy else (entry - last_close)
                trade.actual_exit_price = last_close
                trade.exit_time = last_time
                trade.pnl_points = round(pnl, 2)
                trade.pnl_cash = round(pnl * cash_per_point, 2)
                trade.status = TradeStatus.CLOSED_TP1 if pnl > 0 else TradeStatus.CLOSED_SL
                completed_trades.append(trade)

        # Tính toán toàn bộ thống kê
        result = calculate_metrics(
            trades=[t for t in completed_trades if t.status not in (TradeStatus.INVALIDATED, TradeStatus.EXPIRED)],
            initial_balance=self.config.initial_balance,
            symbol=self.config.symbol,
            timeframe="M5",
        )

        log.info("Backtest hoàn tất: %d lệnh | Lợi nhuận: $%.2f (Win: %.1f%%)",
                 result.total_trades, result.total_net_profit, result.win_rate)
        return result
