"use client";

import { useEffect, useState } from "react";
import { bridgeApi } from "@/lib/bridge-client";
import type { TradeSignal } from "@/lib/types";

export function SignalHistoryTable() {
  const [signals, setSignals] = useState<TradeSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    bridgeApi
      .getSignalHistory()
      .then((res) => {
        if (!cancelled) setSignals(res);
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
      <div className="px-4 py-2.5 border-b border-line">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
          Riwayat Sinyal
        </span>
      </div>

      <div className="max-h-72 overflow-y-auto">
        {loading && <p className="text-xs text-text-tertiary font-mono-num p-4">Memuat...</p>}

        {!loading && signals.length === 0 && (
          <p className="text-xs text-text-tertiary p-4">Belum ada riwayat sinyal.</p>
        )}

        {!loading && signals.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Waktu</th>
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Arah</th>
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Entry</th>
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">SL</th>
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">TP1</th>
                <th className="px-4 py-2 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="px-4 py-2 font-mono-num text-text-secondary text-xs whitespace-nowrap">
                    {new Date(s.time).toLocaleString("id-ID")}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`text-xs font-mono-num px-1.5 py-0.5 rounded ${
                        s.direction === "BUY"
                          ? "text-profit bg-profit-dim/25"
                          : "text-loss bg-loss-dim/25"
                      }`}
                    >
                      {s.direction}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono-num text-text-primary text-right">{s.entry_price}</td>
                  <td className="px-4 py-2 font-mono-num text-loss text-right">{s.sl}</td>
                  <td className="px-4 py-2 font-mono-num text-profit text-right">{s.tp1}</td>
                  <td className="px-4 py-2 text-xs text-text-tertiary">
                    {s.executed ? "Tereksekusi" : "Skip"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
