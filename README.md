# MT5 Dashboard — Panduan Lengkap

Proyek ini punya 2 bagian:

```
bridge/    -> Python service, jalan di VPS Windows lo (dekat MT5)
webapp/    -> Next.js web dashboard, jalan di mana saja (Vercel dsb)
```

## Cara kerja singkat

```
MT5 Terminal (VPS)  <-->  bridge/main.py  <-->  Internet (HTTPS)  <-->  webapp (Next.js server) <--> browser lo
       ↑                                                                       ↑
   EA lo (opsional,                                                    kredensial bridge (URL+token)
   lihat catatan di bawah)                                             disimpan DI SINI, bukan di browser
```

Web app sekarang punya **backend sendiri** (API routes Next.js) yang memegang
`BRIDGE_URL` dan `BRIDGE_TOKEN` sebagai environment variable server. Browser
lo cuma perlu login pakai 1 password — kredensial bridge tidak pernah
diketik ulang tiap ganti device.

## Urutan setup (WAJIB ikuti urutan ini)

### 1. Bridge dulu (di VPS)
Baca **`bridge/SETUP.md`** — langkah demi langkah, dari install Python
sampai HTTPS lewat Caddy. Ini fondasi, tanpa ini web app gak ada data.

Setelah bridge jalan, catat 2 hal dari `bridge/config.py`:
- `API_TOKEN` (token yang lo generate)
- URL publik bridge (misal `https://bridge.domainlo.com`)

### 2. (Opsional) EA lama
Kalau lo masih pakai EA MQL5 (`XAUUSD_Hybrid_EA.mq5`) di samping Signal
Engine baru, baca bagian **"EA lama vs Signal Engine"** di bawah — jangan
jalankan dua-duanya bersamaan di symbol yang sama tanpa sadar risikonya.

### 3. Setup environment variable web app
```bash
cd webapp
cp .env.local.example .env.local
```
Edit `.env.local`, isi 4 variabel:
- `BRIDGE_URL` — URL bridge dari langkah 1
- `BRIDGE_TOKEN` — API_TOKEN dari langkah 1
- `DASHBOARD_PASSWORD` — password bebas buat login ke dashboard ini (punya lo sendiri, bukan password MT5)
- `SESSION_SECRET` — generate dengan `openssl rand -base64 32`, buat menandatangani session login

### 4. Jalankan web app
```bash
npm install
npm run dev        # coba lokal dulu, buka http://localhost:3000
```
Lo akan diarahkan ke halaman **login** — masukkan `DASHBOARD_PASSWORD` yang
tadi diisi di `.env.local`. Setelah login, semua device yang login dengan
password yang sama otomatis bisa akses dashboard tanpa isi ulang apa pun.

### 5. Deploy supaya bisa diakses dari HP di luar rumah
Paling gampang pakai **Vercel** (gratis untuk pemakaian pribadi):
```bash
npm install -g vercel
vercel
```
Setelah deploy pertama, buka **Vercel dashboard → Project → Settings →
Environment Variables**, isi 4 variabel yang sama seperti di `.env.local`
lo (Vercel tidak otomatis membaca `.env.local`, harus diisi manual di sana
untuk environment production). Redeploy setelah env var diisi.

Lo dapat URL publik (misal `https://mt5-dashboard-kamu.vercel.app`).
Buka dari HP, login pakai password yang sama — beres, tidak perlu isi
URL/token bridge lagi di HP.

## Yang sudah ada di dashboard
- **Login sekali, dipakai di semua device** — kredensial bridge tersimpan di server, bukan per-browser
- **Ringkasan akun realtime**: balance, equity, floating P/L, margin level — update tiap detik lewat WebSocket
- **Grafik equity** sesi berjalan
- **Kontrol bot EA lama**: tombol Start/Stop EA langsung dari web (kalau masih pakai EA MQL5)
- **Signal Trading**: bridge menganalisa harga XAUUSD dan menghasilkan sinyal entry + SL + TP1/TP2/TP3, dengan opsi auto-eksekusi
- **Manajemen posisi otomatis**: begitu TP1 kena → sebagian posisi ditutup otomatis + SL sisa posisi dipindah ke breakeven; begitu TP2 kena → sisa posisi beralih ke trailing stop mengejar TP3
- **Tombol STOP DARURAT** — menutup semua posisi signal engine + menghentikan auto-entry, dengan konfirmasi 2 langkah
- **Posisi terbuka**: tabel lengkap + tombol tutup posisi manual
- **Terminal order manual**: buka Buy/Sell dengan SL/TP
- **Riwayat**: tab transaksi tertutup, deposit/penarikan, dan riwayat sinyal

## EA lama vs Signal Engine baru — PENTING
Sekarang ada **dua kemungkinan sumber trading otomatis**:
1. EA MQL5 lo (`XAUUSD_Hybrid_EA.mq5`) — kalau masih attached ke chart di MT5
2. Signal Engine di bridge (`signal_engine.py`) — aktif kalau `AUTO_EXECUTE = True` di `config.py`

**Kalau lo mau pindah total ke Signal Engine dan tidak pakai EA lama lagi:**
buka MT5, klik kanan chart tempat EA lama nempel → **Expert Advisors → Remove**,
supaya tidak ada dua sistem yang sama-sama entry di symbol yang sama.

Signal Engine memakai magic number terpisah (`SIGNAL_MAGIC_NUMBER` di
`config.py`, default `990011`) supaya posisinya tidak tertukar dengan EA lama,
tapi dua-duanya tetap bisa entry bersamaan kalau keduanya aktif — itu bisa
bikin eksposur risiko dobel tanpa lo sadar. Pastikan cuma satu yang aktif.

## Signal Engine — cara kerja & tuning
Semua parameter ada di `bridge/config.py`, tidak perlu compile ulang apa
pun — edit angka, restart bridge (`python main.py`):

**Entry & sinyal:**
- `SIGNAL_SYMBOL`, `SIGNAL_TIMEFRAME` — pair & timeframe yang dipantau
- `AUTO_EXECUTE` — `True` = langsung entry otomatis, `False` = sinyal tampil di web saja
- `SIGNAL_LOT_SIZE` — lot tetap tiap entry (tidak martingale). **Perhatikan**: makin besar lot, makin besar risiko rupiah per trade — SL dihitung dari struktur harga (swing+ATR), bukan angka tetap, jadi jarak SL bisa berubah-ubah tiap sinyal.
- `EMA_FAST/SLOW`, `RSI_*`, `ATR_PERIOD` — parameter indikator
- `TP1_RR/TP2_RR/TP3_RR` — rasio risk:reward tiap take profit
- `SIGNAL_COOLDOWN_MINUTES` — jeda minimum antar entry baru

**Manajemen posisi (partial close, breakeven, trailing):**
- `PARTIAL_CLOSE_AT_TP1`, `PARTIAL_CLOSE_PERCENT` — aktif/nonaktif + berapa % lot ditutup saat TP1
- `MOVE_SL_TO_BREAKEVEN_AT_TP1`, `BREAKEVEN_BUFFER_POINTS` — geser SL ke entry saat TP1 kena
- `TRAILING_AFTER_TP2`, `TRAILING_DISTANCE_ATR_MULT` — trailing stop aktif setelah TP2
- `POSITION_MONITOR_INTERVAL_SEC` — seberapa sering posisi berjalan dicek (default 5 detik)

**Filter tambahan:**
- `USE_SESSION_FILTER`, `SESSION_START_HOUR`, `SESSION_END_HOUR` — hindari entry di jam sepi likuiditas
- `USE_VOLATILITY_FILTER`, `ATR_MIN_MULT_OF_AVG`, `ATR_MAX_MULT_OF_AVG` — hindari entry saat market terlalu sepi atau terlalu liar (news spike)

**Tombol STOP DARURAT** di tab "Signal Trading" pada web app akan langsung:
menutup semua posisi yang dibuka signal engine + menghentikan auto-entry
sampai lo tekan "Aktifkan Kembali". Independen dari kontrol EA lama.

## Keamanan — baca ini
- `BRIDGE_TOKEN` dan `DASHBOARD_PASSWORD` itu setara password ke akun trading lo. Jangan share, jangan commit `.env.local` ke Git publik (sudah masuk `.gitignore`).
- Bridge WAJIB diakses lewat HTTPS (bukan `http://` biasa) — lihat `bridge/SETUP.md` bagian Caddy.
- Session login tersimpan sebagai cookie httpOnly (tidak bisa dibaca JavaScript), ditandatangani dengan `SESSION_SECRET`, berlaku 30 hari.
- WebSocket realtime tidak pernah mengirim `BRIDGE_TOKEN` ke browser — server menukarnya dengan tiket sekali-pakai berumur 30 detik.
- Kalau curiga token/password bocor: generate `API_TOKEN` baru di `bridge/config.py` DAN `BRIDGE_TOKEN`+`DASHBOARD_PASSWORD` baru di environment variable web app, lalu restart/redeploy keduanya.

## Yang belum dibuatkan / bisa dikembangkan lagi
- Notifikasi (Telegram/email) saat ada sinyal baru, deposit/withdrawal, atau emergency stop terpicu
- Multi-akun (saat ini 1 bridge = 1 akun MT5)
- Multi-symbol untuk signal engine (saat ini fokus 1 pair: XAUUSD)
- Batas risiko per trade dalam % balance (saat ini lot ditentukan angka tetap di `SIGNAL_LOT_SIZE`, bukan dihitung otomatis dari jarak SL — kalau mau posisi otomatis mengecil saat SL jauh dan membesar saat SL dekat, bisa saya tambahkan)
- Backtesting sinyal terhadap data historis sebelum dipakai live
- Grafik equity historis permanen (saat ini equity chart cuma nampilin sesi browser terbuka)

Kalau butuh salah satu dari itu, bilang aja, saya lanjutin.
