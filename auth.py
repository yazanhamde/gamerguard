import os, re, time, hmac, hashlib, secrets
import db

ITER = 240_000
USERNAME_RE = re.compile(r"[a-z0-9_.-]{3,24}")
DEFAULT_PW = "غيّرها"


def hash_pw(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return "pbkdf2$%d$%s$%s" % (ITER, salt.hex(), h.hex())


def check_pw(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


DUMMY = hash_pw("dummy")  # للمقارنة الوهمية عند اسم مستخدم غير موجود (يمنع كشف الأسماء بالتوقيت)


def temp_password() -> str:
    return secrets.token_urlsafe(9)


async def get_user(uid):
    return await db.q("SELECT * FROM dash_users WHERE id=?", (uid,), one=True)


async def by_name(name):
    return await db.q("SELECT * FROM dash_users WHERE username=?", ((name or "").strip().lower(),), one=True)


async def audit(actor, action, detail=""):
    await db.q("INSERT INTO audit(ts,actor,action,detail) VALUES(?,?,?,?)",
               (int(time.time()), actor, action, detail[:300]), commit=True)


async def bootstrap():
    """أول تشغيل: ينشئ حساب المدير 'admin' من DASH_PASSWORD (أو كلمة مؤقتة تظهر في الكونسول)."""
    if (await db.q("SELECT COUNT(*) c FROM dash_users", one=True))["c"]:
        return
    pw = os.getenv("DASH_PASSWORD") or ""
    weak = (not pw) or pw == DEFAULT_PW or len(pw) < 8
    shown = None
    if not pw:
        pw = shown = temp_password()
    from asyncio import to_thread
    h = await to_thread(hash_pw, pw)
    await db.q("INSERT INTO dash_users(username,pw,role,active,must_change,created) VALUES('admin',?,'admin',1,?,?)",
               (h, 1 if weak else 0, int(time.time())), commit=True)
    await audit("system", "bootstrap", "تم إنشاء حساب المدير الأول")
    print("لوحة المشرفين: تم إنشاء المدير الأول. المستخدم: admin" + (" | كلمة السر المؤقتة: " + shown if shown else ""))