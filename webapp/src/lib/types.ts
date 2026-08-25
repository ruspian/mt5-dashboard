export interface AccountSnapshot {
  login: number;
  name: string;
  server: string;
  currency: string;
  leverage: number;
  balance: number;
  equity: number;
  profit: number;
  margin: number;
  margin_free: number;
  margin_level: number;
  timestamp: string;
}

export interface Position {
  ticket: number;
  symbol: string;
  type: "BUY" | "SELL";
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  profit: number;
  swap: number;
  magic: number;
  comment: string;
  time: string;
}

export interface TradeDeal {
  ticket: number;
  order: number;
  symbol: string;
  volume: number;
  price: number;
  profit: number;
  commission: number;
  swap: number;
  time: string;
  comment: string;
  type?: "BUY" | "SELL";
}

export interface BalanceOp {
  ticket: number;
  time: string;
  profit: number;
  comment: string;
  kind: "DEPOSIT" | "WITHDRAWAL";
}

export interface HistoryResponse {
  trades: TradeDeal[];
  balance_ops: BalanceOp[];
}

export interface EAStatus {
  status: string;
  last_update?: string | null;
  detail?: string | null;
  signal: "START" | "STOP" | string;
}

export interface ChartAnalysis {
  agree: boolean;
  confidence: number;
  reason: string;
  provider: string;
  error?: string | null;
}

export interface TradeSignal {
  time: string;
  symbol: string;
  direction: "BUY" | "SELL";
  entry_price: number;
  sl: number;
  tp1: number;
  tp2: number;
  tp3: number;
  reason: string;
  executed: boolean;
  execution_detail?: string | null;
  news_status?: "NORMAL" | "CALENDAR_BLACKOUT" | "HIGH_IMPACT_NEWS";
  news_reason?: string | null;
  lot_used?: number | null;
  ai_analysis?: AIAnalysis | null;
  chart_analysis?: ChartAnalysis | null;
  confirmation_score?: number;
  confirmation_details?: string[];
}

export interface CalendarEvent {
  event: string;
  country: string;
  time: string;
  impact: string;
  actual?: string | null;
  estimate?: string | null;
  prev?: string | null;
}

export interface NewsItem {
  headline: string;
  summary: string;
  source: string;
  time: string;
  url: string;
  matched_keywords: string[];
}

export interface AIAnalysis {
  relevant: boolean;
  sentiment: "bullish" | "bearish" | "neutral";
  confidence: number;
  reason: string;
  provider: string;
  error?: string | null;
}

export interface NewsContext {
  status: "NORMAL" | "CALENDAR_BLACKOUT" | "HIGH_IMPACT_NEWS";
  reason: string;
  active_calendar_event?: CalendarEvent | null;
  active_news?: NewsItem | null;
  ai_analysis?: AIAnalysis | null;
}

export interface NewsEngineStatus {
  enabled: boolean;
  last_fetch_time: string | null;
  last_error: string | null;
  current_context: NewsContext | null;
  upcoming_calendar?: CalendarEvent[];
  recent_news?: NewsItem[];
  calendar_running_low?: boolean;
  calendar_running_low_message?: string | null;
  all_news_sources_failed?: boolean;
}

export interface TrackedPosition {
  ticket: number;
  direction: "BUY" | "SELL";
  entry_price?: number;
  tp1: number;
  tp2: number;
  tp3: number;
  partial_done: boolean;
  breakeven_done: boolean;
  trailing_active: boolean;
}

export interface SignalEngineStatus {
  enabled: boolean;
  last_check_time: string | null;
  last_monitor_time?: string | null;
  last_error: string | null;
  last_signal: TradeSignal | null;
  tracked_positions?: TrackedPosition[];
  config?: {
    symbol: string;
    timeframe: string;
    auto_execute: boolean;
    lot_size: number;
    partial_close_percent?: number;
  };
}

export interface WSSnapshot {
  type: "snapshot";
  account: AccountSnapshot;
  positions: Position[];
  ea: EAStatus;
  signal_engine: SignalEngineStatus;
  news_engine: NewsEngineStatus;
}

export interface EquityHistoryPoint {
  time: string;
  balance: number;
  equity: number;
  profit: number;
}

export interface CorrelationMatrix {
  assets: string[];
  matrix: (number | null)[][];
  period_days: number;
  computed_at: string;
}

export interface CorrelationStatus {
  enabled: boolean;
  last_fetch_time: string | null;
  last_error: string | null;
  matrix: CorrelationMatrix | null;
}

export type TradeSource = "manual" | "ea" | "signal";

export interface JournalTrade {
  position_id: number;
  symbol: string;
  direction: "BUY" | "SELL";
  source: TradeSource;
  volume: number;
  entry_price: number;
  exit_price: number;
  open_time: string;
  close_time: string;
  duration_minutes: number;
  profit: number;
  commission: number;
  swap: number;
  net_profit: number;
  is_win: boolean;
  magic: number;
  comment: string;
}

export interface DailyBreakdown {
  date: string;
  trades: number;
  wins: number;
  losses: number;
  net_profit: number;
}

export interface JournalStats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_profit: number;
  total_loss: number;
  net_profit: number;
  average_win: number;
  average_loss: number;
  profit_factor: number | null;
  average_rr: number | null;
  best_trade: JournalTrade | null;
  worst_trade: JournalTrade | null;
  longest_win_streak: number;
  longest_loss_streak: number;
  current_streak: number;
  daily_breakdown: DailyBreakdown[];
  by_source: Record<TradeSource, { trades: number; wins: number; losses: number; win_rate: number; net_profit: number }>;
}
