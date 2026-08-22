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
# 2. PORT untuk bridge service ini
# ==============================================================
HOST = "0.0.0.0"   # jangan diubah, biar bisa diakses dari luar VPS
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

SIGNAL_SYMBOL = "XAUUSD"          # symbol yang dipantau
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

