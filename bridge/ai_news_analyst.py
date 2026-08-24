"""
AI News Analyst
=================
Tahap tambahan setelah news_engine.py mendeteksi berita relevan lewat
keyword matching. Berita yang lolos filter keyword dikirim ke LLM
untuk dinilai lebih dalam:
  - apakah beneran relevan ke pergerakan harga gold (bukan cuma
    kebetulan mengandung kata kunci)
  - arah sentimen: "bullish" | "bearish" | "neutral"
  - tingkat keyakinan (0.0 - 1.0)
  - alasan singkat dalam bahasa natural

Didesain PLUGGABLE — provider AI diatur lewat config.AI_PROVIDER.
Menambah provider baru cukup menambah satu fungsi _call_<provider>()
dengan signature yang sama, lalu daftarkan di PROVIDERS di bawah.

CATATAN JUJUR: LLM tetap bisa salah baca konteks (sarkasme, artikel
opini vs breaking news, judul clickbait). Ini bukan kebenaran mutlak,
melainkan input tambahan untuk membantu ukuran lot — arah entry TETAP
mengikuti sinyal teknikal (lihat signal_engine.py), tidak pernah
ditentukan oleh AI. Kalau AI gagal/timeout/error apa pun, sistem
otomatis dianggap "netral" — tidak pernah membuat bridge berhenti
atau crash karena masalah di sisi AI provider.
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

import requests

import config

log = logging.getLogger("ai-news-analyst")

SYSTEM_PROMPT = """Kamu adalah analis pasar finansial yang fokus pada emas (XAUUSD/gold).
Tugasmu: nilai apakah sebuah berita relevan dan berpotensi menggerakkan harga emas,
dan ke arah mana.

Jawab HANYA dalam format JSON persis seperti ini, tanpa teks lain, tanpa markdown code block:
{"relevant": true/false, "sentiment": "bullish"/"bearish"/"neutral", "confidence": 0.0-1.0, "reason": "alasan singkat 1-2 kalimat dalam Bahasa Indonesia"}

Panduan penilaian:
- "bullish" untuk gold: berita yang cenderung menaikkan harga emas (contoh: eskalasi
  geopolitik/perang, ketidakpastian ekonomi, ekspektasi rate cut, inflasi tinggi,
  pelemahan dolar AS, aksi cari aset safe haven)
- "bearish" untuk gold: berita yang cenderung menurunkan harga emas (contoh: de-eskalasi
  konflik/ceasefire, penguatan dolar AS, ekspektasi rate hike agresif, risk-on sentiment
  di pasar saham)
- "neutral": berita relevan tapi dampaknya tidak jelas arahnya, atau berita yang
  sebenarnya tidak benar-benar berpotensi menggerakkan harga gold meski mengandung
  kata kunci terkait
- confidence rendah (di bawah 0.5) kalau kamu tidak yakin atau informasinya ambigu/tidak lengkap
- relevant: false kalau beritanya sebenarnya tidak relevan sama sekali ke gold meski
  ada kata kunci yang cocok (contoh: berita tentang "Golden Globe Awards" bukan tentang emas)"""


@dataclass
class AIAnalysis:
    relevant: bool
    sentiment: str        # "bullish" | "bearish" | "neutral"
    confidence: float
    reason: str
    provider: str
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def _neutral_fallback(provider: str, error: str) -> AIAnalysis:
    """Dipanggil kalau AI gagal/timeout/error apa pun — jangan pernah
    biarkan kegagalan AI menghentikan atau meng-crash signal engine."""
    log.warning(f"AI news analyst fallback ke netral: {error}")
    return AIAnalysis(
        relevant=False,
        sentiment="neutral",
        confidence=0.0,
        reason=f"Analisa AI tidak tersedia ({error}), diperlakukan sebagai netral.",
        provider=provider,
        error=error,
    )


def _parse_ai_json(raw_text: str, provider: str) -> AIAnalysis:
    # LLM kadang tetap membungkus JSON dengan ```json ... ``` walau sudah
    # diminta tidak — bersihkan dulu sebelum parse
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    sentiment = str(data.get("sentiment", "neutral")).lower()
    if sentiment not in ("bullish", "bearish", "neutral"):
        sentiment = "neutral"

    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    return AIAnalysis(
        relevant=bool(data.get("relevant", False)),
        sentiment=sentiment,
        confidence=confidence,
        reason=str(data.get("reason", "")),
        provider=provider,
    )


# ==============================================================
#  PROVIDER: Google Gemini
# ==============================================================
def _call_gemini(headline: str, summary: str) -> AIAnalysis:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Headline: {headline}\n\nRingkasan: {summary}"}],
            }
        ],
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
def _call_groq(headline: str, summary: str) -> AIAnalysis:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Headline: {headline}\n\nRingkasan: {summary}"},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=config.AI_REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return _parse_ai_json(raw_text, "groq")


# ==============================================================
#  REGISTRY — tambah provider baru di sini
# ==============================================================
PROVIDERS = {
    "gemini": _call_gemini,
    "groq": _call_groq,
}


def analyze_news(headline: str, summary: str = "") -> AIAnalysis:
    """Fungsi utama dipanggil news_engine.py. Selalu return AIAnalysis,
    tidak pernah raise exception ke pemanggil — kegagalan apa pun
    di-handle jadi fallback netral."""
    if not config.USE_AI_NEWS_ANALYST or config.AI_PROVIDER == "none":
        return _neutral_fallback(config.AI_PROVIDER, "AI News Analyst dimatikan di config")

    provider_fn = PROVIDERS.get(config.AI_PROVIDER)
    if provider_fn is None:
        return _neutral_fallback(config.AI_PROVIDER, f"Provider '{config.AI_PROVIDER}' tidak dikenal")

    # cek API key sudah diisi sebelum mencoba call
    key_map = {"gemini": config.GEMINI_API_KEY, "groq": config.GROQ_API_KEY}
    api_key = key_map.get(config.AI_PROVIDER, "")
    if not api_key or api_key.startswith("ISI_"):
        return _neutral_fallback(config.AI_PROVIDER, f"API key untuk {config.AI_PROVIDER} belum diisi di config.py")

    try:
        return provider_fn(headline, summary)
    except requests.RequestException as e:
        return _neutral_fallback(config.AI_PROVIDER, f"Request gagal: {e}")
    except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        return _neutral_fallback(config.AI_PROVIDER, f"Gagal parse respons AI: {e}")
    except Exception as e:
        return _neutral_fallback(config.AI_PROVIDER, f"Error tak terduga: {e}")
