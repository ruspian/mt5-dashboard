"use client";

import { useState } from "react";
import type { Position } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";

export function PositionsTable({ positions }: { positions: Position[] }) {
  const [closingTicket, setClosingTicket] = useState<number | null>(null);

  async function handleClose(ticket: number) {
    setClosingTicket(ticket);
    try {
      await bridgeApi.closePosition(ticket);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Gagal menutup posisi");
    }
    setClosingTicket(null);
  }

  if (positions.length === 0) {
    return (
      <div className="bg-bg-panel border border-line rounded p-8 text-center">
        <p className="text-sm text-text-tertiary">Tidak ada posisi terbuka.</p>
      </div>
    );
  }

  return (
    <div className="bg-bg-panel border border-line rounded overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left">
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Symbol</th>
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium">Tipe</th>
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Lot</th>
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Open</th>
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">Sekarang</th>
            <th className="px-4 py-2.5 text-[11px] uppercase tracking-wide text-text-tertiary font-medium text-right">P/L</th>
            <th className="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.ticket} className="border-b border-line last:border-0">
              <td className="px-4 py-2.5 font-mono-num text-text-primary">{p.symbol}</td>
              <td className="px-4 py-2.5">
                <span
                  className={`text-xs font-mono-num px-1.5 py-0.5 rounded ${
                    p.type === "BUY"
                      ? "text-profit bg-profit-dim/25"
                      : "text-loss bg-loss-dim/25"
                  }`}
                >
                  {p.type}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{p.volume}</td>
              <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{p.price_open}</td>
              <td className="px-4 py-2.5 text-right font-mono-num text-text-secondary">{p.price_current}</td>
              <td
                className={`px-4 py-2.5 text-right font-mono-num font-semibold ${
                  p.profit >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                {p.profit >= 0 ? "+" : ""}
                {p.profit.toFixed(2)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <button
                  onClick={() => handleClose(p.ticket)}
                  disabled={closingTicket === p.ticket}
                  className="text-xs text-text-tertiary hover:text-loss border border-line hover:border-loss-dim px-2 py-1 rounded transition-colors disabled:opacity-40"
                >
                  {closingTicket === p.ticket ? "..." : "Tutup"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
