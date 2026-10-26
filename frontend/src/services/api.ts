// VietKey Gold AI — API Service Layer
// Connects directly to real FastAPI Backend (MT5 + SQLite)

import type {
  MarketOverviewData,
  PerformanceData,
  SignalItem,
  StatusCardData,
  SystemMonitoringData,
  NewsCalendarData,
  BroadcastNewsPayload,
  TelegramStatusData,
  PaperWalletData,
  PaperPositionItem,
  PaperTradeHistoryItem,
  PaperEquitySnapshot,
  SystemDiagnosticsData,
  SystemLogsResponse,
  SelfTestResponse,
} from '../types';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error ${res.status}: ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  /**
   * Lấy dữ liệu tổng quan thẻ trạng thái từ MT5 và hệ thống.
   */
  async getStatusCards(): Promise<StatusCardData> {
    return fetchJson<StatusCardData>(`${API_BASE}/dashboard/overview`);
  },

  /**
   * Lấy phân tích cấu trúc thị trường thực tế đa khung thời gian.
   */
  async getMarketOverview(): Promise<MarketOverviewData> {
    return fetchJson<MarketOverviewData>(`${API_BASE}/market/overview`);
  },

  /**
   * Lấy danh sách tín hiệu thực tế từ SQLite Database.
   */
  async getSignals(limit: number = 20): Promise<SignalItem[]> {
    return fetchJson<SignalItem[]>(`${API_BASE}/signals?limit=${limit}`);
  },

  /**
   * Lấy chi tiết một tín hiệu theo ID từ SQLite Database.
   */
  async getSignalDetail(signalId: string): Promise<SignalItem> {
    return fetchJson<SignalItem>(`${API_BASE}/signals/${encodeURIComponent(signalId)}`);
  },

  /**
   * Lấy thông số tài nguyên hệ thống thực tế (CPU, RAM, Uptime qua psutil).
   */
  async getSystemMetrics(): Promise<SystemMonitoringData> {
    return fetchJson<SystemMonitoringData>(`${API_BASE}/system/metrics`);
  },

  /**
   * Lấy chẩn đoán sức khỏe hệ thống toàn diện, trạng thái phân hệ và thống kê lỗi.
   */
  async getSystemDiagnostics(): Promise<SystemDiagnosticsData> {
    return fetchJson<SystemDiagnosticsData>(`${API_BASE}/system/diagnostics`);
  },

  /**
   * Truy vấn nhật ký hệ thống thời gian thực với bộ lọc lỗi, cảnh báo và tìm kiếm.
   */
  async getSystemLogs(level: string = 'ALL', limit: number = 100, search?: string): Promise<SystemLogsResponse> {
    const params = new URLSearchParams();
    if (level) params.append('level', level);
    if (limit) params.append('limit', String(limit));
    if (search && search.trim()) params.append('search', search.trim());
    return fetchJson<SystemLogsResponse>(`${API_BASE}/system/logs?${params.toString()}`);
  },

  /**
   * Chạy bài tự kiểm tra (Self-Diagnostics Test) cho các kết nối MT5, SQLite, Paper Wallet, Disk.
   */
  async runSystemSelfTest(): Promise<SelfTestResponse> {
    return postJson<SelfTestResponse>(`${API_BASE}/system/run-self-test`, {});
  },

  /**
   * Lấy thống kê hiệu suất thực tế từ outcomes trong SQLite.
   */
  async getPerformance(): Promise<PerformanceData> {
    return fetchJson<PerformanceData>(`${API_BASE}/performance`);
  },

  /**
   * Lấy lịch kinh tế và vùng an toàn tin đỏ từ ForexFactory engine.
   */
  async getNewsCalendar(): Promise<NewsCalendarData> {
    return fetchJson<NewsCalendarData>(`${API_BASE}/news/calendar`);
  },

  // =========================================================================
  // Admin Action Methods (Phát tin, gửi lại lệnh, kiểm tra Telegram)
  // =========================================================================

  /**
   * Admin bấm gửi lại một tín hiệu giao dịch lên Kênh Telegram.
   */
  async adminResendSignal(signalId: string): Promise<{ ok: boolean; message: string }> {
    return postJson<{ ok: boolean; message: string }>(`${API_BASE}/admin/resend-signal`, {
      signal_id: signalId,
    });
  },

  /**
   * Admin bắn bản tin kinh tế & dự báo AI lên Kênh Telegram.
   */
  async adminBroadcastNews(payload: BroadcastNewsPayload): Promise<{ ok: boolean; message: string }> {
    return postJson<{ ok: boolean; message: string }>(`${API_BASE}/admin/broadcast-news`, payload);
  },

  /**
   * Admin gửi thông báo nhanh tùy chỉnh lên Kênh Telegram.
   */
  async adminBroadcastCustom(message: string): Promise<{ ok: boolean; message: string }> {
    return postJson<{ ok: boolean; message: string }>(`${API_BASE}/admin/broadcast-custom`, {
      message,
    });
  },

  /**
   * Lấy trạng thái hoạt động của Telegram Notifier.
   */
  async getTelegramStatus(): Promise<TelegramStatusData> {
    return fetchJson<TelegramStatusData>(`${API_BASE}/telegram/status`);
  },

  /**
   * Gửi tin nhắn kiểm tra kết nối Telegram Bot.
   */
  async testTelegramConnection(): Promise<{ ok: boolean; message: string }> {
    return postJson<{ ok: boolean; message: string }>(`${API_BASE}/telegram/test`, {});
  },

  // =========================================================================
  // AI Financial Newsroom Methods (Tạo Lịch Kinh Tế, Bài Báo Vàng & Cấu Hình AI)
  // =========================================================================

  /**
   * Tự động tổng hợp Bản tin Lịch Kinh Tế trong ngày (Chuẩn Ảnh 1).
   */
  async generateCalendarDigest(useAi: boolean = true, dateStr?: string): Promise<{ ok: boolean; content: string; has_openai: boolean }> {
    return postJson<{ ok: boolean; content: string; has_openai: boolean }>(`${API_BASE}/news/generate-digest`, {
      use_ai: useAi,
      date: dateStr,
    });
  },

  /**
   * Tự động tạo Bài báo Điểm tin Vàng SJC & Thế Giới (Chuẩn Ảnh 2).
   */
  async generateGoldArticle(payload?: { sjc_buy?: number; sjc_sell?: number; use_ai?: boolean; current_price?: number; change_pct?: number }): Promise<{ ok: boolean; content: string; has_openai: boolean }> {
    return postJson<{ ok: boolean; content: string; has_openai: boolean }>(`${API_BASE}/news/generate-article`, payload || {});
  },

  /**
   * Đăng trực tiếp bài viết / bản tin lên Kênh Telegram @dbgtradingfx.
   */
  async publishNewsArticle(content: string): Promise<{ ok: boolean; message: string }> {
    return postJson<{ ok: boolean; message: string }>(`${API_BASE}/news/publish`, {
      content,
    });
  },

  /**
   * Đọc cấu hình OpenAI API và cài đặt tự động đăng bài.
   */
  async getAINewsSettings(): Promise<any> {
    return fetchJson<any>(`${API_BASE}/news/ai-settings`);
  },

  /**
   * Cập nhật OpenAI API Key và các tùy chọn tự động.
   */
  async updateAINewsSettings(payload: { openai_api_key?: string; openai_model?: string; auto_post_enabled?: boolean }): Promise<any> {
    return postJson<any>(`${API_BASE}/news/ai-settings`, payload);
  },

  /**
   * Biên tập và phát tin nhanh thời gian thực (sau khi tin ra 2-3 phút) lên Telegram.
   */
  async dispatchFlashNews(payload?: { event_id?: string; use_ai?: boolean; publish_now?: boolean }): Promise<{ ok: boolean; eventTitle: string; minutesAgo: number; published: boolean; content: string; has_openai: boolean }> {
    return postJson<any>(`${API_BASE}/news/dispatch-flash`, payload || { use_ai: true, publish_now: true });
  },

  // ==========================================
  // PAPER TRADING VIRTUAL WALLET APIS
  // ==========================================
  async getPaperWalletOverview(): Promise<{ wallet: PaperWalletData; openPositionsCount: number; closedTradesCount: number }> {
    return fetchJson<{ wallet: PaperWalletData; openPositionsCount: number; closedTradesCount: number }>(`${API_BASE}/paper-wallet/overview`);
  },

  async setupPaperWallet(payload: { initial_balance: number; default_lot?: number; leverage?: number }): Promise<{ ok: boolean; message: string; wallet: PaperWalletData }> {
    return postJson<{ ok: boolean; message: string; wallet: PaperWalletData }>(`${API_BASE}/paper-wallet/setup`, payload);
  },

  async resetPaperWallet(initial_balance?: number): Promise<{ ok: boolean; message: string; wallet: PaperWalletData }> {
    return postJson<{ ok: boolean; message: string; wallet: PaperWalletData }>(`${API_BASE}/paper-wallet/reset`, { initial_balance });
  },

  async togglePaperAutoTrading(enabled?: boolean): Promise<{ ok: boolean; is_auto_trading: boolean; message: string }> {
    return postJson<{ ok: boolean; is_auto_trading: boolean; message: string }>(`${API_BASE}/paper-wallet/toggle-auto`, { enabled });
  },

  async getPaperPositions(): Promise<PaperPositionItem[]> {
    return fetchJson<PaperPositionItem[]>(`${API_BASE}/paper-wallet/positions`);
  },

  async closePaperPosition(position_id: string): Promise<{ ok: boolean; message: string; trade: PaperTradeHistoryItem }> {
    return postJson<{ ok: boolean; message: string; trade: PaperTradeHistoryItem }>(`${API_BASE}/paper-wallet/close-position`, { position_id });
  },

  async getPaperHistory(limit: number = 50): Promise<PaperTradeHistoryItem[]> {
    return fetchJson<PaperTradeHistoryItem[]>(`${API_BASE}/paper-wallet/history?limit=${limit}`);
  },

  async getPaperEquityCurve(limit: number = 100): Promise<PaperEquitySnapshot[]> {
    return fetchJson<PaperEquitySnapshot[]>(`${API_BASE}/paper-wallet/equity-curve?limit=${limit}`);
  },
};

