"""
translation.py — GamerGuard
تحسينات:
  - يستخدم db.get_guild_config المُكاشة بدل استعلام منفصل لكل رسالة
  - logging بدل print
  - تحسين should_translate: تتجاهل المنشنز والايموجي والأرقام فقط
  - max_tokens مضبوط بدقة لتوفير التكاليف
"""

import os, io, json, logging, time
from openai import AsyncOpenAI

log   = logging.getLogger("gg.tr")
ai    = AsyncOpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYS_DETECT_TRANSLATE = (
    "You are a translation assistant for a gaming Discord server.\n"
    "Given a message, detect its language and translate it to Arabic (ar) and English (en).\n"
    "Always respond with valid JSON only, no markdown, no explanation.\n"
    'Format: {"detected_lang":"ISO-639-1 code","lang_name_ar":"اسم اللغة بالعربي",'
    '"ar":"النص بالعربي","en":"text in English","is_english":true/false,"is_arabic":true/false}\n'
    "If the message is already in Arabic, set is_arabic: true and ar to the original.\n"
    "If already in English, set is_english: true and en to the original.\n"
    "Keep gaming terms (rank names, game names) untranslated."
)

SYS_VOICE_TRANSLATE = (
    "You are a translation assistant. Translate the given text to both Arabic and English.\n"
    'Respond with valid JSON only: {"ar":"...","en":"..."}\n'
    "Keep gaming terms untranslated."
)

SUPPORTED_LANGS = {
    "ar": "العربية",  "en": "English",    "fr": "Français",
    "es": "Español",  "de": "Deutsch",    "tr": "Türkçe",
    "pt": "Português","ru": "Русский",     "ja": "日本語",
    "ko": "한국어",    "zh": "中文",        "it": "Italiano",
    "id": "Bahasa Indonesia", "hi": "हिन्दी", "nl": "Nederlands",
}


async def detect_and_translate(text: str) -> dict | None:
    """يكشف لغة الرسالة ويترجمها للعربي والإنجليزي."""
    if len(text.strip()) < 3:
        return None
    try:
        resp = await ai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYS_DETECT_TRANSLATE},
                {"role": "user",   "content": text[:1000]},
            ],
            temperature=0,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError as e:
        log.warning("translate JSON error: %s", e)
        return None
    except Exception as e:
        log.warning("translate error: %s", e)
        return None


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str | None:
    """يحوّل صوت → نص باستخدام Whisper."""
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        resp = await ai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return resp.text
    except Exception as e:
        log.warning("whisper error: %s", e)
        return None


async def translate_text(text: str) -> dict | None:
    """يترجم نص لعربي وإنجليزي."""
    try:
        resp = await ai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYS_VOICE_TRANSLATE},
                {"role": "user",   "content": text[:1000]},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning("translate_text error: %s", e)
        return None


def is_arabic(text: str) -> bool:
    """فحص سريع: هل النص عربي بشكل رئيسي؟"""
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    return arabic / max(len(text), 1) > 0.4


def should_translate(text: str) -> bool:
    """
    هل الرسالة تستحق الترجمة؟
    نتجاهل:
    - النص العربي الخالص
    - الرسائل القصيرة جداً (< 4 أحرف حقيقية)
    - الأوامر والروابط
    - الرسائل اللي ما فيها أحرف (إيموجي، أرقام، منشن فقط)
    """
    clean = text.strip()
    if len(clean) < 3:
        return False
    if clean.startswith(('/', '!', 'http://', 'https://')):
        return False
    # أزل المنشنز والإيموجي والرولز من الفحص
    import re
    stripped = re.sub(r"<[^>]+>|[\U00010000-\U0010ffff]|\d+", "", clean).strip()
    if len(stripped) < 4:
        return False
    if is_arabic(clean):
        return False
    return True


async def get_guild_translate_enabled(guild_id: int) -> bool:
    """هل الترجمة النصية مفعّلة للسيرفر؟ — يستخدم الكاش من db."""
    import db as _db
    try:
        cfg = await _db.get_guild_config(guild_id)
        return cfg.get("translate_enabled", True)
    except Exception:
        return True


async def get_guild_voice_enabled(guild_id: int) -> bool:
    """هل ترجمة الصوت مفعّلة للسيرفر؟ — يستخدم الكاش من db."""
    import db as _db
    try:
        cfg = await _db.get_guild_config(guild_id)
        return cfg.get("translate_voice", True)
    except Exception:
        return True


async def set_user_lang(guild_id: int, user_id: int, lang: str):
    """احفظ لغة اللاعب المفضلة."""
    import db as _db
    await _db.q(
        "INSERT INTO user_langs(guild, user, lang, ts) VALUES(?,?,?,?) "
        "ON CONFLICT(guild, user) DO UPDATE SET lang=excluded.lang, ts=excluded.ts",
        (guild_id, user_id, lang, int(time.time())), commit=True,
    )


async def get_user_lang(guild_id: int, user_id: int) -> str | None:
    import db as _db
    try:
        row = await _db.q(
            "SELECT lang FROM user_langs WHERE guild=? AND user=?",
            (guild_id, user_id), one=True,
        )
        return row["lang"] if row else None
    except Exception:
        return None