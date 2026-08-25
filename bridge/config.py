"""
Konfigurasi Bridge MT5 <-> Web
================================
EDIT FILE INI SEBELUM MENJALANKAN BRIDGE.
"""

import secrets

# ==============================================================
# 1. AUTH TOKEN
# ==============================================================
# Ini "password" yang dipakai web app untuk bisa akses data & kirim
# order ke akun MT5 lo. WAJIB diganti, jangan pakai contoh di bawah.
#
# Cara generate token baru yang aman:
#   jalankan: python -c "import secrets; print(secrets.token_urlsafe(32))"
#   lalu copy hasilnya ke bawah ini.
#
API_TOKEN = "GANTI_DENGAN_TOKEN_RANDOM_LO_SENDIRI"

# ==============================================================
# 2. HOST & PORT untuk bridge service ini
# ==============================================================
# Kalau webapp Next.js jalan di VPS YANG SAMA dengan bridge ini (misal
# lewat PM2 — lihat webapp/PM2_DEPLOY.md), pakai "127.0.0.1" supaya
# bridge TIDAK bisa diakses dari luar VPS sama sekali — lebih aman,
# karena publik hanya perlu akses webapp-nya, bukan bridge langsung.
#
# Kalau webapp lo di-hosting terpisah (misal Vercel) dan perlu akses
# bridge lewat internet, pakai "0.0.0.0" dan tetap wajib pasang HTTPS
# (lihat bagian Caddy di bawah).
HOST = "127.0.0.1"  # ganti ke "0.0.0.0" HANYA kalau webapp di-hosting terpisah dari VPS ini
PORT = 8765

# ==============================================================
# 3. MT5 LOGIN (opsional)
# ==============================================================
# Kalau terminal MT5 di VPS lo SUDAH login manual dan dibiarkan
# terbuka, biarkan MT5_LOGIN = None (bridge akan connect ke
# instance yang lagi jalan / lagi login).
#
# Kalau mau bridge yang login-in sendiri, isi 3 variabel ini:
MT5_LOGIN = None          # contoh: 12345678
MT5_PASSWORD = None       # contoh: "password_akun_mt5"
MT5_SERVER = None         # contoh: "Exness-MT5Real8"

# Path ke terminal64.exe kalau perlu spesifik (biasanya tidak perlu
# kalau MT5 sudah terinstall normal & pernah dibuka)
MT5_PATH = None  # contoh: r"C:\Program Files\MetaTrader 5\terminal64.exe"

# ==============================================================
# 4. FILE SINYAL untuk kontrol EA (start/stop bot)
# ==============================================================
# Bridge menulis kata "START" atau "STOP" ke file ini.
# EA lo (lihat snippet MQL5 yang saya kasih terpisah) akan
# membaca file ini setiap tick untuk tahu apakah boleh trading.
#
# PENTING: Path ini harus ada di folder "Files" milik MT5 lo, karena
# fungsi MQL5 FileOpen() hanya bisa akses folder itu (folder sandbox
# MT5, demi keamanan). Biasanya lokasinya:
#   C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\<ID_TERMINAL>\MQL5\Files\
#
# Isi path LENGKAP di bawah ini setelah lo cek folder tersebut:
EA_SIGNAL_FILE = r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\COMMON\Files\ea_signal.txt"

# File tempat EA menulis status terakhirnya (last signal, timestamp,
# dll) supaya bridge & web bisa menampilkan status bot
EA_STATUS_FILE = r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\COMMON\Files\ea_status.txt"

# Nomor "magic number" EA lo, dipakai untuk filter posisi mana yang
# dibuka oleh bot vs manual (opsional, isi 0 kalau tidak dipakai)
EA_MAGIC_NUMBER = 0

# ==============================================================
# 5. SIGNAL ENGINE (pengganti EA — logic trading jalan di sini)
# ==============================================================
# Ini adalah "otak" baru yang menggantikan EA MQL5. Semua trading
# real (kalau AUTO_EXECUTE = True) dieksekusi dari sini, bukan dari
# MetaEditor lagi.
#
# PENTING UNTUK AKUN CENT (HFM & broker cent lain umumnya):
# Symbol name di akun cent SERING BEDA dari nama standar — biasanya ada
# suffix, misal "XAUUSD.c", "GOLDcent", "XAUUSDc", dll (setiap broker beda).
# Kalau nama symbol di sini TIDAK PERSIS SAMA dengan yang muncul di
# Market Watch pada MT5 lo, bot akan gagal entry (bisa diam-diam gagal
# atau muncul error yang membingungkan).
#
# CARA CEK SYMBOL YANG BENAR:
# 1. Buka MT5, cari gold di Market Watch (klik kanan -> Show All kalau
#    tidak kelihatan)
# 2. Copy PERSIS nama yang tertera di sana (perhatikan huruf besar/kecil,
#    titik, dan suffix seperti .c / .m / c / m)
# 3. Tempel PERSIS ke SIGNAL_SYMBOL di bawah ini
SIGNAL_SYMBOL = "XAUUSDc"         # dikonfirmasi: symbol gold di HFM akun cent
SIGNAL_TIMEFRAME = "M15"          # timeframe candle: M1, M5, M15, M30, H1, H4, D1
SIGNAL_CHECK_INTERVAL_SEC = 15    # seberapa sering cek sinyal baru (detik)

# Parameter indikator (bisa lo tuning nanti tanpa perlu compile apa pun,
# tinggal edit angka ini dan restart bridge)
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
ATR_PERIOD = 14

# SL = swing high/low terdekat, dijauhkan lagi dengan buffer ATR x faktor ini
SL_ATR_BUFFER_MULT = 0.5

# TP1/TP2/TP3 dihitung sebagai rasio risk:reward dari jarak SL
# (risk = jarak entry ke SL). Contoh default: TP1 di 1x risk, TP2 di 2x, TP3 di 3x
TP1_RR = 1.0
TP2_RR = 2.0
TP3_RR = 3.0

# Lot tetap untuk tiap entry otomatis (tidak martingale — flat sizing)
SIGNAL_LOT_SIZE = 0.1

# Kalau True: begitu sinyal valid muncul, bridge LANGSUNG kirim order ke MT5.
# Kalau False: sinyal cuma ditampilkan di web, tidak ada order otomatis.
AUTO_EXECUTE = True

# Magic number khusus untuk order yang dibuka signal engine ini
# (beda dari EA_MAGIC_NUMBER supaya tidak tercampur kalau EA lama masih ada)
SIGNAL_MAGIC_NUMBER = 990011

# Maksimal posisi terbuka bersamaan dari signal engine (1 = tidak menambah
# posisi baru selama masih ada posisi aktif dari signal engine ini)
SIGNAL_MAX_OPEN_POSITIONS = 1

# Jeda minimum antar entry baru pada symbol yang sama, supaya tidak
# entry berkali-kali di kondisi pasar yang sama (menit)
SIGNAL_COOLDOWN_MINUTES = 30

# ==============================================================
# 6. MANAJEMEN POSISI OTOMATIS (partial close + breakeven + trailing)
# ==============================================================
# Begitu harga menyentuh TP1: tutup sebagian posisi, sisanya SL
# dipindah ke harga entry (breakeven) supaya sisa posisi itu
# "gratis" — tidak mungkin rugi lagi dari titik itu.
PARTIAL_CLOSE_AT_TP1 = True
PARTIAL_CLOSE_PERCENT = 40   # % dari lot AWAL yang ditutup saat TP1 kena (40 = tutup 40%, sisa 60% lanjut)
MOVE_SL_TO_BREAKEVEN_AT_TP1 = True
BREAKEVEN_BUFFER_POINTS = 20  # SL breakeven digeser dikit dari harga entry (points) biar tidak kena spread/slippage pas market bergerak sedikit

# Begitu harga menyentuh TP2: aktifkan trailing stop untuk sisa
# posisi (mengejar profit lebih jauh menuju/lewat TP3 tanpa TP tetap)
TRAILING_AFTER_TP2 = True
TRAILING_DISTANCE_ATR_MULT = 1.5   # jarak trailing stop dari harga saat ini, dalam kelipatan ATR

# Loop pemantauan posisi berjalan (partial close, breakeven, trailing)
# dicek setiap sekian detik — independen dari SIGNAL_CHECK_INTERVAL_SEC
POSITION_MONITOR_INTERVAL_SEC = 5

# ==============================================================
# 7. FILTER TAMBAHAN — sesi trading & volatilitas
# ==============================================================
# Filter sesi: hindari entry baru di jam yang secara historis sepi
# likuiditas untuk gold (di luar overlap London/New York biasanya
# spread lebih lebar & pergerakan kurang bisa diandalkan).
# Jam dalam WAKTU SERVER MT5 (bukan WIB) — cek jam server di terminal MT5 lo.
USE_SESSION_FILTER = True
SESSION_START_HOUR = 9    # sekitar mulai sesi London (sesuaikan dengan offset server broker lo)
SESSION_END_HOUR = 21     # sekitar akhir sesi New York

# Filter volatilitas: skip entry kalau ATR saat ini terlalu ekstrem
# dibanding rata-rata (indikasi news/kondisi pasar tidak normal),
# atau terlalu kecil (market terlalu sepi, sinyal kurang bisa diandalkan)
USE_VOLATILITY_FILTER = True
ATR_MIN_MULT_OF_AVG = 0.5   # skip kalau ATR sekarang < 0.5x rata-rata ATR 50 candle terakhir
ATR_MAX_MULT_OF_AVG = 2.5   # skip kalau ATR sekarang > 2.5x rata-rata (kemungkinan news spike)

# ==============================================================
# 8. NEWS ENGINE — pemantau berita & economic calendar
# ==============================================================
# CATATAN JUJUR: modul ini mendeteksi berita/rilis data berdasarkan
# KEYWORD dan JADWAL, bukan memahami isi berita secara mendalam.
# Ini filter/trigger tambahan, bukan "AI yang paham berita". Selalu
# cek log & riwayat sinyal untuk pastikan perilakunya sesuai ekspektasi.

USE_NEWS_ENGINE = True

# --- Sumber berita utama: RSS feed gratis, TANPA API KEY ---
# RSS adalah format XML terbuka standar yang di-publish resmi oleh situs
# berita — jauh lebih stabil daripada API pihak ketiga yang bisa berubah
# kebijakan kapan saja (seperti kasus Finnhub calendar & Trading Economics
# guest key yang mendadak berhenti berfungsi). Ini AKTIF SECARA DEFAULT
# dan tidak butuh setup apa pun.
#
# CATATAN JUJUR (23 Agustus 2026): Investing.com TERKONFIRMASI memblokir
# request otomatis dengan 403 Forbidden dari sejumlah jaringan/IP
# (kemungkinan mereka mem-blacklist IP datacenter/cloud secara luas,
# bukan cuma soal User-Agent). Kalau VPS lo kena masalah yang sama,
# feed Investing.com akan gagal terus walau kodenya sudah benar — itu
# bukan bug, itu pemblokiran dari sisi mereka. Karena itu daftar di
# bawah sudah ditambah beberapa feed CADANGAN dari sumber lain (Yahoo
# Finance, FXStreet, Kitco — situs berita KHUSUS emas/logam mulia) yang
# secara umum kurang agresif memblokir automated request. Sistem sudah
# didesain supaya SATU feed gagal tidak menghentikan feed lain — makin
# banyak kandidat di daftar ini, makin besar peluang minimal satu
# berhasil. Silakan tambah/kurangi/urutkan ulang sesuai yang ternyata
# paling reliable dari VPS lo (cek log setelah restart, tiap feed yang
# gagal akan tercatat jelas by name).
#
# CARA CEK MANA YANG BERHASIL DARI VPS LO:
# Setelah restart bridge, lihat log — baris "RSS 'nama feed' gagal: ..."
# menunjukkan mana yang bermasalah. Kalau SEMUA feed gagal, AI News
# Analyst tidak akan punya data buat dianalisa (sinyal tetap jalan
# murni teknikal, tapi tanpa filter/boost dari berita) — di titik itu
# pertimbangkan generate RSS feed sendiri lewat layanan seperti
# rss.app untuk situs yang lo percaya, atau isi FINNHUB_API_KEY di
# bawah sebagai sumber tambahan (Finnhub /news gratis, terpisah dari
# masalah blocking Investing.com).
USE_NEWS_RSS_FEEDS = True
NEWS_RSS_FEEDS = [
    ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance"),
    ("https://www.investing.com/rss/news_11.rss", "Investing.com Commodities"),
    ("https://www.investing.com/rss/news_1.rss", "Investing.com Forex"),
    ("https://www.fxstreet.com/rss", "FXStreet"),
    ("https://www.kitco.com/rss/KitcoNews.xml", "Kitco News (Gold)"),
    ("https://www.forexlive.com/feed/news", "ForexLive"),
    (
        "https://news.google.com/rss/search?q=gold+OR+XAUUSD+OR+%22dollar+index%22+when:1d&hl=en-US&gl=US&ceid=US:en",
        "Google News (Gold/XAUUSD)",
    ),
]
# CATATAN soal urutan sumber di atas: semua feed di daftar ini SEKALIGUS
# dipakai bersamaan (bukan "coba satu, kalau gagal baru coba berikutnya")
# — tiap feed di-fetch independen di _fetch_all_news(), lalu hasilnya
# digabung & di-dedup lewat URL. Ini SENGAJA dibuat begini, bukan rantai
# fallback berurutan: kalau Finnhub kena limit ATAU Investing.com
# nge-block IP VPS (lihat catatan di bawah), ForexLive/Google
# News/Kitco/dll yang masih hidup TETAP otomatis ngisi datanya di
# siklus refresh yang sama — tidak perlu nunggu Finnhub "gagal dulu"
# baru pindah, jadi coverage-nya lebih tebal daripada rantai fallback
# satu-per-satu. Kalau salah satu feed di atas ternyata sering gagal di
# VPS lo (misal Google News RSS kena rate limit dari IP tertentu),
# tinggal hapus barisnya dari list ini — sumber lain tetap jalan normal.

# --- Sumber berita tambahan (opsional): Finnhub /news ---
# Ini SUMBER TAMBAHAN, bukan pengganti RSS di atas — kalau diisi, berita
# dari Finnhub digabung dengan RSS (duplikat otomatis dihilangkan lewat
# URL). Kalau dibiarkan kosong, bot tetap jalan normal pakai RSS saja.
# Daftar di https://finnhub.io (gratis, tanpa kartu kredit) untuk dapat
# API key. Free tier: ~60 request/menit.
#
# CATATAN: endpoint /calendar/economic Finnhub BUTUH paket berbayar
# (lihat CALENDAR_PROVIDER di bawah, itu masalah terpisah) — tapi
# endpoint /news yang dipakai di sini tetap gratis.
FINNHUB_API_KEY = "ISI_API_KEY_FINNHUB_LO"

# Seberapa sering bridge mengecek calendar & berita baru (detik).
# Tidak perlu sesering signal check — berita/calendar tidak berubah
# tiap detik. 300 = 5 menit.
NEWS_CHECK_INTERVAL_SEC = 300

# --- Economic calendar (CPI, NFP, FOMC, dll) ---
# Event dengan impact "high" dari negara-negara ini yang dianggap
# relevan untuk XAUUSD (emas paling sensitif ke rilis data USD,
# karena emas dihargakan dalam USD dan jadi safe haven vs kebijakan Fed)
NEWS_CALENDAR_COUNTRIES = ["US"]

# Window "blackout" di sekitar rilis high-impact: signal engine TIDAK
# akan auto-entry baru dalam window ini (menit sebelum & sesudah jadwal rilis)
CALENDAR_BLACKOUT_BEFORE_MIN = 30
CALENDAR_BLACKOUT_AFTER_MIN = 30

# Kalau tidak ada event mendatang dalam MANUAL_CALENDAR_EVENTS untuk
# sekian hari ke depan, bridge akan mencatat WARNING di log dan expose
# status ini lewat endpoint /news/status (field calendar_running_low)
# supaya kelihatan juga di web app — pengingat untuk update daftar
# manual di config.py sebelum blackout window jadi kosong tanpa disadari.
#
# 30 hari dipilih karena event ekonomi (CPI/NFP bulanan, FOMC tiap
# 6-8 minggu) secara alami punya jarak beberapa minggu antar rilis —
# angka lebih kecil (misal 14 hari) akan sering false-alarm walau
# jadwalnya sebenarnya masih lengkap dan valid.
CALENDAR_LOW_WARNING_DAYS = 30

# Provider untuk economic calendar. Endpoint calendar Finnhub TERNYATA
# butuh paket berbayar (free tier akan dapat error 403 Forbidden meski
# token valid — ini bukan bug, memang dikunci Finnhub). Jadi calendar
# dipisah dari berita umum (yang tetap gratis lewat Finnhub /news).
#
# Provider untuk economic calendar. Endpoint calendar Finnhub TERNYATA
# butuh paket berbayar (free tier akan dapat error 403 Forbidden meski
# token valid — ini bukan bug, memang dikunci Finnhub). Jadi calendar
# dipisah dari berita umum (yang tetap gratis lewat Finnhub /news & RSS).
#
#   "forex_factory"     -> feed JSON mingguan resmi yang dipublikasikan
#                           Forex Factory untuk konsumsi publik/EA
#                           (nfs.faireconomy.media/ff_calendar_thisweek.json),
#                           GRATIS, tanpa API key, dipakai luas oleh
#                           komunitas trading MT4/MT5 bertahun-tahun.
#                           Di-cache CALENDAR_FF_CACHE_HOURS jam sekali
#                           untuk hindari rate limit (WAJIB, jangan fetch
#                           tiap siklus). BELUM DIVERIFIKASI langsung dari
#                           lingkungan development — TES DULU di VPS lo
#                           (lihat instruksi di bawah CALENDAR_PROVIDER)
#                           sebelum benar-benar mengandalkannya.
#   "trading_economics" -> pakai API key guest:guest. STATUS PER 23
#                           AGUSTUS 2026: endpoint ini mengembalikan 410
#                           Gone, kemungkinan sudah dimatikan permanen.
#                           Kalau punya API key TE berbayar sendiri, isi
#                           di TRADING_ECONOMICS_API_KEY dan endpoint ini
#                           mungkin masih berfungsi.
#   "manual"             -> tidak fetch API sama sekali, pakai jadwal
#                           yang lo isi sendiri di MANUAL_CALENDAR_EVENTS
#                           di bawah. Paling PASTI jalan karena tidak
#                           bergantung API/feed pihak ketiga sama sekali.
#   "none"               -> matikan blackout window calendar sepenuhnya
#
# Kalau provider API/feed gagal/kosong/error apa pun, sistem OTOMATIS
# fallback ke MANUAL_CALENDAR_EVENTS di bawah (kalau diisi), supaya
# blackout window CPI/NFP/FOMC tetap bisa berfungsi walau sumber
# eksternalnya bermasalah. Ini tidak pernah membuat bridge berhenti.
#
# CARA TES "forex_factory" SEBELUM DIPAKAI SERIUS:
# 1. Ganti CALENDAR_PROVIDER = "forex_factory" di bawah, restart bridge
# 2. Cek log — harus muncul "Forex Factory calendar berhasil di-fetch: N event"
# 3. Cek tab Signal Trading di web app, panel "Jadwal Rilis Data
#    High-Impact" — harus muncul event nyata (CPI/NFP/FOMC), bukan kosong
# 4. Kalau setelah beberapa menit log malah menunjukkan warning gagal
#    fetch/parse berulang, feed ini kemungkinan sedang bermasalah/berubah
#    format — balikin ke "manual" (default), sistem tetap jalan aman
#    lewat MANUAL_CALENDAR_EVENTS yang sudah diisi di bawah.
#
# Default tetap "manual" (bukan "forex_factory") karena belum bisa
# diverifikasi otomatis dari sini — MANUAL_CALENDAR_EVENTS di bawah
# sudah diisi jadwal sampai akhir 2026 sebagai jaring pengaman yang
# pasti bekerja tanpa perlu tes apa pun.
CALENDAR_PROVIDER = "manual"

# Feed JSON Forex Factory di-cache berapa jam sebelum fetch ulang.
# JANGAN diturunkan drastis (misal jadi <1 jam) — Forex Factory
# membatasi jumlah request ke feed publik ini, request berlebihan
# bisa menyebabkan IP/akses diblokir sementara oleh mereka.
CALENDAR_FF_CACHE_HOURS = 6

# guest:guest adalah demo key publik Trading Economics — PER 23 AGUSTUS
# 2026 SUDAH TIDAK BERFUNGSI (410 Gone). Dibiarkan di sini untuk jaga-jaga
# kalau endpoint-nya hidup lagi di masa depan, atau kalau lo ganti dengan
# API key TE asli (https://developer.tradingeconomics.com, ada tier
# berbayar).
TRADING_ECONOMICS_API_KEY = "guest:guest"

# Cadangan manual — WAJIB diisi kalau CALENDAR_PROVIDER = "manual", dan
# otomatis dipakai sebagai fallback kalau provider API gagal/kosong.
# Isi jadwal rilis high-impact yang lo tahu akan datang (cek kalender
# ekonomi resmi seperti bls.gov atau investing.com/economic-calendar
# untuk tanggal pastinya), format waktu WIB. Update berkala manual.
#
# Contoh:
# MANUAL_CALENDAR_EVENTS = [
#     {"event": "US CPI m/m", "time_wib": "2026-09-10 19:30", "impact": "high"},
#     {"event": "US Non-Farm Payrolls", "time_wib": "2026-09-05 19:30", "impact": "high"},
#     {"event": "FOMC Rate Decision", "time_wib": "2026-09-17 01:00", "impact": "high"},
# ]
#
# Sudah diisi jadwal FOMC (dikonfirmasi dari federalreserve.gov & sumber
# turunannya) dan perkiraan CPI/NFP sampai akhir 2026 sebagai starter.
#
# PERINGATAN JUJUR: jadwal rilis data AS beberapa kali BERGESER di 2026
# akibat government shutdown (misal CPI September sempat molor ke akhir
# Oktober di satu periode shutdown). Tanggal FOMC di bawah dikonfirmasi
# dari kalender resmi Federal Reserve (jarang berubah). Tanggal CPI/NFP
# untuk Oktober-Desember adalah PERKIRAAN berdasarkan pola bulanan
# (BLS tidak selalu mempublikasikan jadwal jauh ke depan) — TETAP cek
# ulang tanggal pastinya mendekati hari-H di bls.gov/schedule/ (BLS
# resmi) sebelum mengandalkan blackout window ini untuk modal besar.
#
# CATATAN PENTING SOAL TIMEZONE: selisih WIB terhadap waktu AS berubah
# dari +11 jam ke +12 jam mulai 1 November 2026 (DST AS berakhir),
# makanya jam WIB di bawah tidak konsisten +11 terus — ini BUKAN typo.
#
# Bot akan memberi peringatan otomatis di log & endpoint /news/status
# kalau daftar ini sudah tidak punya event yang akan datang dalam waktu
# dekat (lihat _warn_if_calendar_running_low() di news_engine.py) —
# supaya lo tidak lupa update daftar ini setelah lewat semua tanggalnya.
MANUAL_CALENDAR_EVENTS = [
    # FOMC Rate Decision — keputusan diumumkan hari KEDUA tiap meeting,
    # jam 14:00 ET. Tanggal dikonfirmasi dari federalreserve.gov.
    {"event": "FOMC Rate Decision (September, diumumkan hari ke-2)", "time_wib": "2026-09-17 01:00", "impact": "high"},
    {"event": "FOMC Rate Decision (October, diumumkan hari ke-2)", "time_wib": "2026-10-29 01:00", "impact": "high"},
    {"event": "FOMC Rate Decision (December, diumumkan hari ke-2)", "time_wib": "2026-12-10 02:00", "impact": "high"},  # +12 jam, sudah lewat akhir DST

    # US CPI (rilis 08:30 ET). September dikonfirmasi BLS, Oktober-Desember perkiraan pola bulanan.
    {"event": "US CPI (Agustus, dirilis September)", "time_wib": "2026-09-11 19:30", "impact": "high"},
    {"event": "US CPI (September, dirilis Oktober) - PERKIRAAN, cek ulang", "time_wib": "2026-10-13 19:30", "impact": "high"},
    {"event": "US CPI (Oktober, dirilis November) - PERKIRAAN, cek ulang", "time_wib": "2026-11-12 20:30", "impact": "high"},  # +12 jam

    # US Non-Farm Payrolls (umumnya Jumat pertama tiap bulan, 08:30 ET,
    # TAPI bisa bergeser karena shutdown/holiday — cek ulang mendekati tanggalnya)
    {"event": "US Non-Farm Payrolls (September)", "time_wib": "2026-10-02 19:30", "impact": "high"},
    {"event": "US Non-Farm Payrolls (October) - PERKIRAAN, cek ulang", "time_wib": "2026-11-06 20:30", "impact": "high"},  # +12 jam
    {"event": "US Non-Farm Payrolls (November) - PERKIRAAN, cek ulang", "time_wib": "2026-12-04 20:30", "impact": "high"},
]

# --- Berita umum (geopolitik, dll) ---
# Keyword yang dianggap relevan & berpotensi menggerakkan harga emas
# secara signifikan. Pencarian tidak case-sensitive. Silakan tambah/
# kurangi sesuai kebutuhan.
NEWS_GOLD_KEYWORDS = [
    "gold", "xau", "safe haven", "geopolitical", "war", "conflict",
    "sanctions", "invasion", "military", "missile", "attack",
    "ceasefire", "opec", "oil price", "middle east", "taiwan",
    "nuclear", "central bank", "rate cut", "rate hike", "recession",
    # Aktor geopolitik spesifik yang sering jadi pemicu berita relevan
    # (ditambahkan setelah tes menunjukkan keyword umum di atas saja
    # bisa melewatkan berita geopolitik nyata seperti pernyataan Putin/
    # Rusia soal Ukraina, meski itu jelas relevan ke sentimen safe haven)
    "putin", "russia", "ukraine", "iran", "israel", "gaza",
    "hormuz", "north korea", "tariff", "trade war",
]

# Kata kunci yang menandakan berita ini adalah rilis data terjadwal
# (sudah ditangani lewat economic calendar di atas) — dipakai untuk
# MENGHINDARI dobel sinyal dari sumber berita umum untuk event yang
# sama seperti CPI/NFP/FOMC.
NEWS_CALENDAR_OVERLAP_KEYWORDS = ["cpi", "nonfarm", "nfp", "fomc", "interest rate decision", "ppi"]

# Berapa lama (menit) sebuah berita dianggap masih "baru"/relevan
# sejak waktu publikasinya, sebelum diabaikan
NEWS_FRESHNESS_MINUTES = 45

# Untuk berita geopolitik/umum (BUKAN calendar event) yang terdeteksi
# relevan & searah sinyal teknikal: entry tetap dilakukan tapi dengan
# lot yang dikecilkan (lebih hati-hati, karena arah dampak berita ke
# harga tidak 100% pasti walau judulnya relevan)
NEWS_LOT_MULTIPLIER = 0.5   # 0.5 = separuh dari SIGNAL_LOT_SIZE biasa

# ==============================================================
# 9. AI NEWS ANALYST — analisa berita pakai LLM (opsional)
# ==============================================================
# Tahap TAMBAHAN setelah keyword matching di atas: berita yang lolos
# filter keyword dikirim ke LLM untuk dinilai lebih dalam — apakah
# BENERAN relevan ke gold, arah sentimennya (bullish/bearish/netral),
# dan seberapa yakin. Keyword matching tetap jalan duluan (murah,
# cepat) supaya tidak semua berita mentah dikirim ke AI (boros kuota).
#
# CATATAN JUJUR: AI tetap bisa salah baca konteks (sarkasme, judul
# clickbait, artikel opini vs breaking news). Ini alat bantu tambahan,
# bukan kebenaran mutlak. Selalu pantau riwayat sinyal & alasan yang
# diberikan AI untuk memastikan masuk akal.
#
# Desain PLUGGABLE: provider AI-nya gampang diganti, tinggal ubah
# AI_PROVIDER dan isi API key yang sesuai. Semua provider di bawah
# punya tier gratis tanpa kartu kredit (per Agustus 2026, cek ulang
# halaman resminya karena kebijakan free tier sering berubah):
#
#   "gemini" -> Google AI Studio, https://aistudio.google.com
#               model default: gemini-2.5-flash-lite (cepat & gratis)
#   "groq"   -> https://console.groq.com
#               model default: llama-3.3-70b-versatile (sangat cepat)
#   "none"   -> matikan AI News Analyst, balik ke keyword matching saja
#
USE_AI_NEWS_ANALYST = True
AI_PROVIDER = "gemini"   # "gemini" | "groq" | "none"

# Isi SALAH SATU sesuai AI_PROVIDER yang dipilih di atas. Yang tidak
# dipakai boleh dibiarkan kosong.
GEMINI_API_KEY = "ISI_API_KEY_GEMINI_LO"
GEMINI_MODEL = "gemini-2.5-flash-lite"

GROQ_API_KEY = "ISI_API_KEY_GROQ_LO"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Timeout per panggilan AI (detik) — kalau lambat/tidak respons,
# sistem otomatis fallback ke keyword matching biasa, tidak menahan
# signal engine lebih lama dari ini.
AI_REQUEST_TIMEOUT_SEC = 12

# ==============================================================
# 10. KEPUTUSAN ENTRY SAAT SINYAL TEKNIKAL vs SENTIMEN AI BERBEDA ARAH
# ==============================================================
# Bridge TETAP entry mengikuti arah sinyal TEKNIKAL (bukan ikut AI),
# tapi ukuran lot disesuaikan menurut kecocokan dengan penilaian AI:
#
#  - AI netral / tidak relevan / gagal dianalisa -> lot NORMAL (SIGNAL_LOT_SIZE)
#  - AI SEARAH dengan sinyal teknikal             -> lot NORMAL (tidak dinaikkan)
#  - AI BERLAWANAN arah dengan sinyal teknikal     -> lot MINIMUM broker
#    (tetap entry mengikuti teknikal, tapi risiko ditekan serendah
#    mungkin karena ada sinyal berlawanan dari sisi berita)
#
# Ambang keyakinan AI minimum (0.0 - 1.0) supaya penilaian AI dianggap
# valid untuk mempengaruhi lot sizing. Di bawah ini dianggap "tidak yakin",
# diperlakukan sama seperti netral (lot normal).
AI_MIN_CONFIDENCE = 0.55

# ==============================================================
# 11. AI CHART ANALYST — gate wajib berbasis konfluensi indikator
# ==============================================================
# BEDA dari AI News Analyst (bagian 9, cuma pengaruhi lot): AI Chart
# Analyst ini GATE WAJIB. Sinyal teknikal dasar (EMA+RSI) HARUS
# disetujui AI berdasarkan ringkasan indikator tambahan (MACD,
# Bollinger Bands, candlestick pattern) sebelum entry dieksekusi. Kalau
# AI tidak setuju, sinyal DIBATALKAN sepenuhnya (bukan cuma lot
# dikecilkan) — sesuai permintaan: "sinyal lebih jarang tapi lebih
# meyakinkan".
#
# CATATAN JUJUR: AI di sini TIDAK melihat chart secara visual — yang
# dikirim adalah ANGKA indikator yang sudah dihitung (bukan gambar).
# AI menilai konfluensi/kombinasi angka tersebut, memberi penilaian
# lebih fleksibel daripada if-else kaku, tapi bukan sihir — ini bukan
# jaminan akurasi lebih tinggi, hanya lapisan penyaringan tambahan.
#
# Provider AI yang dipakai SAMA dengan AI_PROVIDER di bagian 9 di atas
# (Gemini/Groq) — tidak ada konfigurasi provider terpisah.
USE_AI_CHART_ANALYST = True

# Ambang keyakinan minimum AI supaya sinyal dianggap "disetujui".
# Di bawah ini, sinyal ditolak walau AI bilang agree=true.
AI_CHART_MIN_CONFIDENCE = 0.6

# PENTING — perilaku kalau AI Chart Analyst gagal/timeout/error:
#   "fail_safe" (default) -> sinyal DITOLAK (tidak dieksekusi) kalau AI
#                             tidak bisa dihubungi. Konsisten dengan
#                             tujuan "lebih ketat" — TAPI konsekuensinya
#                             bot BERHENTI ENTRY total kalau API key AI
#                             habis kuota / provider sedang down, sampai
#                             AI bisa dihubungi lagi.
#   "fail_open"           -> sinyal tetap LOLOS tanpa gate AI kalau AI
#                             gagal (kembali ke perilaku EMA+RSI+filter
#                             session/volatility saja, seperti sebelum
#                             fitur AI Chart Analyst ada). Pilih ini
#                             kalau tidak mau bot berhenti total hanya
#                             karena AI provider bermasalah.
AI_CHART_FAIL_MODE = "fail_safe"

# ==============================================================
# 12. EQUITY HISTORY — persist equity chart di sisi bridge (permanen)
# ==============================================================
# Sebelumnya grafik equity di web app cuma nyimpen data di memory
# browser (React state) — HILANG tiap kali halaman di-refresh. Sekarang
# equity/balance disimpan permanen ke file SQLite lokal di bridge
# (bridge/equity_history.db) lewat equity_store.py, jadi grafiknya
# tetap ada walau browser di-refresh, ganti device, ATAU bridge
# di-restart.

# Interval minimum antar snapshot yang ditulis ke database (detik).
# broadcaster_loop di main.py jalan tiap 1 detik, tapi kita TIDAK perlu
# simpan tiap detik ke disk — cukup tiap 30 detik supaya file db tidak
# membengkak tanpa perlu, sambil grafik tetap cukup detail.
EQUITY_LOG_INTERVAL_SEC = 30

# Berapa lama data equity lama disimpan sebelum dihapus otomatis
# (hari). Dijalankan sekali tiap bridge startup, supaya file db tidak
# tumbuh tanpa batas selamanya.
EQUITY_RETENTION_DAYS = 90

# ==============================================================
# 13. CORRELATION HEATMAP — korelasi XAUUSD vs aset lain (yfinance)
# ==============================================================
# Heatmap korelasi harian antara XAUUSD dan aset-aset makro terkait
# (DXY, EUR/USD, yield, minyak, dll), dihitung dari data gratis
# yfinance — TIDAK butuh API key. Fitur ini murni informational untuk
# ditampilkan di web app, TIDAK dipakai signal engine untuk keputusan
# entry otomatis.
USE_CORRELATION_ENGINE = True

# Ticker yfinance untuk proxy harga XAUUSD. "GC=F" (COMEX Gold Futures)
# dipakai sebagai default karena histori datanya paling lengkap &
# stabil di yfinance. Alternatif kalau ini bermasalah di VPS lo:
# "XAUUSD=X" (ticker forex-style, kadang datanya lebih tipis).
CORRELATION_XAUUSD_TICKER = "GC=F"

# Daftar aset yang dibandingkan di heatmap.
# Format: (ticker_yfinance, label_tampilan_di_web_app).
# CORRELATION_XAUUSD_TICKER di atas WAJIB jadi baris pertama di sini.
CORRELATION_ASSETS = [
    (CORRELATION_XAUUSD_TICKER, "XAUUSD (Gold)"),
    ("DX-Y.NYB", "DXY (Dollar Index)"),
    ("EURUSD=X", "EUR/USD"),
    ("^TNX", "US 10Y Yield"),
    ("CL=F", "WTI Crude Oil"),
    ("SI=F", "Silver"),
    ("^GSPC", "S&P 500"),
    ("BTC-USD", "Bitcoin"),
]

# Berapa hari data historis dipakai untuk hitung korelasi (rolling
# window). 60 hari kira-kira cukup untuk menangkap rezim korelasi
# jangka menengah, tanpa terlalu dipengaruhi outlier satu-dua hari.
CORRELATION_LOOKBACK_DAYS = 60

# Minimum jumlah data point valid supaya suatu aset diikutkan di
# heatmap. Aset dengan data kurang dari ini di-skip (bukan bikin
# seluruh fetch gagal).
CORRELATION_MIN_DATA_POINTS = 20

# Seberapa sering heatmap di-refresh (detik). Data yfinance untuk
# ticker-ticker ini umumnya EOD (update sekali per hari bursa) — TIDAK
# perlu di-refresh sesering signal/news engine. Default 3600 (1 jam)
# supaya tidak membebani Yahoo Finance dengan request berlebihan.
CORRELATION_REFRESH_INTERVAL_SEC = 3600

