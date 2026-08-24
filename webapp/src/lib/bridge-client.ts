import type { AccountSnapshot, HistoryResponse, Position, EAStatus, SignalEngineStatus, TradeSignal, NewsEngineStatus, JournalTrade, JournalStats, TradeSource } from "./types";

/**
 * Semua fungsi di sini memanggil bridge lewat proxy server Next.js
 * (/api/bridge/...), BUKAN langsung ke VPS dari browser. URL bridge asli
 * dan token-nya cuma disimpan sebagai environment variable di server
 * (BRIDGE_URL, BRIDGE_TOKEN) — browser tidak pernah melihatnya.
 *
 * Login/logout dikelola lewat session cookie httpOnly (lihat /lib/session.ts
 * dan halaman /login). Kalau session tidak valid, proxy akan balas 401 dan
 * client mengarahkan user ke /login.
 */

class BridgeError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function bridgeFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/bridge${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new BridgeError(body.detail || `Request gagal (${res.status})`, res.status);
  }
  return res.json();
}

export const bridgeApi = {
  getAccount: () => bridgeFetch<AccountSnapshot>("/account"),
  getPositions: () => bridgeFetch<Position[]>("/positions"),
  getHistory: (days = 30) => bridgeFetch<HistoryResponse>(`/history?days=${days}`),
  getEAStatus: () => bridgeFetch<EAStatus>("/ea/status"),

  controlEA: (command: "START" | "STOP") =>
    bridgeFetch<{ ok: boolean; command: string }>("/ea/control", {
      method: "POST",
      body: JSON.stringify({ command }),
    }),

  openOrder: (params: {
    symbol: string;
    volume: number;
    order_type: "BUY" | "SELL";
    sl?: number;
    tp?: number;
    comment?: string;
  }) =>
    bridgeFetch<{ ok: boolean; ticket: number; price: number }>("/order/open", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  closePosition: (ticket: number) =>
    bridgeFetch<{ ok: boolean }>("/order/close", {
      method: "POST",
      body: JSON.stringify({ ticket }),
    }),

  getSignalStatus: () => bridgeFetch<SignalEngineStatus>("/signal/status"),
  getSignalHistory: () => bridgeFetch<TradeSignal[]>("/signal/history"),

  emergencyStop: () =>
    bridgeFetch<{ ok: boolean; closed_positions: unknown[] }>("/signal/emergency-stop", {
      method: "POST",
    }),

  resumeSignalEngine: () =>
    bridgeFetch<{ ok: boolean }>("/signal/resume", {
      method: "POST",
    }),

  getNewsStatus: () => bridgeFetch<NewsEngineStatus>("/news/status"),

  getJournalTrades: (days = 90, source?: TradeSource) =>
    bridgeFetch<JournalTrade[]>(`/journal/trades?days=${days}${source ? `&source=${source}` : ""}`),

  getJournalStats: (days = 90, source?: TradeSource) =>
    bridgeFetch<JournalStats>(`/journal/stats?days=${days}${source ? `&source=${source}` : ""}`),
};

export { BridgeError };
