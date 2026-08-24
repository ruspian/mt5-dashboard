"""
MT5 Bridge Service
===================
Jalankan file ini di VPS Windows yang sama dengan terminal MT5 lo.

Cara jalanin:
    1. pip install -r requirements.txt
    2. Edit config.py (isi token, path, dll)
    3. python main.py

Service ini akan:
    - Baca data akun (balance, equity, margin) dari MT5
    - Baca open positions & history (termasuk deposit/withdrawal)
    - Terima order dari web (buka/tutup posisi)
    - Kontrol EA (start/stop) lewat file sinyal
    - Broadcast semua data itu secara realtime lewat WebSocket
"""

import asyncio
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

import MetaTrader5 as mt5
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import mt5_utils
import signal_engine
import news_engine
import trade_journal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mt5-bridge")

app = FastAPI(title="MT5 Bridge")

# CORS: izinkan web app (Next.js) di domain manapun untuk akses.
# Kalau mau lebih ketat, ganti "*" dengan domain web app lo nanti.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================
#  AUTH
# ==============================================================
def check_token(authorization: Optional[str]):
    """Semua endpoint (kecuali /health) wajib header:
    Authorization: Bearer <API_TOKEN>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing/invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==============================================================
#  MT5 CONNECTION
# ==============================================================
def ensure_mt5_connected():
    """Pastikan koneksi ke terminal MT5 aktif. Reconnect kalau perlu."""
    if not mt5.terminal_info():
        init_kwargs = {}
        if config.MT5_PATH:
            init_kwargs["path"] = config.MT5_PATH
        if not mt5.initialize(**init_kwargs):
            raise RuntimeError(f"mt5.initialize() gagal: {mt5.last_error()}")

        if config.MT5_LOGIN:
            ok = mt5.login(
                login=config.MT5_LOGIN,
                password=config.MT5_PASSWORD,
                server=config.MT5_SERVER,
            )
            if not ok:
                raise RuntimeError(f"mt5.login() gagal: {mt5.last_error()}")
        log.info("Terhubung ke MT5 terminal.")


# ==============================================================
#  DATA HELPERS
# ==============================================================
def get_account_snapshot() -> dict:
    ensure_mt5_connected()
    acc = mt5.account_info()
    if acc is None:
        raise RuntimeError(f"account_info() gagal: {mt5.last_error()}")
    return {
        "login": acc.login,
        "name": acc.name,
        "server": acc.server,
        "currency": acc.currency,
        "leverage": acc.leverage,
        "balance": acc.balance,
        "equity": acc.equity,
        "profit": acc.profit,
        "margin": acc.margin,
        "margin_free": acc.margin_free,
        "margin_level": acc.margin_level,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def get_open_positions() -> list:
    ensure_mt5_connected()
    positions = mt5.positions_get()
    if positions is None:
        return []
    result = []
    for p in positions:
        result.append({
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": p.volume,
            "price_open": p.price_open,
            "price_current": p.price_current,
            "sl": p.sl,
            "tp": p.tp,
            "profit": p.profit,
            "swap": p.swap,
            "magic": p.magic,
            "comment": p.comment,
            "time": datetime.fromtimestamp(p.time).isoformat(),
        })
    return result


def get_history(days: int = 30) -> dict:
    """Ambil history deals: trades biasa + deposit/withdrawal (balance ops)."""
    ensure_mt5_connected()
    date_from = datetime.now() - timedelta(days=days)
    date_to = datetime.now() + timedelta(days=1)

    deals = mt5.history_deals_get(date_from, date_to)
    if deals is None:
        deals = []

    trades = []
    balance_ops = []  # deposit / withdrawal

    for d in deals:
        entry = {
            "ticket": d.ticket,
            "order": d.order,
            "symbol": d.symbol,
            "volume": d.volume,
            "price": d.price,
            "profit": d.profit,
            "commission": d.commission,
            "swap": d.swap,
            "time": datetime.fromtimestamp(d.time).isoformat(),
            "comment": d.comment,
        }
        # DEAL_TYPE_BALANCE = deposit/withdrawal manual di akun
        if d.type == mt5.DEAL_TYPE_BALANCE:
            entry["kind"] = "DEPOSIT" if d.profit >= 0 else "WITHDRAWAL"
            balance_ops.append(entry)
        elif d.entry == mt5.DEAL_ENTRY_OUT:
            # closing trade -> ini yang biasanya dianggap "riwayat transaksi"
            entry["type"] = "BUY" if d.type == mt5.ORDER_TYPE_SELL else "SELL"
            trades.append(entry)

    return {"trades": trades, "balance_ops": balance_ops}


# ==============================================================
#  EA SIGNAL / STATUS FILE CONTROL
# ==============================================================
def write_ea_signal(command: str):
    os.makedirs(os.path.dirname(config.EA_SIGNAL_FILE), exist_ok=True)
    with open(config.EA_SIGNAL_FILE, "w") as f:
        f.write(command.strip().upper())
    log.info(f"EA signal ditulis: {command}")


def read_ea_status() -> dict:
    if not os.path.exists(config.EA_STATUS_FILE):
        return {"status": "UNKNOWN", "detail": "Status file belum ada. EA belum pernah menulis status."}
    try:
        with open(config.EA_STATUS_FILE, "r") as f:
            raw = f.read().strip()
        # format sederhana: STATUS|timestamp|keterangan
        parts = raw.split("|")
        return {
            "status": parts[0] if len(parts) > 0 else "UNKNOWN",
            "last_update": parts[1] if len(parts) > 1 else None,
            "detail": parts[2] if len(parts) > 2 else None,
        }
    except Exception as e:
        return {"status": "ERROR", "detail": str(e)}


def read_ea_signal() -> str:
    if not os.path.exists(config.EA_SIGNAL_FILE):
        return "START"  # default: jalan normal kalau belum ada file
    with open(config.EA_SIGNAL_FILE, "r") as f:
        return f.read().strip().upper()


# ==============================================================
#  REST ENDPOINTS
# ==============================================================
@app.get("/health")
def health():
    """Endpoint publik, tanpa auth, buat cek service hidup atau tidak."""
    return {"ok": True, "time": datetime.utcnow().isoformat()}


@app.get("/account")
def account(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    try:
        return get_account_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions")
def positions(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    try:
        return get_open_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
def history(days: int = 30, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    try:
        return get_history(days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/journal/stats")
def journal_stats(days: int = 30, source: Optional[str] = None, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    ensure_mt5_connected()
    try:
        trades = trade_journal.get_trades(days)
        if source:
            trades = [t for t in trades if t.source == source]
        stats = trade_journal.compute_stats(trades)
        result = stats.to_dict()
        result["by_source"] = trade_journal.compute_by_source(trades)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/journal/trades")
def journal_trades(days: int = 30, source: Optional[str] = None, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    ensure_mt5_connected()
    try:
        trades = trade_journal.get_trades(days)
        if source:
            trades = [t for t in trades if t.source == source]
        return [t.to_dict() for t in trades]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ea/status")
def ea_status(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    result = read_ea_status()
    result["signal"] = read_ea_signal()
    return result


class EAControlRequest(BaseModel):
    command: str  # "START" atau "STOP"


@app.post("/ea/control")
def ea_control(req: EAControlRequest, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    cmd = req.command.strip().upper()
    if cmd not in ("START", "STOP"):
        raise HTTPException(status_code=400, detail="command harus START atau STOP")
    write_ea_signal(cmd)
    return {"ok": True, "command": cmd}


class OrderRequest(BaseModel):
    symbol: str
    volume: float
    order_type: str          # "BUY" atau "SELL"
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: Optional[str] = "web-terminal"


@app.post("/order/open")
def order_open(req: OrderRequest, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    ensure_mt5_connected()

    symbol_info = mt5.symbol_info(req.symbol)
    if symbol_info is None:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} tidak ditemukan")
    if not symbol_info.visible:
        mt5.symbol_select(req.symbol, True)

    tick = mt5.symbol_info_tick(req.symbol)
    if tick is None:
        raise HTTPException(status_code=400, detail="Gagal mengambil harga terkini")

    order_type = mt5.ORDER_TYPE_BUY if req.order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": req.symbol,
        "volume": req.volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "comment": req.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5_utils.get_supported_filling_mode(req.symbol),
    }
    if req.sl:
        request["sl"] = req.sl
    if req.tp:
        request["tp"] = req.tp

    result = mt5_utils.send_order_with_fallback(request)
    if result is None:
        raise HTTPException(status_code=400, detail="Order gagal: order_send gagal total (cek koneksi MT5 di terminal)")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=f"Order gagal: {result.comment} (retcode={result.retcode})")

    return {"ok": True, "ticket": result.order, "price": result.price}


class CloseRequest(BaseModel):
    ticket: int


@app.post("/order/close")
def order_close(req: CloseRequest, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    ensure_mt5_connected()

    pos_list = mt5.positions_get(ticket=req.ticket)
    if not pos_list:
        raise HTTPException(status_code=404, detail="Posisi tidak ditemukan")
    pos = pos_list[0]

    tick = mt5.symbol_info_tick(pos.symbol)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": pos.volume,
        "type": close_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 20,
        "comment": "close-via-web",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5_utils.get_supported_filling_mode(pos.symbol),
    }
    result = mt5_utils.send_order_with_fallback(request)
    if result is None:
        raise HTTPException(status_code=400, detail="Close gagal: order_send gagal total (cek koneksi MT5 di terminal)")
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=f"Close gagal: {result.comment} (retcode={result.retcode})")

    return {"ok": True}


# ==============================================================
#  SIGNAL ENGINE ENDPOINTS
# ==============================================================
@app.get("/signal/status")
def signal_status(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    return {
        "enabled": signal_engine.state.enabled,
        "last_check_time": signal_engine.state.last_check_time,
        "last_monitor_time": signal_engine.state.last_monitor_time,
        "last_error": signal_engine.state.last_error,
        "last_signal": signal_engine.state.last_signal.to_dict() if signal_engine.state.last_signal else None,
        "tracked_positions": [
            {
                "ticket": t.ticket,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "tp1": t.tp1,
                "tp2": t.tp2,
                "tp3": t.tp3,
                "partial_done": t.partial_done,
                "breakeven_done": t.breakeven_done,
                "trailing_active": t.trailing_active,
            }
            for t in signal_engine.state.tracked_positions.values()
        ],
        "config": {
            "symbol": config.SIGNAL_SYMBOL,
            "timeframe": config.SIGNAL_TIMEFRAME,
            "auto_execute": config.AUTO_EXECUTE,
            "lot_size": config.SIGNAL_LOT_SIZE,
            "partial_close_percent": config.PARTIAL_CLOSE_PERCENT,
        },
        "news_context": news_engine.state.last_context.to_dict() if news_engine.state.last_context else None,
    }


@app.get("/signal/history")
def signal_history(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    return [s.to_dict() for s in reversed(signal_engine.state.signal_history)]


@app.post("/signal/emergency-stop")
def signal_emergency_stop(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    ensure_mt5_connected()
    closed = signal_engine.emergency_stop()
    return {"ok": True, "closed_positions": closed}


@app.post("/signal/resume")
def signal_resume(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    signal_engine.resume()
    return {"ok": True}


@app.get("/news/status")
def news_status(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    return {
        "enabled": config.USE_NEWS_ENGINE,
        "last_fetch_time": news_engine.state.last_fetch_time,
        "last_error": news_engine.state.last_error,
        "current_context": news_engine.state.last_context.to_dict() if news_engine.state.last_context else None,
        "upcoming_calendar": [e.to_dict() for e in news_engine.state.upcoming_calendar],
        "recent_news": [n.to_dict() for n in news_engine.state.recent_news],
        "calendar_running_low": news_engine.state.calendar_running_low,
        "calendar_running_low_message": news_engine.state.calendar_running_low_message,
        "all_news_sources_failed": news_engine.state.all_news_sources_failed,
    }


# ==============================================================
#  TRADE JOURNAL — riwayat trade lengkap + statistik win rate
# ==============================================================
@app.get("/journal/trades")
def journal_trades(
    days: int = 90,
    source: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """source: filter opsional "manual" | "ea" | "signal". Kosongkan
    untuk semua sumber."""
    check_token(authorization)
    ensure_mt5_connected()
    try:
        trades = trade_journal.get_trades(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil trade journal: {e}")

    if source:
        trades = [t for t in trades if t.source == source]

    return [t.to_dict() for t in trades]


@app.get("/journal/stats")
def journal_stats(
    days: int = 90,
    source: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    check_token(authorization)
    ensure_mt5_connected()
    try:
        trades = trade_journal.get_trades(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil trade journal: {e}")

    if source:
        trades = [t for t in trades if t.source == source]

    stats = trade_journal.compute_stats(trades)
    return stats.to_dict()


# ==============================================================
#  WS TICKET — token sekali-pakai berumur pendek untuk koneksi WebSocket
# ==============================================================
# Dipakai supaya API_TOKEN asli tidak perlu dikirim ke browser sama
# sekali. Next.js server (yang pegang API_TOKEN) menukar API_TOKEN
# dengan ticket ini lewat endpoint /ws-ticket (server-to-server), lalu
# ticket itu (bukan API_TOKEN) yang dikirim ke browser untuk connect WS.
_ws_tickets: dict[str, float] = {}  # ticket -> waktu expired (epoch seconds)
WS_TICKET_TTL_SEC = 30


def _cleanup_expired_tickets():
    now = time.time()
    expired = [t for t, exp in _ws_tickets.items() if exp < now]
    for t in expired:
        del _ws_tickets[t]


@app.post("/ws-ticket")
def issue_ws_ticket(authorization: Optional[str] = Header(None)):
    check_token(authorization)
    _cleanup_expired_tickets()
    ticket = secrets.token_urlsafe(24)
    _ws_tickets[ticket] = time.time() + WS_TICKET_TTL_SEC
    return {"ticket": ticket, "expires_in": WS_TICKET_TTL_SEC}


def _consume_ws_ticket(ticket: str) -> bool:
    _cleanup_expired_tickets()
    if ticket in _ws_tickets:
        del _ws_tickets[ticket]  # sekali pakai
        return True
    return False


# ==============================================================
#  WEBSOCKET: broadcast realtime setiap 1 detik
# ==============================================================
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, ticket: str = ""):
    if not _consume_ws_ticket(ticket):
        await ws.close(code=4001)
        return
    await manager.connect(ws)
    try:
        while True:
            # klien tidak wajib kirim apa-apa, ini cuma buat detect disconnect
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def broadcaster_loop():
    """Loop background: setiap 1 detik kirim snapshot terbaru ke semua klien WS."""
    while True:
        try:
            if manager.active:
                payload = {
                    "type": "snapshot",
                    "account": get_account_snapshot(),
                    "positions": get_open_positions(),
                    "ea": {**read_ea_status(), "signal": read_ea_signal()},
                    "signal_engine": {
                        "enabled": signal_engine.state.enabled,
                        "last_check_time": signal_engine.state.last_check_time,
                        "last_error": signal_engine.state.last_error,
                        "last_signal": signal_engine.state.last_signal.to_dict()
                        if signal_engine.state.last_signal
                        else None,
                        "tracked_positions": [
                            {
                                "ticket": t.ticket,
                                "direction": t.direction,
                                "tp1": t.tp1,
                                "tp2": t.tp2,
                                "tp3": t.tp3,
                                "partial_done": t.partial_done,
                                "breakeven_done": t.breakeven_done,
                                "trailing_active": t.trailing_active,
                            }
                            for t in signal_engine.state.tracked_positions.values()
                        ],
                    },
                    "news_engine": {
                        "enabled": config.USE_NEWS_ENGINE,
                        "last_fetch_time": news_engine.state.last_fetch_time,
                        "last_error": news_engine.state.last_error,
                        "current_context": news_engine.state.last_context.to_dict()
                        if news_engine.state.last_context
                        else None,
                    },
                }
                await manager.broadcast(payload)
        except Exception as e:
            log.warning(f"Broadcast loop error: {e}")
        await asyncio.sleep(1)


async def signal_engine_loop():
    """Loop background terpisah: jalankan signal engine tiap SIGNAL_CHECK_INTERVAL_SEC detik."""
    while True:
        try:
            ensure_mt5_connected()
            signal_engine.run_check_cycle()
        except Exception as e:
            signal_engine.state.last_error = str(e)
            log.warning(f"Signal engine loop error: {e}")
        await asyncio.sleep(config.SIGNAL_CHECK_INTERVAL_SEC)


async def position_monitor_loop():
    """Loop background terpisah: pantau posisi berjalan untuk partial
    close di TP1, geser SL ke breakeven, dan trailing stop setelah TP2.
    Jalan lebih sering daripada signal_engine_loop karena time-sensitive."""
    while True:
        try:
            ensure_mt5_connected()
            signal_engine.monitor_open_positions()
        except Exception as e:
            log.warning(f"Position monitor loop error: {e}")
        await asyncio.sleep(config.POSITION_MONITOR_INTERVAL_SEC)


async def news_engine_loop():
    """Loop background terpisah: refresh economic calendar & berita
    umum dari Finnhub secara berkala. Tidak butuh koneksi MT5."""
    while True:
        try:
            news_engine.refresh()
        except Exception as e:
            log.warning(f"News engine loop error: {e}")
        await asyncio.sleep(config.NEWS_CHECK_INTERVAL_SEC)


@app.on_event("startup")
async def on_startup():
    try:
        ensure_mt5_connected()
    except Exception as e:
        log.error(f"Gagal konek MT5 saat startup: {e}. Bridge tetap jalan, akan dicoba ulang saat ada request.")

    _validate_signal_symbol()

    asyncio.create_task(broadcaster_loop())
    asyncio.create_task(signal_engine_loop())
    asyncio.create_task(position_monitor_loop())
    if config.USE_NEWS_ENGINE:
        asyncio.create_task(news_engine_loop())
        # fetch pertama langsung saat startup, tidak perlu tunggu interval pertama
        try:
            news_engine.refresh()
        except Exception as e:
            log.warning(f"News engine initial fetch gagal: {e}")
    log.info(
        f"Signal engine aktif untuk {config.SIGNAL_SYMBOL} ({config.SIGNAL_TIMEFRAME}), "
        f"auto_execute={config.AUTO_EXECUTE}, cek tiap {config.SIGNAL_CHECK_INTERVAL_SEC}s"
    )
    log.info(
        f"Position monitor aktif: partial_close={config.PARTIAL_CLOSE_AT_TP1} "
        f"({config.PARTIAL_CLOSE_PERCENT}% di TP1), breakeven={config.MOVE_SL_TO_BREAKEVEN_AT_TP1}, "
        f"trailing_after_tp2={config.TRAILING_AFTER_TP2}, cek tiap {config.POSITION_MONITOR_INTERVAL_SEC}s"
    )


def _validate_signal_symbol():
    """Cek apakah SIGNAL_SYMBOL di config.py PERSIS cocok dengan nama
    symbol di broker. Ini pengecekan yang PENTING terutama untuk akun
    cent (HFM dan sejenisnya) yang biasanya pakai suffix seperti
    "XAUUSD.c" atau "GOLDcent" — kalau salah, signal engine akan gagal
    entry TANPA error yang jelas kalau tidak divalidasi di sini."""
    info = mt5.symbol_info(config.SIGNAL_SYMBOL)
    if info is not None:
        log.info(
            f"Symbol '{config.SIGNAL_SYMBOL}' ditemukan di broker. "
            f"volume_min={info.volume_min}, volume_step={info.volume_step}, digits={info.digits}"
        )
        # pastikan juga symbol-nya visible di Market Watch, kalau tidak
        # copy_rates/tick bisa gagal walau symbol_info() berhasil
        if not info.visible:
            mt5.symbol_select(config.SIGNAL_SYMBOL, True)
            log.info(f"Symbol '{config.SIGNAL_SYMBOL}' di-enable di Market Watch.")
        return

    # symbol tidak ditemukan -> cari kandidat serupa supaya log-nya membantu
    log.error(
        f"❌ SIGNAL_SYMBOL '{config.SIGNAL_SYMBOL}' TIDAK DITEMUKAN di broker ini. "
        f"Signal engine TIDAK AKAN BISA entry sampai ini diperbaiki."
    )
    try:
        all_symbols = mt5.symbols_get()
        candidates = [
            s.name for s in all_symbols
            if "XAU" in s.name.upper() or "GOLD" in s.name.upper()
        ] if all_symbols else []
        if candidates:
            log.error(
                f"Kemungkinan nama symbol gold yang benar di broker ini: {candidates}. "
                f"Cek juga langsung di Market Watch MT5, lalu perbaiki SIGNAL_SYMBOL di config.py "
                f"dan restart bridge."
            )
        else:
            log.error(
                "Tidak ditemukan symbol yang mengandung 'XAU' atau 'GOLD' sama sekali. "
                "Cek apakah MT5 sudah login dengan benar, dan buka Market Watch untuk "
                "melihat daftar symbol yang tersedia di akun ini."
            )
    except Exception as e:
        log.error(f"Gagal mencari kandidat symbol alternatif: {e}")


if __name__ == "__main__":
    log.info(f"Menjalankan MT5 Bridge di {config.HOST}:{config.PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
