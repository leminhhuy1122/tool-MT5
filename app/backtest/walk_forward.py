# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Walk-Forward Analysis.

Đánh giá độ ổn định của chiến lược theo thời gian:
- Chia dữ liệu lịch sử thành nhiều chu kỳ (Folds / Windows) nối tiếp nhau.
- Chạy backtest trên từng phân đoạn để kiểm tra tính nhất quán (Consistency).
- Giúp loại bỏ hiện tượng may mắn ngẫu nhiên trong một giai đoạn thị trường cụ thể.
"""

from dataclasses import dataclass, field
import pandas as pd

from app.backtest.engine import BacktestEngine
from app.backtest.models import BacktestConfig, BacktestResult
from logger import get_logger

log = get_logger("backtest.walk_forward")


@dataclass
class WalkForwardFold:
    """Kết quả của một chu kỳ Walk-Forward."""
    fold_index: int
    start_time: str
    end_time: str
    total_trades: int
    win_rate: float
    profit_factor: float
    net_profit: float
    max_drawdown_pct: float
    is_profitable: bool


@dataclass
class WalkForwardReport:
    """Báo cáo tổng hợp Walk-Forward."""
    symbol: str
    total_folds: int
    profitable_folds: int
    consistency_rate: float            # % số chu kỳ có lãi
    avg_win_rate: float
    avg_profit_factor: float
    total_net_profit: float
    folds: list[WalkForwardFold] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"=== BÁO CÁO WALK-FORWARD ({self.symbol}) ===\n"
            f"• Số chu kỳ kiểm thử: {self.total_folds} (Chu kỳ có lãi: {self.profitable_folds})\n"
            f"• Độ ổn định (Consistency Rate): {self.consistency_rate:.1f}%\n"
            f"• Win Rate trung bình: {self.avg_win_rate:.1f}%\n"
            f"• Profit Factor trung bình: {self.avg_profit_factor:.2f}\n"
            f"• Tổng lợi nhuận tích lũy: ${self.total_net_profit:+,.2f}\n"
            f"============================================"
        )


class WalkForwardAnalyzer:
    """Phân tích Walk-Forward cho chiến lược."""

    def __init__(self, engine: BacktestEngine, num_folds: int = 3):
        self.engine = engine
        self.num_folds = max(2, num_folds)

    def run(self, df_exec: pd.DataFrame, df_macro: Optional[pd.DataFrame] = None) -> WalkForwardReport:
        """
        Chia dữ liệu thành các đoạn đều nhau và chạy backtest độc lập từng đoạn.
        """
        n_bars = len(df_exec)
        fold_size = n_bars // self.num_folds

        if fold_size < 40:
            log.warning("Dữ liệu không đủ nến để chia thành %d chu kỳ", self.num_folds)
            return WalkForwardReport(
                symbol=self.engine.config.symbol,
                total_folds=0,
                profitable_folds=0,
                consistency_rate=0.0,
                avg_win_rate=0.0,
                avg_profit_factor=0.0,
                total_net_profit=0.0,
            )

        folds: list[WalkForwardFold] = []
        total_profit = 0.0

        for f_idx in range(self.num_folds):
            start_i = f_idx * fold_size
            end_i = (f_idx + 1) * fold_size if f_idx < self.num_folds - 1 else n_bars
            fold_df = df_exec.iloc[start_i:end_i].reset_index(drop=True)

            res: BacktestResult = self.engine.run(df_exec=fold_df, df_macro=df_macro, min_warmup_bars=20)

            start_t = str(fold_df.iloc[0]["time"]) if "time" in fold_df.columns else f"Bar {start_i}"
            end_t = str(fold_df.iloc[-1]["time"]) if "time" in fold_df.columns else f"Bar {end_i}"

            is_prof = res.total_net_profit > 0
            total_profit += res.total_net_profit

            folds.append(
                WalkForwardFold(
                    fold_index=f_idx + 1,
                    start_time=start_t,
                    end_time=end_t,
                    total_trades=res.total_trades,
                    win_rate=res.win_rate,
                    profit_factor=res.profit_factor,
                    net_profit=res.total_net_profit,
                    max_drawdown_pct=res.max_drawdown_pct,
                    is_profitable=is_prof,
                )
            )

        profitable_folds = sum(1 for f in folds if f.is_profitable)
        consistency = (profitable_folds / len(folds) * 100.0) if folds else 0.0
        avg_wr = sum(f.win_rate for f in folds) / len(folds) if folds else 0.0
        avg_pf = sum(f.profit_factor for f in folds) / len(folds) if folds else 0.0

        return WalkForwardReport(
            symbol=self.engine.config.symbol,
            total_folds=len(folds),
            profitable_folds=profitable_folds,
            consistency_rate=round(consistency, 1),
            avg_win_rate=round(avg_wr, 1),
            avg_profit_factor=round(avg_pf, 2),
            total_net_profit=round(total_profit, 2),
            folds=folds,
        )
