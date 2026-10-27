# -*- coding: utf-8 -*-
"""
VietKey Gold AI — REST API Backend Server.

Cung cấp các API trực tiếp cho Dashboard:
- Kết nối trực tiếp MetaTrader 5 (giá thực, bid/ask, spread, nến đa khung thời gian).
- Phân tích cấu trúc thị trường thực (H4, H1, M15, M5) và biến động ATR.
- Truy vấn tín hiệu và kết quả từ SQLite Database (vietkey_gold.db).
- Giám sát tài nguyên hệ thống thực tế (CPU, RAM, Uptime qua psutil).
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import psutil

# Ensure app root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Optional
from pydantic import BaseModel

from app.database.connection import DatabaseManager
from app.database.repository import MarketDataRepository, SignalRepository
from app.market.data_manager import MarketDataManager
from app.market.market_structure import analyze_market_structure
from app.market.timeframe_manager import Timeframe
from app.market.volatility import analyze_volatility
from app.mt5.connector import MT5Connector
from app.news.ai_writer import AINewsWriter
from app.news.calendar import NewsManager
from app.strategy.signal_engine import SignalEngine
from app.strategy.signal_models import TradingSignal
from app.telegram.notifier import TelegramNotifier
from config import get_settings
from logger import get_logger, setup_logging

setup_logging()
log = get_logger("api.server")

# Global instances
START_TIME = time.time()
cpu_history: list[float] = []
ram_history: list[float] = []

settings = get_settings()
connector: MT5Connector | None = None
db_manager: DatabaseManager | None = None
signal_repo: SignalRepository | None = None
market_repo: MarketDataRepository | None = None
signal_engine: SignalEngine | None = None
news_manager = NewsManager()
notifier = TelegramNotifier(settings.telegram)
ai_writer = AINewsWriter(settings.openai)

# Background Live Bot Runner Loop
bot_runner = None
runner_thread = None
runner_stop_event = threading.Event()

# ──────────────────────────────────────────────
# MT5 Thread Safety Lock
# ──────────────────────────────────────────────
_mt5_lock = threading.Lock()


def mt5_safe_get_price(symbol: str) -> dict | None:
    """Thread-safe wrapper để lấy giá từ MT5 (tránh race condition giữa bot runner và API)."""
    with _mt5_lock:
        try:
            mgr = MarketDataManager(symbol)
            return mgr.get_latest_price()
        except Exception as e:
            log.debug("Lỗi đọc giá MT5 (thread-safe): %s", e)
            return None


def mt5_safe_get_candles(symbol: str, timeframe, num_bars: int = 100):
    """Thread-safe wrapper để lấy nến từ MT5."""
    with _mt5_lock:
        try:
            mgr = MarketDataManager(symbol)
            return mgr.get_candles(timeframe, num_bars=num_bars)
        except Exception as e:
            log.debug("Lỗi đọc nến MT5 (thread-safe): %s", e)
            return None


# ──────────────────────────────────────────────
# API Key Authentication cho Admin Endpoints
# ──────────────────────────────────────────────
_ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "").strip()
if not _ADMIN_API_KEY:
    # Tự sinh key ngẫu nhiên nếu chưa cấu hình, in ra console để admin ghi nhận
    _ADMIN_API_KEY = secrets.token_urlsafe(32)
    log.warning(
        "⚠️ ADMIN_API_KEY chưa được cấu hình trong .env. "
        "Đã sinh key tạm thời (sẽ thay đổi mỗi lần khởi động): %s",
        _ADMIN_API_KEY,
    )


def verify_admin_key(
    request: Request,
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> str:
    """Dependency xác thực API Key cho các admin endpoints."""
    configured_key = os.getenv("ADMIN_API_KEY", "").strip()
    if configured_key:
        if not x_api_key or not hmac.compare_digest(x_api_key, configured_key):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized — Thiếu hoặc sai API Key. Vui lòng gửi header X-API-Key hợp lệ.",
            )
        return x_api_key

    # Nếu ADMIN_API_KEY chưa cấu hình trong .env:
    # Cho phép các request nội bộ từ Desktop Client hoặc localhost dev server
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost", "testclient"):
        return "localhost-admin"

    # Nếu truy cập từ bên ngoài mạng nội bộ, yêu cầu key tạm thời
    if x_api_key and hmac.compare_digest(x_api_key, _ADMIN_API_KEY):
        return x_api_key

    raise HTTPException(
        status_code=401,
        detail="Unauthorized — Vui lòng cấu hình ADMIN_API_KEY trong .env và gửi kèm header X-API-Key.",
    )


def bot_runner_worker():
    """Vòng lặp chạy ngầm tự động phân tích và bám sát giá của bot."""
    global bot_runner, runner_stop_event
    log.info("Khởi chạy LiveBotRunner background worker...")
    time.sleep(2.0)
    while not runner_stop_event.is_set():
        try:
            if bot_runner:
                bot_runner.run_once()
        except Exception as e:
            log.debug("Lỗi trong chu kỳ bot runner worker: %s", e)
        runner_stop_event.wait(5.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo các kết nối khi khởi động server."""
    global connector, db_manager, signal_repo, market_repo, signal_engine
    log.info("Khởi động VietKey Gold AI API Server...")

    # 1. Kết nối Database SQLite & chạy migration
    try:
        from app.database.migrations import run_migrations
        db_manager = DatabaseManager(config=settings.database)
        run_migrations(db_manager)
        signal_repo = SignalRepository(db_manager)
        market_repo = MarketDataRepository(db_manager)
        log.info("✓ SQLite Database đã kết nối & chạy migrations: %s", db_manager.db_path)
    except Exception as e:
        log.error("Lỗi kết nối SQLite: %s", e)

    # 2. Kết nối MT5 Terminal
    try:
        connector = MT5Connector(settings.mt5)
        res = connector.connect()
        if res.success:
            log.info("✓ MT5 Terminal đã kết nối thành công.")
        else:
            log.warning("⚠️ Không thể kết nối MT5 Terminal: %s", res.message)
    except Exception as e:
        log.error("Lỗi khởi tạo MT5: %s", e)

    # 3. Khởi tạo Signal Engine
    signal_engine = SignalEngine(
        strategy_version="v1.0-M5",
        symbol=settings.mt5.symbol,
        default_timeframe="M5",
    )

    # 4. Khởi tạo và kích hoạt Live Bot Runner tự động ngầm
    global bot_runner, runner_thread, runner_stop_event
    try:
        from app.bot.runner import LiveBotRunner
        bot_runner = LiveBotRunner(
            settings=settings,
            db_manager=db_manager,
            connector=connector,
            notifier=notifier,
            news_manager=news_manager,
        )
        bot_runner.start()
        runner_stop_event.clear()
        runner_thread = threading.Thread(
            target=bot_runner_worker,
            daemon=True,
            name="LiveBotRunnerWorker",
        )
        runner_thread.start()
        log.info("✓ LiveBotRunner background worker đã kích hoạt tự động!")
    except Exception as e:
        log.error("Không thể khởi động LiveBotRunner: %s", e)

    yield

    # Cleanup khi shutdown
    log.info("Đang tắt VietKey Gold AI API Server...")
    runner_stop_event.set()
    if bot_runner:
        try:
            bot_runner.stop()
        except Exception:
            pass
    if connector and connector.is_connected:
        connector.disconnect()


app = FastAPI(
    title="VietKey Gold AI — API Server",
    version="0.8.0",
    description="Backend API kết nối trực tiếp MT5 và SQLite cho Trading Terminal Dashboard",
    lifespan=lifespan,
)

# CORS: Chỉ cho phép Vite dev server và localhost (không mở wildcard *)
_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


@app.get("/health")
@app.get("/api")
def read_root():
    """Kiểm tra trạng thái server toàn diện."""
    is_mt5_conn = connector.is_connected if connector else False
    active_count = 0
    if signal_repo:
        try:
            active_count = len(signal_repo.get_active_signals(settings.mt5.symbol))
        except Exception:
            pass

    return {
        "app": "VietKey Gold AI",
        "version": "0.8.0",
        "status": "ONLINE",
        "mt5_connected": is_mt5_conn,
        "database_connected": db_manager is not None,
        "active_signals": active_count,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }


@app.get("/api/v1/dashboard/overview")
def get_dashboard_overview():
    """
    Lấy thông tin tổng quan trạng thái (Status Cards):
    - Trạng thái kết nối MT5 thực tế.
    - Giá vàng XAUUSD, Bid, Ask, Spread trực tiếp từ broker.
    - Số lượng tín hiệu active và trong ngày từ SQLite.
    - Mức sử dụng CPU, RAM thực tế của hệ thống.
    """
    symbol = settings.mt5.symbol
    global connector
    if connector is None:
        connector = MT5Connector(settings.mt5)
    is_mt5_connected = connector.is_connected

    current_price = 0.0
    spread = 0.0
    bid = 0.0
    ask = 0.0

    if is_mt5_connected:
        try:
            mgr = MarketDataManager(symbol)
            price_info = mgr.get_latest_price()
            if price_info:
                current_price = price_info.get("bid", 0.0)
                bid = price_info.get("bid", 0.0)
                ask = price_info.get("ask", 0.0)
                spread = price_info.get("spread", 0.0)
        except Exception as e:
            log.warning("Lỗi đọc giá MT5: %s", e)

    # Truy vấn số lượng tín hiệu từ Database
    active_count = 0
    total_today = 0
    if signal_repo:
        try:
            active_signals = signal_repo.get_active_signals(symbol)
            active_count = len(active_signals)
            recent = signal_repo.get_recent_signals(limit=50, symbol=symbol)
            total_today = len(recent)
        except Exception as e:
            log.warning("Lỗi đọc signals từ DB: %s", e)

    # Đo lường tài nguyên thực tế
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    ram_pct = psutil.virtual_memory().percent
    cpu_pct = psutil.cpu_percent(interval=None)

    # Lấy thông tin Ví Đầu Tư Ảo (Paper Wallet 0.01 lot) kèm đồng bộ lệnh active
    paper_wallet_info = None
    if db_manager:
        try:
            p_engine = _get_paper_engine()
            p_engine.sync_active_signals()
            if current_price > 0:
                half_sp = (spread or 0.3) / 2.0
                p_engine.update_positions(
                    current_bid=round(current_price - half_sp, 2),
                    current_ask=round(current_price + half_sp, 2),
                )
            w = p_engine.get_wallet()
            open_pos = p_engine.get_open_positions()
            paper_wallet_info = {
                "balance": w.balance,
                "equity": w.equity,
                "floatingPnl": w.floating_pnl,
                "netProfitUsd": w.net_profit_usd,
                "roiPercent": w.roi_percent,
                "openCount": len(open_pos),
                "isAutoTrading": w.is_auto_trading,
                "defaultLot": w.default_lot,
                "usedMargin": w.used_margin,
                "freeMargin": w.free_margin,
                "marginLevel": w.margin_level,
                "winRate": w.win_rate,
                "totalTrades": w.total_trades,
                "winningTrades": w.winning_trades,
                "losingTrades": w.losing_trades,
                "openPositions": open_pos,
            }
        except Exception as e:
            log.debug("Lỗi đọc thông tin ví ảo cho overview: %s", e)

    return {
        "botStatus": "RUNNING" if is_mt5_connected else "STANDBY",
        "mt5Status": "CONNECTED" if is_mt5_connected else "DISCONNECTED",
        "symbol": symbol,
        "currentPrice": round(current_price, 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "spread": round(spread, 2),
        "activeSignals": active_count,
        "totalSignalsToday": total_today,
        "ramUsageMB": round(ram_mb, 1),
        "ramUsagePct": round(ram_pct, 1),
        "cpuUsagePct": round(cpu_pct, 1),
        "serverTime": datetime.now(timezone.utc).isoformat(),
        "paperWallet": paper_wallet_info,
    }


@app.get("/api/v1/market/overview")
def get_market_overview():
    """
    Lấy dữ liệu phân tích thị trường thực tế:
    - Nến đa khung thời gian: H4, H1, M15, M5.
    - Cấu trúc xu hướng thực tế của từng khung thời gian.
    - Mức biến động ATR thực tế.
    """
    symbol = settings.mt5.symbol
    global connector
    if connector is None:
        connector = MT5Connector(settings.mt5)
    is_mt5_connected = connector.is_connected

    if not is_mt5_connected:
        return {
            "symbol": symbol,
            "price": 0.0,
            "bid": 0.0,
            "ask": 0.0,
            "change24h": 0.0,
            "change24hPct": 0.0,
            "high24h": 0.0,
            "low24h": 0.0,
            "h4Trend": "NEUTRAL",
            "h1Trend": "NEUTRAL",
            "m15Trend": "NEUTRAL",
            "m5Confirmation": "NEUTRAL",
            "volatility": "Chờ kết nối MT5",
            "spread": 0.0,
            "structure": "Chưa có dữ liệu",
            "lastUpdate": datetime.now(timezone.utc).isoformat(),
        }

    mgr = MarketDataManager(symbol)
    price_info = mgr.get_latest_price() or {}
    bid = price_info.get("bid", 0.0)
    ask = price_info.get("ask", 0.0)
    spread = price_info.get("spread", 0.0)

    # Đọc nến các khung thời gian
    df_h4 = mgr.get_candles(Timeframe.H4, num_bars=50)
    df_h1 = mgr.get_candles(Timeframe.H1, num_bars=100)
    df_m15 = mgr.get_candles(Timeframe.M15, num_bars=100)
    df_m5 = mgr.get_candles(Timeframe.M5, num_bars=100)

    # Phân tích cấu trúc thực tế
    h4_trend = "NEUTRAL"
    h1_trend = "NEUTRAL"
    m15_trend = "NEUTRAL"
    m5_trend = "NEUTRAL"
    structure_desc = "Đang tổng hợp cấu trúc"
    volatility_desc = "Bình thường"

    if df_h4 is not None and len(df_h4) >= 10:
        struct_h4 = analyze_market_structure(df_h4)
        h4_trend = struct_h4.trend.value

    if df_h1 is not None and len(df_h1) >= 10:
        struct_h1 = analyze_market_structure(df_h1)
        h1_trend = struct_h1.trend.value

    if df_m15 is not None and len(df_m15) >= 10:
        struct_m15 = analyze_market_structure(df_m15)
        m15_trend = struct_m15.trend.value

    if df_m5 is not None and len(df_m5) >= 10:
        struct_m5 = analyze_market_structure(df_m5)
        m5_trend = struct_m5.trend.value
        structure_desc = (
            f"M5 {struct_m5.trend.value} | {len(struct_m5.swings)} Swings, "
            f"{len(struct_m5.sr_zones)} Vùng Hỗ trợ/Kháng cự"
        )
        try:
            vol = analyze_volatility(df_m5)
            volatility_desc = f"{vol.level.value} (ATR={vol.atr:.2f} giá)"
        except Exception:
            pass

    # Tính High/Low 24h từ nến H1 (24 nến gần nhất)
    high_24h = bid
    low_24h = bid
    change_24h = 0.0
    change_24h_pct = 0.0

    if df_h1 is not None and len(df_h1) >= 24:
        last_24 = df_h1.iloc[-24:]
        high_24h = float(last_24["high"].max())
        low_24h = float(last_24["low"].min())
        first_open = float(last_24["open"].iloc[0])
        current_close = float(last_24["close"].iloc[-1])
        change_24h = current_close - first_open
        change_24h_pct = (change_24h / first_open) * 100 if first_open else 0.0

    return {
        "symbol": symbol,
        "price": round(bid, 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "change24h": round(change_24h, 2),
        "change24hPct": round(change_24h_pct, 2),
        "high24h": round(high_24h, 2),
        "low24h": round(low_24h, 2),
        "h4Trend": h4_trend,
        "h1Trend": h1_trend,
        "m15Trend": m15_trend,
        "m5Confirmation": m5_trend,
        "volatility": volatility_desc,
        "spread": round(spread, 2),
        "structure": structure_desc,
        "lastUpdate": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/signals")
def get_signals(limit: int = 20):
    """Lấy danh sách các tín hiệu thực tế từ SQLite Database."""
    symbol = settings.mt5.symbol
    signals: list[dict] = []

    if signal_repo:
        try:
            rows = signal_repo.get_recent_signals(limit=limit, symbol=symbol)
            for r in rows:
                reasons = r.get("reasons")
                if isinstance(reasons, str):
                    try:
                        reasons = json.loads(reasons)
                    except Exception:
                        pass
                if isinstance(reasons, list):
                    reason_text = " • ".join(reasons)
                else:
                    reason_text = str(reasons or "")

                entry_low = float(r.get("entry_zone_low") or r.get("entry_price") or 0.0)
                entry_high = float(r.get("entry_zone_high") or r.get("entry_price") or 0.0)

                pnl_pts = r.get("pnl_points")
                if pnl_pts is not None:
                    pnl_pts = round(float(pnl_pts), 2)
                    pnl_pips = round(pnl_pts * 10.0, 1)
                else:
                    if r.get("status") == "TP_REACHED":
                        entry_p = float(r.get("entry_price") or 0.0)
                        tp1 = float(r.get("take_profit_1") or 0.0)
                        pnl_pts = round(abs(tp1 - entry_p), 2) if entry_p > 0 and tp1 > 0 else 10.0
                        pnl_pips = round(pnl_pts * 10.0, 1)
                    elif r.get("status") == "SL_REACHED":
                        entry_p = float(r.get("entry_price") or 0.0)
                        sl = float(r.get("stop_loss") or 0.0)
                        pnl_pts = -round(abs(entry_p - sl), 2) if entry_p > 0 and sl > 0 else -10.0
                        pnl_pips = round(pnl_pts * 10.0, 1)
                    else:
                        pnl_pts = None
                        pnl_pips = None

                is_win = (pnl_pts is not None and pnl_pts > 0) or r.get("status") == "TP_REACHED"
                is_loss = (pnl_pts is not None and pnl_pts < 0) or r.get("status") == "SL_REACHED"
                is_be = (pnl_pts is not None and pnl_pts == 0)

                setup_type = r.get("setup_type") or ""
                is_predictive = (setup_type == "PREDICTIVE_LIMIT")

                signals.append({
                    "id": r.get("signal_id"),
                    "symbol": r.get("symbol", symbol),
                    "direction": r.get("direction", "WAIT"),
                    "timeframe": r.get("timeframe", "M5"),
                    "time": r.get("created_at", ""),
                    "entryZone": [round(entry_low, 2), round(entry_high, 2)],
                    "plannedEntry": round(float(r.get("entry_price") or 0.0), 2),
                    "stopLoss": round(float(r.get("stop_loss") or 0.0), 2),
                    "takeProfit1": round(float(r.get("take_profit_1") or 0.0), 2),
                    "takeProfit2": round(float(r.get("take_profit_2") or 0.0), 2),
                    "score": round(float(r.get("score") or 0.0), 1),
                    "status": r.get("status", "PENDING"),
                    "strategyVersion": r.get("strategy_version", "v1.0-M5"),
                    "setupType": setup_type,
                    "isPredictive": is_predictive,
                    "isDca": bool(r.get("is_dca") or (setup_type and setup_type.startswith("DCA_"))),
                    "parentSignalId": r.get("parent_signal_id"),
                    "dcaBreakevenPrice": float(r.get("dca_breakeven_price")) if r.get("dca_breakeven_price") is not None else None,
                    "reason": reason_text,
                    "invalidation": r.get("invalidation", ""),
                    "riskReward": round(float(r.get("risk_reward_ratio") or 0.0), 2),
                    "pnlPoints": pnl_pts,
                    "pnlPips": pnl_pips,
                    "isWin": is_win,
                    "isLoss": is_loss,
                    "isBreakeven": is_be,
                    "exitPrice": round(float(r.get("exit_price")), 2) if r.get("exit_price") is not None else None,
                    "durationSeconds": r.get("duration_seconds"),
                })
        except Exception as e:
            log.warning("Lỗi truy vấn signals: %s", e)

    return signals


@app.get("/api/v1/signals/latest-outcome")
def get_latest_signal_outcome():
    """Lấy thông tin lệnh vừa đóng gần nhất và thống kê pips."""
    if not signal_repo:
        raise HTTPException(status_code=500, detail="Database repository chưa sẵn sàng")

    outcome = signal_repo.get_latest_outcome()
    if not outcome:
        return {"hasData": False, "message": "Chưa có lệnh nào hoàn tất."}

    pnl_pts = float(outcome.get("pnl_points") or 0.0)
    pnl_pips = round(pnl_pts * 10.0, 1)

    return {
        "hasData": True,
        "signalId": outcome.get("signal_id"),
        "symbol": outcome.get("symbol", "XAUUSD"),
        "direction": outcome.get("direction", "BUY"),
        "finalStatus": outcome.get("final_status"),
        "entryPrice": outcome.get("entry_price"),
        "exitPrice": outcome.get("exit_price"),
        "pnlPoints": pnl_pts,
        "pnlPips": pnl_pips,
        "isWin": pnl_pts > 0,
        "isLoss": pnl_pts < 0,
        "isBreakeven": pnl_pts == 0,
        "durationSeconds": outcome.get("duration_seconds"),
        "closedAt": outcome.get("created_at") or outcome.get("exit_time"),
    }


@app.get("/api/v1/signals/{signal_id}")
def get_signal_detail(signal_id: str):
    """Lấy chi tiết một tín hiệu theo ID từ SQLite Database."""
    if not signal_repo:
        raise HTTPException(status_code=500, detail="Database repository chưa sẵn sàng")

    signal = signal_repo.get_signal(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tín hiệu {signal_id}")

    return signal


@app.get("/api/v1/system/metrics")
def get_system_metrics():
    """Lấy thông số giám sát hệ thống và tài nguyên máy tính thực tế."""
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    ram_total_mb = psutil.virtual_memory().total / (1024 * 1024)
    ram_pct = psutil.virtual_memory().percent
    cpu_pct = psutil.cpu_percent(interval=None)

    # Cập nhật buffer lịch sử (tối đa 20 điểm)
    global cpu_history, ram_history
    cpu_history.append(round(cpu_pct, 1))
    ram_history.append(round(ram_mb, 1))
    if len(cpu_history) > 20:
        cpu_history = cpu_history[-20:]
    if len(ram_history) > 20:
        ram_history = ram_history[-20:]

    uptime_sec = int(time.time() - START_TIME)
    is_mt5_connected = connector is not None and connector.is_connected

    # Đo latency với MT5
    latency_ms = 0
    if is_mt5_connected:
        t0 = time.perf_counter()
        connector.get_terminal_info()
        latency_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "cpuPct": round(cpu_pct, 1),
        "ramPct": round(ram_pct, 1),
        "ramUsedMB": round(ram_mb, 1),
        "ramTotalMB": round(ram_total_mb, 0),
        "uptimeSeconds": uptime_sec,
        "dataLatencyMs": max(1, latency_ms),
        "lastMarketUpdate": "Thời gian thực" if is_mt5_connected else "Mất kết nối",
        "databaseStatus": "WAL_MODE" if db_manager else "DISCONNECTED",
        "telegramStatus": "CONFIGURED" if settings.telegram.bot_token else "NOT_CONFIGURED",
        "cpuHistory": cpu_history,
        "ramHistory": ram_history,
    }


@app.get("/api/v1/system/benchmark")
def get_system_benchmark():
    """Lấy báo cáo Benchmark tài nguyên, độ trễ và dung lượng lưu trữ (Phase 10)."""
    from app.system.resource_optimizer import ResourceProfiler
    from app.ml.registry import ModelRegistry
    from app.strategy.signal_engine import SignalEngine
    from app.market.timeframe_manager import Timeframe

    reg = ModelRegistry(db_manager) if db_manager else None
    eng = SignalEngine(strategy_version="v1.0-Bench")
    mgr = MarketDataManager(settings.mt5.symbol) if settings else None
    sample_df = mgr.get_cached(Timeframe.H1) if mgr else None

    return ResourceProfiler.get_system_benchmark(
        db_manager=db_manager,
        model_registry=reg,
        signal_engine=eng,
        sample_df=sample_df,
    )


def _parse_log_file(date_str: Optional[str] = None, max_lines: int = 1500) -> list[dict]:
    """Đọc và phân tích file log với khả năng gộp các dòng traceback."""
    from pathlib import Path
    import re

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_dir = Path("logs")
    log_file = log_dir / f"vietkey_{date_str}.log"
    if not log_file.exists():
        candidates = sorted(log_dir.glob("vietkey_*.log"), key=os.path.getmtime, reverse=True)
        if candidates:
            log_file = candidates[0]
        else:
            return []

    lines = []
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-max_lines:]
    except Exception as e:
        log.warning("Lỗi đọc file log %s: %s", log_file, e)
        return []

    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[,\.]\d+)?) \| ([A-Z ]{4,8}) \| ([^|]+) \| (.*)$")
    parsed = []
    current_entry = None
    entry_id = 0

    for line in lines:
        line_clean = line.rstrip("\r\n")
        m = pattern.match(line_clean)
        if m:
            if current_entry:
                parsed.append(current_entry)
            entry_id += 1
            lvl = m.group(2).strip()
            current_entry = {
                "id": entry_id,
                "timestamp": m.group(1),
                "level": lvl,
                "module": m.group(3).strip(),
                "message": m.group(4).strip(),
                "isError": lvl in ("ERROR", "CRITICAL"),
                "isWarning": lvl == "WARNING",
            }
        elif current_entry:
            current_entry["message"] += "\n" + line_clean

    if current_entry:
        parsed.append(current_entry)

    # Đảo ngược thứ tự để log mới nhất nằm ở trên cùng
    parsed.reverse()
    return parsed


@app.get("/api/v1/system/diagnostics")
def get_system_diagnostics():
    """
    Chẩn đoán toàn diện sức khỏe hệ thống, trạng thái từng phân hệ,
    thống kê lỗi 24h và kiểm tra tính toàn vẹn (Self-Diagnostics & Error Finder).
    """
    from pathlib import Path
    import sqlite3

    # 1. Trạng thái MetaTrader 5
    is_mt5_conn = connector is not None and connector.is_connected
    mt5_latency = 0
    account_info = {}
    price_info = {}

    if is_mt5_conn:
        try:
            t0 = time.perf_counter()
            terminal_info = connector.get_terminal_info()
            mt5_latency = max(1, int((time.perf_counter() - t0) * 1000))
            raw_acc = connector.get_account_info()
            if raw_acc:
                account_info = {
                    "login": raw_acc.get("login", 0),
                    "server": raw_acc.get("server", ""),
                    "leverage": raw_acc.get("leverage", 500),
                    "tradeAllowed": raw_acc.get("trade_allowed", True),
                    "balance": raw_acc.get("balance", 0.0),
                    "equity": raw_acc.get("equity", 0.0),
                }
            mgr = MarketDataManager(settings.mt5.symbol)
            price_info = mgr.get_latest_price() or {}
        except Exception as e:
            log.debug("Lỗi đọc diagnostics MT5: %s", e)

    # 2. Cơ sở dữ liệu SQLite
    db_path = Path("data/vietkey_gold.db")
    db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0.0
    db_integrity = "UNKNOWN"
    db_journal = "UNKNOWN"
    signals_count = 0
    trades_count = 0

    dm = db_manager
    if dm is None:
        try:
            dm = DatabaseManager(db_path=str(db_path))
        except Exception:
            pass

    if dm:
        try:
            with dm.session() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check;")
                row = cur.fetchone()
                db_integrity = row[0] if row else "ok"
                cur.execute("PRAGMA journal_mode;")
                j_row = cur.fetchone()
                db_journal = j_row[0].upper() if j_row else "WAL"
                cur.execute("SELECT COUNT(*) FROM signals;")
                signals_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM paper_trades_history;")
                trades_count = cur.fetchone()[0]
        except Exception as e:
            db_integrity = f"ERROR: {e}"

    # 3. Live Bot Runner & Tracking
    runner_status = "RUNNING" if bot_runner and getattr(bot_runner, "is_running", False) else "IDLE"
    active_tracker_signals = 0
    last_m5_candle = None
    if bot_runner:
        try:
            active_tracker_signals = len(bot_runner.tracker.active_signals) if getattr(bot_runner, "tracker", None) else 0
            last_m5_candle = str(getattr(bot_runner, "last_processed_m5_time", ""))
        except Exception:
            pass

    # 4. Tài nguyên máy tính (Process & System)
    process = psutil.Process(os.getpid())
    proc_ram_mb = round(process.memory_info().rss / (1024 * 1024), 1)
    proc_cpu_pct = round(process.cpu_percent(interval=None), 1)
    sys_ram_pct = round(psutil.virtual_memory().percent, 1)
    disk_free_gb = round(psutil.disk_usage(".").free / (1024**3), 1)
    uptime_sec = int(time.time() - START_TIME)

    # 5. Phân tích nhật ký lỗi trong ngày (Error Diagnostics)
    all_logs = _parse_log_file(max_lines=1000)
    error_logs = [e for e in all_logs if e.get("isError")]
    warning_logs = [e for e in all_logs if e.get("isWarning")]
    total_events = len(all_logs)
    stability_score = round(max(0.0, (1.0 - (len(error_logs) / max(1, total_events))) * 100.0), 1)

    recent_errors = error_logs[:5]

    return {
        "status": "HEALTHY" if len(error_logs) == 0 else "WARNING",
        "stabilityScore": stability_score,
        "uptimeSeconds": uptime_sec,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mt5": {
            "status": "CONNECTED" if is_mt5_conn else "DISCONNECTED",
            "latencyMs": mt5_latency,
            "symbol": settings.mt5.symbol,
            "bid": price_info.get("bid", 0.0),
            "ask": price_info.get("ask", 0.0),
            "spread": price_info.get("spread", 0.0),
            "account": account_info,
        },
        "database": {
            "status": "HEALTHY" if "ok" in db_integrity.lower() else "ERROR",
            "journalMode": db_journal,
            "integrity": db_integrity,
            "fileSizeMB": db_size_mb,
            "signalsCount": signals_count,
            "tradesCount": trades_count,
            "path": str(db_path),
        },
        "botRunner": {
            "status": runner_status,
            "activeTrackingSignals": active_tracker_signals,
            "lastM5ProcessedTime": last_m5_candle,
            "antiHedgingMode": "STRATEGIC_ZONE_HEDGE (Khóa khoảng cách >= 5 giá & có lời)",
            "mlFilterEnabled": getattr(settings.optimization, "enable_ml_filter", True),
        },
        "smartExitAndCopilot": {
            "status": "ACTIVE",
            "copilotCompanion": "ACTIVE (Dặn SL hòa, trấn an sóng rung lắc, khuyên cắt sớm)",
            "beTriggerR": getattr(settings.smart_exit, "be_trigger_r", 1.0),
            "trailingAtrMult": getattr(settings.smart_exit, "trailing_atr_multiplier", 1.5),
        },
        "resources": {
            "pid": os.getpid(),
            "cpuPct": proc_cpu_pct,
            "ramMB": proc_ram_mb,
            "systemRamPct": sys_ram_pct,
            "diskFreeGB": disk_free_gb,
        },
        "errorDiagnostics": {
            "errorCount24h": len(error_logs),
            "warningCount24h": len(warning_logs),
            "totalLogsParsed": total_events,
            "recentErrors": recent_errors,
        },
    }


@app.get("/api/v1/system/logs")
def get_system_logs(
    level: str = "ALL",
    limit: int = 100,
    search: Optional[str] = None,
    date: Optional[str] = None,
):
    """
    Truy vấn nhật ký hệ thống thời gian thực với bộ lọc linh hoạt:
    - level: ALL, ERROR, WARNING, INFO
    - limit: số dòng tối đa (mặc định 100, tối đa 500)
    - search: từ khóa tìm kiếm trong thông điệp
    - date: ngày theo dõi (YYYY-MM-DD, mặc định hôm nay)
    """
    limit = max(10, min(500, limit))
    parsed_logs = _parse_log_file(date_str=date, max_lines=1500)

    # Thống kê nhanh
    err_count = sum(1 for e in parsed_logs if e.get("isError"))
    warn_count = sum(1 for e in parsed_logs if e.get("isWarning"))
    info_count = sum(1 for e in parsed_logs if not e.get("isError") and not e.get("isWarning"))

    # Lọc theo level
    lvl_upper = level.upper().strip()
    if lvl_upper == "ERROR":
        filtered = [e for e in parsed_logs if e.get("isError")]
    elif lvl_upper == "WARNING":
        filtered = [e for e in parsed_logs if e.get("isWarning") or e.get("isError")]
    elif lvl_upper == "INFO":
        filtered = [e for e in parsed_logs if not e.get("isError") and not e.get("isWarning")]
    else:
        filtered = parsed_logs

    # Lọc theo search
    if search and search.strip():
        kw = search.strip().lower()
        filtered = [
            e for e in filtered
            if kw in e.get("message", "").lower()
            or kw in e.get("module", "").lower()
            or kw in e.get("timestamp", "").lower()
            or kw in e.get("level", "").lower()
        ]

    return {
        "total": len(parsed_logs),
        "errorCount": err_count,
        "warningCount": warn_count,
        "infoCount": info_count,
        "filteredCount": len(filtered),
        "logs": filtered[:limit],
    }


@app.post("/api/v1/system/run-self-test")
def run_system_self_test():
    """Chạy tự kiểm tra toàn diện và trả về kết quả từng bài test tức thì."""
    results = []

    # 1. Test SQLite Integrity
    try:
        from pathlib import Path
        db_path = Path("data/vietkey_gold.db")
        dm = db_manager or DatabaseManager(db_path=str(db_path))
        with dm.session() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            r = cur.fetchone()[0]
            results.append({
                "test": "SQLite Database Integrity",
                "ok": "ok" in r.lower(),
                "detail": f"PRAGMA check: {r}",
            })
    except Exception as e:
        results.append({
            "test": "SQLite Database Integrity",
            "ok": False,
            "detail": str(e),
        })

    # 2. Test MT5 Terminal Ping
    try:
        is_conn = connector is not None and connector.is_connected
        if is_conn:
            t0 = time.perf_counter()
            t_info = connector.get_terminal_info()
            dt = int((time.perf_counter() - t0) * 1000)
            results.append({
                "test": "MetaTrader 5 Bridge IPC",
                "ok": True,
                "detail": f"Kết nối ổn định, Ping: {dt}ms | Build: {t_info.get('build', 'N/A') if t_info else 'OK'}",
            })
        else:
            results.append({
                "test": "MetaTrader 5 Bridge IPC",
                "ok": False,
                "detail": "Không thể kết nối tới MT5 Terminal",
            })
    except Exception as e:
        results.append({
            "test": "MetaTrader 5 Bridge IPC",
            "ok": False,
            "detail": str(e),
        })

    # 3. Test Paper Wallet Engine
    try:
        engine = _get_paper_engine()
        w = engine.get_wallet()
        results.append({
            "test": "Paper Trading Wallet Engine",
            "ok": True,
            "detail": f"Ví ảo sẵn sàng (Vốn: ${w.balance:.2f}, Ký quỹ: ${w.used_margin:.2f})",
        })
    except Exception as e:
        results.append({
            "test": "Paper Trading Wallet Engine",
            "ok": False,
            "detail": str(e),
        })

    # 4. Test Disk Space
    try:
        free_gb = round(psutil.disk_usage(".").free / (1024**3), 1)
        results.append({
            "test": "Disk Storage Available",
            "ok": free_gb >= 1.0,
            "detail": f"Dung lượng trống: {free_gb} GB",
        })
    except Exception as e:
        results.append({
            "test": "Disk Storage Available",
            "ok": False,
            "detail": str(e),
        })

    all_passed = all(r["ok"] for r in results)
    return {
        "ok": all_passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tests": results,
    }


@app.get("/api/v1/performance")
def get_performance_stats():
    """Lấy thống kê hiệu suất thực tế từ các lệnh đã có kết quả trong SQLite."""
    if not signal_repo:
        return {"hasRealData": False, "message": "No performance data available."}

    try:
        with db_manager.session() as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl_points > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_points < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(pnl_r) as avg_r,
                    SUM(pnl_points) as net_points,
                    SUM(CASE WHEN pnl_points > 0 THEN pnl_points ELSE 0 END) as total_profit,
                    SUM(CASE WHEN pnl_points < 0 THEN ABS(pnl_points) ELSE 0 END) as total_loss
                FROM signal_outcomes
            """)
            row = cursor.fetchone()
            if not row or row["total"] == 0:
                return {
                    "hasRealData": False,
                    "totalSignals": 0,
                    "winRate": 0.0,
                    "lossRate": 0.0,
                    "unresolvedSignals": 0,
                    "averageR": 0.0,
                    "profitFactor": 0.0,
                    "maxDrawdownPct": 0.0,
                    "maxDrawdownCash": 0.0,
                    "winsCount": 0,
                    "lossesCount": 0,
                    "netPoints": 0.0,
                    "netPips": 0.0,
                    "byStrategy": [],
                    "message": "No performance data available.",
                }

            total = row["total"]
            wins = row["wins"] or 0
            losses = row["losses"] or 0
            win_rate = (wins / total * 100) if total > 0 else 0.0
            loss_rate = (losses / total * 100) if total > 0 else 0.0
            avg_r = float(row["avg_r"] or 0.0)
            total_profit = float(row["total_profit"] or 0.0)
            total_loss = float(row["total_loss"] or 0.0)
            net_points = float(row["net_points"] or 0.0)
            net_pips = round(net_points * 10.0, 1)

            # Công thức Profit Factor chuẩn tài chính
            if total_loss > 0:
                profit_factor = round(total_profit / total_loss, 2)
            else:
                profit_factor = 2.0 if wins > 0 else 0.0

            return {
                "hasRealData": True,
                "totalSignals": total,
                "winRate": round(win_rate, 1),
                "lossRate": round(loss_rate, 1),
                "unresolvedSignals": 0,
                "averageR": round(avg_r, 2),
                "profitFactor": profit_factor,
                "maxDrawdownPct": 0.0,
                "maxDrawdownCash": 0.0,
                "winsCount": wins,
                "lossesCount": losses,
                "netPoints": round(net_points, 2),
                "netPips": net_pips,
                "byStrategy": [
                    {"name": "v1.0-M5", "total": total, "winRate": round(win_rate, 1), "pf": profit_factor}
                ],
            }
    except Exception as e:
        log.warning("Lỗi thống kê performance: %s", e)
        return {"hasRealData": False, "message": "No performance data available."}


@app.get("/api/v1/performance/setups")
def get_setups_performance():
    """Lấy thống kê hiệu suất thực tế phân rã theo từng loại Setup giao dịch (Phase 5)."""
    if not signal_repo:
        return {"hasData": False, "setups": {}}
    try:
        setups = signal_repo.get_setup_performance_summary()
        return {
            "hasData": len(setups) > 0,
            "setups": setups,
        }
    except Exception as e:
        log.warning("Lỗi thống kê setup performance: %s", e)
        return {"hasData": False, "setups": {}, "error": str(e)}


@app.get("/api/v1/setups/specifications")
def get_setup_specifications():
    """Lấy đặc tả kỹ thuật và quy tắc thích ứng chuẩn hóa của 7 setup giao dịch (Phase 9)."""
    from app.strategy.setup_adapter import SetupAdapterEngine
    adapter = SetupAdapterEngine()
    specs = adapter.get_all_specifications()
    return {
        "total_setups": len(specs),
        "specifications": specs,
    }


@app.get("/api/v1/news/calendar")
def get_economic_calendar(hours_ahead: int = 48):
    """
    Lấy danh sách sự kiện Lịch kinh tế và cảnh báo Vùng Cấm Giao Dịch Tin Đỏ (News Blackout):
    - isBlackout: Có đang trong vùng nguy hiểm trước/sau tin đỏ USD không.
    - blackoutEvent: Sự kiện tin đỏ đang gây bão giá (nếu có).
    - nextHighImpact: Tin đỏ USD tiếp theo và thời gian đếm ngược.
    - events: Danh sách các tin tức tài chính sắp tới.
    """
    try:
        in_blackout, blackout_ev = news_manager.is_in_blackout_window(buffer_before_min=30, buffer_after_min=20)
        next_ev_tuple = news_manager.get_next_high_impact_event()
        upcoming = news_manager.get_upcoming_events(hours_ahead=hours_ahead)

        next_event_dict = None
        mins_until = None
        if next_ev_tuple:
            next_ev, mins_until = next_ev_tuple
            next_event_dict = next_ev.to_dict()

        return {
            "isBlackout": in_blackout,
            "blackoutEvent": blackout_ev.to_dict() if blackout_ev else None,
            "nextHighImpactEvent": next_event_dict,
            "minutesUntilNext": mins_until,
            "eventsCount": len(upcoming),
            "events": [ev.to_dict() for ev in upcoming],
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.warning("Lỗi đọc lịch kinh tế: %s", e)
        return {
            "isBlackout": False,
            "blackoutEvent": None,
            "nextHighImpactEvent": None,
            "minutesUntilNext": None,
            "eventsCount": 0,
            "events": [],
            "error": str(e),
        }


# ============================================================================
# Admin Action & Telegram Management Endpoints
# ============================================================================

class ResendSignalRequest(BaseModel):
    signal_id: str


class BroadcastNewsRequest(BaseModel):
    title: str
    country: str = "USD"
    impact: str = "HIGH"
    forecast: str = ""
    previous: str = ""
    bias_direction: str = "WAIT"
    reasoning: str = ""
    custom_note: Optional[str] = None


class BroadcastCustomRequest(BaseModel):
    message: str


@app.post("/api/v1/admin/resend-signal")
def admin_resend_signal(req: ResendSignalRequest, _key: str = Depends(verify_admin_key)):
    """Admin bắn lại một tín hiệu giao dịch lên Kênh Telegram (yêu cầu X-API-Key)."""
    if not signal_repo:
        raise HTTPException(status_code=500, detail="Database repository chưa sẵn sàng.")
    raw_sig = signal_repo.get_signal(req.signal_id)
    if not raw_sig:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tín hiệu #{req.signal_id}")

    try:
        signal_obj = TradingSignal.from_dict(raw_sig)
        success = notifier.resend_signal(signal_obj)
        if not success:
            raise HTTPException(status_code=502, detail="Gửi tín hiệu lên Telegram thất bại (kiểm tra token/kênh).")
        return {"ok": True, "message": f"Đã gửi lại tín hiệu #{req.signal_id} ({signal_obj.direction.value}) lên Telegram thành công!"}
    except Exception as e:
        log.error("Lỗi gửi lại tín hiệu Telegram: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/broadcast-news")
def admin_broadcast_news(req: BroadcastNewsRequest, _key: str = Depends(verify_admin_key)):
    """Admin bắn bản tin kinh tế & dự báo xu hướng Vàng lên Kênh Telegram (yêu cầu X-API-Key)."""
    try:
        success = notifier.send_news_broadcast(
            title=req.title,
            country=req.country,
            impact=req.impact,
            forecast=req.forecast,
            previous=req.previous,
            bias_direction=req.bias_direction,
            reasoning=req.reasoning,
            custom_note=req.custom_note,
        )
        if not success:
            raise HTTPException(status_code=502, detail="Gửi bản tin lên Telegram thất bại.")
        return {"ok": True, "message": f"Đã bắn bản tin [{req.title}] lên Kênh Telegram thành công!"}
    except Exception as e:
        log.error("Lỗi phát bản tin Telegram: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/admin/broadcast-custom")
def admin_broadcast_custom(req: BroadcastCustomRequest, _key: str = Depends(verify_admin_key)):
    """Admin gửi thông báo nhanh tùy chỉnh lên Kênh Telegram (yêu cầu X-API-Key)."""
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Nội dung thông báo không được để trống.")
    try:
        success = notifier.send_custom_broadcast(msg)
        if not success:
            raise HTTPException(status_code=502, detail="Gửi thông báo lên Telegram thất bại.")
        return {"ok": True, "message": "Đã phát thông báo lên Kênh Telegram thành công!"}
    except Exception as e:
        log.error("Lỗi gửi thông báo custom Telegram: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/telegram/status")
def get_telegram_status():
    """Lấy trạng thái cấu hình và số liệu gửi Telegram."""
    return {
        "enabled": notifier.is_enabled,
        "isConfigured": notifier.client.is_configured,
        "chatId": settings.telegram.chat_id,
        "totalSent": notifier.total_sent,
        "totalFailed": notifier.total_failed,
    }


@app.post("/api/v1/telegram/test")
def test_telegram_connection(_key: str = Depends(verify_admin_key)):
    """Gửi tin nhắn kiểm tra kết nối Telegram (yêu cầu X-API-Key)."""
    success = notifier.send_system_event(
        event_type="CONNECT",
        message="Kiểm tra kết nối Telegram Bot từ Dashboard Admin. Hệ thống hoạt động bình thường!"
    )
    if not success:
        raise HTTPException(status_code=502, detail="Không thể gửi tin nhắn thử nghiệm tới Telegram.")
    return {"ok": True, "message": "Gửi tin nhắn thử nghiệm Telegram thành công!"}


# ============================================================================
# AI Newsroom: Tự Động Biên Tập & Bắn Lịch Kinh Tế / Bài Báo Telegram
# ============================================================================

ALLOWED_ENV_KEYS = {"OPENAI_API_KEY", "OPENAI_MODEL", "NEWS_AUTO_POST_ENABLED"}


def _update_env_file(key_values: dict[str, str]) -> None:
    """Cập nhật an toàn các giá trị cấu hình trong file .env (chỉ cho phép các khóa an toàn)."""
    sanitized: dict[str, str] = {}
    for k, v in key_values.items():
        if k not in ALLOWED_ENV_KEYS:
            log.warning("Bỏ qua key không nằm trong whitelist an toàn: %s", k)
            continue
        v_str = str(v).strip().replace("\r", "").replace("\n", "")
        if len(v_str) > 200:
            v_str = v_str[:200]
        sanitized[k] = v_str

    if not sanitized:
        return

    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_set = set(sanitized.keys())
    new_lines: list[str] = []
    found_keys: set[str] = set()

    for line in lines:
        stripped = line.strip()
        matched_key = None
        for k in keys_set:
            if stripped.startswith(f"{k}="):
                matched_key = k
                break
        if matched_key:
            new_lines.append(f"{matched_key}={sanitized[matched_key]}\n")
            found_keys.add(matched_key)
        else:
            new_lines.append(line)

    for k in keys_set - found_keys:
        new_lines.append(f"{k}={sanitized[k]}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


class GenerateDigestRequest(BaseModel):
    date: Optional[str] = None
    use_ai: bool = True


class GenerateArticleRequest(BaseModel):
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    sjc_buy: float = 139.0
    sjc_sell: float = 142.0
    session_name: Optional[str] = None
    use_ai: bool = True


class PublishArticleRequest(BaseModel):
    content: str


class UpdateAISettingsRequest(BaseModel):
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    auto_post_enabled: Optional[bool] = None


class DispatchFlashNewsRequest(BaseModel):
    event_id: Optional[str] = None
    use_ai: bool = True
    publish_now: bool = True


@app.post("/api/v1/news/generate-digest")
def generate_calendar_digest(req: GenerateDigestRequest):
    """
    Tự động tổng hợp Bản tin Lịch Kinh Tế trong ngày (Chuẩn Ảnh mẫu 1).
    Sử dụng dữ liệu lịch trực tiếp từ ForexFactory và NLP tiếng Việt/OpenAI.
    """
    try:
        events = news_manager.fetch_calendar(force=False)
        target_d = None
        if req.date:
            target_d = datetime.strptime(req.date, "%Y-%m-%d").date()

        content = ai_writer.generate_daily_calendar_post(
            events=events,
            target_date=target_d,
            use_ai=req.use_ai,
        )
        return {
            "ok": True,
            "content": content,
            "has_openai": ai_writer.openai_config.is_configured,
        }
    except Exception as e:
        log.error("Lỗi tạo bản tin lịch kinh tế: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/news/generate-article")
def generate_gold_article(req: GenerateArticleRequest):
    """
    Tự động tạo bài báo Điểm Tin Thị Trường Vàng SJC & Thế Giới (Chuẩn Ảnh mẫu 2).
    Lấy giá XAUUSD thực tế trực tiếp từ MT5 và phân tích vĩ mô.
    """
    try:
        # Lấy giá MT5 thực tế nếu không truyền vào
        price = req.current_price
        change_pct = req.change_pct

        if price is None:
            price = 0.0
            if connector and connector.is_connected:
                mgr = MarketDataManager(settings.mt5.symbol)
                price_info = mgr.get_latest_price()
                if price_info:
                    price = price_info.get("bid", 0.0)

        if change_pct is None:
            change_pct = 0.0

        content = ai_writer.generate_gold_market_article(
            current_price=price,
            change_pct=change_pct,
            sjc_buy=req.sjc_buy,
            sjc_sell=req.sjc_sell,
            session_name=req.session_name,
            use_ai=req.use_ai,
        )
        return {
            "ok": True,
            "content": content,
            "has_openai": ai_writer.openai_config.is_configured,
        }
    except Exception as e:
        log.error("Lỗi tạo bài báo vàng: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/news/publish")
def publish_news_article(req: PublishArticleRequest, _key: str = Depends(verify_admin_key)):
    """Bắn trực tiếp bài viết / bản tin lên Kênh Telegram @dbgtradingfx."""
    msg = req.content.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Nội dung bài viết không được để trống.")

    success = notifier.send_raw_message(msg)
    if not success:
        raise HTTPException(status_code=502, detail="Gửi bài viết lên Telegram thất bại (kiểm tra token/kênh).")

    return {"ok": True, "message": "Đã xuất bản bài viết lên Kênh Telegram @dbgtradingfx thành công!"}


@app.post("/api/v1/news/dispatch-flash")
def dispatch_flash_news(req: DispatchFlashNewsRequest, _key: str = Depends(verify_admin_key)):
    """
    Biên tập và phát tin nhanh thời gian thực (sau khi tin ra 2-3 phút) lên Telegram.
    Nếu không truyền event_id, tự động lấy tin tức quan trọng gần nhất vừa diễn ra.
    """
    try:
        events = news_manager.fetch_calendar(force=False)
        target_event = None
        now_utc = datetime.now(timezone.utc)

        if req.event_id:
            for ev in events:
                if ev.id == req.event_id:
                    target_event = ev
                    break
        else:
            # Lấy sự kiện USD / High / Medium gần nhất vừa diễn ra (hoặc sự kiện đầu tiên)
            past_events = [e for e in events if e.time_utc <= now_utc and (e.is_usd or e.is_high_impact)]
            if past_events:
                target_event = past_events[-1]
            elif events:
                target_event = events[0]

        if not target_event:
            raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện kinh tế phù hợp để phát tin nhanh.")

        price = 0.0
        if connector and connector.is_connected:
            mgr = MarketDataManager(settings.mt5.symbol)
            price_info = mgr.get_latest_price()
            if price_info:
                price = price_info.get("bid", 0.0)

        diff_min = max(1.0, (now_utc - target_event.time_utc).total_seconds() / 60.0)
        minutes_ago = int(round(diff_min)) if diff_min < 120 else 2

        content = ai_writer.generate_realtime_flash_news_post(
            event=target_event,
            current_price=price,
            minutes_ago=minutes_ago,
            use_ai=req.use_ai,
        )

        published = False
        if req.publish_now and notifier.is_enabled:
            published = notifier.send_raw_message(content)

        return {
            "ok": True,
            "eventId": target_event.id,
            "eventTitle": target_event.title,
            "minutesAgo": minutes_ago,
            "published": published,
            "content": content,
            "has_openai": ai_writer.openai_config.is_configured,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("Lỗi phát tin nhanh: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news/ai-settings")
def get_ai_news_settings():
    """Lấy cấu hình OpenAI API và trạng thái tự động đăng tin."""
    masked_key = ""
    if ai_writer.openai_config.api_key:
        raw = ai_writer.openai_config.api_key.strip()
        masked_key = f"{raw[:4]}...{raw[-4:]}" if len(raw) > 8 else "***"

    return {
        "openai_configured": ai_writer.openai_config.is_configured,
        "openai_key_masked": masked_key,
        "openai_model": ai_writer.openai_config.model,
        "auto_post_enabled": settings.news_auto.enabled,
        "morning_time": settings.news_auto.morning_post_time,
        "auto_alert_red": settings.news_auto.auto_alert_red_news,
    }


@app.post("/api/v1/news/ai-settings")
def update_ai_news_settings(req: UpdateAISettingsRequest, _key: str = Depends(verify_admin_key)):
    """Cập nhật OpenAI API Key và cài đặt tự động đăng."""
    from config import OpenAIConfig

    updates: dict[str, str] = {}
    new_key = ai_writer.openai_config.api_key
    new_model = ai_writer.openai_config.model

    if req.openai_api_key is not None and req.openai_api_key.strip():
        new_key = req.openai_api_key.strip()
        updates["OPENAI_API_KEY"] = new_key

    if req.openai_model is not None and req.openai_model.strip():
        new_model = req.openai_model.strip()
        updates["OPENAI_MODEL"] = new_model

    if req.auto_post_enabled is not None:
        updates["NEWS_AUTO_POST_ENABLED"] = "true" if req.auto_post_enabled else "false"

    if updates:
        _update_env_file(updates)

    # Cập nhật instance in-memory
    ai_writer.openai_config = OpenAIConfig(
        api_key=new_key,
        model=new_model,
        base_url=None,
    )

    return {
        "ok": True,
        "message": "Đã lưu cấu hình OpenAI và tự động đăng tin thành công!",
        "openai_configured": ai_writer.openai_config.is_configured,
        "openai_model": ai_writer.openai_config.model,
    }


@app.post("/api/v1/telegram/broadcast-last-outcome")
def broadcast_last_outcome_to_telegram(_key: str = Depends(verify_admin_key)):
    """
    Bắn thông báo tổng hợp kết quả của lệnh vừa khớp gần nhất (Lời/Lỗ bao nhiêu Pip) lên Telegram.
    """
    if not signal_repo:
        raise HTTPException(status_code=500, detail="Database repository chưa sẵn sàng")

    outcome = signal_repo.get_latest_outcome()
    if not outcome:
        raise HTTPException(status_code=404, detail="Không tìm thấy lệnh nào đã hoàn tất để gửi báo cáo.")

    pnl_pts = float(outcome.get("pnl_points") or 0.0)
    pnl_pips = round(pnl_pts * 10.0, 1)
    exit_price = float(outcome.get("exit_price") or outcome.get("entry_price") or 0.0)

    # Tính duration_str nếu có
    duration_str = None
    dur_sec = outcome.get("duration_seconds")
    if dur_sec:
        mins = max(1, int(dur_sec) // 60)
        if mins < 60:
            duration_str = f"{mins} phút"
        else:
            duration_str = f"{mins // 60}h {mins % 60}m"

    # Lấy thống kê hiệu suất tích lũy
    perf_stats = signal_repo.get_performance_summary()

    sent = notifier.send_trade_outcome_summary(
        signal_or_data=outcome,
        exit_price=exit_price,
        pnl_points=pnl_pts,
        duration_str=duration_str,
        stats=perf_stats,
        force=True,  # Cho phép bấm gửi ngay theo yêu cầu
    )

    if not sent:
        raise HTTPException(status_code=502, detail="Gửi thông báo tổng hợp lệnh tới Telegram thất bại.")

    status_vn = "LÃI" if pnl_pips > 0 else ("LỖ" if pnl_pips < 0 else "HÒA VỐN")
    return {
        "ok": True,
        "message": f"Đã gửi thông báo tổng hợp lệnh #{outcome.get('signal_id')} ({status_vn} {abs(pnl_pips):.1f} Pips) lên Telegram thành công!",
        "signalId": outcome.get("signal_id"),
        "pnlPips": pnl_pips,
        "pnlPoints": pnl_pts,
    }


# =====================================================================
# MACHINE LEARNING & WALK-FORWARD MANAGEMENT (Phase 7)
# =====================================================================

@app.get("/api/v1/ml/models")
def get_ml_models():
    """Lấy danh sách các phiên bản mô hình ML và mô hình PRODUCTION đang hoạt động."""
    if not db_manager:
        return {
            "total_models": 0,
            "active_production_model": None,
            "active_model_path": None,
            "models": [],
        }
    from app.ml.registry import ModelRegistry
    registry = ModelRegistry(db_manager)
    models = registry.list_models()
    active_path = registry.get_latest_production_model_path()
    active_model = next((m for m in models if m.get("status") == "PRODUCTION"), None)
    return {
        "total_models": len(models),
        "active_production_model": active_model,
        "active_model_path": active_path,
        "models": models,
    }


@app.get("/api/v1/ml/models/{version}")
def get_ml_model_details(version: str):
    """Lấy chi tiết một phiên bản mô hình ML kèm lịch sử thẩm định Walk-Forward."""
    if not db_manager:
        return {}
    from app.ml.registry import ModelRegistry
    registry = ModelRegistry(db_manager)
    details = registry.get_model_details(version)
    if not details:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy mô hình phiên bản '{version}'")
    return details


@app.post("/api/v1/ml/models/{version}/promote")
def promote_ml_model(version: str, force: bool = False, _key: str = Depends(verify_admin_key)):
    """Thăng cấp mô hình ML lên PRODUCTION (yêu cầu admin key, kiểm tra chuẩn Walk-Forward)."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")
    from app.ml.registry import ModelRegistry
    registry = ModelRegistry(db_manager)
    success, message = registry.promote_to_production(version=version, force=force)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message, "version": version}


@app.get("/api/v1/ml/status")
def get_ml_system_status():
    """Kiểm tra trạng thái sẵn sàng của hệ thống ML Signal Filter."""
    if not db_manager:
        return {"is_active": False, "mode": "RULE_BASED", "active_version": None}
    from app.ml.registry import ModelRegistry
    registry = ModelRegistry(db_manager)
    active_path = registry.get_latest_production_model_path()
    models = registry.list_models()
    prod_model = next((m for m in models if m.get("status") == "PRODUCTION"), None)
    has_active = bool(active_path and os.path.exists(active_path))
    return {
        "is_active": has_active,
        "mode": "ML_ASSISTED" if has_active else "RULE_BASED_FALLBACK",
        "active_version": prod_model.get("version") if prod_model else None,
        "active_path": active_path,
        "total_registered_models": len(models),
    }


# =====================================================================
# SELF-LEARNING FEEDBACK & ROOT CAUSE ANALYSIS (Phase 8)
# =====================================================================

@app.get("/api/v1/self-learning/feedback")
def get_self_learning_feedback():
    """Lấy báo cáo chuẩn đoán tự học, phân bổ Root Cause và ma trận thích ứng từ closed trades."""
    if not signal_repo:
        return {"hasData": False, "report": {}}
    from app.strategy.feedback_learner import SelfLearningFeedbackEngine
    engine = SelfLearningFeedbackEngine(repository=signal_repo)
    report = engine.refresh()
    return {
        "hasData": bool(report and report.get("total_outcomes", 0) > 0),
        "report": report,
    }


# =====================================================================
# VÍ ĐẦU TƯ ẢO & TRÌNH GIẢ LẬP ĐI LỆNH 0.01 LOT (PAPER TRADING SIMULATOR)
# =====================================================================

class PaperWalletSetupRequest(BaseModel):
    initial_balance: float = 50.0
    default_lot: float = 0.01
    leverage: int = 500


class PaperWalletResetRequest(BaseModel):
    initial_balance: Optional[float] = None


class PaperWalletToggleRequest(BaseModel):
    enabled: Optional[bool] = None


class PaperClosePositionRequest(BaseModel):
    position_id: str


def _get_paper_engine():
    global bot_runner, db_manager, notifier
    if bot_runner and getattr(bot_runner, "paper_engine", None):
        return bot_runner.paper_engine
    from app.simulator.paper_engine import PaperTradingEngine
    dm = db_manager or DatabaseManager(db_path="data/vietkey_gold.db")
    return PaperTradingEngine(db_manager=dm, notifier=notifier)


@app.get("/api/v1/paper-wallet/overview")
def get_paper_wallet_overview():
    """Lấy số dư ví ảo, tài sản equity, lợi nhuận ròng, win rate và các lệnh đang chạy."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")
    engine = _get_paper_engine()
    engine.sync_active_signals()
    if connector and connector.is_connected:
        try:
            mgr = MarketDataManager(settings.mt5.symbol)
            p_info = mgr.get_latest_price()
            if p_info:
                bid = float(p_info.get("bid", 0.0))
                spread = float(p_info.get("spread", 0.3))
                half_sp = spread / 2.0
                engine.update_positions(
                    current_bid=round(bid, 2),
                    current_ask=round(bid + spread, 2),
                )
        except Exception:
            pass
    wallet = engine.get_wallet()
    positions = engine.get_open_positions()
    return {
        "wallet": wallet.to_dict(),
        "openPositionsCount": len(positions),
        "closedTradesCount": wallet.total_trades,
        "openPositions": positions,
    }


@app.post("/api/v1/paper-wallet/setup")
def setup_paper_wallet(req: PaperWalletSetupRequest):
    """Cấu hình số vốn khởi điểm tùy chỉnh (ví dụ nạp $50, $100, $500) và khối lượng lot."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")
    engine = _get_paper_engine()
    wallet = engine.setup_wallet(
        initial_balance=req.initial_balance,
        default_lot=req.default_lot,
        leverage=req.leverage,
    )
    return {
        "ok": True,
        "message": f"Đã thiết lập ví ảo với số vốn ${req.initial_balance:.2f} và lot {req.default_lot:.2f} thành công!",
        "wallet": wallet.to_dict(),
    }


@app.post("/api/v1/paper-wallet/reset")
def reset_paper_wallet(req: PaperWalletResetRequest):
    """Reset ví ảo về mốc ban đầu, xóa toàn bộ lệnh mở và lịch sử để chạy kịch bản mới."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")
    engine = _get_paper_engine()
    wallet = engine.reset_wallet(initial_balance=req.initial_balance)
    return {
        "ok": True,
        "message": f"Đã reset ví ảo về số dư khởi điểm ${wallet.balance:.2f} thành công!",
        "wallet": wallet.to_dict(),
    }


@app.post("/api/v1/paper-wallet/toggle-auto")
def toggle_paper_auto_trading(req: PaperWalletToggleRequest):
    """Bật / Tắt chế độ tự động khớp lệnh ảo khi bot phát tín hiệu mới."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")
    engine = _get_paper_engine()
    new_state = engine.toggle_auto_trading(enabled=req.enabled)
    return {
        "ok": True,
        "is_auto_trading": new_state,
        "message": f"Tự động đi lệnh Ví ảo: {'ĐÃ BẬT' if new_state else 'ĐÃ TẮT'}",
    }


@app.get("/api/v1/paper-wallet/positions")
def get_paper_open_positions():
    """Lấy danh sách các lệnh ảo đang mở với PnL thả nổi nhấp nháy theo giá thị trường."""
    if not db_manager:
        return []
    engine = _get_paper_engine()
    engine.sync_active_signals()
    if connector and connector.is_connected:
        try:
            mgr = MarketDataManager(settings.mt5.symbol)
            p_info = mgr.get_latest_price()
            if p_info:
                bid = float(p_info.get("bid", 0.0))
                spread = float(p_info.get("spread", 0.3))
                engine.update_positions(
                    current_bid=round(bid, 2),
                    current_ask=round(bid + spread, 2),
                )
        except Exception:
            pass
    return engine.get_open_positions()


@app.post("/api/v1/paper-wallet/close-position")
def close_paper_position_manual(req: PaperClosePositionRequest):
    """Đóng lệnh thủ công từ nút bấm trên giao diện người dùng."""
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database chưa sẵn sàng")

    current_price = 0.0
    if connector and connector.is_connected:
        try:
            mgr = MarketDataManager(settings.mt5.symbol)
            p_info = mgr.get_latest_price()
            if p_info:
                current_price = float(p_info.get("bid", 0.0))
        except Exception:
            pass

    engine = _get_paper_engine()
    trade = engine.close_position_manual(
        position_id=req.position_id,
        current_price=current_price if current_price > 0 else 2700.0,
    )
    if not trade:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lệnh mở #{req.position_id}")

    return {
        "ok": True,
        "message": f"Đã đóng lệnh #{req.position_id} thành công! PnL: {'+' if trade.pnl_usd >= 0 else ''}${trade.pnl_usd:.2f} USD",
        "trade": trade.to_dict(),
    }


@app.get("/api/v1/paper-wallet/history")
def get_paper_trade_history(limit: int = 50):
    """Lấy lịch sử các lệnh đã đóng hoàn tất trên ví ảo."""
    if not db_manager:
        return []
    engine = _get_paper_engine()
    return engine.get_trade_history(limit=limit)


@app.get("/api/v1/paper-wallet/equity-curve")
def get_paper_equity_curve(limit: int = 100):
    """Lấy dữ liệu chuỗi thời gian tăng trưởng vốn (Equity snapshots) để vẽ biểu đồ."""
    if not db_manager:
        return []
    engine = _get_paper_engine()
    return engine.get_equity_curve(limit=limit)










# Gắn Static files của Frontend Terminal nếu đã build
frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
    "dist",
)
if os.path.exists(frontend_dist):
    from starlette.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static_frontend")

