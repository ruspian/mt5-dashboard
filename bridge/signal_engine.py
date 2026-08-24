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
import mt5_utils
import news_engine
import ai_news_analyst
import ai_chart_analyst

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
    news_status: str = "NORMAL"      # "NORMAL" | "CALENDAR_BLACKOUT" | "HIGH_IMPACT_NEWS"
    news_reason: Optional[str] = None
    lot_used: Optional[float] = None  # lot aktual yang dipakai (bisa dikecilkan kalau HIGH_IMPACT_NEWS)
    ai_analysis: Optional["ai_news_analyst.AIAnalysis"] = None
    chart_analysis: Optional["ai_chart_analyst.ChartAnalysis"] = None
    confirmation_score: int = 0             # jumlah indikator yang konfirmasi arah sinyal
    confirmation_details: list = None       # daftar alasan konfirmasi (MACD, BB, candlestick)

    def __post_init__(self):
        if self.confirmation_details is None:
            self.confirmation_details = []

    def to_dict(self):
        d = asdict(self)
        # asdict() sudah otomatis mengubah nested dataclass (ai_analysis,
        # chart_analysis) jadi dict, aman
        return d


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
#  INDIKATOR TAMBAHAN: MACD, Bollinger Bands, candlestick pattern
#  (dipakai sebagai konfirmasi multi-indikator sebelum entry)
# ==============================================================
def _macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float, float]:
    """Return (macd_line, signal_line, histogram) pada candle terakhir.
    MACD = EMA cepat - EMA lambat. Signal line = EMA dari MACD line itu
    sendiri. Histogram positif & membesar = momentum naik menguat."""
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line_series = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line_series = _ema(macd_line_series, signal)
    macd_line = macd_line_series[-1]
    signal_line = signal_line_series[-1]
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(closes: list[float], period: int = 20, std_mult: float = 2.0) -> tuple[float, float, float]:
    """Return (upper_band, middle_band/SMA, lower_band) pada candle terakhir.
    Dipakai untuk konteks volatilitas & posisi harga relatif terhadap
    rentang normal — harga dekat lower band saat trend naik bisa jadi
    entry yang lebih baik daripada mengejar harga yang sudah dekat upper band."""
    window = closes[-period:]
    sma = sum(window) / len(window)
    variance = sum((c - sma) ** 2 for c in window) / len(window)
    std = variance ** 0.5
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return upper, sma, lower


def _detect_candlestick_pattern(rates, direction: str) -> tuple[bool, str]:
    """Cek apakah candle-candle terakhir menunjukkan pola candlestick
    yang MENDUKUNG arah entry (direction). Return (cocok, nama_pola).
    Cuma mengenali beberapa pola paling umum & reliable, bukan daftar
    lengkap — cukup untuk konfirmasi tambahan, bukan sinyal mandiri."""
    if len(rates) < 3:
        return False, "data tidak cukup"

    last = rates[-1]
    prev = rates[-2]

    o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
    po, ph, pl, pc = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])

    body = abs(c - o)
    range_total = h - l if h != l else 1e-9
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    if direction == "BUY":
        # Bullish engulfing: candle sekarang naik & body-nya menelan body candle sebelumnya yang turun
        if pc < po and c > o and c >= po and o <= pc:
            return True, "Bullish Engulfing"
        # Hammer: body kecil di bagian atas range, lower wick panjang (penolakan harga rendah)
        if body / range_total < 0.35 and lower_wick > body * 2 and upper_wick < body:
            return True, "Hammer"
        # Candle bullish biasa dengan body dominan (momentum searah jelas)
        if c > o and body / range_total > 0.6:
            return True, "Strong Bullish Candle"
        return False, "tidak ada pola bullish yang jelas"

    else:  # SELL
        # Bearish engulfing
        if pc > po and c < o and o >= pc and c <= po:
            return True, "Bearish Engulfing"
        # Shooting star: body kecil di bagian bawah range, upper wick panjang (penolakan harga tinggi)
        if body / range_total < 0.35 and upper_wick > body * 2 and lower_wick < body:
            return True, "Shooting Star"
        if c < o and body / range_total > 0.6:
            return True, "Strong Bearish Candle"
        return False, "tidak ada pola bearish yang jelas"


@dataclass
class IndicatorSnapshot:
    """Kumpulan semua indikator yang dihitung untuk satu siklus analisa —
    dipakai baik untuk keputusan teknikal maupun sebagai konteks yang
    dikirim ke AI Chart Analyst."""
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    last_close: float
    candlestick_match: bool
    candlestick_pattern: str

    def to_dict(self):
        return asdict(self)


def _compute_confirmation_score(direction: str, ind: IndicatorSnapshot) -> tuple[int, list[str]]:
    """Hitung berapa banyak indikator KONFIRMASI (setuju) dengan arah
    sinyal EMA+RSI dasar. Dipakai sebagai skor konfluensi multi-indikator
    sebelum meneruskan ke AI Chart Analyst untuk keputusan final.
    Return (jumlah_konfirmasi, daftar_alasan)."""
    confirmations = []

    if direction == "BUY":
        if ind.macd_histogram > 0:
            confirmations.append("MACD histogram positif (momentum naik)")
        if ind.last_close < ind.bb_middle:
            confirmations.append("Harga masih di bawah middle Bollinger Band (ruang naik ke rata-rata)")
        if ind.candlestick_match:
            confirmations.append(f"Pola candlestick mendukung: {ind.candlestick_pattern}")
    else:
        if ind.macd_histogram < 0:
            confirmations.append("MACD histogram negatif (momentum turun)")
        if ind.last_close > ind.bb_middle:
            confirmations.append("Harga masih di atas middle Bollinger Band (ruang turun ke rata-rata)")
        if ind.candlestick_match:
            confirmations.append(f"Pola candlestick mendukung: {ind.candlestick_pattern}")

    return len(confirmations), confirmations


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
        raise RuntimeError(
            f"Gagal ambil candle untuk symbol '{symbol}' ({timeframe_str}): {mt5.last_error()}. "
            f"Kemungkinan besar SIGNAL_SYMBOL di config.py tidak persis sama dengan nama symbol "
            f"di broker (umum terjadi di akun cent seperti HFM, contoh: perlu 'XAUUSD.c' bukan "
            f"'XAUUSD'). Cek nama exact di Market Watch MT5, lalu perbaiki config.py."
        )
    return rates


def _format_indicator_summary(direction: str, ind: IndicatorSnapshot, score: int, confirmations: list[str]) -> str:
    """Format ringkasan indikator jadi teks yang dikirim ke AI Chart
    Analyst — angka mentah, bukan gambar chart."""
    lines = [
        f"- EMA{config.EMA_FAST}: {ind.ema_fast:.2f}, EMA{config.EMA_SLOW}: {ind.ema_slow:.2f} (trend {'naik' if ind.ema_fast > ind.ema_slow else 'turun'})",
        f"- RSI({config.RSI_PERIOD}): {ind.rsi:.1f}",
        f"- MACD line: {ind.macd_line:.3f}, Signal line: {ind.macd_signal:.3f}, Histogram: {ind.macd_histogram:.3f}",
        f"- Bollinger Bands: upper={ind.bb_upper:.2f}, middle={ind.bb_middle:.2f}, lower={ind.bb_lower:.2f}, harga sekarang={ind.last_close:.2f}",
        f"- Pola candlestick terakhir: {ind.candlestick_pattern} ({'mendukung' if ind.candlestick_match else 'tidak mendukung'} arah {direction})",
        f"- Skor konfirmasi teknikal dasar: {score}/3 indikator tambahan sepakat ({'; '.join(confirmations) if confirmations else 'tidak ada konfirmasi tambahan'})",
    ]
    return "\n".join(lines)


def analyze() -> Optional[Signal]:
    """Jalankan satu kali analisa. Return Signal kalau ada sinyal valid
    DAN disetujui AI Chart Analyst (gate wajib), None kalau tidak (baik
    karena tidak ada sinyal teknikal, kena filter sesi/volatilitas,
    maupun ditolak AI Chart Analyst)."""
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

    # --- Konfirmasi multi-indikator (MACD, Bollinger Bands, candlestick) ---
    macd_line, macd_signal, macd_histogram = _macd(closes)
    bb_upper, bb_middle, bb_lower = _bollinger_bands(closes)
    candle_match, candle_pattern = _detect_candlestick_pattern(rates, direction)

    indicator_snapshot = IndicatorSnapshot(
        ema_fast=ema_fast[-1], ema_slow=ema_slow[-1], rsi=rsi, atr=atr,
        macd_line=macd_line, macd_signal=macd_signal, macd_histogram=macd_histogram,
        bb_upper=bb_upper, bb_middle=bb_middle, bb_lower=bb_lower,
        last_close=closes[-1], candlestick_match=candle_match, candlestick_pattern=candle_pattern,
    )
    score, confirmations = _compute_confirmation_score(direction, indicator_snapshot)

    # --- GATE WAJIB: AI Chart Analyst harus setuju sebelum sinyal diteruskan ---
    if config.USE_AI_CHART_ANALYST:
        indicator_summary = _format_indicator_summary(direction, indicator_snapshot, score, confirmations)
        chart_result = ai_chart_analyst.analyze_chart(direction, indicator_summary)

        gate_passed = chart_result.agree and chart_result.confidence >= config.AI_CHART_MIN_CONFIDENCE

        if chart_result.error and config.AI_CHART_FAIL_MODE == "fail_open":
            # Konfigurasi eksplisit memilih "lolos tanpa AI" kalau AI gagal
            log.info(f"AI Chart Analyst gagal ({chart_result.error}), fail_mode=fail_open -> sinyal tetap diteruskan tanpa gate AI.")
            gate_passed = True

        if not gate_passed:
            log.info(
                f"Sinyal {direction} DITOLAK oleh AI Chart Analyst gate: agree={chart_result.agree}, "
                f"confidence={chart_result.confidence:.2f} (min={config.AI_CHART_MIN_CONFIDENCE}). "
                f"Alasan: {chart_result.reason}"
            )
            return None
    else:
        chart_result = None

    # --- cek konteks berita/calendar sebelum finalisasi sinyal ---
    news_ctx = news_engine.evaluate()
    combined_reason = reason
    if chart_result and chart_result.agree:
        combined_reason = f"{reason}. AI Chart Analyst setuju (confidence={chart_result.confidence:.2f}): {chart_result.reason}"
    if news_ctx.status == "HIGH_IMPACT_NEWS":
        combined_reason = f"{combined_reason}. {news_ctx.reason}"

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
        reason=combined_reason,
        executed=False,
        news_status=news_ctx.status,
        news_reason=news_ctx.reason,
        ai_analysis=news_ctx.ai_analysis,
        chart_analysis=chart_result,
        confirmation_score=score,
        confirmation_details=confirmations,
    )


# ==============================================================
#  EXECUTION (entry baru)
# ==============================================================
def count_open_signal_positions() -> int:
    positions = mt5.positions_get(symbol=config.SIGNAL_SYMBOL)
    if positions is None:
        return 0
    return len([p for p in positions if p.magic == config.SIGNAL_MAGIC_NUMBER])


def execute_signal(sig: Signal, lot: float) -> Signal:
    order_type = mt5.ORDER_TYPE_BUY if sig.direction == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sig.symbol,
        "volume": lot,
        "type": order_type,
        "price": sig.entry_price,
        "sl": sig.sl,
        "tp": sig.tp3,  # TP native diarahkan ke TP3 (target terjauh); TP1/TP2 dikelola oleh position monitor (partial close + breakeven + trailing)
        "deviation": 20,
        "magic": config.SIGNAL_MAGIC_NUMBER,
        "comment": "auto-signal" if sig.news_status == "NORMAL" else "auto-signal-news",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5_utils.get_supported_filling_mode(sig.symbol),
    }
    result = mt5_utils.send_order_with_fallback(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        sig.executed = False
        sig.execution_detail = f"Gagal: {result.comment if result else 'order_send gagal total (cek koneksi MT5)'} (retcode={result.retcode if result else 'N/A'})"
        log.warning(f"Eksekusi sinyal gagal: {sig.execution_detail}")
    else:
        sig.executed = True
        sig.lot_used = lot
        sig.execution_detail = f"Order #{result.order} terbuka @ {result.price}, lot {lot}"
        log.info(f"Sinyal dieksekusi: {sig.direction} {sig.symbol} @ {result.price}, lot={lot}, news_status={sig.news_status}")

        # daftarkan posisi ini untuk dipantau (partial close di TP1, breakeven, trailing setelah TP2)
        state.tracked_positions[result.order] = PositionTracking(
            ticket=result.order,
            original_volume=lot,
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

    # --- Keputusan berdasarkan konteks berita ---
    # CALENDAR_BLACKOUT (CPI/NFP/FOMC dll dalam window rilis): sinyal
    # tetap ditampilkan sebagai info, TAPI tidak di-auto-eksekusi.
    #
    # HIGH_IMPACT_NEWS (geopolitik dll): entry TETAP mengikuti arah
    # sinyal TEKNIKAL (bukan arah AI). Ukuran lot ditentukan begini:
    #   - AI netral/gagal/confidence rendah -> lot NORMAL
    #   - AI SEARAH dengan sinyal teknikal    -> lot NORMAL (tidak dinaikkan)
    #   - AI BERLAWANAN arah sinyal teknikal  -> lot MINIMUM broker
    #     (tetap entry ikut teknikal, tapi risiko ditekan serendah mungkin)
    #
    # NORMAL: jalan seperti biasa dengan lot penuh.
    should_execute = config.AUTO_EXECUTE
    lot = config.SIGNAL_LOT_SIZE

    if sig.news_status == "CALENDAR_BLACKOUT":
        should_execute = False
        log.info(f"Sinyal terdeteksi tapi entry ditahan (calendar blackout): {sig.news_reason}")
    elif sig.news_status == "HIGH_IMPACT_NEWS":
        lot, lot_reason = _resolve_news_lot(sig)
        log.info(f"Sinyal dengan berita relevan, lot={lot} ({lot_reason}): {sig.news_reason}")

    if should_execute:
        sig = execute_signal(sig, lot)
        if sig.executed:
            state.last_entry_time = datetime.utcnow()

    state.push_signal(sig)


def _resolve_news_lot(sig: Signal) -> tuple[float, str]:
    """Tentukan ukuran lot untuk sinyal dengan status HIGH_IMPACT_NEWS,
    berdasarkan kecocokan arah sentimen AI dengan arah sinyal teknikal.
    Return (lot, alasan_singkat)."""
    ai = sig.ai_analysis

    min_lot = mt5.symbol_info(config.SIGNAL_SYMBOL).volume_min

    if ai is None or ai.error or ai.confidence < config.AI_MIN_CONFIDENCE or ai.sentiment == "neutral":
        return config.SIGNAL_LOT_SIZE, "AI netral/tidak yakin/tidak tersedia, lot normal"

    ai_direction = "BUY" if ai.sentiment == "bullish" else "SELL"  # bearish -> condong SELL

    if ai_direction == sig.direction:
        return config.SIGNAL_LOT_SIZE, f"AI searah sinyal teknikal ({ai.sentiment}), lot normal"
    else:
        return round(min_lot, 2), f"AI berlawanan arah sinyal teknikal ({ai.sentiment} vs {sig.direction}), lot diperkecil ke minimum"


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
    """Tutup sebagian posisi (PARTIAL_CLOSE_PERCENT dari volume awal).

    Guard penting: kalau volume awal posisi sudah sekecil lot minimum
    broker (misal 0.01 — kasus lot diperkecil karena AI mendeteksi
    berita berlawanan arah, lihat _resolve_news_lot()), maka partial
    close 40% dari situ akan dibulatkan NAIK ke lot minimum juga,
    yang artinya menutup 100% posisi alih-alih sebagian. Dalam kasus
    itu, partial close DILEWATI SELURUHNYA — biarkan posisi utuh
    berjalan menuju TP1/TP2/TP3 secara normal (breakeven & trailing
    tetap berjalan seperti biasa di titik TP1/TP2)."""
    info = mt5.symbol_info(pos.symbol)
    raw_close_volume = tracking.original_volume * config.PARTIAL_CLOSE_PERCENT / 100

    if raw_close_volume < info.volume_min:
        log.info(
            f"Partial close dilewati untuk #{pos.ticket}: volume awal ({tracking.original_volume}) "
            f"terlalu kecil untuk dibagi {config.PARTIAL_CLOSE_PERCENT}% tanpa menutup seluruh posisi. "
            f"Posisi dibiarkan utuh, breakeven & trailing tetap berjalan normal."
        )
        return "skipped_too_small"

    close_volume = _round_lot(pos.symbol, raw_close_volume)
    close_volume = min(close_volume, pos.volume)  # jangan lebih besar dari sisa posisi

    # Guard tambahan: kalau setelah dibulatkan ternyata tetap sama dengan
    # seluruh sisa posisi, batalkan partial close (bukan partial lagi namanya)
    if close_volume >= pos.volume:
        log.info(f"Partial close dilewati untuk #{pos.ticket}: hasil pembulatan lot sama dengan seluruh posisi.")
        return "skipped_too_small"

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
        "type_filling": mt5_utils.get_supported_filling_mode(pos.symbol),
    }
    result = mt5_utils.send_order_with_fallback(request)
    ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
    if ok:
        log.info(f"Partial close TP1: posisi #{pos.ticket}, {close_volume} lot ditutup @ {price}")
    else:
        log.warning(f"Partial close gagal untuk #{pos.ticket}: {result.comment if result else 'order_send gagal total'}")
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
    ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
    if not ok:
        log.warning(f"Modify SL/TP gagal untuk #{pos.ticket}: {result.comment if result else 'order_send gagal total'}")
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
                result = _partial_close(pos, tracking)
                # result bisa: True (berhasil), False (order gagal, akan
                # dicoba lagi di siklus berikutnya), atau "skipped_too_small"
                # (lot awal terlalu kecil untuk dibagi tanpa menutup semua —
                # dianggap selesai, posisi dibiarkan utuh lanjut ke TP2/TP3)
                if result is True or result == "skipped_too_small":
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
                "type_filling": mt5_utils.get_supported_filling_mode(p.symbol),
            }
            result = mt5_utils.send_order_with_fallback(request)
            closed.append({
                "ticket": p.ticket,
                "ok": result is not None and result.retcode == mt5.TRADE_RETCODE_DONE,
                "detail": result.comment if result else "order_send gagal total (cek koneksi MT5)",
            })
    state.tracked_positions.clear()
    log.warning(f"EMERGENCY STOP dipicu. Posisi ditutup: {closed}")
    return closed


def resume():
    """Aktifkan lagi signal engine setelah emergency stop."""
    state.enabled = True
    state.last_error = None
