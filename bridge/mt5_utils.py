"""
MT5 Utilities
==============
Fungsi bantu kecil yang dipakai bersama oleh main.py dan signal_engine.py,
supaya tidak ada duplikasi logic dan tidak circular import antar modul.
"""

import logging

import MetaTrader5 as mt5

log = logging.getLogger("mt5-utils")

# Cache per-symbol supaya tidak query symbol_info() berulang kali untuk
# hal yang jarang berubah (filling mode broker biasanya tetap sama
# selama sesi berjalan, kecuali broker mengubah kebijakan mereka)
_filling_mode_cache: dict[str, int] = {}

RETCODE_UNSUPPORTED_FILLING = 10030


def get_supported_filling_mode(symbol: str) -> int:
    """Deteksi otomatis filling mode yang didukung broker untuk symbol
    ini, alih-alih hardcode ORDER_FILLING_IOC yang bisa gagal dengan
    error 'Unsupported filling mode' (retcode=10030) tergantung
    kebijakan broker/jenis akun (umum terjadi di akun cent).

    MT5 expose filling mode yang didukung lewat symbol_info().filling_mode,
    sebuah bitmask. Urutan pengecekan FOK -> IOC -> RETURN dipilih karena
    itu urutan yang paling umum didukung broker retail secara luas ke
    paling terbatas.

    CATATAN PENTING: bitmask ini kadang TIDAK AKURAT untuk sebagian
    broker (terutama market maker/akun cent seperti HFM) — bitmask bisa
    bilang suatu mode "didukung" padahal order tetap ditolak retcode
    10030 saat benar-benar dikirim. Karena itu, hasil dari fungsi ini
    dipakai sebagai TEBAKAN PERTAMA saja — send_order_with_fallback()
    di bawah akan otomatis mencoba mode lain kalau tebakan pertama
    gagal dengan retcode 10030, dan mengingat mode yang akhirnya
    berhasil untuk dipakai langsung di percobaan berikutnya."""
    if symbol in _filling_mode_cache:
        return _filling_mode_cache[symbol]

    info = mt5.symbol_info(symbol)
    if info is None:
        # symbol tidak ditemukan — biarkan pemanggil yang menangani via
        # error lain (symbol_info() dipanggil lagi di tempat order dikirim,
        # akan gagal dengan pesan yang lebih jelas soal symbol tidak ada)
        return mt5.ORDER_FILLING_IOC

    filling_mode_bitmask = info.filling_mode

    # SYMBOL_FILLING_FOK = 1, SYMBOL_FILLING_IOC = 2 (bitmask, bisa gabungan)
    supports_fok = bool(filling_mode_bitmask & 1)
    supports_ioc = bool(filling_mode_bitmask & 2)

    if supports_fok:
        mode = mt5.ORDER_FILLING_FOK
        mode_name = "FOK"
    elif supports_ioc:
        mode = mt5.ORDER_FILLING_IOC
        mode_name = "IOC"
    else:
        # Tidak ada bit FOK/IOC yang di-set -> broker ini cuma dukung RETURN
        # (umum di akun cent/beberapa broker market maker)
        mode = mt5.ORDER_FILLING_RETURN
        mode_name = "RETURN"

    log.info(f"Filling mode terdeteksi untuk {symbol}: {mode_name} (bitmask broker={filling_mode_bitmask}, tebakan awal — akan dikoreksi otomatis kalau ternyata salah)")
    _filling_mode_cache[symbol] = mode
    return mode


def _mode_name(mode: int) -> str:
    names = {
        mt5.ORDER_FILLING_FOK: "FOK",
        mt5.ORDER_FILLING_IOC: "IOC",
        mt5.ORDER_FILLING_RETURN: "RETURN",
    }
    return names.get(mode, str(mode))


def send_order_with_fallback(request: dict):
    """Kirim order MT5 (mt5.order_send) dengan fallback otomatis kalau
    filling mode yang dipakai ternyata tidak didukung broker (retcode
    10030) — mencoba FOK, IOC, RETURN secara berurutan (skip yang sama
    dengan percobaan pertama supaya tidak dicoba dua kali), dan begitu
    ada yang berhasil, mode itu di-cache untuk symbol ini supaya
    percobaan berikutnya langsung pakai mode yang benar tanpa perlu
    trial-error lagi.

    request: dict permintaan order MT5 standar, HARUS sudah punya key
    'type_filling' terisi (dari get_supported_filling_mode() sebagai
    tebakan awal) dan 'symbol'.

    Return: hasil mt5.order_send() (OrderSendResult) dari percobaan
    yang berhasil, atau percobaan TERAKHIR kalau semua mode gagal
    (supaya pemanggil tetap dapat retcode & comment yang informatif
    untuk kegagalan asli, bukan cuma soal filling mode)."""
    symbol = request.get("symbol", "")
    all_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]

    first_mode = request.get("type_filling", mt5.ORDER_FILLING_IOC)
    # urutan coba: mode pertama (tebakan/cache) dulu, baru sisanya yang belum dicoba
    modes_to_try = [first_mode] + [m for m in all_modes if m != first_mode]

    last_result = None
    for i, mode in enumerate(modes_to_try):
        request["type_filling"] = mode
        result = mt5.order_send(request)
        last_result = result

        if result is None:
            # order_send() bisa return None kalau terminal MT5 disconnect
            # sama sekali — bukan soal filling mode, hentikan percobaan
            log.warning(f"order_send() mengembalikan None untuk {symbol} (kemungkinan MT5 terminal disconnect).")
            return result

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            if i > 0:
                log.info(
                    f"Filling mode {_mode_name(mode)} berhasil untuk {symbol} setelah "
                    f"{_mode_name(first_mode)} ditolak. Mode ini di-cache untuk percobaan berikutnya."
                )
                _filling_mode_cache[symbol] = mode
            return result

        if result.retcode != RETCODE_UNSUPPORTED_FILLING:
            # Gagal karena alasan LAIN (harga bergerak, margin tidak cukup,
            # dll) — bukan soal filling mode, tidak ada gunanya coba mode
            # lain, langsung return supaya pemanggil dapat error yang
            # relevan tanpa delay percobaan tambahan yang percuma.
            return result

        log.info(f"Filling mode {_mode_name(mode)} ditolak (retcode 10030) untuk {symbol}, mencoba mode berikutnya...")

    log.warning(
        f"Semua filling mode (FOK/IOC/RETURN) ditolak broker untuk {symbol}. "
        f"Kemungkinan ada masalah lain di luar filling mode — cek comment/retcode terakhir: "
        f"{last_result.comment if last_result else 'N/A'}"
    )
    return last_result


def clear_filling_mode_cache():
    """Panggil ini kalau curiga broker mengubah kebijakan filling mode
    di tengah sesi (jarang terjadi, tapi jaga-jaga)."""
    _filling_mode_cache.clear()
