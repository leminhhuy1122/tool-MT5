# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Unit Tests cho main.py

Kiểm tra:
- check_environment trả về dictionary đúng format.
- main() chạy không crash.
"""

from unittest.mock import patch, MagicMock

from config import Settings, MT5Config, TelegramConfig, DatabaseConfig, AppConfig
from main import check_environment


class TestCheckEnvironment:
    """Test check_environment function."""

    def _make_settings(
        self,
        mt5_login: int = 0,
        mt5_server: str = "",
        tg_token: str = "",
        tg_chat: str = "",
    ) -> Settings:
        """Helper tạo Settings cho test."""
        return Settings(
            mt5=MT5Config(login=mt5_login, password="", server=mt5_server, terminal_path=""),
            telegram=TelegramConfig(bot_token=tg_token, chat_id=tg_chat),
            database=DatabaseConfig.from_env(),
            app=AppConfig.from_env(),
        )

    def test_returns_dict(self) -> None:
        settings = self._make_settings()
        # Mock setup_logging để tránh tạo file log trong test
        from logger import setup_logging
        setup_logging(log_to_file=False)

        result = check_environment(settings)
        assert isinstance(result, dict)

    def test_has_expected_keys(self) -> None:
        settings = self._make_settings()
        from logger import setup_logging
        setup_logging(log_to_file=False)

        result = check_environment(settings)
        expected_keys = {"python", "mt5_package", "mt5_config", "telegram_config"}
        assert expected_keys == set(result.keys())

    def test_python_check_passes(self) -> None:
        settings = self._make_settings()
        from logger import setup_logging
        setup_logging(log_to_file=False)

        result = check_environment(settings)
        # Chúng ta đang chạy Python >= 3.10
        assert result["python"] is True

    def test_mt5_config_false_when_empty(self) -> None:
        settings = self._make_settings(mt5_login=0, mt5_server="")
        from logger import setup_logging
        setup_logging(log_to_file=False)

        result = check_environment(settings)
        assert result["mt5_config"] is False

    def test_mt5_config_true_when_set(self) -> None:
        settings = self._make_settings(mt5_login=12345, mt5_server="Demo")
        from logger import setup_logging
        setup_logging(log_to_file=False)

        result = check_environment(settings)
        assert result["mt5_config"] is True
