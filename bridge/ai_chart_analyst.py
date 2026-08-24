"""
AI Chart Analyst
==================
Berbeda dari ai_news_analyst.py (yang cuma mempengaruhi ukuran lot),
modul ini adalah GATE WAJIB: sinyal teknikal dasar (EMA+RSI) HARUS
disetujui AI berdasarkan konfluensi multi-indikator (MACD, Bollinger
Bands, candlestick pattern) sebelum entry benar-benar dieksekusi.

CATATAN JUJUR — PENTING:
AI di sini TIDAK "melihat" chart secara visual. Yang dikirim adalah
RINGKASAN ANGKA dari indikator yang sudah dihitung signal_engine.py
(EMA, RSI, MACD, Bollinger Bands, ada/tidaknya pola candlestick). AI
menilai KONFLUENSI (seberapa banyak & seberapa kuat indikator-indikator
itu saling mendukung), bukan menganalisa gambar chart. Ini bukan sihir
— pada dasarnya AI mengevaluasi kombinasi angka yang sama dengan yang
bisa dihitung manual dengan if-else, tapi lebih fleksibel dalam menilai
KOMBINASI kompleks dan bisa memberi alasan dalam bahasa natural.

KARENA INI GATE WAJIB (bukan sekadar filter lot seperti AI News
Analyst), defaultnya FAIL-SAFE: kalau AI gagal/timeout/error apa pun,
sinyal DITOLAK (tidak dieksekusi), bukan dianggap netral/lolos. Ini
konsisten dengan tujuan "lebih ketat, sinyal lebih jarang tapi lebih
meyakinkan" — tapi konsekuensinya: kalau API key AI habis kuota atau
provider down, bot BERHENTI ENTRY sampai AI bisa dihubungi lagi. Kalau
ini tidak diinginkan, ubah AI_CHART_FAIL_MODE di config.py jadi
"fail_open" (lolos tanpa AI, kembali ke perilaku sebelum fitur ini ada).

Didesain PLUGGABLE sama seperti ai_news_analyst.py — provider diatur
lewat config.AI_PROVIDER (provider yang sama dipakai untuk news & chart).
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

import requests

import config

log = logging.getLogger("ai-chart-analyst")

SYSTEM_PROMPT = """Kamu adalah analis teknikal trading yang fokus pada emas (XAUUSD/gold).
Kamu akan menerima ringkasan angka-angka indikator teknikal dari satu titik waktu (BUKAN
gambar chart), dan sinyal arah (BUY/SELL) yang dihasilkan dari EMA+RSI dasar.

Tugasmu: nilai apakah kombinasi indikator-indikator ini BENERAN cukup meyakinkan untuk
mendukung sinyal arah tersebut (konfluensi multi-indikator), atau justru saling
bertentangan / lemah / meragukan.

Jawab HANYA dalam format JSON persis seperti ini, tanpa teks lain, tanpa markdown code block:
{"agree": true/false, "confidence": 0.0-1.0, "reason": "alasan singkat 1-2 kalimat dalam Bahasa Indonesia"}

Panduan penilaian:
- "agree": true HANYA kalau mayoritas indikator (MACD, posisi harga vs Bollinger Bands,
  pola candlestick) benar-benar SEARAH dan MENDUKUNG sinyal EMA+RSI dasar. Bukan cukup
  1 indikator saja yang mendukung — butuh konfluensi (beberapa indikator sepakat).
- "agree": false kalau indikator-indikator saling bertentangan (misal MACD histogram
  negatif padahal sinyal dasarnya BUY), atau harga sudah terlalu ekstrem di luar
  Bollinger Band (overextended, resiko reversal tinggi), atau tidak ada pola
  candlestick yang mendukung sama sekali.
- confidence tinggi (>0.7) hanya kalau SEMUA indikator yang diberikan sepakat kuat.
  confidence sedang (0.4-0.7) kalau ada mayoritas tapi tidak semua sepakat.
  confidence rendah (<0.4) kalau indikator-indikator saling bertentangan atau lemah.
- Jangan ragu memberi agree:false kalau memang datanya tidak meyakinkan — tujuan
  analisa ini justru untuk MENYARING sinyal yang lemah, bukan meloloskan semuanya."""


@dataclass
class ChartAnalysis:
    agree: bool
    confidence: float
    reason: str
    provider: str
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def _rejected_fallback(provider: str, error: str) -> ChartAnalysis:
    """Dipanggil kalau AI gagal/timeout/error apa pun. BEDA dari
    ai_news_analyst.py: di sini defaultnya MENOLAK (agree=False), bukan
    netral — karena AI Chart Analyst adalah gate wajib, bukan filter
    pelengkap. Kalau config.AI_CHART_FAIL_MODE = "fail_open", pemanggil
    (signal_engine.py) akan menangani ini sebagai lolos, bukan modul
    ini yang memutuskan itu."""
    log.warning(f"AI chart analyst gagal ({error}), fail_mode={config.AI_CHART_FAIL_MODE}")
    return ChartAnalysis(
        agree=False,
        confidence=0.0,
        reason=f"Analisa AI tidak tersedia ({error}).",
        provider=provider,
        error=error,
    )


def _parse_ai_json(raw_text: str, provider: str) -> ChartAnalysis:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    return ChartAnalysis(
        agree=bool(data.get("agree", False)),
        confidence=confidence,
        reason=str(data.get("reason", "")),
        provider=provider,
    )


def _build_prompt(direction: str, indicator_summary: str) -> str:
    return (
        f"Sinyal dasar (dari EMA+RSI): {direction}\n\n"
        f"Ringkasan indikator:\n{indicator_summary}\n\n"
        f"Apakah kombinasi indikator ini cukup meyakinkan untuk mendukung sinyal {direction} ini?"
    )


# ==============================================================
#  PROVIDER: Google Gemini
# ==============================================================
def _call_gemini(direction: str, indicator_summary: str) -> ChartAnalysis:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": _build_prompt(direction, indicator_summary)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
    }
    resp = requests.post(url, json=payload, timeout=config.AI_REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_ai_json(raw_text, "gemini")


# ==============================================================
#  PROVIDER: Groq
# ==============================================================
def _call_groq(direction: str, indicator_summary: str) -> ChartAnalysis:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(direction, indicator_summary)},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=config.AI_REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return _parse_ai_json(raw_text, "groq")


PROVIDERS = {
    "gemini": _call_gemini,
    "groq": _call_groq,
}


def analyze_chart(direction: str, indicator_summary: str) -> ChartAnalysis:
    """Fungsi utama dipanggil signal_engine.py sebagai gate wajib
    sebelum eksekusi. Selalu return ChartAnalysis, tidak pernah raise
    exception — tapi BEDA dari ai_news_analyst.py, fallback default
    di sini adalah PENOLAKAN (agree=False), bukan netral, karena
    perannya sebagai gate wajib."""
    if not config.USE_AI_CHART_ANALYST or config.AI_PROVIDER == "none":
        return _rejected_fallback(config.AI_PROVIDER, "AI Chart Analyst dimatikan di config")

    provider_fn = PROVIDERS.get(config.AI_PROVIDER)
    if provider_fn is None:
        return _rejected_fallback(config.AI_PROVIDER, f"Provider '{config.AI_PROVIDER}' tidak dikenal")

    key_map = {"gemini": config.GEMINI_API_KEY, "groq": config.GROQ_API_KEY}
    api_key = key_map.get(config.AI_PROVIDER, "")
    if not api_key or api_key.startswith("ISI_"):
        return _rejected_fallback(config.AI_PROVIDER, f"API key untuk {config.AI_PROVIDER} belum diisi di config.py")

    try:
        return provider_fn(direction, indicator_summary)
    except requests.RequestException as e:
        return _rejected_fallback(config.AI_PROVIDER, f"Request gagal: {e}")
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        return _rejected_fallback(config.AI_PROVIDER, f"Gagal parse respons AI: {e}")
    except Exception as e:
        return _rejected_fallback(config.AI_PROVIDER, f"Error tak terduga: {e}")
