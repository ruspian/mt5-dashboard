"""
Correlation Engine
====================
Menghitung heatmap korelasi harian antara XAUUSD dengan aset-aset yang
relevan secara makro (DXY, EUR/USD, US 10Y yield, minyak WTI, perak,
S&P 500, Bitcoin) memakai yfinance (data gratis dari Yahoo Finance,
tanpa API key). Daftar asetnya bisa diedit lewat config.CORRELATION_ASSETS.

Kenapa ini berguna: emas historisnya berkorelasi NEGATIF dengan DXY
(dollar index) — dolar melemah, emas cenderung naik (karena emas
dihargakan dalam USD), dan sebaliknya. Tapi hubungan itu TIDAK selalu
konstan; kadang "decoupling" saat ada guncangan geopolitik/safe haven
flow besar. Heatmap ini menghitung korelasi rolling dari data aktual,
bukan cuma asumsi tetap, supaya kelihatan apakah hubungan itu masih
kuat berlaku saat ini.

CATATAN JUJUR — PENTING:
    - Data yfinance untuk ticker index/futures (DXY, yield, dll) itu
      END-OF-DAY, bukan realtime tick-by-tick. Heatmap ini jadi
      mencerminkan korelasi HARIAN — cocok untuk analisa rezim
      korelasi jangka menengah, TAPI jangan disalahartikan sebagai
      indikator harga live (untuk itu tetap pakai data MT5 langsung
      yang sudah ada di dashboard).
    - yfinance itu scraping endpoint publik Yahoo Finance, BUKAN API
      resmi dengan kontrak/SLA — kalau Yahoo ubah struktur data,
      fetch bisa gagal sewaktu-waktu. Kalau itu terjadi, fitur ini
      cuma menampilkan status error di web app (lihat state.last_error)
      — TIDAK memengaruhi signal engine atau bagian bot lain sama
      sekali, karena murni informational dan tidak dipakai untuk
      keputusan entry otomatis.
    - Korelasi dihitung dari %change harian (return), BUKAN harga
      mentah — ini standar di analisa korelasi finansial, supaya tidak
      bias oleh skala/trend harga masing-masing aset (harga emas ~2600
      dan DXY ~100 tidak bisa dikorelasikan langsung dari level
      harganya, harus dari pergerakan relatifnya).
    - Kalau satu aset di CORRELATION_ASSETS gagal diambil datanya
      (misal ticker salah/di-delist), aset itu di-skip, TIDAK bikin
      seluruh heatmap gagal — kecuali yang gagal adalah ticker XAUUSD
      itu sendiri (tanpa itu heatmap tidak ada gunanya sama sekali).
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import config

log = logging.getLogger("correlation-engine")


@dataclass
class CorrelationMatrix:
    assets: list[str]
    matrix: list[list[Optional[float]]]
    period_days: int
    computed_at: str

    def to_dict(self):
        return asdict(self)


class CorrelationEngineState:
    def __init__(self):
        self.last_fetch_time: Optional[str] = None
        self.last_error: Optional[str] = None
        self.matrix: Optional[CorrelationMatrix] = None


state = CorrelationEngineState()


def _fetch_and_compute() -> CorrelationMatrix:
    # Import di dalam fungsi (bukan di top-level) supaya bridge tetap bisa
    # jalan normal walau yfinance/pandas belum ke-install — cuma fitur
    # heatmap ini yang error, bukan seluruh bridge gagal start.
    import yfinance as yf
    import pandas as pd

    tickers = [t for t, _ in config.CORRELATION_ASSETS]
    labels = {t: label for t, label in config.CORRELATION_ASSETS}

    raw = yf.download(
        tickers,
        period=f"{config.CORRELATION_LOOKBACK_DAYS}d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    closes = {}
    for t in tickers:
        try:
            series = raw["Close"] if len(tickers) == 1 else raw[t]["Close"]
            series = series.dropna()
            if len(series) >= config.CORRELATION_MIN_DATA_POINTS:
                closes[t] = series
            else:
                log.warning(
                    f"Data '{t}' cuma {len(series)} titik (< {config.CORRELATION_MIN_DATA_POINTS} minimum), di-skip dari heatmap."
                )
        except Exception as e:
            log.warning(f"Gagal ambil data '{t}' dari yfinance: {e}")

    if config.CORRELATION_XAUUSD_TICKER not in closes:
        raise RuntimeError(
            f"Data harga untuk '{config.CORRELATION_XAUUSD_TICKER}' (proxy XAUUSD) tidak tersedia dari "
            f"yfinance — tidak bisa hitung korelasi apa pun. Cek koneksi internet VPS atau coba ganti "
            f"CORRELATION_XAUUSD_TICKER di config.py (misal ke 'XAUUSD=X')."
        )

    df = pd.DataFrame(closes).dropna(how="all")
    returns = df.pct_change().dropna(how="all")
    corr_df = returns.corr()

    ordered = [t for t in tickers if t in corr_df.columns]
    asset_labels = [labels.get(t, t) for t in ordered]

    matrix: list[list[Optional[float]]] = []
    for t1 in ordered:
        row = []
        for t2 in ordered:
            val = corr_df.loc[t1, t2]
            row.append(None if pd.isna(val) else round(float(val), 3))
        matrix.append(row)

    return CorrelationMatrix(
        assets=asset_labels,
        matrix=matrix,
        period_days=config.CORRELATION_LOOKBACK_DAYS,
        computed_at=datetime.utcnow().isoformat() + "Z",
    )


def refresh():
    """Dipanggil berkala oleh background loop di main.py (lewat
    asyncio.to_thread supaya panggilan yfinance yang blocking tidak
    macetin event loop FastAPI)."""
    if not config.USE_CORRELATION_ENGINE:
        return
    try:
        state.matrix = _fetch_and_compute()
        state.last_error = None
        log.info(f"Correlation heatmap berhasil di-refresh: {len(state.matrix.assets)} aset.")
    except Exception as e:
        state.last_error = str(e)
        log.warning(f"Correlation engine refresh gagal: {e}")
    state.last_fetch_time = datetime.utcnow().isoformat() + "Z"
