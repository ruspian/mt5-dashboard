"use client";

import type { AccountSnapshot } from "@/lib/types";

function fmt(n: number, currency: string) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(n);
}

export function AccountSummary({ account }: { account: AccountSnapshot | null }) {
  if (!account) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-bg-panel p-4 h-20 animate-pulse" />
        ))}
      </div>
    );
  }

  const profitPositive = account.profit >= 0;

  const cells = [
    { label: "Balance", value: fmt(account.balance, account.currency) },
    { label: "Equity", value: fmt(account.equity, account.currency) },
    {
      label: "Floating P/L",
      value: fmt(account.profit, account.currency),
      tone: profitPositive ? "profit" : "loss",
    },
    {
      label: "Margin Level",
      value: account.margin_level ? `${account.margin_level.toFixed(1)}%` : "—",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-line rounded overflow-hidden">
      {cells.map((c) => (
        <div key={c.label} className="bg-bg-panel p-4">
          <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-1.5">
            {c.label}
          </div>
          <div
            className={`text-lg font-semibold font-mono-num ${
              c.tone === "profit"
                ? "text-profit"
                : c.tone === "loss"
                ? "text-loss"
                : "text-text-primary"
            }`}
          >
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}
