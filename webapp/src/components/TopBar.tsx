"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { AccountSnapshot } from "@/lib/types";

const statusLabel: Record<string, string> = {
  connecting: "Menghubungkan",
  open: "Live",
  closed: "Terputus",
  error: "Error",
  unauthorized: "Sesi berakhir",
};

export function TopBar({
  account,
  wsStatus,
}: {
  account: AccountSnapshot | null;
  wsStatus: string;
}) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const isLive = wsStatus === "open";

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await fetch("/api/logout", { method: "POST" });
    } finally {
      router.push("/login");
      router.refresh();
    }
  }

  return (
    <header className="border-b border-line bg-bg-panel/60 backdrop-blur">
      <div className="max-w-6xl mx-auto px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-tight text-text-primary">
            Terminal
          </span>
          {account && (
            <span className="text-xs text-text-tertiary font-mono-num hidden sm:inline">
              {account.login} · {account.server}
            </span>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isLive ? "bg-profit pulse-dot" : "bg-loss"
              }`}
            />
            <span className="text-xs font-mono-num text-text-secondary">
              {statusLabel[wsStatus] || wsStatus}
            </span>
          </div>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="text-xs text-text-tertiary hover:text-text-secondary transition-colors font-mono-num disabled:opacity-50"
          >
            {loggingOut ? "..." : "Keluar"}
          </button>
        </div>
      </div>
    </header>
  );
}
