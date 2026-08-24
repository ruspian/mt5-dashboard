"use client";

import { useEffect, useState, useCallback } from "react";
import type { JournalTrade, JournalStats, TradeSource } from "@/lib/types";
import { bridgeApi } from "@/lib/bridge-client";
import { JournalFilters } from "./JournalFilters";
import { JournalStatsCards } from "./JournalStatsCards";
import { BestWorstTrades } from "./BestWorstTrades";
import { DailyBreakdownTable } from "./DailyBreakdownTable";
import { JournalTradesTable } from "./JournalTradesTable";

export function JournalPanel() {
  const [days, setDays] = useState(30);
  const [source, setSource] = useState<TradeSource | "all">("all");
  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const sourceParam = source === "all" ? undefined : source;
      const [tradesRes, statsRes] = await Promise.all([
        bridgeApi.getJournalTrades(days, sourceParam),
        bridgeApi.getJournalStats(days, sourceParam),
      ]);
      setTrades(tradesRes);
      setStats(statsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat trade journal");
    }
    setLoading(false);
  }, [days, source]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <JournalFilters days={days} source={source} onDaysChange={setDays} onSourceChange={setSource} />

      {error && (
        <div className="text-sm px-3 py-2.5 rounded border border-loss-dim bg-loss-dim/20 text-loss">
          {error}
        </div>
      )}

      <JournalStatsCards stats={loading ? null : stats} />

      {stats && (stats.best_trade || stats.worst_trade) && (
        <BestWorstTrades best={stats.best_trade} worst={stats.worst_trade} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="bg-bg-panel border border-line rounded p-8 text-center">
              <p className="text-sm text-text-tertiary">Memuat trade journal...</p>
            </div>
          ) : (
            <JournalTradesTable trades={trades} />
          )}
        </div>
        <div>{stats && <DailyBreakdownTable days={stats.daily_breakdown} />}</div>
      </div>
    </div>
  );
}
