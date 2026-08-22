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
}
