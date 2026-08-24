"use client";

import type { NewsEngineStatus } from "@/lib/types";

const statusMeta: Record<string, { label: string; className: string }> = {
  NORMAL: { label: "Normal", className: "text-profit bg-profit-dim/25 border-profit-dim" },
  CALENDAR_BLACKOUT: { label: "Blackout Rilis Data", className: "text-loss bg-loss-dim/25 border-loss-dim" },
  HIGH_IMPACT_NEWS: { label: "Berita High-Impact", className: "text-accent bg-accent-dim/25 border-accent-dim" },
};

export function NewsPanel({ newsEngine }: { newsEngine: NewsEngineStatus | null }) {
  if (!newsEngine?.enabled) {
    return null;
  }

  const ctx = newsEngine.current_context;
  const meta = statusMeta[ctx?.status ?? "NORMAL"];

  const upcomingHighImpact = (newsEngine.upcoming_calendar ?? [])
    .filter((e) => e.impact === "high")
    .slice(0, 5);

  const recentNews = (newsEngine.recent_news ?? []).slice(0, 5);

  return (
    <div className="space-y-4">
      {newsEngine.calendar_running_low && (
        <div className="bg-loss-dim/20 border border-loss-dim rounded p-3">
          <p className="text-xs text-loss font-medium mb-1">⚠️ Jadwal calendar perlu diperbarui</p>
          <p className="text-[11px] text-text-secondary leading-relaxed">
            {newsEngine.calendar_running_low_message ??
              "Tidak ada jadwal rilis data high-impact dalam waktu dekat. Cek dan tambah MANUAL_CALENDAR_EVENTS di bridge/config.py."}
          </p>
        </div>
      )}

      {newsEngine.all_news_sources_failed && (
        <div className="bg-loss-dim/20 border border-loss-dim rounded p-3">
          <p className="text-xs text-loss font-medium mb-1">⚠️ Semua sumber berita gagal diakses</p>
          <p className="text-[11px] text-text-secondary leading-relaxed">
            AI News Analyst tidak punya data berita untuk dianalisa saat ini. Sinyal teknikal tetap berjalan normal, tapi tanpa filter/penyesuaian dari berita. Cek log bridge untuk detail sumber mana yang gagal.
          </p>
        </div>
      )}

      <div className="bg-bg-panel border border-line rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
            Status Berita &amp; Calendar
          </span>
          <span className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded border ${meta.className}`}>
            {meta.label}
          </span>
        </div>

        {ctx?.reason && (
          <p className="text-xs text-text-secondary leading-relaxed">{ctx.reason}</p>
        )}

        {ctx?.ai_analysis && !ctx.ai_analysis.error && (
          <div className="mt-3 pt-3 border-t border-line">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
                Penilaian AI
              </span>
              <span
                className={`text-[11px] font-mono-num px-1.5 py-0.5 rounded ${
                  ctx.ai_analysis.sentiment === "bullish"
                    ? "text-profit bg-profit-dim/25"
                    : ctx.ai_analysis.sentiment === "bearish"
                    ? "text-loss bg-loss-dim/25"
                    : "text-text-tertiary bg-bg-panel-raised"
                }`}
              >
                {ctx.ai_analysis.sentiment} · {(ctx.ai_analysis.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed">{ctx.ai_analysis.reason}</p>
            <p className="text-[11px] text-text-tertiary font-mono-num mt-1">via {ctx.ai_analysis.provider}</p>
          </div>
        )}

        {ctx?.ai_analysis?.error && (
          <p className="text-[11px] text-text-tertiary mt-2 italic">
            Analisa AI tidak tersedia saat ini — sistem berjalan dengan deteksi kata kunci saja.
          </p>
        )}

        {newsEngine.last_error && (
          <p className="text-xs text-loss mt-2 font-mono-num">{newsEngine.last_error}</p>
        )}

        {newsEngine.last_fetch_time && (
          <p className="text-[11px] text-text-tertiary font-mono-num mt-3 pt-2 border-t border-line">
            Data terakhir diambil: {new Date(newsEngine.last_fetch_time).toLocaleTimeString("id-ID")}
          </p>
        )}
      </div>

      {upcomingHighImpact.length > 0 && (
        <div className="bg-bg-panel border border-line rounded overflow-hidden">
          <div className="px-4 py-2.5 border-b border-line">
            <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
              Jadwal Rilis Data High-Impact
            </span>
          </div>
          <div className="divide-y divide-line">
            {upcomingHighImpact.map((ev, i) => (
              <div key={i} className="px-4 py-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-primary">{ev.event}</span>
                  <span className="text-[11px] font-mono-num text-text-tertiary">{ev.country}</span>
                </div>
                <p className="text-[11px] text-text-tertiary font-mono-num mt-0.5">
                  {new Date(ev.time).toLocaleString("id-ID")}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {recentNews.length > 0 && (
        <div className="bg-bg-panel border border-line rounded overflow-hidden">
          <div className="px-4 py-2.5 border-b border-line">
            <span className="text-[11px] uppercase tracking-wide text-text-tertiary">
              Berita Relevan Terkini
            </span>
          </div>
          <div className="divide-y divide-line">
            {recentNews.map((news, i) => (
              <a
                key={i}
                href={news.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-2.5 hover:bg-bg-panel-raised transition-colors"
              >
                <p className="text-sm text-text-primary leading-snug">{news.headline}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[11px] text-text-tertiary font-mono-num">{news.source}</span>
                  <span className="text-[11px] text-text-tertiary">·</span>
                  <span className="text-[11px] text-text-tertiary font-mono-num">
                    {new Date(news.time).toLocaleTimeString("id-ID")}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      <p className="text-[11px] text-text-tertiary leading-relaxed">
        Deteksi kata kunci sebagai filter awal, lalu berita yang lolos dinilai AI untuk arah sentimen &amp; keyakinan. Tetap bukan pemahaman sempurna — selalu cek langsung sumbernya untuk keputusan penting.
      </p>
    </div>
  );
}
