"""
db_migration.py — يضيف الجداول الجديدة للـ DB الموجودة
"""
import aiosqlite, os

PATH = os.getenv("DB_PATH", "data.db")

NEW_TABLES = """
-- جدول لغات اللاعبين
CREATE TABLE IF NOT EXISTS user_langs(
    guild INT,
    user  INT,
    lang  TEXT,
    ts    INT,
    PRIMARY KEY(guild, user)
);

-- عمود لتفعيل/تعطيل الترجمة لكل سيرفر
-- يُضاف لـ guild_config الموجودة
"""

async def migrate():
    async with aiosqlite.connect(PATH) as con:
        await con.executescript(NEW_TABLES)
        # أضف عمود translate_enabled لـ guild_config لو ما موجود
        try:
            await con.execute("ALTER TABLE guild_config ADD COLUMN translate_enabled INT DEFAULT 1")
        except Exception:
            pass
        # أضف عمود translate_voice لو ما موجود
        try:
            await con.execute("ALTER TABLE guild_config ADD COLUMN translate_voice INT DEFAULT 1")
        except Exception:
            pass
        await con.commit()
    print("✅ DB migration done")

if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate())