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

Ada 2 opsi — pilih salah satu:

**Opsi A — Vercel** (webapp di server terpisah, gratis untuk pemakaian pribadi):
```bash
npm install -g vercel
vercel
```
Setelah deploy pertama, buka **Vercel dashboard → Project → Settings →
Environment Variables**, isi 4 variabel yang sama seperti di `.env.local`
lo, dengan `BRIDGE_URL` mengarah ke domain HTTPS bridge (Vercel tidak
otomatis membaca `.env.local`, harus diisi manual di sana). Redeploy
setelah env var diisi.

**Opsi B — PM2 di VPS yang sama dengan bridge** (semua jadi satu server):
Baca **`webapp/PM2_DEPLOY.md`** — panduan lengkap install Node.js,
build, jalankan dengan PM2, dan setup Caddy untuk HTTPS. Dengan opsi
ini, `BRIDGE_URL` cukup `http://localhost:8765` dan bridge tidak perlu
diekspos ke internet sama sekali — lebih aman dan lebih sederhana
(satu VPS untuk semuanya).

Lo dapat URL publik (misal `https://mt5-dashboard-kamu.vercel.app` atau
`https://dashboard.domainlo.com`). Buka dari HP, login pakai password
yang sama — beres, tidak perlu isi URL/token bridge lagi di HP.

## Yang sudah ada di dashboard
- **Login sekali, dipakai di semua device** — kredensial bridge tersimpan di server, bukan per-browser
- **Ringkasan akun realtime**: balance, equity, floating P/L, margin level — update tiap detik lewat WebSocket
- **Grafik equity** sesi berjalan
- **Kontrol bot EA lama**: tombol Start/Stop EA langsung dari web (kalau masih pakai EA MQL5)
- **Signal Trading**: bridge menganalisa harga XAUUSD dan menghasilkan sinyal entry + SL + TP1/TP2/TP3, dengan opsi auto-eksekusi
- **News Engine**: memantau economic calendar (CPI/NFP/FOMC) dan berita geopolitik yang relevan ke emas — menahan auto-entry di sekitar rilis data high-impact, dan mengecilkan lot otomatis saat entry dipicu bersamaan berita geopolitik high-impact
- **Manajemen posisi otomatis**: begitu TP1 kena → sebagian posisi ditutup otomatis + SL sisa posisi dipindah ke breakeven; begitu TP2 kena → sisa posisi beralih ke trailing stop mengejar TP3
- **Tombol STOP DARURAT** — menutup semua posisi signal engine + menghentikan auto-entry, dengan konfirmasi 2 langkah
- **Trade Journal**: statistik lengkap dari SEMUA trade (manual, EA lama, signal engine) — win rate, profit factor, average risk:reward, win/loss streak, trade terbaik/terburuk, breakdown harian, dan tabel detail tiap trade, dengan filter periode & sumber
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

## Akun Cent (HFM & broker cent lainnya) — sudah dikonfigurasi

Symbol gold di HFM akun cent **sudah dikonfirmasi dan diisi**: `XAUUSDc`
(lihat `SIGNAL_SYMBOL` di `bridge/config.py`). Kalau lo pindah broker atau
ganti jenis akun nanti, symbol-nya bisa beda lagi — di broker cent lain
biasanya `XAUUSD.c`, `GOLDcent`, dll (tiap broker beda konvensinya).

**Kalau suatu saat pindah broker/akun, cara cek & perbaiki:**
1. Buka MT5, lihat **Market Watch** (kalau gold tidak kelihatan, klik kanan → *Show All* atau *Symbols*)
2. Cari baris yang menunjukkan gold, **copy PERSIS** nama yang tertera (perhatikan huruf besar/kecil, titik, dan suffix)
3. Buka `bridge/config.py`, ganti `SIGNAL_SYMBOL` dengan nama itu persis
4. Restart bridge (`python main.py`)

Bridge **otomatis validasi symbol saat startup** — kalau nama salah, log
akan menampilkan pesan error jelas beserta daftar kandidat symbol yang
mengandung "XAU" atau "GOLD" di broker lo, supaya gampang dicocokkan.
Cek log ini setiap kali baru setup atau pindah broker/akun — kalau muncul
baris `"Symbol 'XAUUSDc' ditemukan di broker"` saat startup, berarti
sudah benar.

Hal lain yang biasanya juga beda di akun cent (sudah otomatis
disesuaikan oleh bridge, tapi baik untuk diketahui):
- **Lot minimum & step** — bridge membaca ini otomatis dari `symbol_info()`, bukan angka tetap, jadi otomatis menyesuaikan
- **Jumlah digit harga** — bridge juga membaca ini otomatis (`symbol_info().digits`) untuk pembulatan SL/TP
- **Nilai per pip/point** — di akun cent nilainya beda (karena mata uang akun dalam cent, bukan dolar penuh) — pastikan `SIGNAL_LOT_SIZE` di `config.py` masuk akal untuk ukuran modal akun cent lo, jangan asal samakan dengan akun standar
- **Filling mode order** (`FOK`/`IOC`/`RETURN`) — broker cent sering cuma menerima satu mode tertentu (misal HFM: `FOK`, bukan `IOC` yang lebih umum di broker standar). Bridge otomatis mendeteksi dari broker, dan kalau tebakan awalnya ternyata salah (order gagal dengan `retcode=10030 Unsupported filling mode`), sistem **otomatis mencoba mode lain** (FOK → IOC → RETURN) dan mengingat mode yang berhasil untuk order berikutnya — tidak perlu diatur manual, dan tidak akan gagal diam-diam.

## Trade Journal — statistik win rate & performa

Tab "Journal" di web app menampilkan statistik lengkap dari **semua**
trade yang tercatat di history MT5 lo — baik yang dibuka manual lewat
tab Terminal, oleh EA lama, maupun oleh Signal Engine. Filter periode
(7/30/90 hari, 1 tahun) dan sumber trade tersedia di bagian atas tab.

**Yang ditampilkan:**
- Win rate, total trade, net profit, profit factor
- Rata-rata profit per win, rata-rata loss per lose, average risk:reward realized
- Win streak & loss streak (terpanjang dan yang sedang berjalan)
- Trade terbaik & terburuk
- Breakdown harian (jumlah trade, win/loss, profit per hari) dengan mini bar chart
- Tabel detail tiap trade (waktu, sumber, symbol, arah, lot, entry/exit price, durasi, net P/L)

**Cara kerja partial close (penting untuk akurasi win rate):**
Kalau signal engine menutup sebagian posisi di TP1 lalu sisanya di
TP2/TP3/SL (lihat bagian "Manajemen posisi otomatis" di atas), semua
deal itu **digabung jadi satu trade** dalam journal — bukan dihitung
sebagai beberapa trade terpisah. Ini penting supaya win rate tidak
menyesatkan (satu posisi yang akhirnya profit tidak boleh terhitung
sebagai "beberapa kemenangan kecil").

Sumber trade dibedakan lewat magic number: `0` (atau tidak match yang
lain) = manual, `EA_MAGIC_NUMBER` = EA lama, `SIGNAL_MAGIC_NUMBER` =
signal engine — semua sudah dikonfigurasi otomatis dari `config.py`
yang sama dipakai fitur lain.

## News Engine — cara kerja & tuning

**CATATAN JUJUR SEBELUM PAKAI**: ini bukan AI yang "membaca dan memahami"
berita di tahap awal. Deteksi awal murni **keyword matching** pada
judul/ringkasan berita, dan **jadwal** dari economic calendar. Artinya
bisa saja false positive (kata kunci cocok tapi beritanya tidak
relevan) atau false negative (berita penting tapi tidak memakai kata
kunci yang terdaftar). Pantau log & riwayat sinyal secara berkala, dan
sesuaikan keyword di `config.py` kalau perlu.

**PENTING soal endpoint calendar Finnhub & Trading Economics**: endpoint
economic calendar Finnhub (`/calendar/economic`) **butuh paket
berbayar** (403 Forbidden di free tier). Endpoint demo Trading
Economics (`guest:guest`) **sudah dimatikan permanen** per 23 Agustus
2026 (410 Gone). Karena itu, calendar sekarang punya 3 pilihan sumber
independen (bisa dipilih di `CALENDAR_PROVIDER`), dan berita umum tetap
terpisah pakai Finnhub `/news` + RSS (gratis, tidak terpengaruh
masalah di atas):

- **`"forex_factory"`** (opsi baru) — feed JSON mingguan resmi yang dipublikasikan Forex Factory sendiri untuk konsumsi publik/EA, gratis tanpa API key, dipakai luas komunitas MT4/MT5 bertahun-tahun. Di-cache 6 jam sekali untuk hindari rate limit mereka. **Belum diverifikasi otomatis dari sisi pengembangan** — WAJIB dites dulu di VPS lo sebelum diandalkan serius (lihat langkah tes di komentar `CALENDAR_PROVIDER` pada `config.py`)
- **`"manual"`** (default saat ini) — jadwal diisi sendiri di `MANUAL_CALENDAR_EVENTS`, tidak bergantung API/feed apa pun, **paling pasti berjalan**
- **`"trading_economics"`** — masih ada di kode untuk jaga-jaga kalau endpoint-nya hidup lagi, atau kalau lo punya API key TE berbayar sendiri

Kalau provider manapun gagal/kosong, sistem **otomatis fallback ke `MANUAL_CALENDAR_EVENTS`** — blackout window CPI/NFP/FOMC tetap berfungsi walau sumber eksternal bermasalah.

**Setup (wajib sebelum fitur ini aktif):**
1. Untuk berita umum: RSS feed (Yahoo Finance, Investing.com, FXStreet, Kitco) sudah aktif duluan tanpa perlu API key sama sekali — **tapi cek log setelah restart bridge**, karena beberapa situs (terutama Investing.com) kadang memblokir request otomatis tergantung IP VPS lo. Kalau semua feed gagal, web app akan menampilkan badge peringatan "⚠️ Semua sumber berita gagal diakses" di tab Signal Trading. Sebagai cadangan tambahan: daftar gratis di [finnhub.io](https://finnhub.io) (tanpa kartu kredit), copy API key, isi ke `bridge/config.py` bagian `FINNHUB_API_KEY`
2. Untuk calendar: default `CALENDAR_PROVIDER = "manual"` sudah langsung berfungsi tanpa setup tambahan, karena `MANUAL_CALENDAR_EVENTS` sudah diisi jadwal sampai akhir 2026. Kalau mau coba sumber otomatis: ganti ke `"forex_factory"`, restart bridge, **cek log & tab Signal Trading** untuk pastikan event nyata muncul sebelum dipakai serius
3. Cek ulang tanggal di `MANUAL_CALENDAR_EVENTS` mendekati waktu H — jadwal rilis AS beberapa kali bergeser akibat government shutdown, dan CPI/NFP Oktober-Desember di daftar itu masih **perkiraan** (bukan dikonfirmasi resmi)
4. Restart bridge — log akan menunjukkan status fetch pertama, termasuk kalau provider gagal dan fallback ke manual terpakai

**Cara kerja:**
- **Economic calendar** (CPI, NFP, FOMC, PPI, dll dari negara di `NEWS_CALENDAR_COUNTRIES`, default `["US"]`): kalau event berimpact "high" akan rilis dalam `CALENDAR_BLACKOUT_BEFORE_MIN` menit ke depan, atau baru rilis dalam `CALENDAR_BLACKOUT_AFTER_MIN` menit terakhir — signal engine **menahan semua auto-entry baru**. Sinyal teknikal tetap dihitung & ditampilkan di web (badge "🗓 Ditahan"), tapi tidak dieksekusi otomatis. Lo bisa lihat & putuskan manual lewat tab Terminal kalau mau.
- **Berita umum** (geopolitik dll, lewat `NEWS_GOLD_KEYWORDS` di `config.py`): berita segar (dalam `NEWS_FRESHNESS_MINUTES` menit terakhir) yang relevan dan BUKAN calendar event (dicek lewat `NEWS_CALENDAR_OVERLAP_KEYWORDS` supaya CPI/NFP tidak diproses dua kali) lolos ke tahap AI News Analyst (lihat bagian di bawah) untuk penilaian lebih dalam sebelum entry diputuskan.
- Kalau tidak ada calendar event maupun berita relevan → signal engine jalan normal, lot penuh.
- Kalau `MANUAL_CALENDAR_EVENTS` kehabisan event yang akan datang (semua tanggalnya sudah lewat), bot akan memberi **peringatan otomatis** di log dan badge merah di web app (tab Signal Trading) — lihat `CALENDAR_LOW_WARNING_DAYS`.

**Parameter di `config.py`:**
- `USE_NEWS_ENGINE` — matikan seluruhnya kalau tidak mau pakai fitur ini
- `CALENDAR_PROVIDER` — `"manual"` (default, paling pasti jalan) | `"forex_factory"` (feed gratis, perlu ditest dulu) | `"trading_economics"` (kemungkinan besar sudah mati) | `"none"` (matikan blackout calendar)
- `CALENDAR_FF_CACHE_HOURS` — berapa jam cache feed Forex Factory sebelum fetch ulang (default 6 — jangan diturunkan drastis, ada rate limit)
- `TRADING_ECONOMICS_API_KEY` — default `"guest:guest"` (per Agustus 2026 sudah tidak berfungsi); isi API key asli kalau punya
- `MANUAL_CALENDAR_EVENTS` — daftar jadwal rilis yang lo isi sendiri, dipakai sebagai fallback otomatis atau utama (kalau `CALENDAR_PROVIDER = "manual"`)
- `CALENDAR_LOW_WARNING_DAYS` — ambang hari untuk peringatan "jadwal manual perlu diperbarui" (default 30)
- `FINNHUB_API_KEY` — opsional untuk berita umum tambahan (bukan untuk calendar)
- `NEWS_CHECK_INTERVAL_SEC` — seberapa sering cek berita baru (default 5 menit — economic calendar sendiri punya cache terpisah 6 jam)
- `NEWS_CALENDAR_COUNTRIES` — negara yang dipantau untuk calendar (default hanya US, karena emas paling sensitif ke data USD)
- `CALENDAR_BLACKOUT_BEFORE_MIN` / `CALENDAR_BLACKOUT_AFTER_MIN` — lebar window blackout di sekitar rilis
- `NEWS_GOLD_KEYWORDS` — daftar kata kunci berita yang dianggap relevan (silakan tambah/kurangi)
- `NEWS_FRESHNESS_MINUTES` — berita dianggap "baru" berapa lama sejak publikasi

Status berita & calendar tampil real-time di tab "Signal Trading" pada web
app (panel "Status Berita & Calendar"), termasuk jadwal rilis high-impact
ke depan dan daftar berita relevan terkini dengan link ke sumber aslinya.

## AI News Analyst — analisa sentimen berita pakai LLM gratis

**CATATAN JUJUR SEBELUM PAKAI**: AI di sini menilai teks berita (judul +
ringkasan) dan memberi opini sentiment (bullish/bearish/netral) beserta
tingkat keyakinan — tapi tetap bisa salah baca konteks (sarkasme, artikel
opini vs breaking news, judul clickbait). **Arah entry TIDAK PERNAH
ditentukan oleh AI** — entry selalu mengikuti sinyal **teknikal**; AI
hanya mempengaruhi **ukuran lot**. Kalau AI gagal/timeout/error apa pun,
sistem otomatis fallback ke "netral" (lot normal), tidak pernah membuat
bridge berhenti atau crash.

**Cara kerja — matriks ukuran lot saat ada berita high-impact:**

| Kondisi | Lot yang dipakai |
|---|---|
| Tidak ada berita relevan | `SIGNAL_LOT_SIZE` (normal) |
| Berita relevan, AI netral/gagal/tidak yakin (confidence < `AI_MIN_CONFIDENCE`) | `SIGNAL_LOT_SIZE` (normal) |
| Berita relevan, AI **searah** sinyal teknikal (misal sinyal BUY, AI bilang bullish) | `SIGNAL_LOT_SIZE` (normal, tidak dinaikkan) |
| Berita relevan, AI **berlawanan** arah sinyal teknikal (misal sinyal BUY, AI bilang bearish) | lot **minimum broker** — tetap entry mengikuti arah teknikal, tapi risiko ditekan serendah mungkin |

**Setup (opsional — kalau tidak diisi, otomatis fallback ke keyword matching biasa tanpa AI):**

Provider AI-nya **pluggable**, gampang diganti. Pilih salah satu, keduanya gratis tanpa kartu kredit:

1. **Google Gemini** (`bridge/config.py`: `AI_PROVIDER = "gemini"`) — daftar di [aistudio.google.com](https://aistudio.google.com), copy API key, isi ke `GEMINI_API_KEY`
2. **Groq** (`AI_PROVIDER = "groq"`) — daftar di [console.groq.com](https://console.groq.com), copy API key, isi ke `GROQ_API_KEY`

Cek dulu halaman resmi masing-masing provider untuk limit free tier terbaru — kebijakannya sering berubah. Untuk kebutuhan ini (beberapa panggilan tiap 5 menit, bukan volume tinggi), tier gratis manapun jauh lebih dari cukup.

**Parameter di `config.py`:**
- `USE_AI_NEWS_ANALYST` — matikan seluruhnya kalau tidak mau pakai AI (balik ke keyword matching polos)
- `AI_PROVIDER` — `"gemini"` | `"groq"` | `"none"`
- `AI_MIN_CONFIDENCE` — ambang keyakinan AI (0.0–1.0) supaya penilaiannya dianggap valid mempengaruhi lot; di bawah ini dianggap "tidak yakin", diperlakukan sama seperti netral
- `AI_REQUEST_TIMEOUT_SEC` — batas waktu tunggu respons AI sebelum fallback ke netral

**Menambah provider AI lain:** buka `bridge/ai_news_analyst.py`, tambah satu fungsi `_call_<nama_provider>()` dengan signature yang sama seperti `_call_gemini`/`_call_groq`, lalu daftarkan di dict `PROVIDERS` — tidak perlu ubah bagian lain.

Hasil penilaian AI (sentiment, confidence, alasan) tampil di tab "Signal
Trading" pada web app — baik di badge sinyal individual maupun di panel
"Status Berita & Calendar".

## AI Chart Analyst — gate wajib berbasis konfluensi indikator

**Beda dari AI News Analyst di atas** (yang cuma mempengaruhi ukuran
lot): AI Chart Analyst ini adalah **gate wajib**. Sinyal teknikal dasar
(EMA+RSI) harus disetujui AI berdasarkan analisa konfluensi indikator
tambahan sebelum benar-benar dieksekusi — kalau AI tidak setuju, sinyal
dibatalkan sepenuhnya (bukan cuma lot dikecilkan). Tujuannya: sinyal
lebih jarang muncul, tapi lebih meyakinkan.

**CATATAN JUJUR SEBELUM PAKAI**: AI di sini **tidak melihat chart
secara visual**. Yang dikirim ke AI adalah ringkasan **angka**
indikator yang sudah dihitung bridge (EMA, RSI, MACD, Bollinger Bands,
ada/tidaknya pola candlestick) — bukan gambar chart. AI menilai
konfluensi (seberapa banyak & kuat indikator saling mendukung), yang
pada dasarnya adalah evaluasi kombinasi angka yang sama dengan yang
bisa dihitung manual dengan if-else, hanya lebih fleksibel dalam
menilai kombinasi kompleks. Ini bukan jaminan akurasi lebih tinggi,
hanya lapisan penyaringan tambahan.

**Indikator konfirmasi yang ditambahkan** (di luar EMA+RSI dasar yang
sudah ada):
- **MACD** — histogram positif/negatif menunjukkan momentum searah/berlawanan
- **Bollinger Bands** — posisi harga relatif terhadap band (ruang gerak sebelum overextended)
- **Candlestick pattern** — Bullish/Bearish Engulfing, Hammer, Shooting Star, atau candle dengan body dominan searah sinyal

**PENTING — perilaku kalau AI gagal/timeout** (`AI_CHART_FAIL_MODE` di `config.py`):
- `"fail_safe"` (default) — sinyal **ditolak** kalau AI tidak bisa dihubungi. Konsisten dengan tujuan "lebih ketat", tapi konsekuensinya bot **berhenti entry total** kalau API key AI habis kuota atau provider down, sampai AI bisa dihubungi lagi.
- `"fail_open"` — sinyal tetap **lolos tanpa gate AI** kalau AI gagal (kembali ke perilaku EMA+RSI+filter session/volatility saja). Pilih ini kalau tidak mau bot berhenti total hanya karena AI provider bermasalah.

**Parameter di `config.py`:**
- `USE_AI_CHART_ANALYST` — matikan seluruhnya kalau tidak mau pakai gate ini (balik ke EMA+RSI+filter saja seperti sebelumnya)
- `AI_CHART_MIN_CONFIDENCE` — ambang keyakinan minimum (default 0.6) supaya sinyal dianggap "disetujui" — di bawah ini ditolak walau AI bilang setuju
- `AI_CHART_FAIL_MODE` — `"fail_safe"` | `"fail_open"` (lihat penjelasan di atas)

Provider AI yang dipakai **sama** dengan `AI_PROVIDER` di bagian AI News
Analyst di atas (Gemini/Groq) — tidak ada konfigurasi provider terpisah,
tapi API key yang sama dipakai untuk 2 keperluan (analisa berita +
analisa chart), jadi kuota API terpakai lebih cepat dari sebelumnya —
perhatikan limit free tier provider yang dipilih.

Hasil analisa (setuju/tidak, confidence, alasan, skor konfirmasi
indikator) tampil di badge hijau pada tiap sinyal di tab "Signal
Trading" — sinyal yang ditolak AI tidak akan muncul sama sekali di
riwayat (karena `analyze()` return `None` sebelum sinyal terbentuk).

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
- Cache/dedup untuk panggilan AI News Analyst (saat ini tiap siklus cek berita relevan yang sama bisa terkirim ulang ke AI kalau masih dalam window `NEWS_FRESHNESS_MINUTES` — belum masalah untuk volume pemakaian normal, tapi bisa dioptimasi supaya lebih hemat kuota API kalau perlu)

Kalau butuh salah satu dari itu, bilang aja, saya lanjutin.
