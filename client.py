"""
VietKey Gold AI — Standalone Desktop Client (Native Window).

Chạy giao diện VietKey Gold AI trong một cửa sổ ứng dụng Windows độc lập (Native Window)
bằng Microsoft Edge WebView2 (qua thư viện pywebview).
Không cần mở trình duyệt web bên ngoài (Chrome/Edge/Firefox), không có thanh URL hay tab trình duyệt,
cho trải nghiệm mượt mà, chuyên nghiệp như TradingView Desktop hay Telegram Desktop.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

from logger import get_logger

log = get_logger("vietkey.client")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Kiểm tra xem cổng mạng đã có ứng dụng nào sử dụng chưa."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def is_vietkey_server(url: str) -> bool:
    """Kiểm tra xem server tại URL có phải là VietKey Gold AI không."""
    try:
        req = urllib.request.Request(f"{url}/health", headers={"User-Agent": "VietKeyClient"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def find_available_port(start_port: int = 8000, max_attempts: int = 20) -> int:
    """Tìm cổng TCP còn trống bắt đầu từ start_port."""
    for p in range(start_port, start_port + max_attempts):
        if not is_port_in_use(p):
            return p
    raise RuntimeError(f"Không tìm thấy cổng TCP trống trong khoảng {start_port} - {start_port + max_attempts}")


def run_backend_server(host: str, port: int) -> None:
    """Chạy FastAPI Uvicorn Server trong background daemon thread."""
    import uvicorn
    from app.api.server import app

    uvicorn_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)
    server.run()


def wait_for_server(url: str, timeout: float = 12.0) -> bool:
    """Chờ cho đến khi server phản hồi endpoint /health."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_vietkey_server(url):
            return True
        time.sleep(0.3)
    return False


def launch_desktop_client(
    host: str = "127.0.0.1",
    port: int = 8000,
    dev_mode: bool = False,
    fullscreen: bool = False,
) -> None:
    """Khởi động Desktop Client cửa sổ riêng biệt."""
    import webview

    target_url = f"http://{host}:{port}"

    if dev_mode:
        target_url = "http://localhost:5173"
        log.info("Chế độ DEV: Kết nối tới Vite dev server: %s", target_url)
    else:
        # Kiểm tra xem đã có server VietKey nào đang chạy sẵn chưa
        if is_vietkey_server(target_url):
            log.info("✓ Phát hiện VietKey Backend đang chạy sẵn tại %s", target_url)
        else:
            # Nếu cổng bị ứng dụng khác chiếm dụng, tìm cổng mới
            if is_port_in_use(port, host):
                log.warning("Cổng %d bị chiếm bởi ứng dụng khác. Đang tìm cổng thay thế...", port)
                port = find_available_port(port + 1)
                target_url = f"http://{host}:{port}"

            log.info("Khởi động VietKey Backend Server tại %s...", target_url)
            server_thread = threading.Thread(
                target=run_backend_server,
                args=(host, port),
                daemon=True,
                name="VietKeyServerThread",
            )
            server_thread.start()

            log.info("Đang kiểm tra kết nối server...")
            if not wait_for_server(target_url, timeout=12.0):
                log.error("Không thể kết nối đến Backend Server sau 12 giây.")
                sys.exit(1)
            log.info("✓ Backend Server đã sẵn sàng!")

    log.info("Khởi động cửa sổ Desktop Terminal...")
    window = webview.create_window(
        title="VIETKEY GOLD AI — Institutional Trading Terminal",
        url=target_url,
        width=1440,
        height=900,
        min_size=(1024, 680),
        background_color="#0B0F19",  # Màu nền tối để tránh chớp trắng khi khởi động
        text_select=True,
        fullscreen=fullscreen,
    )

    # Chạy giao diện native (Microsoft Edge WebView2 trên Windows)
    webview.start(debug=dev_mode)
    log.info("Đã đóng cửa sổ Desktop Terminal. Tạm biệt!")


def main() -> None:
    """Điểm vào chính khi chạy client.py."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(
        description="VietKey Gold AI — Standalone Desktop Client (Native Window)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Địa chỉ host backend (mặc định: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Cổng backend (mặc định: 8000)")
    parser.add_argument("--dev", action="store_true", help="Chạy ở chế độ Dev kết nối Vite port 5173")
    parser.add_argument("--fullscreen", action="store_true", help="Mở ở chế độ toàn màn hình")

    args = parser.parse_args()
    launch_desktop_client(
        host=args.host,
        port=args.port,
        dev_mode=args.dev,
        fullscreen=args.fullscreen,
    )


if __name__ == "__main__":
    main()
