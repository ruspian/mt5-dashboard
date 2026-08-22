"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Password salah.");
        setSubmitting(false);
        return;
      }
      router.push("/");
      router.refresh();
    } catch {
      setError("Gagal menghubungi server. Coba lagi.");
      setSubmitting(false);
    }
  }

  return (
    <main className="flex-1 flex items-center justify-center px-6 py-16 bg-bg-base">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            <span className="text-xs uppercase tracking-[0.15em] text-text-tertiary font-mono-num">
              Terminal
            </span>
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Masuk</h1>
          <p className="text-sm text-text-secondary mt-2 leading-relaxed">
            Masukkan password dashboard lo. Kredensial bridge sudah diatur di
            server, tidak perlu diisi ulang di device ini.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs uppercase tracking-wide text-text-tertiary mb-2 font-mono-num">
              Password
            </label>
            <input
              type="password"
              required
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-bg-panel border border-line rounded px-3 py-2.5 text-sm font-mono-num text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-accent hover:bg-accent-dim text-bg-base text-sm font-semibold py-2.5 rounded transition-colors disabled:opacity-50"
          >
            {submitting ? "Memeriksa..." : "Masuk"}
          </button>
        </form>

        {error && (
          <div className="mt-5 text-sm px-3 py-2.5 rounded border border-loss-dim bg-loss-dim/20 text-loss font-mono-num">
            {error}
          </div>
        )}
      </div>
    </main>
  );
}
