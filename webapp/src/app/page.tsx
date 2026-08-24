"use client";

import { useState } from "react";
import { useLiveData } from "@/lib/use-live-data";
import { TopBar } from "@/components/TopBar";
import { AccountSummary } from "@/components/AccountSummary";
import { EquityChart } from "@/components/EquityChart";
import { EAControlPanel } from "@/components/EAControlPanel";
import { OrderTerminal } from "@/components/OrderTerminal";
import { PositionsTable } from "@/components/PositionsTable";
import { HistoryPanel } from "@/components/HistoryPanel";
import { SignalPanel } from "@/components/SignalPanel";
import { SignalHistoryTable } from "@/components/SignalHistoryTable";
import { NewsPanel } from "@/components/NewsPanel";
import { JournalPanel } from "@/components/JournalPanel";

type Tab = "terminal" | "signal" | "journal";

export default function DashboardPage() {
  const { snapshot, status } = useLiveData();
  const [tab, setTab] = useState<Tab>("terminal");

  return (
    <div className="flex-1 flex flex-col bg-bg-base">
      <TopBar account={snapshot?.account ?? null} wsStatus={status} />

      <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-6 space-y-6">
        <AccountSummary account={snapshot?.account ?? null} />

        <div className="flex gap-1 border-b border-line">
          <button
            onClick={() => setTab("terminal")}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === "terminal"
                ? "text-text-primary border-b-2 border-accent -mb-px"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            Terminal
          </button>
          <button
            onClick={() => setTab("signal")}
            className={`px-4 py-2.5 text-sm font-medium transition-colors flex items-center gap-2 ${
              tab === "signal"
                ? "text-text-primary border-b-2 border-accent -mb-px"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            Signal Trading
            {snapshot?.signal_engine && !snapshot.signal_engine.enabled && (
              <span className="w-1.5 h-1.5 rounded-full bg-loss" />
            )}
          </button>
          <button
            onClick={() => setTab("journal")}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              tab === "journal"
                ? "text-text-primary border-b-2 border-accent -mb-px"
                : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            Journal
          </button>
        </div>

        {tab === "terminal" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <EquityChart account={snapshot?.account ?? null} />

              <div>
                <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-2">
                  Posisi Terbuka
                </div>
                <PositionsTable positions={snapshot?.positions ?? []} />
              </div>

              <HistoryPanel />
            </div>

            <div className="space-y-6">
              <EAControlPanel ea={snapshot?.ea ?? null} />
              <OrderTerminal />
            </div>
          </div>
        )}

        {tab === "signal" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <div>
                <div className="text-[11px] uppercase tracking-wide text-text-tertiary mb-2">
                  Posisi Terbuka
                </div>
                <PositionsTable positions={snapshot?.positions ?? []} />
              </div>
              <SignalHistoryTable />
            </div>

            <div className="space-y-6">
              <SignalPanel signalEngine={snapshot?.signal_engine ?? null} />
              <NewsPanel newsEngine={snapshot?.news_engine ?? null} />
            </div>
          </div>
        )}

        {tab === "journal" && <JournalPanel />}
      </main>

      <footer className="border-t border-line py-4">
        <p className="max-w-6xl mx-auto px-5 text-[11px] text-text-tertiary font-mono-num">
          Terhubung langsung ke akun MT5 lo lewat bridge pribadi. Data floating P/L dan posisi bersifat realtime.
        </p>
      </footer>
    </div>
  );
}
