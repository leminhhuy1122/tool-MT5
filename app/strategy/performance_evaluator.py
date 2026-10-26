# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Historical Setup Performance Tracking & Evaluation (Phase 5).

Theo dõi, phân tích và đánh giá hiệu suất của từng loại Setup giao dịch và Market Regime
dựa trên kết quả thực tế (Outcomes) trong cơ sở dữ liệu:
- Win Rate, Profit Factor, Expectancy (R và points), Average R:R.
- Max Favorable Excursion (MFE), Max Adverse Excursion (MAE), Thời gian giữ lệnh.
- Hệ số điều chỉnh điểm Confluence thích ứng (Historical Performance Score Modifier).
- Phân loại trạng thái Setup (FAVORED, ACTIVE, NEUTRAL, UNDERPERFORMING, PROBATION, INSUFFICIENT_DATA).

Quy tắc Thống kê & Kiểm soát Mẫu:
- Nếu số mẫu < min_sample_size (mặc định 5 lệnh): Trạng thái INSUFFICIENT_DATA, modifier = 0.0.
- Setup vượt trội (Expectancy >= 0.8R hoặc WinRate >= 65% & PF >= 2.0): FAVORED (+6.0 đến +10.0 điểm).
- Setup tích cực (Expectancy >= 0.3R hoặc WinRate >= 55% & PF >= 1.5): ACTIVE (+3.0 đến +5.0 điểm).
- Setup trung tính (-0.2R <= Expectancy < 0.3R): NEUTRAL (0.0 điểm).
- Setup hoạt động kém (Expectancy < -0.2R hoặc WinRate < 40%): UNDERPERFORMING (-5.0 điểm).
- Setup cảnh báo nguy cơ (Expectancy < -0.5R hoặc WinRate < 30% với >= 10 lệnh): PROBATION (-10.0 điểm).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import TYPE_CHECKING, Any, Optional, Union

from logger import get_logger

if TYPE_CHECKING:
    from app.database.repository import SignalRepository

log = get_logger("strategy.performance")


class SetupStatus(Enum):
    """Trạng thái đánh giá hiệu suất của Setup."""
    FAVORED = "FAVORED"                         # Hiệu suất xuất sắc, ưu tiên phát lệnh (+thưởng)
    ACTIVE = "ACTIVE"                           # Đạt chuẩn hiệu suất dương (+thưởng nhẹ)
    NEUTRAL = "NEUTRAL"                         # Trung tính, không ảnh hưởng điểm
    UNDERPERFORMING = "UNDERPERFORMING"         # Hiệu suất kém, trừ điểm cảnh báo (-phạt)
    PROBATION = "PROBATION"                     # Kém nghiêm trọng, phạt nặng / cần rà soát
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"     # Chưa đủ dữ liệu mẫu thống kê (0 điểm)


@dataclass
class SetupPerformanceMetrics:
    """Các chỉ số thống kê hiệu suất định lượng cho một loại Setup hoặc Regime."""
    setup_type: str
    sample_size: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: float = 0.0               # % (0 - 100)
    profit_factor: float = 0.0          # Tổng lãi / Tổng lỗ
    expectancy_r: float = 0.0           # Kỳ vọng R mỗi lệnh: (WR*AvgWinR) - (LR*AvgLossR)
    expectancy_points: float = 0.0      # Kỳ vọng điểm giá mỗi lệnh
    net_points: float = 0.0             # Tổng điểm lãi ròng
    avg_win_points: float = 0.0
    avg_loss_points: float = 0.0
    avg_r: float = 0.0                  # R trung bình thực tế đạt được
    avg_duration_minutes: float = 0.0   # Thời gian giữ lệnh trung bình
    mfe_avg_points: float = 0.0         # MFE trung bình
    mae_avg_points: float = 0.0         # MAE trung bình
    score_modifier: float = 0.0         # Hệ số cộng/trừ vào Confluence Score (-10.0 đến +10.0)
    status: SetupStatus = SetupStatus.INSUFFICIENT_DATA
    last_updated: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Chuyển đổi thành từ điển phục vụ API và lưu vết."""
        return {
            "setup_type": self.setup_type,
            "sample_size": self.sample_size,
            "wins": self.wins,
            "losses": self.losses,
            "breakevens": self.breakevens,
            "win_rate": round(self.win_rate, 1),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy_r": round(self.expectancy_r, 2),
            "expectancy_points": round(self.expectancy_points, 2),
            "net_points": round(self.net_points, 2),
            "avg_win_points": round(self.avg_win_points, 2),
            "avg_loss_points": round(self.avg_loss_points, 2),
            "avg_r": round(self.avg_r, 2),
            "avg_duration_minutes": round(self.avg_duration_minutes, 1),
            "mfe_avg_points": round(self.mfe_avg_points, 2),
            "mae_avg_points": round(self.mae_avg_points, 2),
            "score_modifier": round(self.score_modifier, 1),
            "status": self.status.value,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    def __str__(self) -> str:
        return (
            f"[{self.setup_type}] {self.status.value} (N={self.sample_size}) | "
            f"WR: {self.win_rate:.1f}% | PF: {self.profit_factor:.2f} | "
            f"Exp: {self.expectancy_r:+.2f}R | Modifier: {self.score_modifier:+.1f}"
        )


class SetupPerformanceEvaluator:
    """
    Động cơ đánh giá hiệu suất setup và regime theo dữ liệu lịch sử thực tế.
    """

    def __init__(
        self,
        repository: Optional["SignalRepository"] = None,
        min_sample_size: int = 5,
        full_sample_size: int = 15,
        lookback_days: Optional[int] = None,
    ):
        """
        Khởi tạo evaluator.

        Args:
            repository: SignalRepository kết nối database SQLite (tùy chọn).
            min_sample_size: Số mẫu tối thiểu để xét ý nghĩa thống kê (mặc định 5).
            full_sample_size: Số mẫu tối thiểu để đạt độ tin cậy tuyệt đối (mặc định 15).
            lookback_days: Số ngày nhìn lại (None = toàn bộ lịch sử).
        """
        self.repository = repository
        self.min_sample_size = min_sample_size
        self.full_sample_size = full_sample_size
        self.lookback_days = lookback_days
        self._cached_setup_metrics: dict[str, SetupPerformanceMetrics] = {}
        self._cached_regime_metrics: dict[str, dict[str, Any]] = {}
        self._last_refresh: Optional[datetime] = None

    def evaluate_records(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, SetupPerformanceMetrics]:
        """
        Tính toán hiệu suất từ danh sách bản ghi outcome (JOIN giữa signals và signal_outcomes).

        Args:
            records: Danh sách dictionary chứa:
                     - setup_type (str)
                     - pnl_points (float)
                     - pnl_r (float, optional)
                     - final_status (str, optional)
                     - duration_seconds (int, optional)
                     - max_favorable_excursion (float, optional)
                     - max_adverse_excursion (float, optional)

        Returns:
            dict mapping setup_type -> SetupPerformanceMetrics, kèm key "OVERALL".
        """
        now = datetime.now(timezone.utc)
        if not records:
            empty_all = SetupPerformanceMetrics(
                setup_type="OVERALL",
                status=SetupStatus.INSUFFICIENT_DATA,
                last_updated=now,
            )
            return {"OVERALL": empty_all}

        # Gom nhóm bản ghi theo setup_type
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in records:
            st = str(r.get("setup_type") or "UNKNOWN")
            grouped.setdefault(st, []).append(r)

        result: dict[str, SetupPerformanceMetrics] = {}

        # Đánh giá từng nhóm setup
        for st, items in grouped.items():
            metrics = self._calculate_metrics_for_group(st, items, now)
            result[st] = metrics

        # Đánh giá tổng hợp toàn bộ hệ thống
        overall_metrics = self._calculate_metrics_for_group("OVERALL", records, now)
        result["OVERALL"] = overall_metrics

        return result

    def _calculate_metrics_for_group(
        self,
        group_name: str,
        items: list[dict[str, Any]],
        timestamp: datetime,
    ) -> SetupPerformanceMetrics:
        """Tính toán các chỉ số cho một nhóm bản ghi."""
        sample_size = len(items)
        if sample_size == 0:
            return SetupPerformanceMetrics(
                setup_type=group_name,
                status=SetupStatus.INSUFFICIENT_DATA,
                last_updated=timestamp,
            )

        wins = 0
        losses = 0
        breakevens = 0
        total_pnl_points = 0.0
        total_profit_points = 0.0
        total_loss_points = 0.0

        r_values: list[float] = []
        durations: list[float] = []
        mfes: list[float] = []
        maes: list[float] = []

        for item in items:
            pnl_pts = float(item.get("pnl_points") or 0.0)
            pnl_r = item.get("pnl_r")

            total_pnl_points += pnl_pts

            if pnl_pts > 0:
                wins += 1
                total_profit_points += pnl_pts
            elif pnl_pts < 0:
                losses += 1
                total_loss_points += abs(pnl_pts)
            else:
                breakevens += 1

            if pnl_r is not None:
                try:
                    r_values.append(float(pnl_r))
                except (ValueError, TypeError):
                    pass

            dur = item.get("duration_seconds")
            if dur is not None and dur > 0:
                durations.append(float(dur) / 60.0)

            mfe = item.get("max_favorable_excursion")
            if mfe is not None:
                mfes.append(float(mfe))

            mae = item.get("max_adverse_excursion")
            if mae is not None:
                maes.append(float(mae))

        win_rate = (wins / sample_size * 100.0) if sample_size > 0 else 0.0
        loss_rate = (losses / sample_size * 100.0) if sample_size > 0 else 0.0

        if total_loss_points > 0:
            profit_factor = total_profit_points / total_loss_points
        else:
            profit_factor = 3.0 if wins > 0 else 0.0

        avg_win_points = (total_profit_points / wins) if wins > 0 else 0.0
        avg_loss_points = (total_loss_points / losses) if losses > 0 else 0.0
        expectancy_points = total_pnl_points / sample_size if sample_size > 0 else 0.0

        # Kỳ vọng theo R (Expectancy in R)
        if r_values:
            avg_r = sum(r_values) / len(r_values)
            win_r_vals = [r for r in r_values if r > 0]
            loss_r_vals = [abs(r) for r in r_values if r < 0]
            avg_win_r = (sum(win_r_vals) / len(win_r_vals)) if win_r_vals else 1.5
            avg_loss_r = (sum(loss_r_vals) / len(loss_r_vals)) if loss_r_vals else 1.0
            expectancy_r = ((win_rate / 100.0) * avg_win_r) - ((loss_rate / 100.0) * avg_loss_r)
        else:
            avg_r = (expectancy_points / 10.0) if expectancy_points != 0 else 0.0
            expectancy_r = avg_r

        avg_duration_minutes = (sum(durations) / len(durations)) if durations else 0.0
        mfe_avg_points = (sum(mfes) / len(mfes)) if mfes else 0.0
        mae_avg_points = (sum(maes) / len(maes)) if maes else 0.0

        # Phân loại trạng thái và tính hệ số Score Modifier
        modifier, status = self._determine_modifier_and_status(
            sample_size=sample_size,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy_r=expectancy_r,
        )

        return SetupPerformanceMetrics(
            setup_type=group_name,
            sample_size=sample_size,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy_r=expectancy_r,
            expectancy_points=expectancy_points,
            net_points=total_pnl_points,
            avg_win_points=avg_win_points,
            avg_loss_points=avg_loss_points,
            avg_r=avg_r,
            avg_duration_minutes=avg_duration_minutes,
            mfe_avg_points=mfe_avg_points,
            mae_avg_points=mae_avg_points,
            score_modifier=modifier,
            status=status,
            last_updated=timestamp,
        )

    def _determine_modifier_and_status(
        self,
        sample_size: int,
        win_rate: float,
        profit_factor: float,
        expectancy_r: float,
    ) -> tuple[float, SetupStatus]:
        """
        Xác định hệ số điều chỉnh Confluence Score (-10 đến +10) và trạng thái Setup.
        """
        # Nếu chưa đủ cỡ mẫu tối thiểu
        if sample_size < self.min_sample_size:
            return 0.0, SetupStatus.INSUFFICIENT_DATA

        # Hệ số tin cậy mẫu (Sample Confidence Weight: từ 0.7 đến 1.0)
        sample_weight = min(1.0, 0.7 + 0.3 * (sample_size / self.full_sample_size))

        # 1. Setup xuất sắc (Favored)
        if expectancy_r >= 0.8 or (win_rate >= 65.0 and profit_factor >= 2.0):
            base_mod = 10.0 if sample_size >= self.full_sample_size else 8.0
            return round(base_mod * sample_weight, 1), SetupStatus.FAVORED

        # 2. Setup tích cực (Active)
        elif expectancy_r >= 0.3 or (win_rate >= 55.0 and profit_factor >= 1.5):
            base_mod = 6.0 if sample_size >= self.full_sample_size else 4.0
            return round(base_mod * sample_weight, 1), SetupStatus.ACTIVE

        # 3. Setup trung tính (Neutral)
        elif expectancy_r >= -0.2:
            return 0.0, SetupStatus.NEUTRAL

        # 4. Setup cảnh báo nguy cơ nghiêm trọng (Probation)
        elif expectancy_r < -0.5 or (win_rate < 30.0 and sample_size >= 10):
            return -10.0, SetupStatus.PROBATION

        # 5. Setup dưới chuẩn (Underperforming)
        else:
            return -5.0, SetupStatus.UNDERPERFORMING

    def refresh(self) -> dict[str, SetupPerformanceMetrics]:
        """
        Truy vấn database để cập nhật lại toàn bộ metrics cho các setup.
        """
        if not self.repository:
            log.debug("Evaluator chưa gắn repository, giữ nguyên metrics hiện tại.")
            return self._cached_setup_metrics

        try:
            records = self.repository.get_historical_outcomes(
                lookback_days=self.lookback_days
            )
            self._cached_setup_metrics = self.evaluate_records(records)
            self._last_refresh = datetime.now(timezone.utc)
            log.info("✓ Đã cập nhật metrics hiệu suất cho %d loại setup.", len(self._cached_setup_metrics))
        except Exception as e:
            log.warning("Lỗi truy vấn lịch sử setup từ database: %s", e)

        return self._cached_setup_metrics

    def get_metrics(
        self,
        setup_type: Union[str, Any],
    ) -> SetupPerformanceMetrics:
        """
        Lấy thông số hiệu suất của một loại setup cụ thể.
        """
        st_val = getattr(setup_type, "value", str(setup_type))
        if st_val in self._cached_setup_metrics:
            return self._cached_setup_metrics[st_val]

        # Trả về đối tượng trung tính nếu chưa có dữ liệu
        return SetupPerformanceMetrics(
            setup_type=st_val,
            status=SetupStatus.INSUFFICIENT_DATA,
            last_updated=datetime.now(timezone.utc),
        )

    def get_score_modifier(
        self,
        setup_type: Union[str, Any],
    ) -> float:
        """
        Lấy hệ số cộng/trừ điểm (-10.0 đến +10.0) của setup dựa trên hiệu suất lịch sử.
        """
        metrics = self.get_metrics(setup_type)
        return metrics.score_modifier

    def is_setup_on_probation(
        self,
        setup_type: Union[str, Any],
    ) -> bool:
        """Kiểm tra setup có đang trong diện cảnh báo rủi ro cao (PROBATION) không."""
        metrics = self.get_metrics(setup_type)
        return metrics.status == SetupStatus.PROBATION

    def get_all_performances(self) -> dict[str, dict[str, Any]]:
        """Trả về toàn bộ thống kê setup dưới dạng dict cho API và UI."""
        return {st: m.to_dict() for st, m in self._cached_setup_metrics.items()}
