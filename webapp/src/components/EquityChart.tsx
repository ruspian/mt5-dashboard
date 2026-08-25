"use client";

import { useEffect, useState, useRef } from "react";
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import type { AccountSnapshot } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";

interface Point {
  t: number;
  equity: number;
}

const MAX_POINTS = 500;
const RANGE_HOURS = 24;

export function EquityChart({ account }: { account: AccountSnapshot | null }) {
  const [points, setPoints] = useState<Point[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const lastLogged = useRef(0);

  // Ambil riwayat equity yang sudah disimpan PERMANEN di sisi bridge
  // (SQLite) sekali saat komponen ini pertama kali render — jadi
  // grafik langsung terisi dengan data lama, bukan mulai dari kosong
  // tiap kali halaman di-refresh.
  useEffect(() => {
    let cancelled = false;
    bridgeApi
      .getEquityHistory(RANGE_HOURS)
      .then((history) => {
        if (cancelled) return;
        const historical = history.map((h) => ({ t: new Date(h.time).getTime(), equity: h.equity }));
        setPoints(historical.slice(-MAX_POINTS));
        setLoaded(true);
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError(e instanceof Error ? e.message : "Gagal memuat riwayat equity");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Setelah riwayat termuat, lanjutkan menambah titik baru secara live
  // dari data WebSocket yang mengalir tiap detik — disaring tiap ~3
  // detik biar chart tidak terlalu padat.
  useEffect(() => {
    if (!loaded || !account) return;
    const now = Date.now();
    if (now - lastLogged.current < 3000) return;
    lastLogged.current = now;
    setPoints((prev) => {
      const next = [...prev, { t: now, equity: account.equity }];
      return next.slice(-MAX_POINTS);
    });
  }, [account, loaded]);

  if (!loaded) {
    return (
      <div className="bg-bg-panel border border-line rounded p-4 h-56 flex items-center justify-center">
        <p className="text-xs text-text-tertiary font-mono-num">Memuat riwayat equity...</p>
      </div>
    );
  }

  if (points.length < 2) {
    return (
      <div className="bg-bg-panel border border-line rounded p-4 h-56 flex items-center justify-center">
        <p className="text-xs text-text-tertiary font-mono-num">
          {loadError
            ? `Gagal memuat riwayat (${loadError}). Mengumpulkan data baru...`
            : "Belum ada cukup data equity tersimpan. Mengumpulkan..."}
        </p>
      </div>
    );
  }

  const values = points.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = (max - min) * 0.1 || 1;

  return (
    <div className="bg-bg-panel border border-line rounded p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
          Equity ({RANGE_HOURS} jam terakhir, tersimpan permanen)
        </span>
        {loadError && (
          <span className="text-[10px] text-loss font-mono-num">Riwayat lama gagal dimuat</span>
        )}
      </div>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points}>
            <YAxis
              domain={[min - padding, max + padding]}
              hide
            />
            <Tooltip
              contentStyle={{
                background: "var(--bg-panel-raised)",
                border: "1px solid var(--line-strong)",
                borderRadius: 4,
                fontSize: 12,
                fontFamily: "var(--font-mono)",
              }}
              labelFormatter={(label) =>
                typeof label === "number" ? new Date(label).toLocaleString("id-ID") : ""
              }
              formatter={(value) => [Number(value).toFixed(2), "Equity"]}
            />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="var(--accent)"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
