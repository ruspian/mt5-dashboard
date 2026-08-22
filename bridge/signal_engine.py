"""
Signal Engine
==============
Ini "otak" trading yang menggantikan EA MQL5. Terdiri dari 2 loop terpisah
(lihat main.py):

1. run_check_cycle()      -> cari sinyal entry baru (tiap SIGNAL_CHECK_INTERVAL_SEC)
2. monitor_open_positions() -> kelola posisi yang sedang berjalan: partial
   close di TP1, geser SL ke breakeven, trailing stop setelah TP2
   (tiap POSITION_MONITOR_INTERVAL_SEC — lebih sering karena ini time-sensitive)

Kalau config.AUTO_EXECUTE = True, sinyal valid akan langsung dieksekusi
sebagai order market di MT5. Kalau False, sinyal hanya disimpan untuk
ditampilkan di web (mode "rekomendasi saja") dan position monitor tidak
akan memodifikasi apa pun (karena tidak ada posisi yang dibuka otomatis).

CATATAN JUJUR:
Ini strategi trend + momentum + manajemen risiko yang umum dipakai,
BUKAN strategi yang "pasti profit" — tidak ada yang bisa menjamin itu.
Semua parameter ada di config.py supaya bisa di-tuning. Uji dulu di
akun demo/cent sebelum modal besar.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict

import MetaTrader5 as mt5

import config

log = logging.getLogger("signal-engine")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


@dataclass
class Signal:
    time: str
    symbol: str
    direction: str          # "BUY" atau "SELL"
    entry_price: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    reason: str             # penjelasan singkat kenapa sinyal ini muncul
    executed: bool
    execution_detail: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class PositionTracking:
    """Menyimpan info tambahan per-posisi yang tidak disimpan MT5 sendiri
    (target TP2/TP3, apakah sudah partial close, apakah trailing aktif)."""
    ticket: int
    original_volume: float
    entry_price: float
    direction: str  # BUY / SELL
    tp1: float
    tp2: float
    tp3: float
    partial_done: bool = False
    breakeven_done: bool = False
    trailing_active: bool = False


class SignalEngineState:
    """Menyimpan state terakhir supaya web bisa query kapan saja."""
    def __init__(self):
        self.enabled = True          # tombol darurat: False = signal engine berhenti total
        self.last_signal: Optional[Signal] = None
        self.signal_history: list[Signal] = []
        self.last_check_time: Optional[str] = None
        self.last_monitor_time: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_entry_time: Optional[datetime] = None
        # ticket -> PositionTracking, untuk posisi yang dibuka signal engine ini
        self.tracked_positions: dict[int, PositionTracking] = {}

    def push_signal(self, sig: Signal):
        self.last_signal = sig
        self.signal_history.append(sig)
        self.signal_history = self.signal_history[-50:]  # simpan 50 terakhir saja


state = SignalEngineState()


# ==============================================================
#  INDICATOR MATH (tanpa pandas/numpy dependency tambahan, manual)
# ==============================================================
def _ema(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    ema_vals = [values[0]]
    for price in values[1:]:
        ema_vals.append(price * k + ema_vals[-1] * (1 - k))
    return ema_vals


def _rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr_series(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """Return daftar True Range mentah (belum di-average), dipakai untuk
    hitung ATR sekarang maupun rata-rata ATR historis."""
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return trs


def _atr(trs: list[float], period: int) -> float:
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    return sum(trs[-period:]) / period


def _swing_low(lows: list[float], lookback: int = 20) -> float:
    return min(lows[-lookback:])


def _swing_high(highs: list[float], lookback: int = 20) -> float:
    return max(highs[-lookback:])


# ==============================================================
#  FILTER: sesi trading & volatilitas
# ==============================================================
def _session_filter_ok() -> tuple[bool, str]:
    if not config.USE_SESSION_FILTER:
        return True, ""
    server_hour = datetime.now().hour  # waktu lokal VPS; anggap sudah selaras dgn waktu server MT5 (lihat catatan config.py)
    start, end = config.SESSION_START_HOUR, config.SESSION_END_HOUR
    in_session = (start <= server_hour < end) if start <= end else (server_hour >= start or server_hour < end)
    if not in_session:
        return False, f"Di luar sesi trading ({start}:00-{end}:00), jam sekarang {server_hour}:00"
    return True, ""


def _volatility_filter_ok(trs: list[float], atr_now: float) -> tuple[bool, str]:
    if not config.USE_VOLATILITY_FILTER:
        return True, ""
    avg_atr = _atr(trs, 50)
    if avg_atr <= 0:
        return True, ""
    ratio = atr_now / avg_atr
    if ratio < config.ATR_MIN_MULT_OF_AVG:
        return False, f"Volatilitas terlalu rendah (ATR={ratio:.2f}x rata-rata, market sepi)"
    if ratio > config.ATR_MAX_MULT_OF_AVG:
        return False, f"Volatilitas terlalu ekstrem (ATR={ratio:.2f}x rata-rata, kemungkinan news spike)"
    return True, ""


# ==============================================================
#  CORE: ambil data & hitung sinyal
# ==============================================================
def fetch_candles(symbol: str, timeframe_str: str, count: int = 200):
    tf = TIMEFRAME_MAP.get(timeframe_str, mt5.TIMEFRAME_M15)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Gagal ambil candle {symbol} {timeframe_str}: {mt5.last_error()}")
    return rates


def analyze() -> Optional[Signal]:
    """Jalankan satu kali analisa. Return Signal kalau ada sinyal valid, None kalau tidak
    (baik karena tidak ada sinyal teknikal, maupun karena kena filter sesi/volatilitas)."""
    symbol = config.SIGNAL_SYMBOL
    rates = fetch_candles(symbol, config.SIGNAL_TIMEFRAME, count=max(config.EMA_SLOW * 3, 150))

    closes = [r["close"] for r in rates]
    highs = [r["high"] for r in rates]
    lows = [r["low"] for r in rates]

    ema_fast = _ema(closes, config.EMA_FAST)
    ema_slow = _ema(closes, config.EMA_SLOW)
    rsi = _rsi(closes, config.RSI_PERIOD)
    trs = _atr_series(highs, lows, closes)
    atr = _atr(trs, config.ATR_PERIOD)

    # --- filter sesi & volatilitas dulu, sebelum buang waktu hitung entry ---
    ok, why = _session_filter_ok()
    if not ok:
        return None

    ok, why = _volatility_filter_ok(trs, atr)
    if not ok:
        log.info(f"Sinyal diskip oleh filter volatilitas: {why}")
        return None

    trend_up = ema_fast[-1] > ema_slow[-1]
    trend_down = ema_fast[-1] < ema_slow[-1]

    direction = None
    reason = ""

    if trend_up and 50 < rsi < config.RSI_OVERBOUGHT:
        direction = "BUY"
        reason = f"Trend naik (EMA{config.EMA_FAST}>EMA{config.EMA_SLOW}), RSI={rsi:.1f} (momentum sehat, belum overbought)"
    elif trend_down and config.RSI_OVERSOLD < rsi < 50:
        direction = "SELL"
        reason = f"Trend turun (EMA{config.EMA_FAST}<EMA{config.EMA_SLOW}), RSI={rsi:.1f} (momentum sehat, belum oversold)"
    else:
        return None  # tidak ada sinyal valid saat ini

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Gagal ambil harga tick {symbol}: {mt5.last_error()}")

    entry = tick.ask if direction == "BUY" else tick.bid
    buffer = atr * config.SL_ATR_BUFFER_MULT

    if direction == "BUY":
        sl = _swing_low(lows) - buffer
        risk = entry - sl
        tp1 = entry + risk * config.TP1_RR
        tp2 = entry + risk * config.TP2_RR
        tp3 = entry + risk * config.TP3_RR
    else:
        sl = _swing_high(highs) + buffer
        risk = sl - entry
        tp1 = entry - risk * config.TP1_RR
        tp2 = entry - risk * config.TP2_RR
        tp3 = entry - risk * config.TP3_RR

    if risk <= 0:
        return None  # data tidak wajar, skip

    digits = mt5.symbol_info(symbol).digits
    return Signal(
        time=datetime.utcnow().isoformat() + "Z",
        symbol=symbol,
        direction=direction,
        entry_price=round(entry, digits),
        sl=round(sl, digits),
        tp1=round(tp1, digits),
        tp2=round(tp2, digits),
        tp3=round(tp3, digits),
        reason=reason,
        executed=False,
    )


# ==============================================================
#  EXECUTION (entry baru)
# ==============================================================
def count_open_signal_positions() -> int:
    positions = mt5.positions_get(symbol=config.SIGNAL_SYMBOL)
    if positions is None:
        return 0
    return len([p for p in positions if p.magic == config.SIGNAL_MAGIC_NUMBER])


def execute_signal(sig: Signal) -> Signal:
    order_type = mt5.ORDER_TYPE_BUY if sig.direction == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sig.symbol,
        "volume": config.SIGNAL_LOT_SIZE,
        "type": order_type,
        "price": sig.entry_price,
        "sl": sig.sl,
        "tp": sig.tp3,  # TP native diarahkan ke TP3 (target terjauh); TP1/TP2 dikelola oleh position monitor (partial close + breakeven + trailing)
        "deviation": 20,
        "magic": config.SIGNAL_MAGIC_NUMBER,
        "comment": "auto-signal",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        sig.executed = False
        sig.execution_detail = f"Gagal: {result.comment} (retcode={result.retcode})"
        log.warning(f"Eksekusi sinyal gagal: {sig.execution_detail}")
    else:
        sig.executed = True
        sig.execution_detail = f"Order #{result.order} terbuka @ {result.price}"
        log.info(f"Sinyal dieksekusi: {sig.direction} {sig.symbol} @ {result.price}")

        # daftarkan posisi ini untuk dipantau (partial close di TP1, breakeven, trailing setelah TP2)
        state.tracked_positions[result.order] = PositionTracking(
            ticket=result.order,
            original_volume=config.SIGNAL_LOT_SIZE,
            entry_price=result.price,
            direction=sig.direction,
            tp1=sig.tp1,
            tp2=sig.tp2,
            tp3=sig.tp3,
        )
    return sig


# ==============================================================
#  LOOP 1 — cari sinyal entry baru
# ==============================================================
def run_check_cycle():
    """Satu siklus: analisa, dan kalau valid + diizinkan, eksekusi."""
    state.last_check_time = datetime.utcnow().isoformat() + "Z"

    if not state.enabled:
        return  # tombol darurat aktif, signal engine tidak melakukan apa pun

    try:
        sig = analyze()
    except Exception as e:
        state.last_error = str(e)
        log.warning(f"Analyze error: {e}")
        return

    state.last_error = None
    if sig is None:
        return

    # Cooldown: jangan entry lagi kalau baru saja entry
    if state.last_entry_time:
        elapsed = datetime.utcnow() - state.last_entry_time
        if elapsed < timedelta(minutes=config.SIGNAL_COOLDOWN_MINUTES):
            return

    # Batas posisi terbuka
    if count_open_signal_positions() >= config.SIGNAL_MAX_OPEN_POSITIONS:
        return

    if config.AUTO_EXECUTE:
        sig = execute_signal(sig)
        if sig.executed:
            state.last_entry_time = datetime.utcnow()

    state.push_signal(sig)


# ==============================================================
#  LOOP 2 — kelola posisi berjalan: partial close, breakeven, trailing
# ==============================================================
def _round_lot(symbol: str, lot: float) -> float:
    info = mt5.symbol_info(symbol)
    step = info.volume_step
    min_lot = info.volume_min
    lot = round(lot / step) * step
    return max(lot, min_lot)


def _partial_close(pos, tracking: PositionTracking):
    """Tutup sebagian posisi (PARTIAL_CLOSE_PERCENT dari volume awal)."""
    close_volume = _round_lot(pos.symbol, tracking.original_volume * config.PARTIAL_CLOSE_PERCENT / 100)
    close_volume = min(close_volume, pos.volume)  # jangan lebih besar dari sisa posisi

    tick = mt5.symbol_info_tick(pos.symbol)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": close_volume,
        "type": close_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 20,
        "comment": "partial-tp1",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    ok = result.retcode == mt5.TRADE_RETCODE_DONE
    if ok:
        log.info(f"Partial close TP1: posisi #{pos.ticket}, {close_volume} lot ditutup @ {price}")
    else:
        log.warning(f"Partial close gagal untuk #{pos.ticket}: {result.comment}")
    return ok


def _modify_sltp(pos, new_sl: float, new_tp: Optional[float] = None):
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": pos.ticket,
        "symbol": pos.symbol,
        "sl": new_sl,
        "tp": new_tp if new_tp is not None else pos.tp,
    }
    result = mt5.order_send(request)
    ok = result.retcode == mt5.TRADE_RETCODE_DONE
    if not ok:
        log.warning(f"Modify SL/TP gagal untuk #{pos.ticket}: {result.comment}")
    return ok


def monitor_open_positions():
    """Dipanggil berkala (lebih sering dari run_check_cycle). Untuk tiap
    posisi yang sedang dipantau (dibuka oleh signal engine ini):
    - Kalau harga sudah lewat TP1 dan belum partial close -> partial close + geser SL ke breakeven
    - Kalau harga sudah lewat TP2 dan trailing belum aktif -> aktifkan trailing stop
    - Kalau trailing aktif -> update trailing SL mengikuti harga
    """
    state.last_monitor_time = datetime.utcnow().isoformat() + "Z"

    if not state.tracked_positions:
        return

    positions = mt5.positions_get(symbol=config.SIGNAL_SYMBOL)
    open_tickets = {p.ticket: p for p in positions} if positions else {}

    # bersihkan tracking untuk posisi yang sudah tidak ada (closed manual/TP/SL)
    for ticket in list(state.tracked_positions.keys()):
        if ticket not in open_tickets:
            del state.tracked_positions[ticket]

    for ticket, tracking in list(state.tracked_positions.items()):
        pos = open_tickets.get(ticket)
        if pos is None:
            continue

        tick = mt5.symbol_info_tick(pos.symbol)
        current_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        digits = mt5.symbol_info(pos.symbol).digits
        point = mt5.symbol_info(pos.symbol).point

        tp1_hit = (current_price >= tracking.tp1) if is_buy else (current_price <= tracking.tp1)
        tp2_hit = (current_price >= tracking.tp2) if is_buy else (current_price <= tracking.tp2)

        # --- Tahap 1: TP1 kena -> partial close + breakeven ---
        if tp1_hit and not tracking.partial_done:
            if config.PARTIAL_CLOSE_AT_TP1:
                success = _partial_close(pos, tracking)
                if success:
                    tracking.partial_done = True
            else:
                tracking.partial_done = True  # dianggap selesai walau tidak partial (fitur dimatikan di config)

            if config.MOVE_SL_TO_BREAKEVEN_AT_TP1 and not tracking.breakeven_done:
                buf = config.BREAKEVEN_BUFFER_POINTS * point
                new_sl = tracking.entry_price + buf if is_buy else tracking.entry_price - buf
                new_sl = round(new_sl, digits)
                # re-fetch posisi (volume berubah setelah partial close)
                refreshed = mt5.positions_get(ticket=ticket)
                if refreshed:
                    if _modify_sltp(refreshed[0], new_sl):
                        tracking.breakeven_done = True
                        log.info(f"SL posisi #{ticket} dipindah ke breakeven: {new_sl}")

        # --- Tahap 2: TP2 kena -> aktifkan trailing stop ---
        if tp2_hit and config.TRAILING_AFTER_TP2 and not tracking.trailing_active:
            tracking.trailing_active = True
            log.info(f"Trailing stop diaktifkan untuk posisi #{ticket}")

        # --- Tahap 3: kalau trailing aktif, update SL mengikuti harga ---
        if tracking.trailing_active:
            rates = fetch_candles(pos.symbol, config.SIGNAL_TIMEFRAME, count=config.ATR_PERIOD + 5)
            closes = [r["close"] for r in rates]
            highs = [r["high"] for r in rates]
            lows = [r["low"] for r in rates]
            trs = _atr_series(highs, lows, closes)
            atr_now = _atr(trs, config.ATR_PERIOD)
            trail_dist = atr_now * config.TRAILING_DISTANCE_ATR_MULT

            refreshed = mt5.positions_get(ticket=ticket)
            if not refreshed:
                continue
            live_pos = refreshed[0]
            current_sl = live_pos.sl

            if is_buy:
                candidate_sl = round(current_price - trail_dist, digits)
                if candidate_sl > current_sl:  # trailing hanya boleh naik, tidak boleh turun
                    _modify_sltp(live_pos, candidate_sl)
            else:
                candidate_sl = round(current_price + trail_dist, digits)
                if current_sl == 0 or candidate_sl < current_sl:  # trailing hanya boleh turun
                    _modify_sltp(live_pos, candidate_sl)


# ==============================================================
#  EMERGENCY STOP / RESUME
# ==============================================================
def emergency_stop():
    """Tombol darurat: matikan signal engine + tutup semua posisi yang
    dibuka oleh signal engine ini (magic number SIGNAL_MAGIC_NUMBER)."""
    state.enabled = False
    positions = mt5.positions_get(symbol=config.SIGNAL_SYMBOL)
    closed = []
    if positions:
        for p in positions:
            if p.magic != config.SIGNAL_MAGIC_NUMBER:
                continue
            tick = mt5.symbol_info_tick(p.symbol)
            close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": close_type,
                "position": p.ticket,
                "price": price,
                "deviation": 20,
                "comment": "emergency-stop",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            closed.append({"ticket": p.ticket, "ok": result.retcode == mt5.TRADE_RETCODE_DONE})
    state.tracked_positions.clear()
    log.warning(f"EMERGENCY STOP dipicu. Posisi ditutup: {closed}")
    return closed


def resume():
    """Aktifkan lagi signal engine setelah emergency stop."""
    state.enabled = True
    state.last_error = None
