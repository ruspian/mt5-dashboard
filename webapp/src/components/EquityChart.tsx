"use client";

import { useEffect, useState, useRef } from "react";
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import type { AccountSnapshot } from "@/lib/types";

interface Point {
  t: number;
  equity: number;
}

const MAX_POINTS = 200;

export function EquityChart({ account }: { account: AccountSnapshot | null }) {
  const [points, setPoints] = useState<Point[]>([]);
  const lastLogged = useRef(0);

  useEffect(() => {
    if (!account) return;
    const now = Date.now();
    // simpan 1 titik tiap ~3 detik biar chart tidak terlalu padat
    if (now - lastLogged.current < 3000) return;
    lastLogged.current = now;
    setPoints((prev) => {
      const next = [...prev, { t: now, equity: account.equity }];
      return next.slice(-MAX_POINTS);
    });
  }, [account]);

  if (points.length < 2) {
    return (
      <div className="bg-bg-panel border border-line rounded p-4 h-56 flex items-center justify-center">
        <p className="text-xs text-text-tertiary font-mono-num">
          Mengumpulkan data equity...
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
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-3">
        Equity (sesi berjalan)
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
              labelFormatter={() => ""}
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
