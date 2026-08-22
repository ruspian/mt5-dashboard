# Panduan Setup Bridge di VPS Windows

## Langkah 1 — Install Python
1. Download Python dari https://www.python.org/downloads/ (versi 3.10 atau 3.11 — **jangan** versi terbaru banget, kadang library MT5 belum support)
2. Waktu install, **centang "Add Python to PATH"**
3. Cek berhasil: buka Command Prompt, ketik `python --version`

## Langkah 2 — Copy folder `bridge` ke VPS
Copy seluruh folder `bridge/` (isinya: `main.py`, `config.py`, `requirements.txt`) ke VPS, taruh misalnya di `C:\mt5-bridge\`

## Langkah 3 — Install dependency
Buka Command Prompt di folder itu:
```
cd C:\mt5-bridge
pip install -r requirements.txt
```

> **Kalau muncul error terkait NumPy** ("A module that was compiled using
> NumPy 1.x cannot be run in NumPy 2.x", atau `_ARRAY_API not found`):
> package `MetaTrader5` belum kompatibel dengan NumPy versi terbaru.
> Perbaiki dengan:
> ```
> pip uninstall numpy MetaTrader5 -y
> pip install "numpy<2"
> pip install MetaTrader5
> ```
> `requirements.txt` di atas sudah mengunci NumPy ke versi 1.x supaya
> ini tidak terjadi kalau install dari awal.

## Langkah 4 — Generate token auth
```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy hasilnya, paste ke `config.py` bagian `API_TOKEN = "..."`

## Langkah 5 — Cari path file signal EA
1. Buka MT5 terminal di VPS
2. Klik menu **File → Open Data Folder**
3. Masuk ke folder `MQL5\Files\` — kalau lo mau EA-nya bisa diakses semua terminal, sebaiknya pakai folder **Common**: buka `MQL5\Files\` lalu cari folder bernama sama tapi ada tulisan "Common" di file explorer path atas, atau lihat di `C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\Common\Files\`
4. Copy path lengkap itu ke `config.py` di `EA_SIGNAL_FILE` dan `EA_STATUS_FILE` (tambahkan nama file `ea_signal.txt` / `ea_status.txt` di belakangnya)

## Langkah 6 — Pastikan MT5 sudah login
Buka terminal MT5 di VPS, login ke akun trading lo seperti biasa, **biarkan tetap terbuka** (jangan ditutup). Bridge akan connect ke instance yang sedang berjalan ini.

> Kalau lo mau bridge yang otomatis login sendiri (misal VPS restart), isi `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` di config.py.

## Langkah 7 — Jalankan bridge
```
python main.py
```
Kalau berhasil, muncul log: `Menjalankan MT5 Bridge di 0.0.0.0:8765`

Test dari browser VPS itu sendiri: buka `http://localhost:8765/health` — harus muncul `{"ok":true,...}`

## Langkah 8 — Supaya bridge tetap jalan walau lo close Command Prompt
Cara paling gampang: pakai **NSSM** (Non-Sucking Service Manager) supaya jadi Windows Service.
1. Download NSSM: https://nssm.cc/download
2. Extract, buka Command Prompt as Administrator di folder nssm
3. Jalankan: `nssm install MT5Bridge`
4. Di window yang muncul:
   - **Path**: lokasi `python.exe` lo (cek dengan `where python`)
   - **Startup directory**: `C:\mt5-bridge`
   - **Arguments**: `main.py`
5. Klik **Install service**
6. Jalankan: `nssm start MT5Bridge`

Sekarang bridge otomatis jalan walau VPS restart.

## Langkah 9 — Setup HTTPS (supaya web app di Vercel bisa akses dengan aman)
Browser modern **memblokir** koneksi dari halaman HTTPS (web app lo di Vercel) ke endpoint HTTP biasa (bridge lo). Jadi bridge WAJIB punya HTTPS juga. Paling gampang pakai **Caddy** (auto HTTPS gratis, tidak perlu urus sertifikat manual):

1. Lo butuh **domain** yang di-pointing ke IP VPS ini (misal beli domain murah di Namecheap ~Rp150rb/tahun, atau kalau cuma buat coba-coba bisa pakai DuckDNS gratis: https://www.duckdns.org)
2. Set DNS domain itu (A record) mengarah ke IP publik VPS lo
3. Download Caddy untuk Windows: https://caddyserver.com/download
4. Taruh `caddy.exe` di `C:\caddy\`
5. Buat file `C:\caddy\Caddyfile` isinya:
   ```
   bridge.domainlo.com {
       reverse_proxy localhost:8765
   }
   ```
6. Buka Command Prompt as Administrator di `C:\caddy`, jalankan:
   ```
   caddy run
   ```
   Caddy otomatis urus sertifikat HTTPS lewat Let's Encrypt, dan `reverse_proxy`
   di atas juga otomatis meneruskan koneksi WebSocket (endpoint `/ws`) tanpa
   perlu konfigurasi tambahan — tidak perlu edit apa pun untuk itu.
7. Sekarang bridge lo bisa diakses aman di `https://bridge.domainlo.com`
8. (Opsional tapi disarankan) Jadikan Caddy juga Windows Service pakai NSSM seperti langkah 8, supaya jalan terus.

**Firewall VPS**: pastikan port 443 (HTTPS) dan 80 (buat verifikasi Let's Encrypt) terbuka di firewall VPS/provider cloud lo. Port 8765 **tidak perlu** dibuka ke publik — cukup diakses localhost oleh Caddy.

---

Setelah semua ini jalan, lo punya:
`https://bridge.domainlo.com` ← ini yang nanti dimasukkan ke web app Next.js sebagai `NEXT_PUBLIC_BRIDGE_URL`, plus token dari Langkah 4.
