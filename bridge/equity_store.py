"""
Equity History Store
=====================
Sebelumnya, grafik equity di web app cuma nyimpen titik data di memory
BROWSER (React state) — jadi HILANG total tiap kali halaman di-refresh,
tab ditutup, atau browser lain dipakai. Modul ini memindahkan pencatatan
equity ke sisi BRIDGE (server), disimpan permanen sebagai file SQLite
lokal (equity_history.db, satu folder dengan file ini).

Konsekuensinya:
    - Grafik equity di web app sekarang PERMANEN — reload halaman, ganti
      device, atau bridge di-restart, datanya tetap ada (bukan reset ke
      kosong tiap kali).
    - Web app tinggal fetch riwayatnya lewat GET /equity/history saat
      pertama kali dibuka, lalu lanjut nambah titik baru secara live
      lewat WebSocket seperti biasa.

CATATAN JUJUR:
    - SQLite dipilih (bukan Postgres/dll) karena ini single-writer,
      single-process, jalan di VPS yang sama dengan bridge — tidak perlu
      database server terpisah. Kalau suatu saat butuh multi-instance
      bridge, ini perlu diganti ke database yang mendukung concurrent
      write dari banyak proses.
    - Penulisan di-throttle (lihat config.EQUITY_LOG_INTERVAL_SEC) supaya
      file db tidak membengkak tanpa perlu — broadcaster_loop di main.py
      jalan tiap 1 detik, tapi kita tidak perlu simpan tiap detik.
    - Data lama otomatis dihapus lewat prune_old() (dipanggil sekali saat
      startup) sesuai config.EQUITY_RETENTION_DAYS, supaya file db tidak
      tumbuh tanpa batas selamanya.
"""

import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import config

log = logging.getLogger("equity-store")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equity_history.db")

_lock = threading.Lock()
_last_write_ts: float = 0.0


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS equity_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "ts REAL NOT NULL, "
        "balance REAL NOT NULL, "
        "equity REAL NOT NULL, "
        "profit REAL NOT NULL"
        ")"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_equity_history_ts ON equity_history(ts)")
    return conn


def record(balance: float, equity: float, profit: float) -> None:
    """Simpan satu snapshot equity. Dipanggil dari broadcaster_loop di
    main.py tiap 1 detik, tapi di-throttle di sini lewat
    config.EQUITY_LOG_INTERVAL_SEC — jadi frekuensi tulis ke disk jauh
    lebih jarang daripada frekuensi broadcast ke browser."""
    global _last_write_ts
    now = time.time()
    with _lock:
        if now - _last_write_ts < config.EQUITY_LOG_INTERVAL_SEC:
            return
        _last_write_ts = now

    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO equity_history (ts, balance, equity, profit) VALUES (?, ?, ?, ?)",
            (now, balance, equity, profit),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Gagal menyimpan snapshot equity: {e}")


def get_history(hours: float = 24, max_points: int = 500) -> list[dict]:
    """Ambil riwayat equity dalam N jam terakhir. Kalau jumlah baris
    melebihi max_points, di-downsample (rata-rata per bucket) supaya
    payload ke web app tidak membengkak untuk rentang waktu yang panjang
    (misal 7 hari dengan interval 30 detik = puluhan ribu baris mentah)."""
    cutoff = time.time() - hours * 3600
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT ts, balance, equity, profit FROM equity_history WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        ).fetchall()
        conn.close()
    except Exception as e:
        log.warning(f"Gagal membaca riwayat equity: {e}")
        return []

    if not rows:
        return []

    if len(rows) > max_points:
        bucket_size = len(rows) / max_points
        downsampled = []
        i = 0.0
        while int(i) < len(rows):
            chunk = rows[int(i):max(int(i + bucket_size), int(i) + 1)]
            if not chunk:
                break
            n = len(chunk)
            avg_ts = sum(r[0] for r in chunk) / n
            avg_bal = sum(r[1] for r in chunk) / n
            avg_eq = sum(r[2] for r in chunk) / n
            avg_pf = sum(r[3] for r in chunk) / n
            downsampled.append((avg_ts, avg_bal, avg_eq, avg_pf))
            i += bucket_size
        rows = downsampled

    return [
        {
            "time": datetime.fromtimestamp(r[0], tz=timezone.utc).isoformat(),
            "balance": round(r[1], 2),
            "equity": round(r[2], 2),
            "profit": round(r[3], 2),
        }
        for r in rows
    ]


def prune_old(days: Optional[int] = None) -> None:
    """Hapus data equity yang lebih tua dari config.EQUITY_RETENTION_DAYS.
    Dipanggil sekali saat bridge startup — bukan tiap loop — supaya tidak
    ada overhead delete berulang."""
    days = days if days is not None else config.EQUITY_RETENTION_DAYS
    cutoff = time.time() - days * 86400
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM equity_history WHERE ts < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Gagal menghapus riwayat equity lama: {e}")
