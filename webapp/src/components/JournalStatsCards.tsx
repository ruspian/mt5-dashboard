"use client";

import type { JournalStats } from "@/lib/types";

function StatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "profit" | "loss" | "neutral";
}) {
  return (
    <div className="bg-bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-1.5">{label}</div>
      <div
        className={`text-lg font-semibold font-mono-num ${
          tone === "profit" ? "text-profit" : tone === "loss" ? "text-loss" : "text-text-primary"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

export function JournalStatsCards({ stats }: { stats: JournalStats | null }) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-bg-panel p-4 h-20 animate-pulse" />
        ))}
      </div>
    );
  }

  if (stats.total_trades === 0) {
    return (
      <div className="bg-bg-panel border border-line rounded p-8 text-center">
        <p className="text-sm text-text-tertiary">Belum ada trade closed pada rentang waktu ini.</p>
      </div>
    );
  }

  return (
    <div className="space-y-px">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
        <StatCell label="Win Rate" value={`${stats.win_rate}%`} tone={stats.win_rate >= 50 ? "profit" : "loss"} />
        <StatCell label="Total Trade" value={`${stats.total_trades}`} />
        <StatCell
          label="Net Profit"
          value={`${stats.net_profit >= 0 ? "+" : ""}${stats.net_profit.toFixed(2)}`}
          tone={stats.net_profit >= 0 ? "profit" : "loss"}
        />
        <StatCell
          label="Profit Factor"
          value={stats.profit_factor !== null ? stats.profit_factor.toFixed(2) : "—"}
          tone={stats.profit_factor !== null ? (stats.profit_factor >= 1 ? "profit" : "loss") : "neutral"}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
        <StatCell label="Menang / Kalah" value={`${stats.wins} / ${stats.losses}`} />
        <StatCell label="Rata-rata Profit" value={`+${stats.average_win.toFixed(2)}`} tone="profit" />
        <StatCell label="Rata-rata Loss" value={`-${stats.average_loss.toFixed(2)}`} tone="loss" />
        <StatCell
          label="Avg Risk:Reward"
          value={stats.average_rr !== null ? `1:${stats.average_rr.toFixed(2)}` : "—"}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
        <StatCell
          label="Streak Saat Ini"
          value={
            stats.current_streak === 0
              ? "—"
              : stats.current_streak > 0
              ? `${stats.current_streak} menang`
              : `${Math.abs(stats.current_streak)} kalah`
          }
          tone={stats.current_streak > 0 ? "profit" : stats.current_streak < 0 ? "loss" : "neutral"}
        />
        <StatCell label="Win Streak Terpanjang" value={`${stats.longest_win_streak}`} tone="profit" />
        <StatCell label="Loss Streak Terpanjang" value={`${stats.longest_loss_streak}`} tone="loss" />
        <StatCell
          label="Total Profit / Loss"
          value={`+${stats.total_profit.toFixed(2)} / -${stats.total_loss.toFixed(2)}`}
        />
      </div>
    </div>
  );
}
