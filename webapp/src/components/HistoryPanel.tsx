"use client";

import { useEffect, useState } from "react";
import { bridgeApi } from "@/lib/bridge-client";
import type { HistoryResponse } from "@/lib/types";

type Tab = "trades" | "balance";

export function HistoryPanel() {
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [tab, setTab] = useState<Tab>("trades");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    bridgeApi
      .getHistory(30)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="bg-bg-panel border border-line rounded overflow-hidden">
      <div className="flex border-b border-line">
        <button
          onClick={() => setTab("trades")}
          className={`px-4 py-2.5 text-xs font-medium transition-colors ${
            tab === "trades"
              ? "text-text-primary border-b-2 border-accent -mb-px"
              : "text-text-tertiary hover:text-text-secondary"
          }`}
        >
          Riwayat Transaksi
        </button>
        <button
          onClick={() => setTab("balance")}
          className={`px-4 py-2.5 text-xs font-medium transition-colors ${
            tab === "balance"
              ? "text-text-primary border-b-2 border-accent -mb-px"
              : "text-text-tertiary hover:text-text-secondary"
          }`}
        >
          Deposit &amp; Penarikan
        </button>
      </div>

      <div className="max-h-72 overflow-y-auto">
        {loading && (
          <p className="text-xs text-text-tertiary font-mono-num p-4">Memuat...</p>
        )}

        {!loading && tab === "trades" && (
          <TradesTable trades={data?.trades || []} />
        )}
        {!loading && tab === "balance" && (
          <BalanceOpsTable ops={data?.balance_ops || []} />
        )}
      </div>
    </div>
  );
}

function TradesTable({ trades }: { trades: HistoryResponse["trades"] }) {
  if (trades.length === 0) {
    return <p className="text-xs text-text-tertiary p-4">Belum ada riwayat transaksi 30 hari terakhir.</p>;
  }
  return (
    <table className="w-full text-sm">
      <tbody>
        {trades
          .slice()
          .reverse()
          .map((t) => (
            <tr key={t.ticket} className="border-b border-line last:border-0">
              <td className="px-4 py-2 font-mono-num text-text-secondary text-xs whitespace-nowrap">
                {new Date(t.time).toLocaleString("id-ID")}
              </td>
              <td className="px-4 py-2 font-mono-num text-text-primary">{t.symbol}</td>
              <td className="px-4 py-2 font-mono-num text-text-secondary text-right">{t.volume}</td>
              <td
                className={`px-4 py-2 font-mono-num text-right font-semibold ${
                  t.profit >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                {t.profit >= 0 ? "+" : ""}
                {t.profit.toFixed(2)}
              </td>
            </tr>
          ))}
      </tbody>
    </table>
  );
}

function BalanceOpsTable({ ops }: { ops: HistoryResponse["balance_ops"] }) {
  if (ops.length === 0) {
    return <p className="text-xs text-text-tertiary p-4">Belum ada deposit/penarikan 30 hari terakhir.</p>;
  }
  return (
    <table className="w-full text-sm">
      <tbody>
        {ops
          .slice()
          .reverse()
          .map((op) => (
            <tr key={op.ticket} className="border-b border-line last:border-0">
              <td className="px-4 py-2 font-mono-num text-text-secondary text-xs whitespace-nowrap">
                {new Date(op.time).toLocaleString("id-ID")}
              </td>
              <td className="px-4 py-2">
                <span
                  className={`text-xs font-mono-num px-1.5 py-0.5 rounded ${
                    op.kind === "DEPOSIT"
                      ? "text-profit bg-profit-dim/25"
                      : "text-loss bg-loss-dim/25"
                  }`}
                >
                  {op.kind === "DEPOSIT" ? "Deposit" : "Penarikan"}
                </span>
              </td>
              <td className="px-4 py-2 text-text-secondary text-xs">{op.comment}</td>
              <td
                className={`px-4 py-2 font-mono-num text-right font-semibold ${
                  op.profit >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                {op.profit >= 0 ? "+" : ""}
                {op.profit.toFixed(2)}
              </td>
            </tr>
          ))}
      </tbody>
    </table>
  );
}
