"use client";

import type { TradeSource } from "@/lib/types";

const dayOptions = [
  { label: "7 Hari", value: 7 },
  { label: "30 Hari", value: 30 },
  { label: "90 Hari", value: 90 },
  { label: "1 Tahun", value: 365 },
];

const sourceOptions: { label: string; value: TradeSource | "all" }[] = [
  { label: "Semua", value: "all" },
  { label: "Manual", value: "manual" },
  { label: "EA", value: "ea" },
  { label: "Signal Engine", value: "signal" },
];

export function JournalFilters({
  days,
  source,
  onDaysChange,
  onSourceChange,
}: {
  days: number;
  source: TradeSource | "all";
  onDaysChange: (d: number) => void;
  onSourceChange: (s: TradeSource | "all") => void;
}) {
  return (
    <div className="flex flex-wrap gap-3 items-center">
      <div className="flex gap-1 bg-bg-panel border border-line rounded p-0.5">
        {dayOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onDaysChange(opt.value)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              days === opt.value
                ? "bg-bg-panel-raised text-text-primary"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="flex gap-1 bg-bg-panel border border-line rounded p-0.5">
        {sourceOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onSourceChange(opt.value)}
            className={`px-2.5 py-1 text-xs rounded transition-colors ${
              source === opt.value
                ? "bg-bg-panel-raised text-text-primary"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
