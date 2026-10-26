# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Configuration Module.

Đọc cấu hình từ environment variables (.env file).
Không bao giờ lưu trực tiếp token, password hoặc API key trong source code.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Đảm bảo stdout hỗ trợ UTF-8 trên Windows
# ──────────────────────────────────────────────
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ──────────────────────────────────────────────
# Đường dẫn gốc của project
# ──────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent

# Load .env file
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    load_dotenv(_env_path, encoding="utf-8")
else:
    # Không có .env → in cảnh báo nhưng không crash
    print(
        "[WARNING] .env file not found. "
        "Copy .env.example to .env and fill in your values."
    )


# ──────────────────────────────────────────────
# Hàm tiện ích đọc env
# ──────────────────────────────────────────────
def _get_env(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """Đọc biến môi trường, tự động loại bỏ khoảng trắng và dấu ngoặc kép thừa."""
    value = os.getenv(key, default)
    if required and not value:
        raise EnvironmentError(
            f"Biến môi trường '{key}' là bắt buộc nhưng chưa được thiết lập. "
            f"Kiểm tra file .env hoặc environment variables."
        )
    if value is not None:
        value = value.strip().strip("'\"").strip()
    return value or ""


# ──────────────────────────────────────────────
# Data classes cho từng nhóm cấu hình
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class MT5Config:
    """Cấu hình kết nối MetaTrader 5."""

    login: int = field(default=0)
    password: str = field(default="", repr=False)  # repr=False: không in password
    server: str = field(default="")
    terminal_path: str = field(default="")
    symbol: str = field(default="XAUUSD")

    @classmethod
    def from_env(cls) -> "MT5Config":
        """Tạo MT5Config từ environment variables."""
        login_str = _get_env("MT5_LOGIN", default="0")
        try:
            login = int(login_str)
        except ValueError:
            login = 0
        return cls(
            login=login,
            password=_get_env("MT5_PASSWORD"),
            server=_get_env("MT5_SERVER"),
            terminal_path=_get_env("MT5_TERMINAL_PATH"),
            symbol=_get_env("MT5_SYMBOL", default="XAUUSD"),
        )


@dataclass(frozen=True)
class TelegramConfig:
    """Cấu hình Telegram Bot."""

    bot_token: str = field(default="", repr=False)  # repr=False: không in token
    chat_id: str = field(default="")
    enabled: bool = field(default=True)

    @property
    def is_configured(self) -> bool:
        """Kiểm tra Telegram đã được cấu hình và bật hay chưa."""
        return bool(self.enabled and self.bot_token and self.chat_id)

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        """Tạo TelegramConfig từ environment variables."""
        enabled_val = _get_env("TELEGRAM_ENABLED", default="true").lower()
        enabled = enabled_val in ("true", "1", "yes")
        return cls(
            bot_token=_get_env("TELEGRAM_BOT_TOKEN"),
            chat_id=_get_env("TELEGRAM_CHAT_ID"),
            enabled=enabled,
        )


@dataclass(frozen=True)
class DatabaseConfig:
    """Cấu hình database."""

    url: str = field(default="sqlite:///data/vietkey_gold.db")

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Tạo DatabaseConfig từ environment variables."""
        return cls(
            url=_get_env("DATABASE_URL", default="sqlite:///data/vietkey_gold.db"),
        )


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình chung của ứng dụng."""

    log_level: str = field(default="INFO")
    base_dir: Path = field(default=BASE_DIR)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Tạo AppConfig từ environment variables."""
        return cls(
            log_level=_get_env("LOG_LEVEL", default="INFO").upper(),
            base_dir=BASE_DIR,
        )


@dataclass(frozen=True)
class OpenAIConfig:
    """Cấu hình OpenAI API để tự động tổng hợp & phân tích bài viết tài chính."""

    api_key: str = field(default="", repr=False)
    model: str = field(default="gpt-4o-mini")
    base_url: Optional[str] = field(default=None)

    @property
    def is_configured(self) -> bool:
        """Kiểm tra xem OpenAI API key đã được nạp hay chưa."""
        return bool(self.api_key and len(self.api_key.strip()) > 8)

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        return cls(
            api_key=_get_env("OPENAI_API_KEY", default=""),
            model=_get_env("OPENAI_MODEL", default="gpt-4o-mini"),
            base_url=_get_env("OPENAI_BASE_URL", default="") or None,
        )


@dataclass(frozen=True)
class NewsAutoPostConfig:
    """Cấu hình tự động tổng hợp và đăng tin lên Telegram."""

    enabled: bool = field(default=False)
    morning_post_time: str = field(default="07:30")  # HH:MM Giờ VN
    auto_alert_red_news: bool = field(default=True)
    buffer_before_min: int = field(default=30)

    @classmethod
    def from_env(cls) -> "NewsAutoPostConfig":
        enabled_val = _get_env("NEWS_AUTO_POST_ENABLED", default="false").lower()
        return cls(
            enabled=enabled_val in ("true", "1", "yes"),
            morning_post_time=_get_env("NEWS_MORNING_POST_TIME", default="07:30"),
            auto_alert_red_news=_get_env("NEWS_AUTO_ALERT_RED", default="true").lower() in ("true", "1", "yes"),
            buffer_before_min=int(_get_env("NEWS_BUFFER_BEFORE_MIN", default="30")),
        )


@dataclass(frozen=True)
class OptimizationConfig:
    """Cấu hình tối ưu hóa tài nguyên hệ thống (Phase 10)."""

    enable_ml_filter: bool = field(default=True)
    enable_self_learning: bool = field(default=True)
    max_cached_candles: int = field(default=200)
    data_cache_ttl_sec: float = field(default=3.0)
    enable_process_singleton: bool = field(default=True)
    benchmark_interval_sec: float = field(default=300.0)

    @classmethod
    def from_env(cls) -> "OptimizationConfig":
        return cls(
            enable_ml_filter=_get_env("ENABLE_ML_FILTER", default="true").lower() in ("true", "1", "yes"),
            enable_self_learning=_get_env("ENABLE_SELF_LEARNING", default="true").lower() in ("true", "1", "yes"),
            max_cached_candles=int(_get_env("MAX_CACHED_CANDLES", default="200")),
            data_cache_ttl_sec=float(_get_env("DATA_CACHE_TTL_SEC", default="3.0")),
            enable_process_singleton=_get_env("ENABLE_PROCESS_SINGLETON", default="true").lower() in ("true", "1", "yes"),
            benchmark_interval_sec=float(_get_env("BENCHMARK_INTERVAL_SEC", default="300.0")),
        )


@dataclass(frozen=True)
class SmartExitConfig:
    """Cấu hình động cơ thoát lệnh và bảo vệ lợi nhuận thích ứng (Phase 12)."""

    enabled: bool = field(default=True)
    be_trigger_r: float = field(default=1.0)              # Ngưỡng kéo BE theo R (mặc định 1.0R)
    be_cushion_min_pts: float = field(default=0.5)        # Mức đệm tối thiểu cho BE (bù spread)
    trailing_trigger_r: float = field(default=1.5)        # Ngưỡng kích hoạt Trailing Stop (1.5R)
    trailing_atr_multiplier: float = field(default=1.5)   # Hệ số nhân ATR cho khoảng cách trailing
    enable_swing_trailing: bool = field(default=True)     # Cho phép bám theo Swing High/Low M5
    enable_scaled_exits: bool = field(default=True)       # Bật khuyến nghị chốt lời từng bậc 50/30/20
    tier1_r_threshold: float = field(default=1.0)         # Ngưỡng chốt 50% Tier 1 (+1.0R)
    tier2_r_threshold: float = field(default=2.0)         # Ngưỡng chốt thêm 30% Tier 2 (+2.0R)

    @classmethod
    def from_env(cls) -> "SmartExitConfig":
        return cls(
            enabled=_get_env("SMART_EXIT_ENABLED", default="true").lower() in ("true", "1", "yes"),
            be_trigger_r=float(_get_env("SMART_EXIT_BE_TRIGGER_R", default="1.0")),
            be_cushion_min_pts=float(_get_env("SMART_EXIT_BE_CUSHION_MIN", default="0.5")),
            trailing_trigger_r=float(_get_env("SMART_EXIT_TRAILING_TRIGGER_R", default="1.5")),
            trailing_atr_multiplier=float(_get_env("SMART_EXIT_ATR_MULT", default="1.5")),
            enable_swing_trailing=_get_env("SMART_EXIT_ENABLE_SWING", default="true").lower() in ("true", "1", "yes"),
            enable_scaled_exits=_get_env("SMART_EXIT_ENABLE_SCALED", default="true").lower() in ("true", "1", "yes"),
            tier1_r_threshold=float(_get_env("SMART_EXIT_TIER1_R", default="1.0")),
            tier2_r_threshold=float(_get_env("SMART_EXIT_TIER2_R", default="2.0")),
        )


@dataclass(frozen=True)
class HedgingConfig:
    """Cấu hình chiến lược quản lý vị thế 2 đầu (Strategic Zone Hedging)."""

    allow_strategic_hedging: bool = field(default=True)       # Cho phép mở BUY & SELL nếu thỏa mãn điều kiện an toàn
    min_hedging_distance_points: float = field(default=5.0)   # Khoảng cách tối thiểu giữa 2 lệnh ngược chiều (cấm lệch 1-2 giá)
    require_breakeven_or_profit: bool = field(default=True)   # Lệnh cũ bắt buộc phải có lãi hoặc đã dời SL về BE
    min_existing_profit_points: float = field(default=3.0)    # Lệnh cũ phải lãi tối thiểu X giá (ví dụ 3 giá = 30 pips)

    @classmethod
    def from_env(cls) -> "HedgingConfig":
        return cls(
            allow_strategic_hedging=_get_env("ALLOW_STRATEGIC_HEDGING", default="true").lower() in ("true", "1", "yes"),
            min_hedging_distance_points=float(_get_env("MIN_HEDGING_DISTANCE_POINTS", default="5.0")),
            require_breakeven_or_profit=_get_env("REQUIRE_BREAKEVEN_OR_PROFIT", default="true").lower() in ("true", "1", "yes"),
            min_existing_profit_points=float(_get_env("MIN_EXISTING_PROFIT_POINTS", default="3.0")),
        )


# ──────────────────────────────────────────────
# Factory function: tạo tất cả config một lần
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    """Container cho toàn bộ cấu hình ứng dụng."""

    mt5: MT5Config
    telegram: TelegramConfig
    database: DatabaseConfig
    app: AppConfig
    openai: OpenAIConfig = field(default_factory=OpenAIConfig.from_env)
    news_auto: NewsAutoPostConfig = field(default_factory=NewsAutoPostConfig.from_env)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig.from_env)
    smart_exit: SmartExitConfig = field(default_factory=SmartExitConfig.from_env)
    hedging: HedgingConfig = field(default_factory=HedgingConfig.from_env)

    @classmethod
    def load(cls) -> "Settings":
        """Load toàn bộ cấu hình từ environment."""
        return cls(
            mt5=MT5Config.from_env(),
            telegram=TelegramConfig.from_env(),
            database=DatabaseConfig.from_env(),
            app=AppConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            news_auto=NewsAutoPostConfig.from_env(),
            optimization=OptimizationConfig.from_env(),
            smart_exit=SmartExitConfig.from_env(),
            hedging=HedgingConfig.from_env(),
        )


def get_settings() -> Settings:
    """Hàm tiện ích để lấy Settings. Có thể mở rộng thêm caching sau."""
    return Settings.load()

