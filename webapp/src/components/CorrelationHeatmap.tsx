"use client";

import { useEffect, useState, type CSSProperties } from "react";
import type { CorrelationStatus } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";

// Poll tiap 5 menit — data korelasi dihitung dari harga harian (EOD),
// jadi tidak perlu di-refresh secepat data akun/posisi yang lewat WS.
const POLL_INTERVAL_MS = 5 * 60 * 1000;

const PROFIT_RGB = "79, 174, 122"; // var(--profit)
const LOSS_RGB = "194, 91, 82"; // var(--loss)

function cellStyle(value: number | null): CSSProperties {
  if (value === null) {
    return { background: "transparent", color: "var(--text-tertiary)" };
  }
  const abs = Math.min(Math.abs(value), 1);
  const alpha = 0.12 + abs * 0.55;
  const rgb = value >= 0 ? PROFIT_RGB : LOSS_RGB;
  return {
    background: `rgba(${rgb}, ${alpha})`,
    color: abs > 0.45 ? "#f5f2ea" : "var(--text-secondary)",
  };
}

export function CorrelationHeatmap() {
  const [data, setData] = useState<CorrelationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      bridgeApi
        .getCorrelation()
        .then((res) => {
          if (!cancelled) {
            setData(res);
            setError(null);
          }
        })
        .catch((e) => {
          if (!cancelled) setError(e instanceof Error ? e.message : "Gagal memuat korelasi");
        });
    };
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!data?.enabled) return null;

  const matrix = data.matrix;

  return (
    <div className="bg-bg-panel border border-line rounded p-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
          Korelasi Aset (XAUUSD vs DXY &amp; lainnya)
        </span>
        {matrix && (
          <span className="text-[10px] text-text-tertiary font-mono-num">
            {matrix.period_days}d return
          </span>
        )}
      </div>

      {error && !matrix && (
        <p className="text-[11px] text-loss mt-3">Gagal memuat heatmap: {error}</p>
      )}

      {data.last_error && (
        <p className="text-[11px] text-loss mt-2 leading-relaxed">
          Peringatan: refresh terakhir gagal ({data.last_error}). Menampilkan data terakhir yang berhasil diambil (kalau ada).
        </p>
      )}

      {!matrix && !error && (
        <p className="text-xs text-text-tertiary font-mono-num mt-3">Menghitung korelasi...</p>
      )}

      {matrix && (
        <div className="overflow-x-auto mt-3">
          <table className="border-collapse text-[10px] font-mono-num">
            <thead>
              <tr>
                <th className="p-1"></th>
                {matrix.assets.map((a) => (
                  <th
                    key={a}
                    className="p-1 text-text-tertiary font-normal align-bottom whitespace-nowrap"
                    style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", maxHeight: 80 }}
                  >
                    {a}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.assets.map((rowLabel, i) => (
                <tr key={rowLabel}>
                  <td className="p-1 pr-2 text-text-tertiary whitespace-nowrap text-right">{rowLabel}</td>
                  {matrix.matrix[i].map((val, j) => (
                    <td
                      key={j}
                      title={`${rowLabel} vs ${matrix.assets[j]}: ${val === null ? "n/a" : val.toFixed(2)}`}
                      className="p-1 text-center w-11 h-8 rounded-[2px]"
                      style={cellStyle(val)}
                    >
                      {val === null ? "–" : val.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[10px] text-text-tertiary leading-relaxed mt-3">
        Dihitung dari korelasi return harian ({matrix?.period_days ?? "-"} hari terakhir). Hijau = korelasi
        positif, merah = negatif. Emas biasanya berkorelasi negatif dengan DXY — kalau angka itu mendekati 0
        atau berbalik positif, artinya hubungan itu sedang melemah/decoupling.
      </p>
    </div>
  );
}
