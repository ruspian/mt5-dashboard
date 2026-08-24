"""
News Engine
============
Memantau 2 sumber independen:

1. Economic calendar — jadwal rilis data terjadwal (CPI, NFP, FOMC, dll).
   Dipakai untuk membuat "blackout window": signal engine tidak auto-entry
   di sekitar waktu rilis high-impact karena harga bisa gap/spike tajam.
   Provider diatur lewat config.CALENDAR_PROVIDER:
     - "trading_economics": pakai API key guest:guest (gratis, tapi tidak
       dijamin selalu tersedia/lengkap — lihat catatan di
       _fetch_calendar_trading_economics())
     - "manual": jadwal diisi sendiri di config.MANUAL_CALENDAR_EVENTS,
       paling pasti berjalan karena tidak bergantung API pihak ketiga
     - "none": matikan fitur blackout calendar sepenuhnya
   Kalau provider "trading_economics" gagal atau kosong, OTOMATIS
   fallback ke "manual" (kalau ada isinya) — supaya blackout window
   tetap berfungsi walau API pihak ketiga bermasalah/berubah kebijakan.

2. Berita umum — sekarang MULTI-SUMBER, tidak lagi bergantung ke satu
   provider saja:
     - RSS feeds gratis (config.NEWS_RSS_FEEDS) — format XML terbuka
       standar yang di-publish resmi situs berita (default: Investing.com
       Commodities & Forex), TIDAK BUTUH API KEY, dan jauh lebih stabil
       daripada API pihak ketiga karena tidak bisa "dimatikan" lewat
       kebijakan tier seperti yang terjadi pada Finnhub calendar &
       Trading Economics guest key sebelumnya.
     - Finnhub /news (opsional, kalau FINNHUB_API_KEY diisi) — tetap
       dipertahankan sebagai sumber TAMBAHAN, bukan pengganti.
   Semua sumber diambil independen dan digabung (dedup lewat URL) —
   kalau satu sumber gagal/mati, sumber lain tetap jalan. Dicari
   keyword yang relevan ke emas (geopolitik, safe haven, dll) sebagai
   filter awal, lalu berita yang lolos dikirim ke AI News Analyst
   (ai_news_analyst.py) untuk dinilai lebih dalam: relevan atau tidak,
   arah sentimen (bullish/bearish/netral), dan tingkat keyakinan. Hasil
   ini dipakai signal_engine.py untuk menentukan ukuran lot (lihat
   matriks keputusan di config.py bagian 10).

CATATAN JUJUR — PENTING:
Tahap 1 (keyword matching) BUKAN pemahaman bahasa alami — murni mencari
kata kunci pada judul/ringkasan, dan JADWAL dari calendar API/manual. Ini
bisa false positive (kata cocok tapi tidak relevan) atau false negative
(berita penting tapi tidak memakai kata kunci terdaftar).

Tahap 2 (AI News Analyst) memahami konteks lebih baik, tapi TETAP bisa
salah baca nuansa (sarkasme, artikel opini vs breaking news, dll), dan
bergantung pada ketersediaan/kualitas provider AI yang dipakai. Kalau
AI gagal/timeout, sistem otomatis fallback ke netral — tidak pernah
menghentikan bridge. Arah entry SELALU mengikuti sinyal teknikal, AI
hanya mempengaruhi ukuran lot.

Kedua sumber data (calendar & berita) SENGAJA independen satu sama lain
di refresh() — kalau salah satu gagal (misal API pihak ketiga berubah
kebijakan lagi), yang lain tetap jalan normal, dan error masing-masing
tercatat terpisah supaya jelas sumber masalahnya di log & web app.

Pantau log & riwayat sinyal secara berkala untuk memastikan perilakunya
sesuai ekspektasi. Kalau banyak false positive, sesuaikan/kurangi
keyword di config.py.
"""

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from typing import Optional
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests

import config
import ai_news_analyst

log = logging.getLogger("news-engine")

FINNHUB_BASE = "https://finnhub.io/api/v1"
TRADING_ECONOMICS_BASE = "https://api.tradingeconomics.com"
WIB = ZoneInfo("Asia/Jakarta")


@dataclass
class CalendarEvent:
    event: str
    country: str
    time: str          # ISO
    impact: str         # low/medium/high
    actual: Optional[str] = None
    estimate: Optional[str] = None
    prev: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class NewsItem:
    headline: str
    summary: str
    source: str
    time: str           # ISO
    url: str
    matched_keywords: list[str]

    def to_dict(self):
        return asdict(self)


@dataclass
class NewsContext:
    """Hasil evaluasi news engine pada satu titik waktu — dipakai
    signal_engine.analyze() untuk memutuskan boleh/tidak entry, dan
    apakah harus mengecilkan lot."""
    status: str  # "NORMAL" | "CALENDAR_BLACKOUT" | "HIGH_IMPACT_NEWS"
    reason: str
    active_calendar_event: Optional[CalendarEvent] = None
    active_news: Optional[NewsItem] = None
    ai_analysis: Optional["ai_news_analyst.AIAnalysis"] = None

    def to_dict(self):
        d = {
            "status": self.status,
            "reason": self.reason,
            "active_calendar_event": self.active_calendar_event.to_dict() if self.active_calendar_event else None,
            "active_news": self.active_news.to_dict() if self.active_news else None,
            "ai_analysis": self.ai_analysis.to_dict() if self.ai_analysis else None,
        }
        return d


class NewsEngineState:
    def __init__(self):
        self.last_fetch_time: Optional[str] = None
        self.last_error: Optional[str] = None
        self.upcoming_calendar: list[CalendarEvent] = []
        self.recent_news: list[NewsItem] = []
        self.last_context: Optional[NewsContext] = None
        # Cache hasil AI per URL berita, supaya berita yang sama tidak
        # dikirim ulang ke AI tiap siklus signal check (bisa tiap 15 detik)
        # selama masih dalam window kesegaran yang sama. Key: url berita,
        # value: AIAnalysis. Dibersihkan otomatis saat refresh() menemukan
        # berita itu sudah tidak ada lagi di recent_news (kadaluarsa).
        self.ai_cache: dict[str, "ai_news_analyst.AIAnalysis"] = {}
        # True kalau MANUAL_CALENDAR_EVENTS sudah tidak punya event yang
        # akan datang dalam CALENDAR_LOW_WARNING_DAYS ke depan — tanda
        # bahwa daftar manual di config.py perlu di-update lagi supaya
        # blackout window tidak bolong diam-diam.
        self.calendar_running_low: bool = False
        self.calendar_running_low_message: Optional[str] = None
        # True kalau SEMUA sumber berita (RSS + Finnhub) gagal fetch di
        # siklus refresh() terakhir — berarti AI News Analyst tidak
        # punya input apa pun untuk dianalisa saat ini.
        self.all_news_sources_failed: bool = False


state = NewsEngineState()


# ==============================================================
#  FETCH ECONOMIC CALENDAR (multi-provider, dengan fallback aman)
# ==============================================================
def _fetch_calendar_trading_economics() -> list[CalendarEvent]:
    """Provider: Trading Economics. Endpoint 'by date + importance'.
    importance=3 berarti high-impact di skema mereka (1=low, 2=medium, 3=high).

    CATATAN: dengan API key demo (guest:guest), Trading Economics sering
    hanya mengembalikan data SAMPEL (negara/tanggal terbatas), bukan data
    live semua negara. Kode ini tetap memparsingnya dengan benar KALAU
    API mengembalikan data asli — tapi kalau hasilnya kosong terus,
    kemungkinan besar itu keterbatasan tier gratis, bukan bug di sini."""
    today = datetime.now(timezone.utc).date()
    frm = (today - timedelta(days=2)).isoformat()
    to = (today + timedelta(days=2)).isoformat()

    url = f"{TRADING_ECONOMICS_BASE}/calendar/country/All/{frm}/{to}"
    resp = requests.get(
        url,
        params={"c": config.TRADING_ECONOMICS_API_KEY, "importance": 3, "f": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise ValueError(f"Format respons Trading Economics tidak terduga: {type(data)}")

    events = []
    for row in data:
        country = row.get("Country", "")
        # Trading Economics pakai nama negara penuh ("United States"),
        # sedangkan config pakai kode ("US") — cocokkan secara longgar
        country_code = _country_name_to_code(country)
        if config.NEWS_CALENDAR_COUNTRIES and country_code not in config.NEWS_CALENDAR_COUNTRIES:
            continue
        events.append(
            CalendarEvent(
                event=row.get("Event", "Unknown event"),
                country=country_code,
                time=row.get("Date", ""),
                impact="high",  # sudah difilter importance=3 di request
                actual=row.get("Actual") or None,
                estimate=row.get("Forecast") or None,
                prev=row.get("Previous") or None,
            )
        )
    return events


def _country_name_to_code(name: str) -> str:
    """Pemetaan sederhana nama negara -> kode, cukup untuk negara yang
    umum dipakai di NEWS_CALENDAR_COUNTRIES. Tambah sendiri kalau perlu."""
    mapping = {
        "United States": "US",
        "Euro Area": "EU",
        "United Kingdom": "GB",
        "Japan": "JP",
        "China": "CN",
        "Australia": "AU",
        "Canada": "CA",
    }
    return mapping.get(name, name)


def _fetch_calendar_manual() -> list[CalendarEvent]:
    """Provider: jadwal manual dari config.MANUAL_CALENDAR_EVENTS.
    Tidak bergantung API apa pun — paling pasti berjalan, tapi perlu
    di-update manual oleh user saat ada jadwal rilis baru."""
    events = []
    for item in config.MANUAL_CALENDAR_EVENTS:
        try:
            # time_wib diisi user dalam WIB, dikonversi ke UTC untuk
            # konsistensi dengan sisa sistem (semua timestamp lain pakai UTC)
            local_dt = datetime.strptime(item["time_wib"], "%Y-%m-%d %H:%M").replace(tzinfo=WIB)
            utc_dt = local_dt.astimezone(timezone.utc)
        except (KeyError, ValueError) as e:
            log.warning(f"Format MANUAL_CALENDAR_EVENTS tidak valid untuk entry {item}: {e}")
            continue
        events.append(
            CalendarEvent(
                event=item.get("event", "Unknown event"),
                country=item.get("country", "US"),
                time=utc_dt.isoformat(),
                impact=item.get("impact", "high"),
            )
        )
    return events


def _fetch_calendar_forex_factory() -> list[CalendarEvent]:
    """Provider: Forex Factory weekly calendar feed (resmi dipublikasikan
    Forex Factory sendiri untuk konsumsi publik/EA, bukan scraping HTML
    tidak resmi). Sudah dipakai luas oleh komunitas MT4/MT5 selama
    bertahun-tahun. Format: JSON per event dengan title/country/date/
    impact/forecast/previous.

    PENTING — RATE LIMIT: Forex Factory MEMBATASI jumlah request ke feed
    ini (lebih dari beberapa ribu request/bulan secara global akan kena
    block sementara, sesuai pengumuman resmi mereka). Karena data
    calendar mingguan tidak berubah tiap menit, fungsi ini di-cache
    selama CALENDAR_FF_CACHE_HOURS jam (default 6 jam) — TIDAK fetch
    ulang tiap kali dipanggil, walau news_engine_loop jalan tiap
    beberapa menit. Jangan turunkan interval cache ini terlalu agresif.

    CATATAN JUJUR: ini feed publik pihak ketiga (bukan API resmi dengan
    kontrak layanan/SLA) — URL atau format bisa berubah sewaktu-waktu
    tanpa pemberitahuan (sudah beberapa kali pindah domain di masa lalu:
    forexfactory.com -> cdn-nfs.forexfactory.net -> nfs.faireconomy.media).
    Kalau tiba-tiba berhenti berfungsi, itu bukan bug di kode ini —
    fallback otomatis ke MANUAL_CALENDAR_EVENTS akan tetap menjaga
    blackout window berfungsi."""
    now = datetime.now(timezone.utc)
    if (
        _ff_calendar_cache["events"] is not None
        and _ff_calendar_cache["fetched_at"] is not None
        and (now - _ff_calendar_cache["fetched_at"]) < timedelta(hours=config.CALENDAR_FF_CACHE_HOURS)
    ):
        return _ff_calendar_cache["events"]

    resp = requests.get(
        FOREX_FACTORY_JSON_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; mt5-dashboard-bridge/1.0)"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise ValueError(f"Format respons Forex Factory tidak terduga: {type(data)}")

    impact_map = {"High": "high", "Medium": "medium", "Low": "low", "Holiday": "low"}

    events = []
    for row in data:
        country = row.get("country", "")
        if config.NEWS_CALENDAR_COUNTRIES and country not in config.NEWS_CALENDAR_COUNTRIES:
            continue

        impact_raw = row.get("impact", "")
        impact = impact_map.get(impact_raw, "low")

        # Forex Factory JSON feed memberi date+time sebagai ISO 8601
        # dengan timezone (biasanya sudah UTC atau ada offset eksplisit)
        event_time = row.get("date", "")

        events.append(
            CalendarEvent(
                event=row.get("title", "Unknown event"),
                country=country,
                time=event_time,
                impact=impact,
                actual=row.get("actual") or None,
                estimate=row.get("forecast") or None,
                prev=row.get("previous") or None,
            )
        )

    _ff_calendar_cache["events"] = events
    _ff_calendar_cache["fetched_at"] = now
    log.info(f"Forex Factory calendar berhasil di-fetch: {len(events)} event (di-cache {config.CALENDAR_FF_CACHE_HOURS} jam).")
    return events


# Cache module-level (bukan di NewsEngineState) karena ini murni soal
# rate-limiting HTTP, bukan state yang perlu diekspos ke web app
_ff_calendar_cache: dict = {"events": None, "fetched_at": None}
FOREX_FACTORY_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def _fetch_economic_calendar() -> list[CalendarEvent]:
    """Dispatcher: coba provider yang dipilih di config, fallback ke
    manual kalau gagal/kosong, supaya blackout window CPI/NFP/FOMC
    tetap bisa berfungsi walau API pihak ketiga bermasalah."""
    if config.CALENDAR_PROVIDER == "none":
        return []

    if config.CALENDAR_PROVIDER == "manual":
        return _fetch_calendar_manual()

    if config.CALENDAR_PROVIDER == "forex_factory":
        try:
            events = _fetch_calendar_forex_factory()
            if events:
                return events
            log.info(
                "Forex Factory calendar mengembalikan 0 event yang cocok filter negara. "
                f"Fallback ke MANUAL_CALENDAR_EVENTS ({len(config.MANUAL_CALENDAR_EVENTS)} entry terisi)."
            )
            return _fetch_calendar_manual()
        except requests.RequestException as e:
            log.warning(f"Forex Factory calendar gagal ({e}), fallback ke MANUAL_CALENDAR_EVENTS.")
            return _fetch_calendar_manual()
        except (ValueError, KeyError) as e:
            log.warning(f"Gagal parse respons Forex Factory ({e}), fallback ke MANUAL_CALENDAR_EVENTS.")
            return _fetch_calendar_manual()

    if config.CALENDAR_PROVIDER == "trading_economics":
        try:
            events = _fetch_calendar_trading_economics()
            if events:
                return events
            log.info(
                "Trading Economics calendar API mengembalikan 0 event high-impact yang cocok. "
                "Ini bisa berarti memang tidak ada rilis high-impact dalam window ini, ATAU "
                "keterbatasan API key demo (guest:guest) yang cuma kasih data sampel. "
                f"Fallback ke MANUAL_CALENDAR_EVENTS ({len(config.MANUAL_CALENDAR_EVENTS)} entry terisi)."
            )
            return _fetch_calendar_manual()
        except requests.RequestException as e:
            log.warning(f"Trading Economics calendar API gagal ({e}), fallback ke MANUAL_CALENDAR_EVENTS.")
            return _fetch_calendar_manual()
        except (ValueError, KeyError) as e:
            log.warning(f"Gagal parse respons Trading Economics ({e}), fallback ke MANUAL_CALENDAR_EVENTS.")
            return _fetch_calendar_manual()

    log.warning(f"CALENDAR_PROVIDER '{config.CALENDAR_PROVIDER}' tidak dikenal, fallback ke manual.")
    return _fetch_calendar_manual()


def _parse_rss_pubdate(pubdate_str: str) -> Optional[datetime]:
    """RSS pakai format RFC 2822 untuk tanggal (misal 'Mon, 23 Aug 2026
    19:39:57 +0000'), tapi beberapa feed pakai format lain — coba
    beberapa cara parsing sebelum menyerah."""
    if not pubdate_str:
        return None
    try:
        dt = parsedate_to_datetime(pubdate_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass
    # fallback: format "YYYY-MM-DD HH:MM:SS" tanpa timezone info (dilihat
    # dari contoh respons Investing.com, mereka pakai UTC tanpa offset eksplisit)
    try:
        dt = datetime.strptime(pubdate_str.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fetch_news_rss(feed_url: str, source_label: str) -> list[NewsItem]:
    """Ambil & parse satu RSS feed. RSS adalah format XML terbuka standar
    yang di-publish resmi oleh situs berita — tidak butuh API key dan
    jauh lebih stabil daripada API pihak ketiga yang bisa berubah
    kebijakan (seperti kasus Finnhub calendar & Trading Economics guest
    key yang sebelumnya mendadak berhenti berfungsi)."""
    resp = requests.get(feed_url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; MT5Bridge/1.0)"})
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.NEWS_FRESHNESS_MINUTES)

    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")

        headline_raw = title_el.text if title_el is not None else ""
        link = link_el.text if link_el is not None else ""
        pub_time = _parse_rss_pubdate(pubdate_el.text if pubdate_el is not None else "")

        if pub_time is None or pub_time < cutoff:
            continue
        if not headline_raw:
            continue

        headline_lower = headline_raw.lower()
        matched = [kw for kw in config.NEWS_GOLD_KEYWORDS if kw in headline_lower]
        if not matched:
            continue

        items.append(
            NewsItem(
                headline=headline_raw,
                summary="",  # RSS feed publik biasanya tidak menyertakan ringkasan lengkap
                source=source_label,
                time=pub_time.isoformat(),
                url=link,
                matched_keywords=matched,
            )
        )
    return items


def _fetch_news_finnhub() -> list[NewsItem]:
    resp = requests.get(
        f"{FINNHUB_BASE}/news",
        params={"category": "general", "token": config.FINNHUB_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.NEWS_FRESHNESS_MINUTES)
    items = []
    for row in data:
        try:
            pub_time = datetime.fromtimestamp(row.get("datetime", 0), tz=timezone.utc)
        except (ValueError, OSError):
            continue
        if pub_time < cutoff:
            continue

        headline_raw = row.get("headline") or ""
        summary_raw = row.get("summary") or ""
        headline_lower = (headline_raw + " " + summary_raw).lower()

        matched = [kw for kw in config.NEWS_GOLD_KEYWORDS if kw in headline_lower]
        if not matched:
            continue

        items.append(
            NewsItem(
                headline=headline_raw,
                summary=summary_raw,
                source=row.get("source", "Finnhub"),
                time=pub_time.isoformat(),
                url=row.get("url", ""),
                matched_keywords=matched,
            )
        )
    return items


def _fetch_all_news() -> tuple[list[NewsItem], list[str]]:
    """Gabungkan berita dari SEMUA sumber yang aktif (RSS + Finnhub kalau
    key diisi). Tiap sumber independen — kalau satu gagal, sumber lain
    tetap dicoba, dan error masing-masing dikumpulkan terpisah (bukan
    membuat seluruh fetch berita gagal total). Duplikat (URL sama dari
    lebih dari satu sumber) dihilangkan."""
    all_items: list[NewsItem] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    # --- RSS feeds (gratis, tanpa API key, format terbuka standar) ---
    if config.USE_NEWS_RSS_FEEDS:
        for feed_url, label in config.NEWS_RSS_FEEDS:
            try:
                items = _fetch_news_rss(feed_url, label)
                for item in items:
                    if item.url and item.url in seen_urls:
                        continue
                    seen_urls.add(item.url)
                    all_items.append(item)
            except Exception as e:
                errors.append(f"RSS '{label}' gagal: {e}")
                log.warning(errors[-1])

    # --- Finnhub (opsional, butuh API key) ---
    if config.FINNHUB_API_KEY and not config.FINNHUB_API_KEY.startswith("ISI_"):
        try:
            items = _fetch_news_finnhub()
            for item in items:
                if item.url and item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                all_items.append(item)
        except requests.RequestException as e:
            errors.append(f"Finnhub gagal: {e}")
            log.warning(errors[-1])
        except Exception as e:
            errors.append(f"Finnhub error tak terduga: {e}")
            log.warning(errors[-1])

    all_items.sort(key=lambda n: n.time, reverse=True)
    return all_items, errors


def _warn_if_calendar_running_low():
    """Cek apakah MANUAL_CALENDAR_EVENTS (yang jadi fallback utama/satu-
    satunya sumber blackout window) sudah kehabisan event yang akan
    datang dalam waktu dekat. Kalau ya, catat warning di log DAN simpan
    statusnya di state supaya web app juga bisa menampilkan pengingat —
    tujuannya supaya lo tidak lupa update jadwal manual setelah semua
    tanggal yang diisi sudah lewat."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=config.CALENDAR_LOW_WARNING_DAYS)

    upcoming_high_impact = [
        e for e in state.upcoming_calendar
        if e.impact == "high" and _parse_event_time(e.time) and now <= _parse_event_time(e.time) <= horizon
    ]

    if upcoming_high_impact:
        state.calendar_running_low = False
        state.calendar_running_low_message = None
        return

    state.calendar_running_low = True
    state.calendar_running_low_message = (
        f"Tidak ada event calendar high-impact terjadwal dalam {config.CALENDAR_LOW_WARNING_DAYS} hari ke depan. "
        f"Kemungkinan besar MANUAL_CALENDAR_EVENTS di config.py perlu ditambah jadwal baru (cek bls.gov/schedule/ "
        f"dan federalreserve.gov/newsevents/calendar.htm), supaya blackout window CPI/NFP/FOMC tidak bolong."
    )
    log.warning(state.calendar_running_low_message)


def _parse_event_time(time_str: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def refresh():
    """Dipanggil berkala oleh background loop di main.py. Update state
    dengan data calendar & berita terbaru. Dua sumber (calendar dan
    berita umum) SENGAJA independen satu sama lain — kalau salah satu
    gagal, yang lain tetap ter-update, dan error masing-masing dicatat
    terpisah supaya jelas sumber masalahnya."""
    if not config.USE_NEWS_ENGINE:
        return

    errors = []

    # --- Economic calendar: independen, sudah punya fallback sendiri
    # (multi-provider + manual override) di _fetch_economic_calendar() ---
    try:
        state.upcoming_calendar = _fetch_economic_calendar()
        _warn_if_calendar_running_low()
    except Exception as e:
        errors.append(f"Calendar gagal total (termasuk fallback manual): {e}")
        log.warning(errors[-1])

    # --- Berita umum: independen dari calendar. Sekarang multi-sumber
    # (RSS gratis tanpa API key + Finnhub kalau key diisi) — kalau satu
    # sumber gagal/mati, sumber lain tetap jalan, tidak semua-atau-tidak-
    # sama-sekali seperti sebelumnya (waktu cuma andalkan Finnhub saja).
    try:
        news_items, news_errors = _fetch_all_news()
        state.recent_news = news_items
        errors.extend(news_errors)

        # Bersihkan cache AI dari berita yang sudah tidak ada lagi di
        # recent_news (kadaluarsa lewat NEWS_FRESHNESS_MINUTES, atau
        # sudah tidak relevan lagi) — supaya cache tidak terus membesar
        # tanpa batas selama bridge berjalan lama.
        active_urls = {n.url for n in state.recent_news}
        state.ai_cache = {url: result for url, result in state.ai_cache.items() if url in active_urls}

        # Deteksi kasus PALING PENTING untuk diketahui user: SEMUA sumber
        # berita gagal total (bukan cuma sebagian). Ini berarti AI News
        # Analyst tidak punya input apa pun untuk dianalisa — signal
        # engine tetap jalan (murni teknikal), tapi tanpa filter/boost
        # dari berita sama sekali. Beda dengan calendar_running_low
        # (yang soal jadwal habis), ini soal SEMUA percobaan fetch
        # berita gagal di siklus ini.
        total_sources_attempted = (1 if config.USE_NEWS_RSS_FEEDS else 0) + (
            1 if (config.FINNHUB_API_KEY and not config.FINNHUB_API_KEY.startswith("ISI_")) else 0
        )
        total_sources_failed = len(news_errors)
        state.all_news_sources_failed = (
            total_sources_attempted > 0 and len(news_items) == 0 and total_sources_failed >= total_sources_attempted
        )
    except Exception as e:
        errors.append(f"Error tak terduga saat fetch berita: {e}")
        log.warning(errors[-1])
        state.all_news_sources_failed = True

    state.last_error = " | ".join(errors) if errors else None
    state.last_fetch_time = datetime.utcnow().isoformat() + "Z"


# ==============================================================
#  EVALUASI: dipanggil signal_engine.analyze() sebelum entry
# ==============================================================
def _is_calendar_overlap(news_headline: str) -> bool:
    headline_lower = news_headline.lower()
    return any(kw in headline_lower for kw in config.NEWS_CALENDAR_OVERLAP_KEYWORDS)


def evaluate() -> NewsContext:
    """Return status news engine saat ini. Dipanggil tiap kali signal
    engine mau memutuskan entry baru."""
    if not config.USE_NEWS_ENGINE:
        ctx = NewsContext(status="NORMAL", reason="News engine dimatikan di config")
        state.last_context = ctx
        return ctx

    now = datetime.now(timezone.utc)

    # --- 1. Cek blackout window dari economic calendar ---
    for ev in state.upcoming_calendar:
        if ev.impact != "high":
            continue
        ev_time = _parse_event_time(ev.time)
        if ev_time is None:
            continue

        before = timedelta(minutes=config.CALENDAR_BLACKOUT_BEFORE_MIN)
        after = timedelta(minutes=config.CALENDAR_BLACKOUT_AFTER_MIN)
        if (ev_time - before) <= now <= (ev_time + after):
            ctx = NewsContext(
                status="CALENDAR_BLACKOUT",
                reason=f"Dalam window rilis high-impact: {ev.event} ({ev.country}) pada {ev.time}. Auto-entry dijeda.",
                active_calendar_event=ev,
            )
            state.last_context = ctx
            return ctx

    # --- 2. Cek berita umum high-impact (geopolitik, dll) ---
    # ambil berita ter-relevan yang BUKAN overlap dengan calendar event
    # (supaya CPI/NFP/FOMC tidak diproses dua kali lewat jalur berita umum)
    for news in state.recent_news:
        if _is_calendar_overlap(news.headline):
            continue

        # Tahap 2: kirim ke AI News Analyst untuk penilaian lebih dalam.
        # Pakai cache per-URL supaya berita yang sama tidak dikirim ulang
        # ke AI tiap siklus signal check (bisa tiap 15 detik) selama berita
        # itu masih dalam window kesegaran yang sama — hemat kuota API.
        # Kalau AI gagal/dimatikan, ai_result akan berisi fallback netral
        # (lihat ai_news_analyst.py) — tidak pernah melempar exception ke sini.
        ai_result = state.ai_cache.get(news.url)
        if ai_result is None:
            ai_result = ai_news_analyst.analyze_news(news.headline, news.summary)
            state.ai_cache[news.url] = ai_result

        reason = f"Berita relevan terdeteksi: \"{news.headline}\" (kata kunci: {', '.join(news.matched_keywords)})"
        if ai_result.confidence >= config.AI_MIN_CONFIDENCE and not ai_result.error:
            reason += f". Penilaian AI ({ai_result.provider}): {ai_result.sentiment}, confidence={ai_result.confidence:.2f} — {ai_result.reason}"

        ctx = NewsContext(
            status="HIGH_IMPACT_NEWS",
            reason=reason,
            active_news=news,
            ai_analysis=ai_result,
        )
        state.last_context = ctx
        return ctx

    ctx = NewsContext(status="NORMAL", reason="Tidak ada berita/calendar event yang relevan saat ini")
    state.last_context = ctx
    return ctx
