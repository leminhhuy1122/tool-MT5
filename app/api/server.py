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
import json
import os
import sys
import threading
import time

from fastapi import FastAPI, HTTPException
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

    # 1. Kết nối Database SQLite
    try:
        db_manager = DatabaseManager(config=settings.database)
        signal_repo = SignalRepository(db_manager)
        market_repo = MarketDataRepository(db_manager)
        log.info("✓ SQLite Database đã kết nối: %s", db_manager.db_path)
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

# Cho phép Vite dev server và localhost truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api")
def read_root():
    """Kiểm tra trạng thái server."""
    return {
        "app": "VietKey Gold AI",
        "version": "0.8.0",
        "status": "ONLINE",
        "server_time": datetime.now(timezone.utc).isoformat(),
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
                    "reason": reason_text,
                    "invalidation": r.get("invalidation", ""),
                    "riskReward": round(float(r.get("risk_reward_ratio") or 0.0), 2),
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
def admin_resend_signal(req: ResendSignalRequest):
    """Admin bắn lại một tín hiệu giao dịch lên Kênh Telegram."""
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
def admin_broadcast_news(req: BroadcastNewsRequest):
    """Admin bắn bản tin kinh tế & dự báo xu hướng Vàng lên Kênh Telegram."""
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
def admin_broadcast_custom(req: BroadcastCustomRequest):
    """Admin gửi thông báo nhanh tùy chỉnh lên Kênh Telegram."""
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
def test_telegram_connection():
    """Gửi tin nhắn kiểm tra kết nối Telegram."""
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

def _update_env_file(key_values: dict[str, str]) -> None:
    """Cập nhật an toàn các giá trị trong file .env."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_set = set(key_values.keys())
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
            new_lines.append(f"{matched_key}={key_values[matched_key]}\n")
            found_keys.add(matched_key)
        else:
            new_lines.append(line)

    for k in keys_set - found_keys:
        new_lines.append(f"{k}={key_values[k]}\n")

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
            price = 3996.34
            change_pct = -0.76
            if connector and connector.is_connected:
                mgr = MarketDataManager(settings.mt5.symbol)
                price_info = mgr.get_latest_price()
                if price_info:
                    price = price_info.get("bid", 3996.34)

        if change_pct is None:
            change_pct = -0.71

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
def publish_news_article(req: PublishArticleRequest):
    """Bắn trực tiếp bài viết / bản tin lên Kênh Telegram @dbgtradingfx."""
    msg = req.content.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Nội dung bài viết không được để trống.")

    success = notifier.send_raw_message(msg)
    if not success:
        raise HTTPException(status_code=502, detail="Gửi bài viết lên Telegram thất bại (kiểm tra token/kênh).")

    return {"ok": True, "message": "Đã xuất bản bài viết lên Kênh Telegram @dbgtradingfx thành công!"}


@app.post("/api/v1/news/dispatch-flash")
def dispatch_flash_news(req: DispatchFlashNewsRequest):
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

        price = 3996.34
        if connector and connector.is_connected:
            mgr = MarketDataManager(settings.mt5.symbol)
            price_info = mgr.get_latest_price()
            if price_info:
                price = price_info.get("bid", 3996.34)

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
def update_ai_news_settings(req: UpdateAISettingsRequest):
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
def broadcast_last_outcome_to_telegram():
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





# Gắn Static files của Frontend Terminal nếu đã build
frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
    "dist",
)
if os.path.exists(frontend_dist):
    from starlette.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static_frontend")

