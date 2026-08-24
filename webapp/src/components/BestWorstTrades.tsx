"use client";

import type { JournalTrade } from "@/lib/types";

const sourceLabel: Record<string, string> = {
  manual: "Manual",
  ea: "EA",
  signal: "Signal Engine",
};

function BestWorstCard({ trade, label, tone }: { trade: JournalTrade; label: string; tone: "profit" | "loss" }) {
  return (
    <div className="bg-bg-panel border border-line rounded p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">{label}</span>
        <span className="text-[11px] font-mono-num text-text-tertiary">{sourceLabel[trade.source]}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm font-mono-num text-text-primary">
          {trade.direction} {trade.symbol} · {trade.volume} lot
        </span>
        <span className={`text-lg font-semibold font-mono-num ${tone === "profit" ? "text-profit" : "text-loss"}`}>
          {trade.net_profit >= 0 ? "+" : ""}
          {trade.net_profit.toFixed(2)}
        </span>
      </div>
      <p className="text-[11px] text-text-tertiary font-mono-num mt-1">
        {new Date(trade.close_time).toLocaleString("id-ID")}
      </p>
    </div>
  );
}

export function BestWorstTrades({
  best,
  worst,
}: {
  best: JournalTrade | null;
  worst: JournalTrade | null;
}) {
  if (!best && !worst) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {best && <BestWorstCard trade={best} label="Trade Terbaik" tone="profit" />}
      {worst && <BestWorstCard trade={worst} label="Trade Terburuk" tone="loss" />}
    </div>
  );
}
