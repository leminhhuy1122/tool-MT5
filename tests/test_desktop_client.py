"""
Unit tests cho Desktop Client launcher (client.py) và API endpoints.
"""

from unittest.mock import MagicMock, patch
import pytest

from client import (
    find_available_port,
    is_port_in_use,
    is_vietkey_server,
    wait_for_server,
)
from app.api.server import read_root


def test_client_is_port_in_use():
    """Kiểm tra hàm kiểm tra trạng thái port."""
    # Port 0 hoặc port không tồn tại phải trả về False
    assert is_port_in_use(59999) is False


def test_client_find_available_port():
    """Kiểm tra hàm tìm port TCP khả dụng."""
    port = find_available_port(start_port=58000, max_attempts=5)
    assert 58000 <= port < 58005


def test_client_is_vietkey_server_failure():
    """Kiểm tra is_vietkey_server khi server không phản hồi."""
    assert is_vietkey_server("http://127.0.0.1:59999") is False


def test_client_wait_for_server_timeout():
    """Kiểm tra wait_for_server timeout nếu server không chạy."""
    result = wait_for_server("http://127.0.0.1:59999", timeout=0.5)
    assert result is False


@patch("urllib.request.urlopen")
def test_client_is_vietkey_server_success(mock_urlopen):
    """Kiểm tra is_vietkey_server khi server phản hồi HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    assert is_vietkey_server("http://127.0.0.1:8000") is True


def test_api_read_root():
    """Kiểm tra hàm read_root trả về trạng thái ONLINE."""
    res = read_root()
    assert res["status"] == "ONLINE"
    assert res["app"] == "VietKey Gold AI"
    assert "version" in res
