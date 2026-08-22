"use client";

import { useState } from "react";
import { bridgeApi } from "@/lib/bridge-client";

export function OrderTerminal() {
  const [symbol, setSymbol] = useState("EURUSD");
  const [volume, setVolume] = useState("0.01");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [submitting, setSubmitting] = useState<"BUY" | "SELL" | null>(null);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  async function submit(orderType: "BUY" | "SELL") {
    setSubmitting(orderType);
    setFeedback(null);
    try {
      const res = await bridgeApi.openOrder({
        symbol: symbol.trim().toUpperCase(),
        volume: parseFloat(volume),
        order_type: orderType,
        sl: sl ? parseFloat(sl) : undefined,
        tp: tp ? parseFloat(tp) : undefined,
      });
      setFeedback({ ok: true, message: `Order terbuka #${res.ticket} @ ${res.price}` });
    } catch (e) {
      setFeedback({ ok: false, message: e instanceof Error ? e.message : "Order gagal" });
    }
    setSubmitting(null);
  }

  return (
    <div className="bg-bg-panel border border-line rounded p-4">
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-3">
        Buka Posisi
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-[11px] text-text-tertiary mb-1">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-full bg-bg-panel-raised border border-line rounded px-2.5 py-1.5 text-sm font-mono-num text-text-primary focus:outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-[11px] text-text-tertiary mb-1">Lot</label>
          <input
            value={volume}
            onChange={(e) => setVolume(e.target.value)}
            type="number"
            step="0.01"
            min="0.01"
            className="w-full bg-bg-panel-raised border border-line rounded px-2.5 py-1.5 text-sm font-mono-num text-text-primary focus:outline-none focus:border-accent"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[11px] text-text-tertiary mb-1">SL (opsional)</label>
            <input
              value={sl}
              onChange={(e) => setSl(e.target.value)}
              type="number"
              step="0.00001"
              placeholder="—"
              className="w-full bg-bg-panel-raised border border-line rounded px-2.5 py-1.5 text-sm font-mono-num text-text-primary focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="block text-[11px] text-text-tertiary mb-1">TP (opsional)</label>
            <input
              value={tp}
              onChange={(e) => setTp(e.target.value)}
              type="number"
              step="0.00001"
              placeholder="—"
              className="w-full bg-bg-panel-raised border border-line rounded px-2.5 py-1.5 text-sm font-mono-num text-text-primary focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            onClick={() => submit("BUY")}
            disabled={submitting !== null}
            className="py-2.5 rounded text-sm font-semibold bg-profit-dim/40 hover:bg-profit-dim/60 text-profit border border-profit-dim transition-colors disabled:opacity-40"
          >
            {submitting === "BUY" ? "..." : "Buy"}
          </button>
          <button
            onClick={() => submit("SELL")}
            disabled={submitting !== null}
            className="py-2.5 rounded text-sm font-semibold bg-loss-dim/40 hover:bg-loss-dim/60 text-loss border border-loss-dim transition-colors disabled:opacity-40"
          >
            {submitting === "SELL" ? "..." : "Sell"}
          </button>
        </div>

        {feedback && (
          <p
            className={`text-xs font-mono-num pt-1 ${
              feedback.ok ? "text-profit" : "text-loss"
            }`}
          >
            {feedback.message}
          </p>
        )}
      </div>
    </div>
  );
}
