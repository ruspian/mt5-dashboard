"use client";

import type { JournalTrade } from "@/lib/types";

const sourceBadge: Record<string, string> = {
  manual: "text-text-secondary bg-bg-panel-raised",
  ea: "text-accent bg-accent-dim/25",
  signal: "text-text-primary bg-line",
};

const sourceLabel: Record<string, string> = {
  manual: "Manual",
  ea: "EA",
  signal: "Signal",
};

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours < 24) return `${hours}j ${mins}m`;
  const days = Math.floor(hours / 24);
  return `${days}h ${hours % 24}j`;
}

export function JournalTradesTable({ trades }: { trades: JournalTrade[] }) {
  if (trades.length === 0) {
    return (
      <div className="bg-bg-panel border border-line rounded p-8 text-center">
        <p className="text-sm text-text-tertiary">Belum ada trade closed pada rentang waktu ini.</p>
      </div>
    );
  }

  return (
    <div className="bg-bg-panel border border-line rounded overflow-hidden">
      <div className="max-h-[480px] overflow-y-auto overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-bg-panel-raised z-10">
            <tr className="border-b border-line text-left">
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium whitespace-nowrap">Ditutup</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Sumber</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Symbol</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Arah</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Lot</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Entry</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Exit</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Durasi</th>
              <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Net P/L</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.position_id} className="border-b border-line last:border-0">
                <td className="px-4 py-2.5 font-mono-num text-text-secondary text-xs whitespace-nowrap">
                  {new Date(t.close_time).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                </td>
                <td className="px-4 py-2.5">
                  <span className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded ${sourceBadge[t.source]}`}>
                    {sourceLabel[t.source]}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono-num text-text-primary">{t.symbol}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`text-xs font-mono-num px-1.5 py-0.5 rounded ${
                      t.direction === "BUY" ? "text-profit bg-profit-dim/25" : "text-loss bg-loss-dim/25"
                    }`}
                  >
                    {t.direction}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{t.volume}</td>
                <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{t.entry_price}</td>
                <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{t.exit_price}</td>
                <td className="px-4 py-2.5 text-right font-mono-num text-text-tertiary text-xs">
                  {formatDuration(t.duration_minutes)}
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-mono-num font-semibold ${
                    t.net_profit >= 0 ? "text-profit" : "text-loss"
                  }`}
                >
                  {t.net_profit >= 0 ? "+" : ""}
                  {t.net_profit.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2 border-t border-line text-[11px] text-text-tertiary font-mono-num">
        {trades.length} trade
      </div>
    </div>
  );
}
