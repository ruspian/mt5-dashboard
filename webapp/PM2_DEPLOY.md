# Deploy Webapp di VPS dengan PM2

Panduan ini untuk kasus: bridge Python DAN webapp Next.js jalan di **VPS
yang sama**. Ini lebih simpel dari deploy ke Vercel karena webapp bisa
akses bridge lewat `localhost`, tidak perlu domain terpisah untuk bridge.

## Ringkasan arsitektur baru

```
Internet (HTTPS) --> Caddy (port 443) --> Next.js/PM2 (port 3000) --> Bridge (localhost:8765) --> MT5
```

Caddy sekarang mengarah ke **webapp**, bukan langsung ke bridge. Bridge
cukup didengar di `127.0.0.1` (tidak perlu diekspos ke internet sama
sekali — lebih aman).

---

## Langkah 1 — Install Node.js di VPS (Windows)

1. Download Node.js LTS dari https://nodejs.org (pilih versi LTS, misal 22.x)
2. Install seperti biasa (Next installer), centang "Add to PATH"
3. Cek: buka Command Prompt baru, ketik:
   ```
   node --version
   npm --version
   ```

## Langkah 2 — Copy folder `webapp` ke VPS

Copy seluruh folder `webapp/` ke VPS, taruh di `C:\mt5-webapp\`
(sejajar dengan `C:\mt5-bridge\` yang sudah ada).

## Langkah 3 — Setup environment variable

Di `C:\mt5-webapp\`, buat file `.env.local` (copy dari `.env.local.example`):

```
BRIDGE_URL=http://localhost:8765
BRIDGE_TOKEN=isi_token_yang_sama_dengan_di_bridge/config.py
DASHBOARD_PASSWORD=password_bebas_buat_login
SESSION_SECRET=generate_string_acak_panjang
```

Untuk `SESSION_SECRET`, generate string acak dengan salah satu cara ini
di Command Prompt:
```
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```
Copy hasilnya ke `SESSION_SECRET`.

**Penting**: `BRIDGE_URL` di sini pakai `http://localhost:8765` (bukan
`https://bridge.domainlo.com` lagi), karena webapp dan bridge sekarang
satu server. Ini lebih cepat dan bridge tidak perlu expose HTTPS ke
publik sama sekali.

## Langkah 4 — Sesuaikan bridge supaya hanya dengar di localhost

Buka `C:\mt5-bridge\config.py`, cek bagian ini:
```python
HOST = "0.0.0.0"
PORT = 8765
```
Karena bridge sekarang hanya diakses oleh webapp yang satu server, lebih
aman ganti jadi:
```python
HOST = "127.0.0.1"
PORT = 8765
```
Ini artinya bridge **tidak bisa diakses dari luar VPS sama sekali** —
cuma proses lain di VPS yang sama (webapp-nya) yang bisa akses. Restart
bridge (`python main.py`) setelah ubah ini.

Kalau bridge lo sebelumnya sudah pakai Caddy mengarah ke bridge, itu
**tidak perlu lagi** — hapus/nonaktifkan reverse proxy yang lama untuk
bridge, karena sekarang publik hanya akan mengakses webapp.

## Langkah 5 — Install dependency & build

Buka Command Prompt di `C:\mt5-webapp`:
```
npm install
npm run build
```
`npm run build` menghasilkan versi production yang dioptimasi — ini yang
dijalankan PM2, bukan `npm run dev`.

## Langkah 6 — Install PM2

PM2 untuk Windows dipasang lewat npm:
```
npm install -g pm2
npm install -g pm2-windows-startup
pm2-startup install
```
Perintah kedua & ketiga membuat PM2 otomatis jalan lagi kalau VPS
di-restart.

## Langkah 7 — Jalankan webapp dengan PM2

Di `C:\mt5-webapp`, jalankan:
```
pm2 start npm --name "mt5-webapp" -- start
```
Penjelasan: `npm start` menjalankan `next start` (server production),
sudah didefinisikan di `package.json`. Nama proses `mt5-webapp` supaya
gampang dikenali di daftar PM2.

Cek statusnya:
```
pm2 status
```
Harus muncul proses `mt5-webapp` dengan status `online`.

Lihat log real-time:
```
pm2 logs mt5-webapp
```

Test dari VPS itu sendiri: buka browser, akses `http://localhost:3000`
— harus muncul halaman login.

## Langkah 8 — Simpan konfigurasi PM2 supaya survive restart VPS

```
pm2 save
```
Ini menyimpan daftar proses yang sedang dikelola PM2 (termasuk
`mt5-webapp`), supaya `pm2-startup` tahu proses apa saja yang harus
dihidupkan lagi otomatis saat VPS restart.

## Langkah 9 — Setup Caddy mengarah ke webapp (bukan bridge lagi)

Edit `C:\caddy\Caddyfile` (kalau sebelumnya sudah ada untuk bridge,
ganti isinya):
```
dashboard.domainlo.com {
    reverse_proxy localhost:3000
}
```
Jalankan Caddy (kalau belum jadi service, `caddy run` as Administrator
di folder itu; kalau mau permanen, install juga sebagai Windows Service
pakai NSSM seperti bridge — lihat `bridge/SETUP.md` langkah 8 untuk
caranya, tinggal ganti target ke `caddy.exe`).

Sekarang webapp lo bisa diakses dari mana saja lewat
`https://dashboard.domainlo.com`, login pakai `DASHBOARD_PASSWORD`
yang tadi diisi di `.env.local` — dan **bridge sepenuhnya privat**,
tidak pernah diekspos ke internet.

---

## Perintah PM2 yang sering dipakai

| Perintah | Fungsi |
|---|---|
| `pm2 status` | lihat semua proses & statusnya |
| `pm2 logs mt5-webapp` | lihat log real-time |
| `pm2 restart mt5-webapp` | restart webapp (misal setelah ganti `.env.local`) |
| `pm2 stop mt5-webapp` | hentikan sementara |
| `pm2 delete mt5-webapp` | hapus proses dari PM2 sepenuhnya |

**Penting**: kalau lo edit `.env.local` atau ganti kode webapp, harus
`npm run build` ulang lalu `pm2 restart mt5-webapp` — PM2 menjalankan
hasil build, bukan source code langsung, jadi perubahan tidak otomatis
kepakai tanpa build ulang.

## Kalau mau kelola bridge juga lewat PM2 (opsional)

PM2 sebenarnya bisa juga menjalankan proses Python, bukan cuma Node:
```
cd C:\mt5-bridge
pm2 start main.py --name "mt5-bridge" --interpreter python
pm2 save
```
Dengan ini, satu perintah `pm2 status` menunjukkan bridge dan webapp
sekaligus, dan keduanya otomatis restart bareng kalau VPS reboot.
