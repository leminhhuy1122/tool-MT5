# -*- coding: utf-8 -*-
"""
VietKey Gold AI — Telegram API Client.

Giao tiếp với Telegram Bot API sử dụng thư viện chuẩn urllib:
- Không phụ thuộc bên ngoài (zero external dependencies).
- Hỗ trợ retry với exponential backoff.
- Bắt lỗi an toàn, không làm gián đoạn luồng giao dịch chính.
- Hỗ trợ HTML parse mode.
"""

from dataclasses import dataclass, field
import json
import time
from typing import Optional
import urllib.error
import urllib.parse
import urllib.request

from config import TelegramConfig
from logger import get_logger

log = get_logger("telegram.client")

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


@dataclass
class TelegramResponse:
    """Kết quả trả về từ Telegram Bot API."""
    ok: bool
    message_id: Optional[int] = None
    error_code: Optional[int] = None
    description: Optional[str] = None
    raw: dict = field(default_factory=dict)

    def __str__(self) -> str:
        if self.ok:
            return f"TelegramResponse(OK, message_id={self.message_id})"
        return f"TelegramResponse(FAIL, error_code={self.error_code}, desc='{self.description}')"


class TelegramClient:
    """
    Client kết nối và gửi thông điệp tới Telegram Bot API.
    """

    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ):
        if config is not None:
            self.bot_token = config.bot_token
            self.chat_id = config.chat_id
            self.enabled = config.enabled
        else:
            self.bot_token = bot_token or ""
            self.chat_id = chat_id or ""
            self.enabled = True

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def is_configured(self) -> bool:
        """Kiểm tra client đã đủ cấu hình để gửi tin hay chưa."""
        return bool(self.enabled and self.bot_token and self.chat_id)

    def _make_request(self, endpoint: str, payload: Optional[dict] = None) -> TelegramResponse:
        """
        Thực hiện HTTP POST request tới Telegram API kèm retry.

        Args:
            endpoint: API method (e.g. 'sendMessage', 'getMe').
            payload: Dữ liệu POST JSON (nếu có).

        Returns:
            TelegramResponse object.
        """
        if not self.bot_token:
            log.warning("Telegram Bot Token chưa được thiết lập.")
            return TelegramResponse(ok=False, description="Missing bot_token")

        url = f"{TELEGRAM_API_BASE}{self.bot_token}/{endpoint}"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "VietKeyGoldAI/1.0",
        }

        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if resp_data.get("ok"):
                        result = resp_data.get("result", {})
                        msg_id = result.get("message_id") if isinstance(result, dict) else None
                        log.debug("Telegram request %s thành công (msg_id=%s)", endpoint, msg_id)
                        return TelegramResponse(ok=True, message_id=msg_id, raw=resp_data)
                    else:
                        desc = resp_data.get("description", "Unknown error")
                        err_code = resp_data.get("error_code")
                        log.error("Telegram API trả về lỗi: %s (code: %s)", desc, err_code)
                        return TelegramResponse(
                            ok=False,
                            error_code=err_code,
                            description=desc,
                            raw=resp_data,
                        )

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                try:
                    err_json = json.loads(err_body)
                    desc = err_json.get("description", str(e))
                except Exception:
                    desc = err_body or str(e)

                log.warning(
                    "HTTPError %d khi gọi Telegram %s (lần %d/%d): %s",
                    e.code, endpoint, attempt, self.max_retries, desc,
                )

                # Rate limiting (429) -> chờ retry_after nếu có
                if e.code == 429:
                    retry_after = 5
                    try:
                        retry_after = int(err_json.get("parameters", {}).get("retry_after", 5))
                    except Exception:
                        pass
                    time.sleep(retry_after)
                    continue

                if attempt == self.max_retries:
                    return TelegramResponse(ok=False, error_code=e.code, description=desc)

            except (urllib.error.URLError, TimeoutError) as e:
                log.warning(
                    "Network error khi gọi Telegram %s (lần %d/%d): %s",
                    endpoint, attempt, self.max_retries, str(e),
                )
                if attempt == self.max_retries:
                    return TelegramResponse(ok=False, description=str(e))

            except Exception as e:
                log.error("Lỗi không mong muốn khi gọi Telegram %s: %s", endpoint, e)
                return TelegramResponse(ok=False, description=str(e))

            # Sleep backoff trước khi thử lại
            time.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        return TelegramResponse(ok=False, description="Max retries reached")

    def get_me(self) -> TelegramResponse:
        """Kiểm tra bot token và lấy thông tin bot."""
        return self._make_request("getMe")

    def verify_connection(self) -> bool:
        """
        Kiểm tra xem bot token có hợp lệ không.

        Returns:
            True nếu token hợp lệ và kết nối thành công.
        """
        if not self.bot_token:
            return False
        resp = self.get_me()
        return resp.ok

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> TelegramResponse:
        """
        Gửi tin nhắn văn bản tới chat_id.

        Args:
            text: Nội dung tin nhắn (HTML format).
            chat_id: Chat ID người nhận (mặc định lấy từ cấu hình).
            parse_mode: 'HTML' hoặc 'MarkdownV2'.
            disable_web_page_preview: Tắt preview link.

        Returns:
            TelegramResponse.
        """
        target_chat_id = chat_id or self.chat_id
        if not target_chat_id:
            log.warning("Chưa thiết lập chat_id để gửi tin nhắn Telegram.")
            return TelegramResponse(ok=False, description="Missing chat_id")

        if not text:
            return TelegramResponse(ok=False, description="Empty message text")

        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        return self._make_request("sendMessage", payload)
