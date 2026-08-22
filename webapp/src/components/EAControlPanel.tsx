"use client";

import { useState } from "react";
import type { EAStatus } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";

export function EAControlPanel({ ea }: { ea: EAStatus | null }) {
  const [pending, setPending] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const isRunning = ea?.signal !== "STOP";

  async function toggle() {
    setPending(true);
    setErrorMsg(null);
    try {
      await bridgeApi.controlEA(isRunning ? "STOP" : "START");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Gagal mengirim perintah");
    }
    setPending(false);
  }

  return (
    <div className="bg-bg-panel border border-line rounded p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
          Kontrol Bot (EA)
        </span>
        <span
          className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded ${
            isRunning
              ? "text-profit bg-profit-dim/30"
              : "text-loss bg-loss-dim/30"
          }`}
        >
          {ea?.status || "—"}
        </span>
      </div>

      {ea?.detail && (
        <p className="text-xs text-text-secondary mb-3 leading-relaxed">
          {ea.detail}
        </p>
      )}

      <button
        onClick={toggle}
        disabled={pending || !ea}
        className={`w-full py-2.5 rounded text-sm font-semibold transition-colors disabled:opacity-40 ${
          isRunning
            ? "bg-loss-dim/40 hover:bg-loss-dim/60 text-loss border border-loss-dim"
            : "bg-profit-dim/40 hover:bg-profit-dim/60 text-profit border border-profit-dim"
        }`}
      >
        {pending ? "Mengirim perintah..." : isRunning ? "Hentikan Bot" : "Jalankan Bot"}
      </button>

      {errorMsg && (
        <p className="text-xs text-loss mt-2 font-mono-num">{errorMsg}</p>
      )}

      {ea?.last_update && (
        <p className="text-[11px] text-text-tertiary mt-3 font-mono-num">
          Update terakhir dari EA: {ea.last_update}
        </p>
      )}
    </div>
  );
}
