// VietKey Gold AI — Type Definitions
// Institutional Trading Dashboard

export type BotStatus = 'RUNNING' | 'STANDBY' | 'STOPPED' | 'ERROR';
export type MT5Status = 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';
export type MarketTrend = 'BULLISH' | 'BEARISH' | 'NEUTRAL';
export type SignalDirection = 'BUY' | 'SELL' | 'WAIT';
export type SignalStatus = 
  | 'PENDING'
  | 'ACTIVE'
  | 'ENTRY_REACHED'
  | 'TP_REACHED'
  | 'SL_REACHED'
  | 'INVALIDATED'
  | 'EXPIRED'
  | 'UNRESOLVED';

export interface ConfluenceItem {
  name: string;
  score: number;
  max: number;
  detail: string;
}

export interface SignalItem {
  id: string;
  symbol: string;
  direction: SignalDirection;
  timeframe: string;
  time: string;
  entryZone: [number, number];
  plannedEntry: number;
  stopLoss: number;
  takeProfit1: number;
  takeProfit2: number;
  score: number; // 0 - 100 Confluence Score (chưa phải xác suất thắng)
  status: SignalStatus;
  strategyVersion: string;
  setupType?: string;
  isPredictive?: boolean;
  isDca?: boolean;
  parentSignalId?: string;
  dcaBreakevenPrice?: number;
  modelVersion?: string;
  reason: string;
  invalidation: string;
  riskReward: number;
  confluences?: ConfluenceItem[];
  mfePoints?: number;
  maePoints?: number;
  pnlPoints?: number | null;
  pnlPips?: number | null;
  isWin?: boolean;
  isLoss?: boolean;
  isBreakeven?: boolean;
  exitPrice?: number | null;
  durationSeconds?: number | null;
  breakevenTriggered?: boolean;
  partialClosed?: boolean;
}

export interface MarketOverviewData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  change24h: number;
  change24hPct: number;
  high24h: number;
  low24h: number;
  h4Trend: MarketTrend;
  h1Trend: MarketTrend;
  m15Trend: MarketTrend;
  m5Confirmation: MarketTrend;
  volatility: string;
  spread: number;
  structure: string;
  lastUpdate: string;
}

export interface PaperWalletOverviewSummary {
  balance: number;
  equity: number;
  floatingPnl: number;
  netProfitUsd: number;
  roiPercent: number;
  openCount: number;
  isAutoTrading: boolean;
  defaultLot: number;
  usedMargin: number;
  freeMargin: number;
  marginLevel: number;
  winRate: number;
  totalTrades: number;
  winningTrades?: number;
  losingTrades?: number;
  openPositions?: PaperPositionItem[];
}

export interface StatusCardData {
  botStatus: BotStatus;
  mt5Status: MT5Status;
  symbol: string;
  currentPrice: number;
  spread: number;
  activeSignals: number;
  totalSignalsToday: number;
  ramUsageMB: number;
  ramUsagePct: number;
  cpuUsagePct: number;
  paperWallet?: PaperWalletOverviewSummary;
}

export interface PerformanceStrategyItem {
  name: string;
  total: number;
  winRate: number;
  pf: number;
}

export interface PerformanceData {
  totalSignals: number;
  winRate: number;
  lossRate: number;
  unresolvedSignals: number;
  averageR: number;
  profitFactor: number;
  maxDrawdownPct: number;
  maxDrawdownCash: number;
  byStrategy: PerformanceStrategyItem[];
  hasRealData: boolean;
  winsCount?: number;
  lossesCount?: number;
  netPoints?: number;
  netPips?: number;
}

export interface SystemMonitoringData {
  cpuPct: number;
  ramPct: number;
  ramUsedMB: number;
  ramTotalMB: number;
  uptimeSeconds: number;
  dataLatencyMs: number;
  lastMarketUpdate: string;
  databaseStatus: 'CONNECTED' | 'DISCONNECTED' | 'WAL_MODE';
  telegramStatus: 'CONNECTED' | 'DISCONNECTED' | 'NOT_CONFIGURED' | 'CONFIGURED';
  cpuHistory: number[];
  ramHistory: number[];
}

export interface LogItem {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL' | 'DEBUG';
  module: string;
  message: string;
  isError: boolean;
  isWarning: boolean;
}

export interface SystemLogsResponse {
  total: number;
  errorCount: number;
  warningCount: number;
  infoCount: number;
  filteredCount: number;
  logs: LogItem[];
}

export interface SelfTestItem {
  test: string;
  ok: boolean;
  detail: string;
}

export interface SelfTestResponse {
  ok: boolean;
  timestamp: string;
  tests: SelfTestItem[];
}

export interface SystemDiagnosticsData {
  status: 'HEALTHY' | 'WARNING' | 'ERROR';
  stabilityScore: number;
  uptimeSeconds: number;
  timestamp: string;
  mt5: {
    status: 'CONNECTED' | 'DISCONNECTED';
    latencyMs: number;
    symbol: string;
    bid: number;
    ask: number;
    spread: number;
    account: {
      login?: number;
      server?: string;
      leverage?: number;
      tradeAllowed?: boolean;
      balance?: number;
      equity?: number;
    };
  };
  database: {
    status: 'HEALTHY' | 'ERROR';
    journalMode: string;
    integrity: string;
    fileSizeMB: number;
    signalsCount: number;
    tradesCount: number;
    path: string;
  };
  botRunner: {
    status: 'RUNNING' | 'IDLE' | 'STOPPED';
    activeTrackingSignals: number;
    lastM5ProcessedTime?: string;
    antiHedgingMode: string;
    mlFilterEnabled: boolean;
  };
  smartExitAndCopilot: {
    status: string;
    copilotCompanion: string;
    beTriggerR: number;
    trailingAtrMult: number;
  };
  resources: {
    pid: number;
    cpuPct: number;
    ramMB: number;
    systemRamPct: number;
    diskFreeGB: number;
  };
  errorDiagnostics: {
    errorCount24h: number;
    warningCount24h: number;
    totalLogsParsed: number;
    recentErrors: LogItem[];
  };
}

export type MenuId =
  | 'overview'
  | 'signals'
  | 'news'
  | 'paper-wallet'
  | 'system'
  | 'live-signals'
  | 'market-analysis'
  | 'signal-history'
  | 'strategy'
  | 'economic-calendar'
  | 'ai-models'
  | 'telegram-settings'
  | 'backtest'
  | 'performance'
  | 'system-monitoring'
  | 'logs'
  | 'settings';

export interface PaperWalletData {
  wallet_id: string;
  name: string;
  initial_balance: number;
  balance: number;
  equity: number;
  currency: string;
  leverage: number;
  default_lot: number;
  is_auto_trading: boolean;
  used_margin: number;
  free_margin: number;
  margin_level: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  floating_pnl: number;
  net_profit_usd: number;
  roi_percent: number;
  created_at?: string;
  updated_at?: string;
}

export interface PaperPositionItem {
  position_id: string;
  wallet_id: string;
  signal_id?: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  volume: number;
  open_price: number;
  current_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2?: number;
  floating_pnl: number;
  floating_pnl_percent: number;
  status: string;
  open_time: string;
  last_update?: string;
}

export interface PaperTradeHistoryItem {
  trade_id: string;
  wallet_id: string;
  signal_id?: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  volume: number;
  open_price: number;
  close_price: number;
  stop_loss?: number;
  take_profit?: number;
  pnl_usd: number;
  pnl_percent: number;
  pnl_pips: number;
  close_reason: string;
  open_time?: string;
  close_time?: string;
  duration_seconds: number;
}

export interface PaperEquitySnapshot {
  timestamp: string;
  balance: number;
  equity: number;
}

export interface EconomicEventItem {
  id: string;
  title: string;
  country: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW' | 'HOLIDAY';
  timeUtc: string;
  forecast: string;
  previous: string;
  actual: string;
  biasOnGold: string;
  note: string;
}

export interface NewsCalendarData {
  isBlackout: boolean;
  blackoutEvent: EconomicEventItem | null;
  nextHighImpactEvent: EconomicEventItem | null;
  minutesUntilNext: number | null;
  eventsCount: number;
  events: EconomicEventItem[];
  lastUpdated: string;
}

export interface BroadcastNewsPayload {
  title: string;
  country?: string;
  impact?: string;
  forecast?: string;
  previous?: string;
  bias_direction?: string;
  reasoning?: string;
  custom_note?: string;
}

export interface TelegramStatusData {
  enabled: boolean;
  isConfigured: boolean;
  chatId: string;
  totalSent: number;
  totalFailed: number;
}

export interface AINewsSettings {
  openai_configured: boolean;
  openai_key_masked: string;
  openai_model: string;
  auto_post_enabled: boolean;
  morning_time: string;
  auto_alert_red: boolean;
}

export interface NavItem {
  id: MenuId;
  label: string;
  badge?: string;
  phase?: string;
  icon?: string;
}


