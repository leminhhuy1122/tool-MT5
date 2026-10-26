import React, { useCallback, useEffect, useState } from 'react';
import { ErrorBoundary } from './components/layout/ErrorBoundary';
import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { LatestSignals } from './components/overview/LatestSignals';
import { LiveOpenPositions } from './components/overview/LiveOpenPositions';
import { MarketTickerHero } from './components/overview/MarketTickerHero';
import { PaperWalletHeroCard } from './components/overview/PaperWalletHeroCard';
import { PerformanceCharts } from './components/overview/PerformanceCharts';
import { PerformanceSummary } from './components/overview/PerformanceSummary';
import { SystemHealthFooter } from './components/overview/SystemHealthFooter';
import { EconomicCalendarView } from './components/views/EconomicCalendarView';
import { MarketAnalysisView } from './components/views/MarketAnalysisView';
import { PaperWalletView } from './components/views/PaperWalletView';
import { StrategySettingsView } from './components/views/StrategySettingsView';
import { SystemMonitoringView } from './components/views/SystemMonitoringView';
import { TelegramSettingsView } from './components/views/TelegramSettingsView';
import { api } from './services/api';
import type {
  MarketOverviewData,
  MenuId,
  NewsCalendarData,
  PerformanceData,
  SignalItem,
  StatusCardData,
  SystemMonitoringData,
} from './types';

export const App: React.FC = () => {
  const [currentMenu, setCurrentMenu] = useState<MenuId>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [density, setDensity] = useState<'normal' | 'compact'>('normal');
  const [pollIntervalSec, setPollIntervalSec] = useState<number>(5);

  // System sub-tab state when in 'system' view
  const [systemSubTab, setSystemSubTab] = useState<'telegram' | 'monitoring' | 'market' | 'strategy' | 'performance'>('monitoring');

  // Real data state
  const [statusCards, setStatusCards] = useState<StatusCardData>({
    botStatus: 'RUNNING',
    mt5Status: 'CONNECTED',
    symbol: 'XAUUSD',
    currentPrice: 3996.34,
    spread: 1.49,
    activeSignals: 0,
    totalSignalsToday: 1,
    ramUsageMB: 106.4,
    ramUsagePct: 89.9,
    cpuUsagePct: 5.4,
  });

  const [marketOverview, setMarketOverview] = useState<MarketOverviewData>({
    symbol: 'XAUUSD',
    price: 3996.34,
    bid: 3996.34,
    ask: 3997.83,
    change24h: -30.61,
    change24hPct: -0.76,
    high24h: 4038.5,
    low24h: 3985.2,
    h4Trend: 'BEARISH',
    h1Trend: 'NEUTRAL',
    m15Trend: 'NEUTRAL',
    m5Confirmation: 'NEUTRAL',
    volatility: 'BÌNH THƯỜNG (ATR=2.85 giá)',
    spread: 1.49,
    structure: 'M5 NEUTRAL | 20 Swings, 7 Vùng Hỗ trợ/Kháng cự',
    lastUpdate: 'Live MT5 Feed',
  });

  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [performance, setPerformance] = useState<PerformanceData>({
    totalSignals: 0,
    winRate: 0,
    lossRate: 0,
    unresolvedSignals: 0,
    averageR: 0,
    profitFactor: 0,
    maxDrawdownPct: 0,
    maxDrawdownCash: 0,
    byStrategy: [],
    hasRealData: false,
  });

  const [systemMetrics, setSystemMetrics] = useState<SystemMonitoringData>({
    cpuPct: 5.4,
    ramPct: 89.9,
    ramUsedMB: 106.4,
    ramTotalMB: 16104,
    uptimeSeconds: 120,
    dataLatencyMs: 12,
    lastMarketUpdate: 'Thời gian thực',
    databaseStatus: 'WAL_MODE',
    telegramStatus: 'CONFIGURED',
    cpuHistory: [4, 5, 5.4],
    ramHistory: [105, 106, 106.4],
  });

  const [newsData, setNewsData] = useState<NewsCalendarData>({
    isBlackout: false,
    blackoutEvent: null,
    nextHighImpactEvent: null,
    minutesUntilNext: null,
    eventsCount: 0,
    events: [],
    lastUpdated: 'Live Feed',
  });

  // Tải dữ liệu từ backend API thực tế
  const loadData = useCallback(async (showRefreshingSpinner = false) => {
    if (showRefreshingSpinner) setIsRefreshing(true);
    setErrorMsg(null);

    try {
      const [cardsRes, marketRes, signalsRes, metricsRes, perfRes, newsRes] = await Promise.allSettled([
        api.getStatusCards(),
        api.getMarketOverview(),
        api.getSignals(20),
        api.getSystemMetrics(),
        api.getPerformance(),
        api.getNewsCalendar(),
      ]);

      if (cardsRes.status === 'fulfilled') setStatusCards(cardsRes.value);
      if (marketRes.status === 'fulfilled') setMarketOverview(marketRes.value);
      if (signalsRes.status === 'fulfilled') setSignals(signalsRes.value);
      if (metricsRes.status === 'fulfilled') setSystemMetrics(metricsRes.value);
      if (perfRes.status === 'fulfilled') setPerformance(perfRes.value);
      if (newsRes.status === 'fulfilled') setNewsData(newsRes.value);
    } catch (err) {
      console.error('Lỗi nạp dữ liệu backend:', err);
      setErrorMsg('Không thể kết nối Backend API. Vui lòng kiểm tra server tại port 8000.');
    } finally {
      if (showRefreshingSpinner) setIsRefreshing(false);
    }
  }, []);

  // Polling tự động theo pollIntervalSec
  useEffect(() => {
    loadData(false);
    const interval = setInterval(() => {
      loadData(false);
    }, pollIntervalSec * 1000);

    return () => clearInterval(interval);
  }, [loadData, pollIntervalSec]);

  // Route identifier normalized to core tabs
  const isOverview = currentMenu === 'overview';
  const isSignals = currentMenu === 'signals' || currentMenu === 'live-signals' || currentMenu === 'signal-history';
  const isPaperWallet = currentMenu === 'paper-wallet';
  const isNews = currentMenu === 'news' || currentMenu === 'economic-calendar';
  const isSystem =
    currentMenu === 'system' ||
    currentMenu === 'telegram-settings' ||
    currentMenu === 'system-monitoring' ||
    currentMenu === 'market-analysis' ||
    currentMenu === 'strategy' ||
    currentMenu === 'performance' ||
    currentMenu === 'ai-models' ||
    currentMenu === 'backtest' ||
    currentMenu === 'logs' ||
    currentMenu === 'settings';

  return (
    <div className={`app-container ${density === 'compact' ? 'density-compact' : ''}`}>
      {/* Sidebar Navigation */}
      <Sidebar
        currentMenu={currentMenu}
        onSelectMenu={(menu) => setCurrentMenu(menu)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        botStatus={statusCards.botStatus}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Topbar
          symbol={statusCards.symbol}
          mt5Status={statusCards.mt5Status}
          botStatus={statusCards.botStatus}
          onRefresh={() => loadData(true)}
          isRefreshing={isRefreshing}
          onOpenMobileMenu={() => setMobileOpen(true)}
          density={density}
          onToggleDensity={() => setDensity(density === 'normal' ? 'compact' : 'normal')}
          pollIntervalSec={pollIntervalSec}
          onChangePollInterval={setPollIntervalSec}
          currentMenu={currentMenu}
          onSelectMenu={setCurrentMenu}
          paperWallet={statusCards.paperWallet}
        />

        <main className="content-area">
          <ErrorBoundary fallbackTitle="Đã xảy ra sự cố trong khu vực nội dung">
          {errorMsg && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid var(--color-sell-border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--color-sell)',
                fontSize: '13px',
                marginBottom: '16px',
              }}
            >
              ⚠️ {errorMsg}
            </div>
          )}

          {/* Cảnh báo Vùng Nguy Hiểm Tin Đỏ */}
          {newsData.isBlackout && newsData.blackoutEvent && (
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(239, 68, 68, 0.16)',
                border: '1px solid var(--color-sell)',
                borderRadius: 'var(--radius-sm)',
                color: '#F87171',
                fontSize: '13px',
                fontWeight: 600,
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>
                🚨 <strong>CẢNH BÁO BÃO GIÁ TIN ĐỎ:</strong> Đang trong vùng cấm giao dịch sự kiện{' '}
                <strong style={{ color: '#FFF' }}>{newsData.blackoutEvent.title} ({newsData.blackoutEvent.country})</strong>.
                Bot tự động tạm dừng phát tín hiệu mới để bảo vệ tài khoản khỏi quét SL 2 đầu!
              </span>
              <button
                className="btn btn-secondary"
                style={{ padding: '3px 8px', fontSize: '11px' }}
                onClick={() => setCurrentMenu('news')}
              >
                Xem Lịch Kinh Tế
              </button>
            </div>
          )}

          {/* Tab 1: Tổng Quan (Overview) */}
          {isOverview && (
            <>
              {/* 1. TOP HERO: Giá vàng MT5, Tích hợp AI Copilot & Xu hướng đa khung */}
              <MarketTickerHero
                statusCards={statusCards}
                marketOverview={marketOverview}
                onRefresh={() => loadData(true)}
              />

              {/* 2. VÍ ĐẦU TƯ ẢO (0.01 LOT): Hiển thị trực tiếp Lời/Lỗ tiền đô (U) gọn gàng */}
              <PaperWalletHeroCard
                paperWallet={statusCards.paperWallet}
                currentPrice={statusCards.currentPrice || marketOverview.price}
                onNavigateToWallet={setCurrentMenu}
                onRefresh={() => loadData(false)}
              />

              {/* 2. TRỌNG TÂM #1: Vị Thế Đang Khớp Lệnh & PnL Thả Nổi Real-time (Pips & Giá) */}
              <LiveOpenPositions
                signals={signals}
                currentPrice={statusCards.currentPrice || marketOverview.price}
              />

              {/* 3. TRỌNG TÂM #2: Bảng Tín Hiệu Giao Dịch & Quản Lý Lệnh Win / Lost (Full-width bao quát) */}
              <div style={{ marginBottom: '12px' }}>
                <LatestSignals
                  signals={signals}
                  currentPrice={statusCards.currentPrice || marketOverview.price}
                />
              </div>

              {/* 4. BIỂU ĐỒ HIỆU SUẤT TRỰC QUAN: Đường cong PnL tích lũy & Vòng tròn Winrate */}
              <PerformanceCharts
                performance={performance}
                signals={signals}
              />

              {/* 5. ĐÁY TRANG: Báo cáo thông số hệ thống & tài nguyên (Đưa xuống dưới cùng) */}
              <SystemHealthFooter data={systemMetrics} />
            </>
          )}

          {/* Tab 2: Tín Hiệu & Điều Khiển Lệnh (Signals & Admin Controls) */}
          {isSignals && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div
                className="card"
                style={{
                  borderLeft: '4px solid var(--color-accent-gold)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)' }}>
                    📡 Trung Tâm Tín Hiệu & Điều Khiển Bắn Lệnh Admin
                  </h2>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Setup BUY/SELL khung M5 được lọc qua Machine Learning. Admin có thể bấm 1-click để gửi lại lệnh lên Kênh Telegram.
                  </p>
                </div>
                <span className="status-pill connected font-mono font-bold">
                  {signals.length} TÍN HIỆU ĐÃ LƯU
                </span>
              </div>
              <LatestSignals signals={signals} />
            </div>
          )}

          {/* Tab: Ví Đầu Tư Ảo (Paper Trading 0.01 Lot) */}
          {isPaperWallet && <PaperWalletView />}

          {/* Tab 3: Tin Tức & Dự Báo AI (Economic News & AI Bias) */}
          {isNews && <EconomicCalendarView data={newsData} />}

          {/* Tab 4: Hệ Thống & Cài Đặt (System, Telegram & Settings) */}
          {isSystem && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Sub-tab Navigation */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  borderBottom: '1px solid var(--border-color)',
                  paddingBottom: '8px',
                  flexWrap: 'wrap',
                }}
              >
                {[
                  { id: 'monitoring', label: '💻 Giám Sát & Tìm Lỗi' },
                  { id: 'telegram', label: '🔔 Quản Trị Telegram' },
                  { id: 'market', label: '📈 Phân Tích Cấu Trúc' },
                  { id: 'strategy', label: '⚙️ Cấu Hình Chiến Lược' },
                  { id: 'performance', label: '📊 Thống Kê Hiệu Suất' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    className={`btn ${systemSubTab === tab.id ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '6px 14px', fontSize: '12px', fontWeight: 700 }}
                    onClick={() => setSystemSubTab(tab.id as any)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Sub-tab Contents */}
              {systemSubTab === 'telegram' && <TelegramSettingsView />}
              {systemSubTab === 'monitoring' && <SystemMonitoringView data={systemMetrics} />}
              {systemSubTab === 'market' && <MarketAnalysisView data={marketOverview} />}
              {systemSubTab === 'strategy' && <StrategySettingsView />}
              {systemSubTab === 'performance' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <PerformanceSummary data={performance} />
                  <div className="card">
                    <div className="card-header">
                      <span className="card-title">Hiệu Suất Theo Chiến Lược Thực Nghiệm</span>
                      <span className="text-xs text-gold font-mono">Walk-Forward Validated</span>
                    </div>
                    <div className="text-xs text-secondary" style={{ lineHeight: 1.6 }}>
                      Hệ thống ghi nhận tỷ lệ thắng (Win Rate), Profit Factor và tỷ lệ R-Multiple dựa trên quy tắc quản lý lệnh chặt chẽ:
                      Lãi 5 giá dời SL hòa vốn, Lãi 10 giá chốt 50% TP1 nuôi TP2.
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
};

export default App;
