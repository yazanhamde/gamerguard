"""
moderation.py — GamerGuard
تحسينات:
  - كاش للـ seed pattern لكل سيرفر بدل إعادة compile بكل رسالة
  - logging بدل print
  - حماية من الاستثناءات في JSON parsing
"""

import os, re, json, logging
from openai import AsyncOpenAI

log = logging.getLogger("gg.mod")
ai  = AsyncOpenAI()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LOW  = float(os.getenv("MOD_LOW",  "0.3"))
HIGH = float(os.getenv("MOD_HIGH", "0.85"))

_DEFAULT_SEED = (
    r"كلب|حمار|حيوان|غبي|ابن ال|يلعن|عرص|شرموط|منيك|كس ام"
    r"|ya kalb|sharmou|ibn el|kos om"
)
SEED = re.compile(_DEFAULT_SEED, re.I)

SYS = (
    "You moderate Discord chats of Arabic-speaking gamers "
    "(Levantine, Gulf, Egyptian dialects, Arabizi).\n"
    "Judge the LAST message using the context. "
    "Friendly trash-talk between friends that is not hateful or threatening = \"banter\".\n"
    "Insults aimed at someone who seems upset, slurs, sectarian/racial hate, "
    "sexual harassment, threats = \"abuse\". Else \"ok\".\n"
    "Reply JSON only: {\"verdict\":\"ok|banter|abuse\",\"reason\":\"<short Arabic reason>\"}"
)

# كاش لـ compiled seed patterns لكل سيرفر
_seed_cache: dict[str, re.Pattern] = {}


def _get_seed(extra_words: str) -> re.Pattern:
    """احصل على compiled pattern للكلمات — مع كاش بالـ words string كـ key."""
    if extra_words in _seed_cache:
        return _seed_cache[extra_words]
    parts = [_DEFAULT_SEED]
    for w in extra_words.split("\n"):
        w = w.strip()
        if w:
            parts.append(re.escape(w))
    pattern = re.compile("|".join(parts), re.I)
    _seed_cache[extra_words] = pattern
    return pattern


def normalize(t: str) -> str:
    t = re.sub(r"[\u064B-\u0652\u0640]", "", t)
    t = re.sub("[إأآ]", "ا", t).replace("ى", "ي")
    return re.sub(r"(.)\1{2,}", r"\1\1", t).strip()


async def analyze(text: str, context=(), cfg=None) -> dict:
    low   = float(cfg["mod_low"])   if cfg else LOW
    high  = float(cfg["mod_high"])  if cfg else HIGH
    seed  = _get_seed(cfg["seed_words"]) if cfg and cfg.get("seed_words") else SEED

    t = normalize(text)
    if len(t) < 3:
        return {"verdict": "ok", "score": 0, "reason": ""}

    try:
        res = (await ai.moderations.create(
            model="omni-moderation-latest", input=t
        )).results[0]
    except Exception as e:
        log.warning("moderation API error: %s", e)
        return {"verdict": "ok", "score": 0, "reason": ""}

    sc    = res.category_scores.model_dump()
    score = max((v or 0) for k, v in sc.items()
                if k.startswith(("harassment", "hate")))

    if score < low and not seed.search(t):
        return {"verdict": "ok", "score": score, "reason": ""}

    if score >= high:
        return {"verdict": "abuse", "score": score, "reason": "إساءة واضحة"}

    msgs = [
        {"role": "system", "content": SYS},
        {"role": "user",   "content": "Context:\n" + "\n".join(context) + "\nLAST: " + t},
    ]
    try:
        c = await ai.chat.completions.create(
            model=MODEL, messages=msgs, temperature=0,
            response_format={"type": "json_object"},
            max_tokens=80,
        )
        j = json.loads(c.choices[0].message.content)
    except json.JSONDecodeError as e:
        log.warning("moderation JSON parse error: %s", e)
        j = {}
    except Exception as e:
        log.warning("moderation GPT error: %s", e)
        j = {}

    v = j.get("verdict")
    return {
        "verdict": v if v in ("ok", "banter", "abuse") else "ok",
        "score":   score,
        "reason":  j.get("reason", ""),
    }