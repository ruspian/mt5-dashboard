"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { WSSnapshot } from "./types";

type ConnStatus = "connecting" | "open" | "closed" | "error" | "unauthorized";

export function useLiveData() {
  const [snapshot, setSnapshot] = useState<WSSnapshot | null>(null);
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(1000);
  const cancelled = useRef(false);

  const connect = useCallback(async () => {
    setStatus("connecting");

    // Minta tiket sekali-pakai dari server (server yang pegang token asli).
    let wsUrl: string;
    try {
      const res = await fetch("/api/ws-ticket", { method: "POST" });
      if (res.status === 401) {
        setStatus("unauthorized");
        return;
      }
      if (!res.ok) throw new Error("Gagal mendapat tiket WebSocket");
      const data = await res.json();
      wsUrl = data.ws_url;
    } catch {
      setStatus("error");
      retryTimer.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 1.5, 15000);
        connect();
      }, retryDelay.current);
      return;
    }

    if (cancelled.current) return;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("open");
      retryDelay.current = 1000;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "snapshot") {
          setSnapshot(data as WSSnapshot);
        }
      } catch {
        // abaikan pesan yang tidak bisa di-parse
      }
    };

    ws.onclose = () => {
      setStatus("closed");
      if (cancelled.current) return;
      // auto-reconnect dengan backoff, maks 15 detik. Tiket berumur pendek
      // (lihat WS_TICKET_TTL_SEC di bridge/config.py) jadi kita selalu minta
      // tiket baru tiap kali reconnect, bukan pakai ulang yang lama.
      retryTimer.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 1.5, 15000);
        connect();
      }, retryDelay.current);
    };

    ws.onerror = () => {
      setStatus("error");
    };
  }, []);

  useEffect(() => {
    cancelled.current = false;
    connect();
    return () => {
      cancelled.current = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { snapshot, status };
}
