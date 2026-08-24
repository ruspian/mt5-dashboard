"use client";

import type { DailyBreakdown } from "@/lib/types";

export function DailyBreakdownTable({ days }: { days: DailyBreakdown[] }) {
  if (days.length === 0) return null;

  const maxAbsProfit = Math.max(...days.map((d) => Math.abs(d.net_profit)), 1);

  return (
    <div className="bg-bg-panel border border-line rounded overflow-hidden">
      <div className="px-4 py-2.5 border-b border-line">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">Breakdown Harian</span>
      </div>
      <div className="divide-y divide-line max-h-80 overflow-y-auto">
        {days.map((d) => {
          const barWidth = (Math.abs(d.net_profit) / maxAbsProfit) * 100;
          const isProfit = d.net_profit >= 0;
          return (
            <div key={d.date} className="px-4 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-mono-num text-text-secondary">
                  {new Date(d.date).toLocaleDateString("id-ID", { weekday: "short", day: "2-digit", month: "short" })}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono-num text-text-tertiary">
                    {d.wins}W / {d.losses}L
                  </span>
                  <span className={`text-sm font-mono-num font-semibold ${isProfit ? "text-profit" : "text-loss"}`}>
                    {isProfit ? "+" : ""}
                    {d.net_profit.toFixed(2)}
                  </span>
                </div>
              </div>
              <div className="h-1.5 bg-bg-panel-raised rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isProfit ? "bg-profit" : "bg-loss"}`}
                  style={{ width: `${Math.max(barWidth, 2)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
