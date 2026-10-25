# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho config.py

Kiểm tra:
- Load config từ environment variables.
- Giá trị mặc định khi env trống.
- Ẩn password/token trong repr.
- Required env variable raise lỗi đúng.
"""

import os
import pytest
from unittest.mock import patch

from config import (
    _get_env,
    MT5Config,
    TelegramConfig,
    DatabaseConfig,
    AppConfig,
    Settings,
    get_settings,
)


class TestGetEnv:
    """Test hàm _get_env."""

    def test_returns_env_value(self) -> None:
        with patch.dict(os.environ, {"TEST_KEY": "test_value"}):
            assert _get_env("TEST_KEY") == "test_value"

    def test_returns_default_when_missing(self) -> None:
        result = _get_env("NONEXISTENT_KEY_12345", default="fallback")
        assert result == "fallback"

    def test_returns_empty_string_when_no_default(self) -> None:
        result = _get_env("NONEXISTENT_KEY_12345")
        assert result == ""

    def test_required_raises_when_missing(self) -> None:
        with pytest.raises(EnvironmentError, match="bắt buộc"):
            _get_env("NONEXISTENT_KEY_12345", required=True)

    def test_required_ok_when_present(self) -> None:
        with patch.dict(os.environ, {"TEST_REQ": "value"}):
            assert _get_env("TEST_REQ", required=True) == "value"


class TestMT5Config:
    """Test MT5Config dataclass."""

    def test_from_env_with_values(self) -> None:
        env = {
            "MT5_LOGIN": "12345",
            "MT5_PASSWORD": "secret",
            "MT5_SERVER": "Demo-Server",
            "MT5_TERMINAL_PATH": r"C:\MT5\terminal64.exe",
            "MT5_SYMBOL": "XAUUSD",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = MT5Config.from_env()
            assert cfg.login == 12345
            assert cfg.password == "secret"
            assert cfg.server == "Demo-Server"
            assert cfg.terminal_path == r"C:\MT5\terminal64.exe"
            assert cfg.symbol == "XAUUSD"

    def test_from_env_defaults(self) -> None:
        env = {"MT5_LOGIN": "", "MT5_PASSWORD": "", "MT5_SERVER": "", "MT5_TERMINAL_PATH": ""}
        with patch.dict(os.environ, env, clear=False):
            cfg = MT5Config.from_env()
            assert cfg.login == 0
            assert cfg.password == ""
            assert cfg.symbol == "XAUUSD"  # giá trị mặc định

    def test_password_hidden_in_repr(self) -> None:
        cfg = MT5Config(login=123, password="secret_pass", server="sv", terminal_path="p")
        repr_str = repr(cfg)
        assert "secret_pass" not in repr_str

    def test_invalid_login_defaults_to_zero(self) -> None:
        with patch.dict(os.environ, {"MT5_LOGIN": "not_a_number"}, clear=False):
            cfg = MT5Config.from_env()
            assert cfg.login == 0


class TestTelegramConfig:
    """Test TelegramConfig dataclass."""

    def test_from_env_with_values(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "123:ABC",
            "TELEGRAM_CHAT_ID": "-100123",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = TelegramConfig.from_env()
            assert cfg.bot_token == "123:ABC"
            assert cfg.chat_id == "-100123"

    def test_token_hidden_in_repr(self) -> None:
        cfg = TelegramConfig(bot_token="secret_token", chat_id="123")
        repr_str = repr(cfg)
        assert "secret_token" not in repr_str


class TestDatabaseConfig:
    """Test DatabaseConfig dataclass."""

    def test_default_url(self) -> None:
        cfg = DatabaseConfig.from_env()
        assert cfg.url == "sqlite:///data/vietkey_gold.db"

    def test_custom_url(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///custom.db"}, clear=False):
            cfg = DatabaseConfig.from_env()
            assert cfg.url == "sqlite:///custom.db"


class TestAppConfig:
    """Test AppConfig dataclass."""

    def test_default_log_level(self) -> None:
        cfg = AppConfig.from_env()
        assert cfg.log_level == "INFO"

    def test_log_level_uppercased(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}, clear=False):
            cfg = AppConfig.from_env()
            assert cfg.log_level == "DEBUG"


class TestSettings:
    """Test Settings container."""

    def test_load_creates_all_configs(self) -> None:
        settings = Settings.load()
        assert isinstance(settings.mt5, MT5Config)
        assert isinstance(settings.telegram, TelegramConfig)
        assert isinstance(settings.database, DatabaseConfig)
        assert isinstance(settings.app, AppConfig)

    def test_get_settings_returns_settings(self) -> None:
        settings = get_settings()
        assert isinstance(settings, Settings)
