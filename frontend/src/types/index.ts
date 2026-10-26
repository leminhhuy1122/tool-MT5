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
  modelVersion?: string;
  reason: string;
  invalidation: string;
  riskReward: number;
  confluences?: ConfluenceItem[];
  mfePoints?: number;
  maePoints?: number;
  pnlPoints?: number;
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

export type MenuId =
  | 'overview'
  | 'signals'
  | 'news'
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


