"""
db.py — GamerGuard
تحسينات:
  - connection pool دائم بدل فتح connection جديد بكل استدعاء
  - guild config cache (TTL 60 ثانية) لتفادي ضغط SQLite بكل رسالة
  - دعم translate_enabled و translate_voice في get_guild_config
  - invalidate_guild_cache() لمسح الكاش عند حفظ الإعدادات
"""

import aiosqlite, os, time, asyncio
from typing import Any

PATH = os.getenv("DB_PATH", "data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS flags(id INTEGER PRIMARY KEY, guild INT, user INT, channel INT, snippet TEXT, score REAL, reason TEXT, action TEXT, fp INT DEFAULT 0, ts INT);
CREATE TABLE IF NOT EXISTS ratings(guild INT, rater INT, target INT, stars INT, ts INT);
CREATE TABLE IF NOT EXISTS reports(guild INT, reporter INT, target INT, reason TEXT, ts INT);
CREATE TABLE IF NOT EXISTS lfg(guild INT, user INT, game TEXT, slot TEXT, ts INT);
CREATE TABLE IF NOT EXISTS settings(guild INT PRIMARY KEY, mod_channel INT);
CREATE TABLE IF NOT EXISTS report_done(rid INTEGER PRIMARY KEY, ts INT);
CREATE TABLE IF NOT EXISTS dash_users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pw TEXT, role TEXT, active INT DEFAULT 1, must_change INT DEFAULT 0, sv INT DEFAULT 0, created INT, last_login INT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts INT, actor TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, guild INT, user INT, author TEXT, text TEXT, ts INT);
CREATE TABLE IF NOT EXISTS guild_config(guild INT PRIMARY KEY, mod_low REAL DEFAULT 0.3, mod_high REAL DEFAULT 0.85, seed_words TEXT DEFAULT '', retention_days INT DEFAULT 30, translate_enabled INT DEFAULT 1, translate_voice INT DEFAULT 1, updated INT);
CREATE TABLE IF NOT EXISTS guild_games(guild INT, game_id TEXT, PRIMARY KEY(guild, game_id));
CREATE TABLE IF NOT EXISTS guild_lfg_settings(guild INT PRIMARY KEY, lfg_channel INT, vc_category INT);
CREATE TABLE IF NOT EXISTS lfg_posts(id INTEGER PRIMARY KEY, guild INT, channel INT, message INT, host INT, game_id TEXT, needed INT, joined TEXT DEFAULT '', filters TEXT DEFAULT '{}', ts INT, done INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_langs(guild INT, user INT, lang TEXT, ts INT, PRIMARY KEY(guild, user));
"""

# ════════════════════════════════════════════════════════════════
#  Connection Pool
# ════════════════════════════════════════════════════════════════
_pool: list[aiosqlite.Connection] = []
_pool_lock = asyncio.Lock()
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))


async def _acquire() -> aiosqlite.Connection:
    """اسحب connection من الـ pool، أو افتح واحد جديد."""
    async with _pool_lock:
        if _pool:
            return _pool.pop()
    con = await aiosqlite.connect(PATH)
    con.row_factory = aiosqlite.Row
    await con.execute("PRAGMA journal_mode=WAL")
    await con.execute("PRAGMA synchronous=NORMAL")
    await con.execute("PRAGMA foreign_keys=ON")
    return con


async def _release(con: aiosqlite.Connection):
    """أرجع الـ connection للـ pool أو أغلقه لو ممتلئ."""
    async with _pool_lock:
        if len(_pool) < POOL_SIZE:
            _pool.append(con)
            return
    await con.close()


async def q(sql: str, args=(), one=False, commit=False) -> Any:
    """نفّذ استعلام وأرجع النتيجة."""
    con = await _acquire()
    try:
        cur = await con.execute(sql, args)
        if commit:
            await con.commit()
            return cur.lastrowid
        rows = await cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        await _release(con)


# ════════════════════════════════════════════════════════════════
#  Guild Config Cache
# ════════════════════════════════════════════════════════════════
_guild_cfg_cache: dict[int, tuple[dict, float]] = {}
_GUILD_CFG_TTL = 60.0  # ثانية


def invalidate_guild_cache(guild_id: int):
    """امسح الكاش عند تغيير الإعدادات من الداش."""
    _guild_cfg_cache.pop(guild_id, None)


async def get_guild_config(guild_id: int) -> dict:
    """إعدادات الإشراف + الترجمة للسيرفر — مكاشة 60 ثانية."""
    now = time.monotonic()
    cached = _guild_cfg_cache.get(guild_id)
    if cached and now - cached[1] < _GUILD_CFG_TTL:
        return cached[0]

    row = await q("SELECT * FROM guild_config WHERE guild=?", (guild_id,), one=True)
    if row:
        cfg = {
            "mod_low":           row["mod_low"],
            "mod_high":          row["mod_high"],
            "seed_words":        row["seed_words"] or "",
            "retention_days":    row["retention_days"],
            "translate_enabled": bool(row["translate_enabled"]) if "translate_enabled" in row.keys() else True,
            "translate_voice":   bool(row["translate_voice"])   if "translate_voice"   in row.keys() else True,
        }
    else:
        cfg = {
            "mod_low":           float(os.getenv("MOD_LOW",          "0.3")),
            "mod_high":          float(os.getenv("MOD_HIGH",         "0.85")),
            "seed_words":        "",
            "retention_days":    int(os.getenv("RETENTION_DAYS",     "30")),
            "translate_enabled": True,
            "translate_voice":   True,
        }

    _guild_cfg_cache[guild_id] = (cfg, now)
    return cfg


async def set_guild_config(guild_id: int, mod_low: float, mod_high: float,
                           seed_words: str, retention_days: int,
                           translate_enabled: int | None = None,
                           translate_voice: int | None = None):
    """احفظ إعدادات السيرفر وامسح الكاش."""
    # اقرأ القيم الحالية لو لم تُمرَّر translate flags
    current = await get_guild_config(guild_id)
    te = translate_enabled if translate_enabled is not None else int(current["translate_enabled"])
    tv = translate_voice   if translate_voice   is not None else int(current["translate_voice"])

    await q(
        "INSERT INTO guild_config(guild,mod_low,mod_high,seed_words,retention_days,translate_enabled,translate_voice,updated) "
        "VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(guild) DO UPDATE SET "
        "mod_low=excluded.mod_low, mod_high=excluded.mod_high, "
        "seed_words=excluded.seed_words, retention_days=excluded.retention_days, "
        "translate_enabled=excluded.translate_enabled, translate_voice=excluded.translate_voice, "
        "updated=excluded.updated",
        (guild_id, mod_low, mod_high, seed_words, retention_days, te, tv, int(time.time())),
        commit=True,
    )
    invalidate_guild_cache(guild_id)


async def get_guild_games(guild_id: int) -> list[str]:
    rows = await q("SELECT game_id FROM guild_games WHERE guild=?", (guild_id,))
    return [r["game_id"] for r in rows]


async def set_guild_games(guild_id: int, game_ids: list):
    con = await _acquire()
    try:
        await con.execute("DELETE FROM guild_games WHERE guild=?", (guild_id,))
        await con.executemany("INSERT INTO guild_games VALUES(?,?)",
                              [(guild_id, g) for g in game_ids])
        await con.commit()
    finally:
        await _release(con)


async def get_lfg_settings(guild_id: int):
    return await q("SELECT * FROM guild_lfg_settings WHERE guild=?", (guild_id,), one=True)


async def set_lfg_settings(guild_id: int, lfg_channel, vc_category):
    await q(
        "INSERT INTO guild_lfg_settings(guild,lfg_channel,vc_category) VALUES(?,?,?) "
        "ON CONFLICT(guild) DO UPDATE SET lfg_channel=excluded.lfg_channel, vc_category=excluded.vc_category",
        (guild_id, lfg_channel, vc_category), commit=True,
    )


async def init():
    """أنشئ الجداول وشغّل migrations بسيطة."""
    con = await _acquire()
    try:
        await con.executescript(SCHEMA)
        # migrations للـ DB القديمة
        for migration in [
            "ALTER TABLE lfg_posts ADD COLUMN filters TEXT DEFAULT '{}'",
            "ALTER TABLE guild_config ADD COLUMN translate_enabled INT DEFAULT 1",
            "ALTER TABLE guild_config ADD COLUMN translate_voice INT DEFAULT 1",
        ]:
            try:
                await con.execute(migration)
            except Exception:
                pass
        await con.commit()
    finally:
        await _release(con)


async def purge(days: int):
    await q("DELETE FROM flags WHERE ts<?",
            (int(time.time()) - days * 86400,), commit=True)


async def reputation(guild: int, user: int) -> tuple:
    """سمعة 0-100 بناءً على التقييمات والإنذارات والبلاغات (30 يوم)."""
    d30 = int(time.time()) - 30 * 86400
    r  = await q("SELECT AVG(stars) a, COUNT(*) n FROM ratings WHERE guild=? AND target=?",
                 (guild, user), one=True)
    f  = (await q("SELECT COUNT(*) c FROM flags WHERE guild=? AND user=? AND fp=0 AND ts>?",
                  (guild, user, d30), one=True))["c"]
    rp = (await q("SELECT COUNT(*) c FROM reports WHERE guild=? AND target=? AND ts>?",
                  (guild, user, d30), one=True))["c"]
    s = 50 + ((r["a"] - 3) * 15 if r["n"] else 0) - 8 * f - 3 * rp
    return max(0, min(100, round(s))), r["n"], f, rp