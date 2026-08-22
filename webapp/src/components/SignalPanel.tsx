"use client";

import { useState } from "react";
import type { SignalEngineStatus } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";

function PriceRow({ label, value, tone }: { label: string; value: number; tone?: "sl" | "tp" | "entry" }) {
  const color =
    tone === "sl" ? "text-loss" : tone === "tp" ? "text-profit" : "text-text-primary";
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-line last:border-0">
      <span className="text-xs text-text-tertiary">{label}</span>
      <span className={`text-sm font-mono-num font-semibold ${color}`}>{value}</span>
    </div>
  );
}

export function SignalPanel({ signalEngine }: { signalEngine: SignalEngineStatus | null }) {
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const sig = signalEngine?.last_signal ?? null;
  const isEnabled = signalEngine?.enabled ?? true;

  async function handleEmergencyStop() {
    setPending(true);
    setFeedback(null);
    try {
      const res = await bridgeApi.emergencyStop();
      const n = res.closed_positions?.length ?? 0;
      setFeedback(n > 0 ? `Dihentikan. ${n} posisi ditutup.` : "Signal engine dihentikan.");
    } catch (e) {
      setFeedback(e instanceof Error ? e.message : "Gagal menghentikan");
    }
    setPending(false);
    setConfirming(false);
  }

  async function handleResume() {
    setPending(true);
    setFeedback(null);
    try {
      await bridgeApi.resumeSignalEngine();
      setFeedback("Signal engine diaktifkan kembali.");
    } catch (e) {
      setFeedback(e instanceof Error ? e.message : "Gagal mengaktifkan");
    }
    setPending(false);
  }

  return (
    <div className="space-y-4">
      {/* Status bar + tombol darurat */}
      <div className="bg-bg-panel border border-line rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
            Signal Engine
          </span>
          <span
            className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded ${
              isEnabled ? "text-profit bg-profit-dim/30" : "text-loss bg-loss-dim/30"
            }`}
          >
            {isEnabled ? "AKTIF" : "DIHENTIKAN"}
          </span>
        </div>

        {signalEngine?.config && (
          <p className="text-xs text-text-secondary mb-3 font-mono-num">
            {signalEngine.config.symbol} · {signalEngine.config.timeframe} ·{" "}
            {signalEngine.config.auto_execute ? "auto-eksekusi ON" : "rekomendasi saja"} · lot{" "}
            {signalEngine.config.lot_size}
          </p>
        )}

        {signalEngine?.last_error && (
          <p className="text-xs text-loss mb-3 font-mono-num">{signalEngine.last_error}</p>
        )}

        {!isEnabled ? (
          <button
            onClick={handleResume}
            disabled={pending}
            className="w-full py-2.5 rounded text-sm font-semibold bg-profit-dim/40 hover:bg-profit-dim/60 text-profit border border-profit-dim transition-colors disabled:opacity-40"
          >
            {pending ? "Memproses..." : "Aktifkan Kembali"}
          </button>
        ) : confirming ? (
          <div className="space-y-2">
            <p className="text-xs text-loss font-medium">
              Yakin? Ini akan menutup semua posisi dari signal engine dan menghentikan auto-entry.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setConfirming(false)}
                className="py-2 rounded text-xs border border-line text-text-secondary hover:bg-bg-panel-raised transition-colors"
              >
                Batal
              </button>
              <button
                onClick={handleEmergencyStop}
                disabled={pending}
                className="py-2 rounded text-xs font-semibold bg-loss text-bg-base hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                {pending ? "..." : "Ya, Hentikan"}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="w-full py-3 rounded text-sm font-bold bg-loss/90 hover:bg-loss text-bg-base transition-colors tracking-wide"
          >
            ⏹ STOP DARURAT
          </button>
        )}

        {feedback && <p className="text-xs text-text-secondary mt-2 font-mono-num">{feedback}</p>}
      </div>

      {/* Sinyal terbaru */}
      <div className="bg-bg-panel border border-line rounded p-4">
        <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-3">
          Sinyal Terbaru
        </div>

        {!sig ? (
          <p className="text-sm text-text-tertiary py-4 text-center">
            Belum ada sinyal. Menunggu kondisi pasar yang sesuai.
          </p>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-3">
              <span
                className={`text-sm font-bold px-2 py-1 rounded ${
                  sig.direction === "BUY"
                    ? "text-profit bg-profit-dim/25"
                    : "text-loss bg-loss-dim/25"
                }`}
              >
                {sig.direction} {sig.symbol}
              </span>
              <span
                className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded ${
                  sig.executed
                    ? "text-profit bg-profit-dim/30"
                    : "text-text-tertiary bg-bg-panel-raised"
                }`}
              >
                {sig.executed ? "Tereksekusi" : "Belum dieksekusi"}
              </span>
            </div>

            <div className="mb-3">
              <PriceRow label="Entry" value={sig.entry_price} tone="entry" />
              <PriceRow label="Stop Loss" value={sig.sl} tone="sl" />
              <PriceRow label="Take Profit 1" value={sig.tp1} tone="tp" />
              <PriceRow label="Take Profit 2" value={sig.tp2} tone="tp" />
              <PriceRow label="Take Profit 3" value={sig.tp3} tone="tp" />
            </div>

            <p className="text-xs text-text-secondary leading-relaxed border-t border-line pt-2">
              {sig.reason}
            </p>

            <p className="text-[11px] text-text-tertiary leading-relaxed mt-2">
              Order dikirim dengan TP di level TP3. Saat harga menyentuh TP1, sebagian posisi otomatis ditutup dan SL sisanya dipindah ke breakeven. Saat menyentuh TP2, sisa posisi beralih ke trailing stop.
            </p>

            {sig.execution_detail && (
              <p className="text-xs text-text-tertiary font-mono-num mt-2">{sig.execution_detail}</p>
            )}

            <p className="text-[11px] text-text-tertiary font-mono-num mt-2">
              {new Date(sig.time).toLocaleString("id-ID")}
            </p>
          </div>
        )}

        {signalEngine?.last_check_time && (
          <p className="text-[11px] text-text-tertiary font-mono-num mt-3 pt-2 border-t border-line">
            Cek terakhir: {new Date(signalEngine.last_check_time).toLocaleTimeString("id-ID")}
          </p>
        )}
      </div>

      {/* Progress manajemen posisi berjalan */}
      {signalEngine?.tracked_positions && signalEngine.tracked_positions.length > 0 && (
        <div className="bg-bg-panel border border-line rounded p-4">
          <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-3">
            Manajemen Posisi Berjalan
          </div>
          <div className="space-y-3">
            {signalEngine.tracked_positions.map((tp) => (
              <div key={tp.ticket} className="border border-line rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono-num text-text-secondary">
                    #{tp.ticket} · {tp.direction}
                  </span>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <StageBadge label="TP1 → Partial + BE" done={tp.partial_done && tp.breakeven_done} />
                  <StageBadge label="TP2 → Trailing" done={tp.trailing_active} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StageBadge({ label, done }: { label: string; done: boolean }) {
  return (
    <span
      className={`text-[11px] font-mono-num px-2 py-1 rounded border ${
        done
          ? "text-profit bg-profit-dim/25 border-profit-dim"
          : "text-text-tertiary bg-bg-panel-raised border-line"
      }`}
    >
      {done ? "✓" : "○"} {label}
    </span>
  );
}
