import os, re, html, time, hmac, secrets, asyncio, collections
from games import GAMES, CATEGORIES
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
import db, auth

CSS = """
:root{color-scheme:dark;--bg:#0b0e17;--s1:#121726;--s2:#181e30;--bd:#232b42;--fg:#e8ebf5;--mut:#8b94ab;--ac:#5766ee;--acl:#a3adff;--bad:#ff6b6b;--ok:#3ecf8e;--wn:#f0b429}
[data-theme=light]{color-scheme:light;--bg:#f2f4f9;--s1:#fff;--s2:#f6f7fb;--bd:#e1e5ef;--fg:#141a2b;--mut:#5f6a82;--ac:#4452d8;--acl:#3b49c9;--bad:#c2332f;--ok:#13805a;--wn:#a86a00}
*{box-sizing:border-box}html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 'IBM Plex Sans Arabic',Tahoma,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--acl)}h1,h2{font-weight:600}h2{font-size:1.02rem;margin:2em 0 .6em}
.ic{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}
.app{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}
.sb{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:18px;padding:18px 14px;background:var(--s1);border-inline-end:1px solid var(--bd);overflow-y:auto}
.bd{display:flex;align-items:center;gap:11px;padding:2px 6px}.bd .mk{width:36px;height:36px;border-radius:10px;background:var(--ac);color:#fff;display:grid;place-items:center}
.bd .mk .ic{width:20px;height:20px}.bd b{display:block;line-height:1.25}.bd small{color:var(--mut);font-size:.8rem}
.nav,.gl{display:flex;flex-direction:column;gap:2px}.gl{padding-bottom:14px;border-bottom:1px solid var(--bd)}
.nav a,.gl a{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;color:var(--mut);text-decoration:none;transition:background .12s,color .12s}
.nav a:hover,.gl a:hover{background:var(--s2);color:var(--fg)}
.nav a.on,.gl a.on{background:color-mix(in srgb,var(--ac) 20%,transparent);color:var(--fg);box-shadow:inset -2px 0 0 var(--acl)}
.gl a{padding:6px 10px;font-size:.9rem}
.nav .badge{margin-inline-start:auto}.badge{background:var(--bad);color:#0b0e17;border-radius:99px;padding:0 8px;font-size:.75rem;font-weight:600;line-height:1.6}
.ft{margin-top:auto;display:flex;flex-direction:column;gap:10px}
.ub{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid var(--bd);border-radius:11px;background:var(--s2)}
.av{width:34px;height:34px;border-radius:50%;background:color-mix(in srgb,var(--ac) 30%,transparent);color:var(--acl);display:grid;place-items:center;font-weight:600;flex:none}
.un{display:flex;flex-direction:column;line-height:1.35;min-width:0}.un a{color:var(--fg);text-decoration:none;font-weight:500;overflow:hidden;text-overflow:ellipsis}.un .chip{align-self:flex-start;margin-top:2px}
.fb{display:flex;gap:8px}.fb form{margin:0;flex:1}.fb .ib{width:100%}
.mn{padding:28px 34px 64px;max-width:1180px;width:100%}.pg h1{font-size:1.6rem;margin:0;line-height:1.3}.pg .sub{color:var(--mut);margin:2px 0 20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--bd);border:1px solid var(--bd);border-radius:12px;overflow:hidden;margin:14px 0}
.s{background:var(--s1);padding:14px 18px}.s b{display:block;font-size:1.75rem;line-height:1.25;font-weight:600;font-variant-numeric:tabular-nums}.s b small{font-size:.9rem;color:var(--mut);font-weight:400}.s span{color:var(--mut);font-size:.84rem}
.t{background:var(--s1);border:1px solid var(--bd);border-radius:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:640px}th,td{padding:11px 14px;text-align:start;border-bottom:1px solid var(--bd);vertical-align:top}
tr:last-child td{border-bottom:0}th{color:var(--mut);font-weight:500;font-size:.8rem;background:var(--s2)}tr:hover td{background:color-mix(in srgb,var(--s2) 70%,transparent)}
tr.fpr td{opacity:.42;text-decoration:line-through}tr.fpr td:last-child{opacity:1;text-decoration:none}td a:not(.btn){text-decoration:none;font-weight:500}td a:not(.btn):hover{text-decoration:underline}tr.dn td{opacity:.5}.sn{max-width:340px;word-break:break-word}.mut{color:var(--mut);font-size:.88rem}.bad{color:var(--bad)}
button{font:inherit;font-weight:500;cursor:pointer;border:0;border-radius:9px;padding:9px 16px;background:var(--ac);color:#fff;transition:filter .12s,background .12s}button:hover{filter:brightness(1.12)}
button.wide{width:100%;margin-top:14px;padding:11px}
button.g,a.btn{display:inline-block;background:transparent;color:var(--acl);border:1px solid var(--bd);padding:3px 11px;font-size:.88rem;border-radius:8px;text-decoration:none;font-weight:400}
button.g:hover,a.btn:hover{background:var(--s2);filter:none}button.g.red{color:var(--bad)}
.ib{display:inline-flex;align-items:center;justify-content:center;gap:8px;background:var(--s2);color:var(--fg);border:1px solid var(--bd);padding:7px 11px;font-size:.88rem;font-weight:400}
.ib .i-moon{display:none}[data-theme=light] .ib .i-sun{display:none}[data-theme=light] .ib .i-moon{display:inline}
form.i{display:inline;margin:0}
input,select,textarea{font:inherit;color:var(--fg);background:var(--s2);border:1px solid var(--bd);border-radius:9px;padding:10px 12px;width:100%;margin:6px 0;transition:border-color .12s}
textarea{min-height:76px;resize:vertical}input:focus,select:focus,textarea:focus{border-color:var(--acl)}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,a:focus-visible{outline:2px solid var(--acl);outline-offset:2px}
label{display:block;color:var(--mut);font-size:.85rem;margin-top:8px}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.row>div{flex:1 1 180px}
.chip{display:inline-block;padding:0 10px;border-radius:99px;font-size:.78rem;line-height:1.7;border:1px solid var(--bd);color:var(--mut);white-space:nowrap}
.chip.bad{color:var(--bad);background:color-mix(in srgb,var(--bad) 13%,transparent);border-color:color-mix(in srgb,var(--bad) 40%,transparent)}
.chip.good{color:var(--ok);background:color-mix(in srgb,var(--ok) 13%,transparent);border-color:color-mix(in srgb,var(--ok) 40%,transparent)}
.chip.warn{color:var(--wn);background:color-mix(in srgb,var(--wn) 13%,transparent);border-color:color-mix(in srgb,var(--wn) 40%,transparent)}
.chip.ac{color:var(--acl);background:color-mix(in srgb,var(--ac) 16%,transparent);border-color:color-mix(in srgb,var(--ac) 40%,transparent)}
.box{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:14px 18px;margin:12px 0}.box.okb{border-color:var(--ok)}.box.badb{border-color:var(--bad)}
code{background:var(--s2);border:1px solid var(--bd);border-radius:6px;padding:2px 9px;font-size:1rem;user-select:all}
.nh{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:4px}.back{display:inline-block;color:var(--mut);text-decoration:none;font-size:.9rem;margin-bottom:6px}.back:hover{color:var(--fg)}
.ph{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:6px 0 4px}.ph h1{margin:0;font-size:1.7rem}.verdict{font-size:.95rem;padding:2px 14px}
.solo{max-width:420px;margin:18vh auto;padding:0 20px;text-align:center}
.auth{display:grid;grid-template-columns:minmax(380px,500px) 1fr;min-height:100vh}
.af{position:relative;display:flex;flex-direction:column;justify-content:center;padding:40px 52px;background:var(--s1);border-inline-end:1px solid var(--bd)}
.af form{width:100%;max-width:340px;margin:0 auto}.af .bd{padding:0;margin-bottom:34px}.af h1{font-size:1.5rem;margin:0 0 14px}.af .tg{position:absolute;top:18px;inset-inline-end:18px}
.alert{background:color-mix(in srgb,var(--bad) 13%,transparent);border:1px solid color-mix(in srgb,var(--bad) 45%,transparent);color:var(--bad);border-radius:9px;padding:9px 12px;margin:4px 0 8px;font-size:.9rem}
.art{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:16px;padding:56px 48px}.art>*{width:100%;max-width:470px}.art h2{font-size:1.7rem;line-height:1.45;margin:0}.art>p{margin:0 0 14px}
.chat{display:flex;flex-direction:column;gap:12px;max-width:470px}.msg{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:12px 16px}
.msg.flag{border-color:color-mix(in srgb,var(--bad) 50%,var(--bd))}.msg .who{color:var(--mut);font-size:.82rem}.msg .tx{margin:1px 0 9px}.msg .vd{display:flex;align-items:center;gap:10px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.stats .s:last-child:nth-child(odd){grid-column:1/-1}.app{display:block}.sb{position:static;height:auto;border-inline-end:0;border-bottom:1px solid var(--bd)}.nav{flex-direction:row;flex-wrap:wrap}.ft{margin-top:0}.mn{padding:20px 16px 48px}
.auth{display:block}.art{display:none}.af{min-height:100vh;border:0;padding:32px 22px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""
H = lambda s: html.escape(str(s))
ROLE = {"admin": "مدير", "mod": "مشرف"}
ACTIONS = {
    "login": "تسجيل دخول", "login_failed": "محاولة دخول فاشلة", "logout": "تسجيل خروج", "bootstrap": "إنشاء المدير الأول",
    "flag_fp": "تعليم إنذار كاذب", "flag_restore": "استرجاع إنذار", "report_done": "إغلاق بلاغ", "report_reopen": "إعادة فتح بلاغ",
    "note_add": "إضافة ملاحظة", "note_del": "حذف ملاحظة", "pw_change": "تغيير كلمة السر",
    "user_add": "إنشاء مستخدم", "user_toggle": "تفعيل/تعطيل مستخدم", "user_reset": "إعادة تعيين كلمة سر",
    "user_role": "تغيير صلاحية", "user_delete": "حذف مستخدم",
    "settings_save": "حفظ إعدادات السيرفر",
    "translate_save": "حفظ إعدادات الترجمة",
    "games_save":    "حفظ إعدادات الألعاب",
}


ICONS = {
    "flag": '<path d="M5 21V4m0 0h11l-2 4 2 4H5"/>',
    "alert": '<path d="M12 3.5 2.8 19.5h18.4L12 3.5z"/><path d="M12 10v4M12 17v.01"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c.5-3.5 3-5.5 6-5.5s5.5 2 6 5.5"/><circle cx="17" cy="9" r="2.4"/><path d="M17.5 14.6c2 .3 3.2 1.9 3.5 4.4"/>',
    "log": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3v3h6V3M9 12h6M9 16h4"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    "out": '<path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9"/>',
    "shield": '<path d="M12 2.5 4 5.5v6c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10v-6l-8-3z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "translate": '<path d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"/>',
    "gamepad":  '<path d="M6 11h4M8 9v4M15 12h.01M18 10h.01"/><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.544-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z"/>',
}


def ico(n, cls="ic"):
    return "<svg class='%s i-%s' viewBox='0 0 24 24' aria-hidden=true>%s</svg>" % (cls, n, ICONS[n])


THEME_BTN = ("<button type=button class='ib %s' data-toggle-theme title='تبديل المظهر (داكن / فاتح)'>" + ico("sun") + ico("moon") + "<span>المظهر</span></button>")

THEME_JS = """(function(){var k='gg-theme',d=document.documentElement,t;try{t=localStorage.getItem(k)}catch(e){}
if(t!=='light'&&t!=='dark')t='dark';d.setAttribute('data-theme',t);
document.addEventListener('click',function(e){var b=e.target.closest('[data-toggle-theme]');if(!b)return;
t=d.getAttribute('data-theme')==='dark'?'light':'dark';d.setAttribute('data-theme',t);try{localStorage.setItem(k,t)}catch(x){}});})();
document.addEventListener('DOMContentLoaded',function(){
var a=document.getElementById('gg-sel-all');
var b=document.getElementById('gg-sel-none');
if(a)a.addEventListener('click',function(){document.querySelectorAll('[name=games]').forEach(function(c){c.checked=true;});});
if(b)b.addEventListener('click',function(){document.querySelectorAll('[name=games]').forEach(function(c){c.checked=false;});});
});"""

AUTH_HTML = ("<div class=auth><main class=af>" + (THEME_BTN % "tg") + "<form method=post>"
             "<div class=bd><span class=mk>" + ico("shield") + "</span><div><b>GamerGuard</b><small>لوحة المشرفين</small></div></div>"
             "<h1>تسجيل الدخول</h1>{ERR}"
             "<label for=u>اسم المستخدم</label><input id=u name=username autocomplete=username autofocus required>"
             "<label for=p>كلمة السر</label><input id=p type=password name=pw autocomplete=current-password required>"
             "<button class=wide>تسجيل الدخول</button><p class=mut>الدخول للمشرفين والمدراء فقط.</p></form></main>"
             "<section class=art aria-hidden=true><h2>يفرّق بين المزح بين الأصحاب والإساءة الحقيقية</h2>"
             "<p class=mut>كل إنذار بيوصل لمشرف بشري. ما في حظر تلقائي.</p><div class=chat>"
             "<div class=msg><div class=who>ليث</div><div class=tx>يا كلب وينك؟ يلا ندخل الماتش 😂</div>"
             "<div class=vd><span class='chip good'>مزاح</span><span class=mut>ما صار شي</span></div></div>"
             "<div class='msg flag'><div class=who>ركان</div><div class=tx>اترك اللعبة يا غبي، ما بتفهم شي</div>"
             "<div class=vd><span class='chip bad'>إساءة</span><span class=mut>تحذير خاص للاعب</span></div></div></div></section></div>")


def page(b, title="لوحة المشرفين"):
    return ("<!doctype html><html lang=ar dir=rtl data-theme=dark><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><meta name=color-scheme content='dark light'>"
            "<title>" + H(title) + " | GamerGuard</title><script src=/theme.js></script>"
            "<link href='https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap' rel=stylesheet>"
            "<style>" + CSS + "</style><body>" + b + "</body></html>")


def safe_back(b, default="/"):
    return b if (b and b.startswith("/") and not b.startswith("//") and re.fullmatch(r"[A-Za-z0-9_\-./?=&%]*", b)) else default


def tm(ts):
    return "<bdi dir=ltr>%s</bdi>" % time.strftime("%Y/%m/%d %H:%M", time.localtime(ts)) if ts else "—"


def make_app(bot):
    @asynccontextmanager
    async def lifespan(app):
        await auth.bootstrap()
        yield

    app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=os.environ["SECRET_KEY"], max_age=7 * 86400,
                       same_site="lax", https_only=os.getenv("HTTPS_ONLY") == "1")
    fails = collections.defaultdict(list)

    @app.middleware("http")
    async def sec_headers(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                                   "font-src https://fonts.gstatic.com; frame-ancestors 'none'; form-action 'self'")
        return resp

    # ---------- أدوات مساعدة ----------
    def pick(g):
        return next((x for x in bot.guilds if x.id == g), bot.guilds[0])

    def namer(gu):
        def nm(u):
            m = gu.get_member(u)
            return m.display_name if m else str(u)

        def clean(t):  # <@123> ← @الاسم ثم تهريب HTML
            return H(re.sub(r"<@!?(\d+)>", lambda m: "@" + nm(int(m.group(1))), t))
        return nm, clean

    def gname(gid, uid):
        for x in bot.guilds:
            if x.id == gid:
                m = x.get_member(uid)
                return m.display_name if m else str(uid)
        return str(uid)

    async def me(r):
        uid = r.session.get("uid")
        if not uid:
            return None
        u = await auth.get_user(uid)
        if not u or not u["active"] or u["sv"] != r.session.get("sv"):
            r.session.clear()
            return None
        return u

    def tok(r):
        return "<input type=hidden name=t value='%s'>" % H(r.session.get("csrf", ""))

    def csrf_ok(r, t):
        return bool(t) and hmac.compare_digest(t, r.session.get("csrf", ""))

    def deny(msg, code=403):
        return HTMLResponse(page("<div class=solo><h1>%s</h1><p><a href='/'>العودة للوحة</a></p></div>" % H(msg)), code)

    async def gate(r, admin=False, pending=False):
        u = await me(r)
        if not u:
            return None, RedirectResponse("/login", 303)
        if u["must_change"] and not pending:
            return None, RedirectResponse("/account", 303)
        if admin and u["role"] != "admin":
            return None, deny("ما عندك صلاحية لهالصفحة.")
        return u, None

    async def gatep(r, t, **kw):
        u, bad = await gate(r, **kw)
        if bad:
            return None, bad
        if not csrf_ok(r, t):
            return None, deny("انتهت صلاحية الجلسة أو الطلب غير صالح. حدّث الصفحة وجرّب مرة ثانية.")
        return u, None

    def pform(r, action, label, back, cls="g", extra=""):
        return ("<form class=i method=post action='%s'>%s<input type=hidden name=back value='%s'>%s<button class='%s'>%s</button></form>"
                % (action, tok(r), H(back), extra, cls, label))

    async def layout(r, u, gu, tab, body, head=True):
        gid = gu.id if gu else (bot.guilds[0].id if bot.guilds else 0)
        n = (await db.q("SELECT COUNT(*) c FROM reports WHERE guild=? AND rowid NOT IN (SELECT rid FROM report_done)", (gid,), one=True))["c"] if gid else 0
        badge = "<span class=badge>%d</span>" % n if n else ""
        items = [("f", "/?g=%d" % gid, "الإنذارات", "flag", ""), ("r", "/reports?g=%d" % gid, "البلاغات", "alert", badge)]
        if u["role"] == "admin":
            items += [("u", "/admin/users", "المستخدمون", "users", ""), ("a", "/admin/audit", "سجل النشاط", "log", ""),
                     ("s", "/settings?g=%d" % gid, "الإعدادات", "settings", ""),
                     ("g", "/games?g=%d" % gid,    "الألعاب",   "gamepad",  ""),
                     ("x", "/translate?g=%d" % gid, "الترجمة",  "translate", "")]
        nav = "<nav class=nav>" + "".join("<a class='%s' href='%s'%s>%s<span>%s</span>%s</a>" % (
            "on" if k == tab else "", h, " aria-current=page" if k == tab else "", ico(i), t, b) for k, h, t, i, b in items) + "</nav>"
        gl = ""
        if gu and len(bot.guilds) > 1:
            gl = "<div class=gl>" + "".join("<a class='%s' href='/?g=%d'>%s</a>" % ("on" if x.id == gid else "", x.id, H(x.name)) for x in bot.guilds) + "</div>"
        ft = ("<div class=ft><div class=ub><span class=av>%s</span><div class=un><a href='/account'>%s</a><span class='chip ac'>%s</span></div></div>"
              "<div class=fb>%s<form method=post action=/logout>%s<button class=ib title='تسجيل الخروج'>%s<span>خروج</span></button></form></div></div>"
              % (H(u["username"][:1].upper()), H(u["username"]), ROLE.get(u["role"], u["role"]), THEME_BTN % "", tok(r), ico("out")))
        side = ("<aside class=sb><div class=bd><span class=mk>" + ico("shield") + "</span><div><b>GamerGuard</b><small>لوحة المشرفين</small></div></div>"
                + gl + nav + ft + "</aside>")
        titles = {"f": "الإنذارات", "r": "البلاغات", "u": "المستخدمون", "a": "سجل النشاط", "s": "الإعدادات", "g": "الألعاب", "": "حسابي"}
        subs = {"f": H(gu.name) if gu else "", "r": H(gu.name) if gu else "", "u": "حسابات اللوحة وصلاحياتها",
                "a": "آخر 200 إجراء على اللوحة", "s": H(gu.name) if gu else "إعدادات السيرفر",
                "g": "الألعاب المفعّلة في أمر /lfg", "x": "إعدادات ترجمة الرسائل والصوت", "": ""}
        hd = "<header class=pg><h1>%s</h1><p class=sub>%s</p></header>" % (titles.get(tab, ""), subs.get(tab, "")) if head else ""
        return page("<div class=app>" + side + "<main class=mn>" + hd + body + "</main></div>", titles.get(tab, "") or "لوحة المشرفين")

    # ---------- الدخول والخروج ----------
    @app.get("/theme.js")
    async def theme_js():
        return Response(THEME_JS, media_type="application/javascript")

    @app.get("/login", response_class=HTMLResponse)
    async def login_form(r: Request, err: int = 0):
        if await me(r):
            return RedirectResponse("/", 303)
        msgs = {1: "اسم المستخدم أو كلمة السر غلط.", 2: "محاولات كثيرة. انتظر 10 دقائق ثم جرّب."}
        e = "<div class=alert role=alert>%s</div>" % msgs[err] if err in msgs else ""
        return page(AUTH_HTML.replace("{ERR}", e), "تسجيل الدخول")

    @app.post("/login")
    async def login(r: Request, username: str = Form(""), pw: str = Form("")):
        ip, now = (r.client.host if r.client else "?"), time.time()
        fails[ip] = [t for t in fails[ip] if now - t < 600]
        if len(fails[ip]) >= 5:
            return RedirectResponse("/login?err=2", 303)
        u = await auth.by_name(username)
        good = await asyncio.to_thread(auth.check_pw, pw, u["pw"] if u else auth.DUMMY)
        if not (u and u["active"] and good):
            fails[ip].append(now)
            await auth.audit(username.strip().lower()[:24] or "?", "login_failed", "")
            return RedirectResponse("/login?err=1", 303)
        r.session.clear()
        r.session.update(uid=u["id"], sv=u["sv"], csrf=secrets.token_urlsafe(24))
        await db.q("UPDATE dash_users SET last_login=? WHERE id=?", (int(now), u["id"]), commit=True)
        await auth.audit(u["username"], "login", "")
        return RedirectResponse("/", 303)

    @app.post("/logout")
    async def logout(r: Request):
        u = await me(r)
        if u:
            await auth.audit(u["username"], "logout", "")
        r.session.clear()
        return RedirectResponse("/login", 303)

    # ---------- الإنذارات ----------
    @app.post("/fp/{fid}")
    async def toggle_fp(r: Request, fid: int, t: str = Form(""), back: str = Form("/")):
        u, bad = await gatep(r, t)
        if bad:
            return bad
        f = await db.q("SELECT * FROM flags WHERE id=?", (fid,), one=True)
        if f:
            await db.q("UPDATE flags SET fp=1-fp WHERE id=?", (fid,), commit=True)
            await auth.audit(u["username"], "flag_restore" if f["fp"] else "flag_fp", "إنذار #%d على %s" % (fid, gname(f["guild"], f["user"])))
        return RedirectResponse(safe_back(back), 303)

    @app.get("/", response_class=HTMLResponse)
    async def home(r: Request, g: int = 0):
        u, bad = await gate(r)
        if bad:
            return bad
        if not bot.guilds:
            return await layout(r, u, None, "f", "<h2>البوت مو بأي سيرفر بعد</h2><p>ادعُ البوت لسيرفر ثم حدّث الصفحة.</p>")
        gu = pick(g)
        gid, w = gu.id, int(time.time()) - 7 * 86400
        nm, clean = namer(gu)
        back = "/?g=%d" % gid

        async def count(sql):
            return (await db.q(sql, (gid, w), one=True))["c"]
        fl = await count("SELECT COUNT(*) c FROM flags WHERE guild=? AND ts>?")
        fpn = await count("SELECT COUNT(*) c FROM flags WHERE guild=? AND ts>? AND fp=1")
        rp = await count("SELECT COUNT(*) c FROM reports WHERE guild=? AND ts>?")
        rate = "%d%%" % round(100 * fpn / fl) if fl else "—"

        def row(x):
            act = "تحذير خاص" if x["action"] == "warn" else "تنبيه للمشرفين"
            return ("<tr class='%s'><td>%s</td><td><a href='/player/%d?g=%d'>%s</a></td><td class=sn>%s</td><td>%s</td><td>%s</td><td>%s %s</td></tr>"
                    % ("fpr" if x["fp"] else "", tm(x["ts"]), x["user"], gid, H(nm(x["user"])), clean(x["snippet"]), H(x["reason"]), act,
                       "<a class=btn href='/player/%d?g=%d'>السجل</a>" % (x["user"], gid),
                       pform(r, "/fp/%d" % x["id"], "استرجع" if x["fp"] else "إنذار كاذب", back)))
        rows = await db.q("SELECT * FROM flags WHERE guild=? ORDER BY id DESC LIMIT 50", (gid,))
        body = "".join(row(x) for x in rows) or "<tr><td colspan=6>ما في إنذارات. المجتمع هادي.</td></tr>"
        top = await db.q("SELECT user, COUNT(*) c FROM flags WHERE guild=? AND fp=0 GROUP BY user ORDER BY c DESC LIMIT 5", (gid,))
        tops = "".join("<tr><td><a href='/player/%d?g=%d'>%s</a></td><td>%d</td></tr>" % (x["user"], gid, H(nm(x["user"])), x["c"]) for x in top) or "<tr><td colspan=2>لا أحد حتى الآن.</td></tr>"
        return await layout(r, u, gu, "f",
            "<div class=stats><div class=s><b>%d</b><span>إنذارات (7 أيام)</span></div>"
            "<div class=s><b>%s</b><span>نسبة الإنذارات الكاذبة</span></div>"
            "<div class=s><b>%d</b><span>بلاغات (7 أيام)</span></div></div>" % (fl, rate, rp) +
            "<h2>آخر الإنذارات</h2><div class=t><table><tr><th>الوقت<th>اللاعب<th>المقتطف<th>السبب<th>الإجراء<th></tr>" + body + "</table></div>"
            "<h2>الأكثر إنذارات</h2><div class=t><table><tr><th>اللاعب<th>العدد</tr>" + tops + "</table></div>")

    # ---------- البلاغات ----------
    @app.post("/rp/{rid}")
    async def toggle_report(r: Request, rid: int, t: str = Form(""), back: str = Form("/reports")):
        u, bad = await gatep(r, t)
        if bad:
            return bad
        rep = await db.q("SELECT rowid id, guild, target FROM reports WHERE rowid=?", (rid,), one=True)
        if rep:
            if await db.q("SELECT 1 FROM report_done WHERE rid=?", (rid,), one=True):
                await db.q("DELETE FROM report_done WHERE rid=?", (rid,), commit=True)
                act = "report_reopen"
            else:
                await db.q("INSERT INTO report_done VALUES(?,?)", (rid, int(time.time())), commit=True)
                act = "report_done"
            await auth.audit(u["username"], act, "بلاغ #%d على %s" % (rid, gname(rep["guild"], rep["target"])))
        return RedirectResponse(safe_back(back, "/reports"), 303)

    @app.get("/reports", response_class=HTMLResponse)
    async def reports(r: Request, g: int = 0):
        u, bad = await gate(r)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        gid = gu.id
        nm, clean = namer(gu)
        back = "/reports?g=%d" % gid
        rows = await db.q(
            "SELECT r.rowid id, r.reporter, r.target, r.reason, r.ts, d.rid done, "
            "(SELECT COUNT(*) FROM reports x WHERE x.guild=r.guild AND x.target=r.target) n "
            "FROM reports r LEFT JOIN report_done d ON d.rid=r.rowid WHERE r.guild=? "
            "ORDER BY (d.rid IS NOT NULL), r.rowid DESC LIMIT 100", (gid,))

        def row(x):
            multi = " <span class='chip bad'>%d بلاغات عليه</span>" % x["n"] if x["n"] > 1 else ""
            return ("<tr class='%s'><td>%s</td><td><a href='/player/%d?g=%d'>%s</a>%s</td><td>%s</td><td class=sn>%s</td><td>%s %s</td></tr>"
                    % ("dn" if x["done"] else "", tm(x["ts"]), x["target"], gid, H(nm(x["target"])), multi, H(nm(x["reporter"])), clean(x["reason"]),
                       "<a class=btn href='/player/%d?g=%d'>السجل</a>" % (x["target"], gid),
                       pform(r, "/rp/%d" % x["id"], "استرجع" if x["done"] else "تم الحل", back)))
        body = "".join(row(x) for x in rows) or "<tr><td colspan=5>ما في بلاغات.</td></tr>"
        return await layout(r, u, gu, "r",
            "<div class=t><table><tr><th>الوقت<th>المُبلَّغ عليه<th>المُبلِّغ<th>السبب<th></tr>" + body + "</table></div>")

    # ---------- سجل اللاعب ----------
    @app.get("/player/{uid}", response_class=HTMLResponse)
    async def player(r: Request, uid: int, g: int = 0, ok: int = 0):
        u, bad = await gate(r)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        gid = gu.id
        nm, clean = namer(gu)
        back = "/player/%d?g=%d" % (uid, gid)
        now = int(time.time())
        flags = await db.q("SELECT * FROM flags WHERE guild=? AND user=? ORDER BY ts DESC LIMIT 100", (gid, uid))
        rin = await db.q("SELECT r.rowid id, r.reporter, r.reason, r.ts, d.rid done FROM reports r LEFT JOIN report_done d ON d.rid=r.rowid "
                         "WHERE r.guild=? AND r.target=? ORDER BY r.ts DESC LIMIT 100", (gid, uid))
        rout = (await db.q("SELECT COUNT(*) c FROM reports WHERE guild=? AND reporter=?", (gid, uid), one=True))["c"]
        rat = await db.q("SELECT rater, stars, ts FROM ratings WHERE guild=? AND target=? ORDER BY ts DESC LIMIT 100", (gid, uid))
        notes = await db.q("SELECT * FROM notes WHERE guild=? AND user=? ORDER BY id DESC", (gid, uid))
        score, rn, f30, rp30 = await db.reputation(gid, uid)
        avg = (sum(x["stars"] for x in rat) / len(rat)) if rat else 0
        total_ok = sum(1 for x in flags if not x["fp"])
        fp_n = sum(1 for x in flags if x["fp"])

        if f30 >= 2:
            vt, vc = "نمط متكرر", "bad"
        elif f30 == 1:
            vt, vc = "أول مخالفة حديثة", "warn"
        elif total_ok:
            vt, vc = "مخالفات قديمة فقط", "warn"
        else:
            vt, vc = "سجل نظيف", "good"
        extra = " <span class='chip bad'>%d بلاغات آخر 30 يوم</span>" % rp30 if rp30 >= 3 else ""

        m = gu.get_member(uid)
        if m:
            j, c = getattr(m, "joined_at", None), getattr(m, "created_at", None)
            info = "<p class=mut>انضم للسيرفر: %s | الحساب أُنشئ: %s</p>" % (j.strftime("%Y/%m/%d") if j else "—", c.strftime("%Y/%m/%d") if c else "—")
        else:
            info = "<p class=mut><span class='chip'>مو موجود بالسيرفر حالياً</span></p>"

        ev = []
        for x in flags:
            act = "تحذير خاص" if x["action"] == "warn" else "تنبيه للمشرفين"
            ev.append((x["ts"], "<span class='chip bad'>إنذار</span>",
                       "%s<br><span class=mut>%s — %s</span>" % (clean(x["snippet"]), H(x["reason"]), act),
                       pform(r, "/fp/%d" % x["id"], "استرجع" if x["fp"] else "إنذار كاذب", back), "fpr" if x["fp"] else ""))
        for x in rin:
            ev.append((x["ts"], "<span class='chip warn'>بلاغ</span>", "من %s: %s" % (H(nm(x["reporter"])), clean(x["reason"])),
                       pform(r, "/rp/%d" % x["id"], "استرجع" if x["done"] else "تم الحل", back), "dn" if x["done"] else ""))
        for x in rat:
            ev.append((x["ts"], "<span class=chip>تقييم</span>", "%s: %s" % (H(nm(x["rater"])), "⭐" * x["stars"]), "", ""))
        ev.sort(key=lambda e: -e[0])
        trs = "".join("<tr class='%s'><td>%s</td><td>%s</td><td class=sn>%s</td><td>%s</td></tr>" % (c, tm(ts), k, d, a) for ts, k, d, a, c in ev[:150]) \
            or "<tr><td colspan=4>ما في أي نشاط مسجّل على هالاعب.</td></tr>"

        nl = "".join("<div class=box><div class=nh><span class=mut>%s — %s</span>%s</div>%s</div>" % (
            H(x["author"]), tm(x["ts"]), pform(r, "/note/%d/del" % x["id"], "حذف", back, "g red") if u["role"] == "admin" else "",
            H(x["text"]).replace("\n", "<br>")) for x in notes) \
            or "<p class=mut>ما في ملاحظات. سجّل هون أي سياق مهم للمشرفين الباقيين.</p>"
        retention = os.getenv("RETENTION_DAYS", "30")
        return await layout(r, u, gu, "f",
            "<a class=back href='/?g=%d'>العودة للإنذارات</a>" % gid +
            "<div class=ph><h1>%s</h1><span class='chip verdict %s'>%s</span>%s</div>%s" % (H(nm(uid)), vc, vt, extra, info) +
            "<div class=stats>"
            "<div class=s><b>%d<small>/100</small></b><span>السمعة</span></div>"
            "<div class=s><b>%d</b><span>إنذارات مؤكدة (30 يوم)</span></div>"
            "<div class=s><b>%d</b><span>إنذارات كاذبة</span></div>"
            "<div class=s><b>%d</b><span>بلاغات عليه</span></div>"
            "<div class=s><b>%s</b><span>تقييمات (%d)</span></div>"
            "<div class=s><b>%d</b><span>بلاغات قدّمها</span></div></div>" % (score, f30, fp_n, len(rin), ("%.1f" % avg) if rat else "—", len(rat), rout) +
            "<h2>السجل الزمني</h2><div class=t><table><tr><th>الوقت<th>النوع<th>التفاصيل<th></tr>" + trs + "</table></div>"
            "<p class=mut>الإنذارات بتنحذف تلقائياً بعد %s يوم.</p>" % H(retention) +
            "<h2>ملاحظات المشرفين</h2>" + nl +
            "<form method=post action='/note/%d'>%s<input type=hidden name=g value=%d><input type=hidden name=back value='%s'>"
            "<label>ملاحظة جديدة</label><textarea name=text maxlength=500 required></textarea><button>حفظ الملاحظة</button></form>" % (uid, tok(r), gid, H(back)), head=False)

    @app.post("/note/{uid}")
    async def add_note(r: Request, uid: int, g: int = Form(0), text: str = Form(""), t: str = Form(""), back: str = Form("/")):
        u, bad = await gatep(r, t)
        if bad:
            return bad
        text = text.strip()[:500]
        if text and bot.guilds:
            gid = pick(g).id
            await db.q("INSERT INTO notes(guild,user,author,text,ts) VALUES(?,?,?,?,?)", (gid, uid, u["username"], text, int(time.time())), commit=True)
            await auth.audit(u["username"], "note_add", "ملاحظة على " + gname(gid, uid))
        return RedirectResponse(safe_back(back), 303)

    @app.post("/note/{nid}/del")
    async def del_note(r: Request, nid: int, t: str = Form(""), back: str = Form("/")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        n = await db.q("SELECT * FROM notes WHERE id=?", (nid,), one=True)
        if n:
            await db.q("DELETE FROM notes WHERE id=?", (nid,), commit=True)
            await auth.audit(u["username"], "note_del", "ملاحظة #%d على %s" % (nid, gname(n["guild"], n["user"])))
        return RedirectResponse(safe_back(back), 303)

    # ---------- حسابي ----------
    async def account_page(r, u, msg="", okmsg=""):
        force = "<div class='box badb'>لازم تغيّر كلمة السر قبل ما تكمل.</div>" if u["must_change"] else ""
        m = ("<p class=bad>%s</p>" % H(msg)) if msg else ""
        o = ("<div class='box okb'>%s</div>" % H(okmsg)) if okmsg else ""
        body = (force + o + "<p class=mut>%s — %s</p>" % (H(u["username"]), ROLE.get(u["role"], u["role"])) +
                "<form method=post action=/account class=box style='max-width:420px'>" + tok(r) + m +
                "<label>كلمة السر الحالية</label><input type=password name=cur autocomplete=current-password required>"
                "<label>كلمة السر الجديدة (8 أحرف على الأقل)</label><input type=password name=new autocomplete=new-password required>"
                "<label>تأكيد كلمة السر الجديدة</label><input type=password name=new2 autocomplete=new-password required>"
                "<button>تغيير كلمة السر</button></form>")
        return await layout(r, u, None, "", body)

    @app.get("/account", response_class=HTMLResponse)
    async def account(r: Request):
        u, bad = await gate(r, pending=True)
        if bad:
            return bad
        return await account_page(r, u)

    @app.post("/account", response_class=HTMLResponse)
    async def account_set(r: Request, cur: str = Form(""), new: str = Form(""), new2: str = Form(""), t: str = Form("")):
        u, bad = await gatep(r, t, pending=True)
        if bad:
            return bad
        if not await asyncio.to_thread(auth.check_pw, cur, u["pw"]):
            return await account_page(r, u, "كلمة السر الحالية غلط.")
        if len(new) < 8:
            return await account_page(r, u, "كلمة السر الجديدة قصيرة. لازم 8 أحرف على الأقل.")
        if new != new2:
            return await account_page(r, u, "التأكيد ما بيطابق كلمة السر الجديدة.")
        if new == cur:
            return await account_page(r, u, "اختر كلمة سر مختلفة عن الحالية.")
        h = await asyncio.to_thread(auth.hash_pw, new)
        await db.q("UPDATE dash_users SET pw=?, must_change=0, sv=sv+1 WHERE id=?", (h, u["id"]), commit=True)
        u2 = await auth.get_user(u["id"])
        r.session.update(sv=u2["sv"], csrf=secrets.token_urlsafe(24))
        await auth.audit(u["username"], "pw_change", "")
        if u["must_change"]:
            return RedirectResponse("/", 303)
        return await account_page(r, u2, okmsg="تم تغيير كلمة السر.")

    # ---------- إدارة المستخدمين (للمدير) ----------
    async def other_admins(excl):
        return (await db.q("SELECT COUNT(*) c FROM dash_users WHERE role='admin' AND active=1 AND id<>?", (excl,), one=True))["c"]

    async def users_page(r, u, flash="", err=""):
        rows = await db.q("SELECT * FROM dash_users ORDER BY id")
        back = "/admin/users"

        def row(x):
            self_ = x["id"] == u["id"]
            st = "<span class='chip good'>فعّال</span>" if x["active"] else "<span class='chip bad'>معطّل</span>"
            if self_:
                acts = "<span class=mut>(حسابك)</span>"
            else:
                acts = (pform(r, "/admin/users/%d/toggle" % x["id"], "تعطيل" if x["active"] else "تفعيل", back) + " " +
                        pform(r, "/admin/users/%d/reset" % x["id"], "إعادة تعيين كلمة السر", back) + " " +
                        pform(r, "/admin/users/%d/role" % x["id"], "تحويل لمشرف" if x["role"] == "admin" else "ترقية لمدير", back))
                if not x["active"]:
                    acts += " " + pform(r, "/admin/users/%d/delete" % x["id"], "حذف", back, "g red")
            return ("<tr><td>%s</td><td><span class='chip ac'>%s</span></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (H(x["username"]), ROLE.get(x["role"], x["role"]), st, tm(x["last_login"]), tm(x["created"]), acts))
        f = ("<div class='box okb'>%s</div>" % flash) if flash else ""
        e = ("<div class='box badb'>%s</div>" % H(err)) if err else ""
        body = (f + e + "<div class=t><table><tr><th>المستخدم<th>الصلاحية<th>الحالة<th>آخر دخول<th>أُنشئ<th></tr>" +
                "".join(row(x) for x in rows) + "</table></div>"
                "<h2>إضافة مستخدم</h2><form method=post action=/admin/users/add class=box>" + tok(r) +
                "<div class=row><div><label>اسم المستخدم (إنجليزي صغير وأرقام)</label><input name=username pattern='[A-Za-z0-9_.\\-]{3,24}' required></div>"
                "<div><label>الصلاحية</label><select name=role><option value=mod>مشرف</option><option value=admin>مدير</option></select></div></div>"
                "<button>إنشاء الحساب</button>"
                "<p class=mut>بنولّد كلمة سر مؤقتة وبتظهرلك مرة وحدة. المستخدم لازم يغيّرها عند أول دخول.</p></form>"
                "<p class=mut><b>المدير:</b> كل الصلاحيات + إدارة المستخدمين + سجل النشاط + حذف الملاحظات. "
                "<b>المشرف:</b> الإنذارات والبلاغات وسجل اللاعب والملاحظات.</p>")
        return await layout(r, u, None, "u", body)

    @app.get("/admin/users", response_class=HTMLResponse)
    async def users(r: Request):
        u, bad = await gate(r, admin=True)
        if bad:
            return bad
        return await users_page(r, u)

    @app.post("/admin/users/add", response_class=HTMLResponse)
    async def user_add(r: Request, username: str = Form(""), role: str = Form("mod"), t: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        name = username.strip().lower()
        if not auth.USERNAME_RE.fullmatch(name):
            return await users_page(r, u, err="اسم المستخدم لازم يكون 3-24 حرف إنجليزي صغير أو أرقام أو _ . -")
        if role not in ("admin", "mod"):
            role = "mod"
        if await auth.by_name(name):
            return await users_page(r, u, err="هالاسم مستخدم من قبل.")
        pw = auth.temp_password()
        h = await asyncio.to_thread(auth.hash_pw, pw)
        await db.q("INSERT INTO dash_users(username,pw,role,active,must_change,created) VALUES(?,?,?,1,1,?)", (name, h, role, int(time.time())), commit=True)
        await auth.audit(u["username"], "user_add", "%s (%s)" % (name, ROLE[role]))
        return await users_page(r, u, flash="تم إنشاء <b>%s</b> (%s). كلمة السر المؤقتة: <code>%s</code><br><span class=mut>بتظهر مرة وحدة فقط. انسخها وابعتها للمستخدم.</span>" % (H(name), ROLE[role], H(pw)))

    async def target(r, u, uid):
        x = await auth.get_user(uid)
        if not x:
            return None, await users_page(r, u, err="المستخدم غير موجود.")
        if x["id"] == u["id"]:
            return None, await users_page(r, u, err="ما بتقدر تعدّل حسابك من هون. استخدم صفحة «حسابي».")
        return x, None

    @app.post("/admin/users/{uid}/toggle", response_class=HTMLResponse)
    async def user_toggle(r: Request, uid: int, t: str = Form(""), back: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        x, resp = await target(r, u, uid)
        if resp:
            return resp
        if x["active"] and x["role"] == "admin" and not await other_admins(uid):
            return await users_page(r, u, err="ما بتقدر تعطّل آخر مدير فعّال.")
        await db.q("UPDATE dash_users SET active=1-active, sv=sv+1 WHERE id=?", (uid,), commit=True)
        await auth.audit(u["username"], "user_toggle", "%s ← %s" % (x["username"], "معطّل" if x["active"] else "فعّال"))
        return RedirectResponse("/admin/users", 303)

    @app.post("/admin/users/{uid}/reset", response_class=HTMLResponse)
    async def user_reset(r: Request, uid: int, t: str = Form(""), back: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        x, resp = await target(r, u, uid)
        if resp:
            return resp
        pw = auth.temp_password()
        h = await asyncio.to_thread(auth.hash_pw, pw)
        await db.q("UPDATE dash_users SET pw=?, must_change=1, sv=sv+1 WHERE id=?", (h, uid), commit=True)
        await auth.audit(u["username"], "user_reset", x["username"])
        return await users_page(r, u, flash="كلمة السر المؤقتة الجديدة لـ <b>%s</b>: <code>%s</code><br><span class=mut>بتظهر مرة وحدة، وجلساته الحالية انتهت.</span>" % (H(x["username"]), H(pw)))

    @app.post("/admin/users/{uid}/role", response_class=HTMLResponse)
    async def user_role(r: Request, uid: int, t: str = Form(""), back: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        x, resp = await target(r, u, uid)
        if resp:
            return resp
        new = "mod" if x["role"] == "admin" else "admin"
        if x["role"] == "admin" and x["active"] and not await other_admins(uid):
            return await users_page(r, u, err="ما بتقدر تنزّل آخر مدير فعّال.")
        await db.q("UPDATE dash_users SET role=? WHERE id=?", (new, uid), commit=True)
        await auth.audit(u["username"], "user_role", "%s ← %s" % (x["username"], ROLE[new]))
        return RedirectResponse("/admin/users", 303)

    @app.post("/admin/users/{uid}/delete", response_class=HTMLResponse)
    async def user_delete(r: Request, uid: int, t: str = Form(""), back: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        x, resp = await target(r, u, uid)
        if resp:
            return resp
        if x["active"]:
            return await users_page(r, u, err="عطّل الحساب أولاً قبل حذفه.")
        await db.q("DELETE FROM dash_users WHERE id=?", (uid,), commit=True)
        await auth.audit(u["username"], "user_delete", x["username"])
        return RedirectResponse("/admin/users", 303)

    @app.get("/admin/audit", response_class=HTMLResponse)
    async def audit_page(r: Request):
        u, bad = await gate(r, admin=True)
        if bad:
            return bad
        rows = await db.q("SELECT * FROM audit ORDER BY id DESC LIMIT 200")
        trs = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td class=sn>%s</td></tr>" % (tm(x["ts"]), H(x["actor"]), H(ACTIONS.get(x["action"], x["action"])), H(x["detail"])) for x in rows) \
            or "<tr><td colspan=4>ما في نشاط.</td></tr>"
        return await layout(r, u, None, "a", "<div class=t><table><tr><th>الوقت<th>المستخدم<th>الإجراء<th>التفاصيل</tr>" + trs + "</table></div>")

    # ---------- إعدادات السيرفر (للمدير) ----------
    async def settings_page(r, u, gu, cfg, flash="", err=""):
        gid = gu.id
        f = ("<div class='box okb'>%s</div>" % H(flash)) if flash else ""
        e = ("<div class='box badb'>%s</div>" % H(err)) if err else ""

        # بناء جدول الكلمات المراقبة كـ preview
        seed_words = cfg.get("seed_words", "")
        word_list = [w.strip() for w in seed_words.split("\n") if w.strip()]
        words_preview = "".join("<span class='chip warn' style='margin:2px'>%s</span>" % H(w) for w in word_list) if word_list else "<span class=mut>لا توجد كلمات مضافة بعد.</span>"

        body = (
            f + e +
            "<form method=post action='/settings' class=box style='max-width:600px'>" + tok(r) +
            "<input type=hidden name=g value=%d>" % gid +
            "<h2 style='margin-top:0'>عتبات الحساسية</h2>"
            "<p class=mut>البوت يفحص كل رسالة بثلاث مراحل. العتبات تتحكم في حدود الانتقال بينها.</p>"
            "<div class='box' style='background:var(--s2);border-color:var(--bd);padding:12px 16px;margin:10px 0'>"
            "<p style='margin:0 0 6px'><b>كيف يشتغل المحرك:</b></p>"
            "<ol style='margin:0;padding-inline-start:20px;color:var(--mut);font-size:.9rem'>"
            "<li>فحص سريع بـ OpenAI Moderation API → يعطي score بين 0 و1</li>"
            "<li>إذا الـ score &lt; العتبة الدنيا <b>وما في كلمة مراقبة</b> → تجاهل الرسالة</li>"
            "<li>إذا الـ score ≥ العتبة العليا → إساءة مباشرة بدون GPT</li>"
            "<li>بين العتبتين → GPT يحكم: مزاح؟ إساءة؟</li>"
            "</ol></div>"
            "<div class=row>"
            "<div><label>العتبة الدنيا (0.0 – 1.0)</label>"
            "<input type=number name=mod_low min=0 max=1 step=0.05 value='%.2f' required>" % cfg["mod_low"] +
            "<p class=mut style='font-size:.8rem'>أقل من هذا = تجاهل (بدون كلمات مراقبة). مقترح: 0.25 – 0.40</p></div>"
            "<div><label>العتبة العليا (0.0 – 1.0)</label>"
            "<input type=number name=mod_high min=0 max=1 step=0.05 value='%.2f' required>" % cfg["mod_high"] +
            "<p class=mut style='font-size:.8rem'>فوق هذا = إساءة مباشرة. مقترح: 0.75 – 0.90</p></div>"
            "</div>"
            "<h2>كلمات المراقبة المخصصة</h2>"
            "<p class=mut>كلمات أو عبارات قصيرة تجبر مراجعة GPT حتى لو الـ score منخفض — كلمة واحدة في كل سطر، باللغة العربية أو Arabizi.</p>"
            "<p class=mut>البوت يحتوي على قائمة افتراضية من الكلمات الشائعة. هنا تضيف ما يخص مجتمعك.</p>"
            "<textarea name=seed_words rows=6 placeholder='مثال:\nنوب\nترول\ngg ez\nيلعن'>%s</textarea>" % H(seed_words) +
            "<div style='margin:8px 0 4px'><span class=mut style='font-size:.85rem'>الكلمات المضافة حالياً: </span>" + words_preview + "</div>"
            "<h2>الاحتفاظ بالسجلات</h2>"
            "<label>مدة الاحتفاظ بالإنذارات (بالأيام)</label>"
            "<input type=number name=retention_days min=7 max=365 value='%d' required>" % cfg["retention_days"] +
            "<p class=mut style='font-size:.8rem'>الإنذارات القديمة تُحذف تلقائياً. أقل قيمة مسموح بها: 7 أيام.</p>"
            "<button style='margin-top:16px'>حفظ الإعدادات</button>"
            "</form>"
        )
        return await layout(r, u, gu, "s", body)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_get(r: Request, g: int = 0):
        u, bad = await gate(r, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        cfg = await db.get_guild_config(gu.id)
        return await settings_page(r, u, gu, cfg)

    @app.post("/settings", response_class=HTMLResponse)
    async def settings_post(r: Request, g: int = Form(0),
                            mod_low: float = Form(0.3), mod_high: float = Form(0.85),
                            seed_words: str = Form(""), retention_days: int = Form(30),
                            t: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        # تحقق من القيم
        if not (0.0 <= mod_low < mod_high <= 1.0):
            cfg = {"mod_low": mod_low, "mod_high": mod_high, "seed_words": seed_words, "retention_days": retention_days}
            return await settings_page(r, u, gu, cfg, err="العتبة الدنيا لازم تكون أصغر من العتبة العليا، وكلتاهما بين 0 و1.")
        if retention_days < 7:
            cfg = {"mod_low": mod_low, "mod_high": mod_high, "seed_words": seed_words, "retention_days": retention_days}
            return await settings_page(r, u, gu, cfg, err="أقل مدة احتفاظ مسموح بها 7 أيام.")
        # نظّف الكلمات: اسطر فارغة وتكرار
        cleaned_words = "\n".join(dict.fromkeys(w.strip() for w in seed_words.splitlines() if w.strip()))
        await db.set_guild_config(gu.id, mod_low, mod_high, cleaned_words, retention_days)
        db.invalidate_guild_cache(gu.id)   # مسح الكاش فوراً
        await auth.audit(u["username"], "settings_save",
                         "%s: عتبة دنيا=%.2f عليا=%.2f احتفاظ=%dي" % (gu.name, mod_low, mod_high, retention_days))
        cfg = await db.get_guild_config(gu.id)
        return await settings_page(r, u, gu, cfg, flash="تم حفظ الإعدادات ✓")

    # ---------- إدارة الألعاب (للمدير) ----------
    async def games_page(r, u, gu, enabled: set, lfg_cfg, flash=""):
        gid = gu.id
        f = ("<div class='box okb'>%s</div>" % H(flash)) if flash else ""

        cards = ""
        for cat in CATEGORIES:
            cat_games = [g for g in GAMES if g["category"] == cat]
            items = ""
            for g in cat_games:
                checked = "checked" if g["id"] in enabled else ""
                items += (
                    "<label style='display:flex;align-items:center;gap:10px;padding:10px 12px;"
                    "border-radius:9px;cursor:pointer;border:1px solid var(--bd);"
                    "background:var(--s2);margin:4px 0'>"
                    "<input type=checkbox name=games value='%s' %s style='width:16px;height:16px;flex:none;margin:0'>"
                    "<span style='font-size:1.3rem'>%s</span>"
                    "<span style='font-weight:500'>%s</span>"
                    "</label>" % (H(g["id"]), checked, H(g["emoji"]), H(g["name"]))
                )
            cards += ("<div style='margin-bottom:24px'>"
                      "<h2 style='margin-top:0;font-size:.9rem;color:var(--mut)'>%s</h2>%s</div>" % (H(cat), items))

        lfg_ch = str(lfg_cfg["lfg_channel"]) if lfg_cfg and lfg_cfg["lfg_channel"] else ""
        vc_cat = str(lfg_cfg["vc_category"])  if lfg_cfg and lfg_cfg["vc_category"]  else ""

        body = (
            f +
            "<form method=post action='/games'>" + tok(r) +
            "<input type=hidden name=g value=%d>" % gid +
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:700px;margin-bottom:24px'>"
            "<div class=box><label>قناة الـ LFG (ID)</label>"
            "<input name=lfg_channel value='%s' placeholder='مثال: 1234567890' pattern='\\d*'>" % H(lfg_ch) +
            "<p class=mut style='font-size:.8rem'>وين ينزل الـ embed. فاضي = نفس قناة الأمر.</p></div>"
            "<div class=box><label>كاتيغوري الـ Voice Channels (ID)</label>"
            "<input name=vc_category value='%s' placeholder='مثال: 9876543210' pattern='\\d*'>" % H(vc_cat) +
            "<p class=mut style='font-size:.8rem'>وين يتعمل الـ VC المؤقت. فاضي = جذر السيرفر.</p></div></div>"
            "<h2 style='margin-bottom:8px'>الألعاب المتاحة في /lfg</h2>"
            "<p class=mut>اختر الألعاب اللي تظهر للاعبين عند استخدام /lfg في هالسيرفر.</p>"
            "<div style='max-width:700px'>" + cards + "</div>"
            "<div style='display:flex;gap:10px;align-items:center;margin-top:8px'>"
            "<button>حفظ</button>"
            "<button type=button class=g id=gg-sel-all>تحديد الكل</button>"
            "<button type=button class=g id=gg-sel-none>إلغاء الكل</button>"
            "</div></form>"
        )
        return await layout(r, u, gu, "g", body)

    @app.get("/games", response_class=HTMLResponse)
    async def games_get(r: Request, g: int = 0):
        u, bad = await gate(r, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        enabled = set(await db.get_guild_games(gu.id))
        lfg_cfg = await db.get_lfg_settings(gu.id)
        return await games_page(r, u, gu, enabled, lfg_cfg)

    @app.post("/games", response_class=HTMLResponse)
    async def games_post(r: Request, g: int = Form(0), lfg_channel: str = Form(""),
                         vc_category: str = Form(""), t: str = Form(""),
                         games: list = Form(default=[])):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        valid_ids = {gm["id"] for gm in GAMES}
        chosen = [x for x in games if x in valid_ids]
        lfg_ch_int = int(lfg_channel) if lfg_channel.strip().isdigit() else None
        vc_cat_int = int(vc_category) if vc_category.strip().isdigit() else None
        await db.set_guild_games(gu.id, chosen)
        await db.set_lfg_settings(gu.id, lfg_ch_int, vc_cat_int)
        await auth.audit(u["username"], "games_save",
                         "%s: %d لعبة مفعّلة" % (gu.name, len(chosen)))
        enabled = set(await db.get_guild_games(gu.id))
        lfg_cfg = await db.get_lfg_settings(gu.id)
        return await games_page(r, u, gu, enabled, lfg_cfg, flash="تم حفظ إعدادات الألعاب ✓")

    # ---------- إعدادات الترجمة ----------
    @app.get("/translate", response_class=HTMLResponse)
    async def translate_get(r: Request, g: int = 0):
        u, bad = await gate(r, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        cfg = await db.get_guild_config(gu.id)
        return await translate_page(r, u, gu, cfg)

    @app.post("/translate", response_class=HTMLResponse)
    async def translate_post(r: Request, g: int = Form(0),
                             translate_enabled: str = Form("off"),
                             translate_voice: str = Form("off"),
                             t: str = Form("")):
        u, bad = await gatep(r, t, admin=True)
        if bad:
            return bad
        if not bot.guilds:
            return RedirectResponse("/", 303)
        gu = pick(g)
        te = 1 if translate_enabled == "on" else 0
        tv = 1 if translate_voice   == "on" else 0
        # نستخدم set_guild_config المُحدَّثة — تحفظ وتمسح الكاش تلقائياً
        current = await db.get_guild_config(gu.id)
        await db.set_guild_config(
            gu.id,
            current["mod_low"], current["mod_high"],
            current["seed_words"], current["retention_days"],
            translate_enabled=te, translate_voice=tv,
        )
        await auth.audit(u["username"], "translate_save",
                         "%s: نص=%s صوت=%s" % (gu.name, "مفعّل" if te else "معطّل", "مفعّل" if tv else "معطّل"))
        cfg = await db.get_guild_config(gu.id)
        return await translate_page(r, u, gu, cfg, flash="تم حفظ إعدادات الترجمة ✓")

    async def translate_page(r, u, gu, cfg, flash=""):
        gid = gu.id
        fl  = ("<div class='box okb'>%s</div>" % H(flash)) if flash else ""
        te  = cfg.get("translate_enabled", 1)
        tv  = cfg.get("translate_voice",   1)

        stats_row = await db.q(
            "SELECT COUNT(*) c FROM user_langs WHERE guild=?", (gid,), one=True)
        users_set = stats_row["c"] if stats_row else 0

        body = (
            fl +
            "<form method=post action='/translate' class=box style='max-width:620px'>" + tok(r) +
            "<input type=hidden name=g value=%d>" % gid +
            "<h2 style='margin-top:0'>إعدادات الترجمة التلقائية</h2>"
            "<p class=mut>البوت يكشف لغة كل رسالة تلقائياً ويترجمها للعربي والإنجليزي "
            "بجانب الرسالة الأصلية. اللاعبين يقدرون يحددون لغتهم بأمر <b>/setlang</b>.</p>"
            "<div class='box' style='background:var(--s2);margin:10px 0'><b>📊 إحصائيات:</b> "
            "%d لاعب حدّد لغته المفضلة في هالسيرفر.</div>" % users_set +
            "<label style='display:flex;align-items:center;gap:12px;cursor:pointer;margin:14px 0'><input type=checkbox name=translate_enabled value=on %s '" % ("checked" if te else "") +
            "style='width:18px;height:18px'><span><b>🌐 تفعيل ترجمة الرسائل النصية</b><br>"
            "<small class=mut>البوت يترجم كل رسالة بلغة غير عربية أو إنجليزية تلقائياً</small></span></label>"
            "<label style='display:flex;align-items:center;gap:12px;cursor:pointer;margin:14px 0'><input type=checkbox name=translate_voice value=on %s '" % ("checked" if tv else "") +
            "style='width:18px;height:18px'><span><b>🎙️ تفعيل ترجمة الرسائل الصوتية</b><br>"
            "<small class=mut>يحوّل الصوت لنص ويترجمه (Whisper AI — تكلفة إضافية بسيطة)</small></span></label>"
            "<h2>اللغات المدعومة</h2>"
            "<div style='display:flex;flex-wrap:wrap;gap:6px'>"
            "<span class='chip ac'>&rlm;🇸🇦 العربية</span>"
            "<span class='chip ac'>&rlm;🇬🇧 English</span>"
            "<span class='chip'>&rlm;🇫🇷 Français</span>"
            "<span class='chip'>&rlm;🇪🇸 Español</span>"
            "<span class='chip'>&rlm;🇩🇪 Deutsch</span>"
            "<span class='chip'>&rlm;🇹🇷 Türkçe</span>"
            "<span class='chip'>&rlm;🇵🇹 Português</span>"
            "<span class='chip'>&rlm;🇷🇺 Русский</span>"
            "<span class='chip'>&rlm;🇯🇵 日本語</span>"
            "<span class='chip'>&rlm;🇰🇷 한국어</span>"
            "<span class='chip'>&rlm;🇨🇳 中文</span>"
            "<span class='chip'>&rlm;🇮🇩 Bahasa</span>"
            "<span class='chip'>&rlm;🇮🇳 हिन्दी</span>"
            "<span class='chip'>&rlm;🇮🇹 Italiano</span>"
            "<span class='chip'>&rlm;🇳🇱 Nederlands</span>"
            "</div>"
            "<h2>تكلفة تقديرية</h2>"
            "<div class='box' style='background:var(--s2)'>'"
            "<p><b>نص:</b> ~/bin/sh.0004 لكل رسالة (GPT-4o-mini — موجود أصلاً)</p>"
            "<p><b>صوت:</b> /bin/sh.006 لكل دقيقة (Whisper AI)</p>"
            "<p class=mut>100 لاعب × 50 رسالة + 5 رسائل صوتية يومياً ≈ <b>–5 شهرياً</b></p>"
            "'</div>"
            "<button style='margin-top:14px'>حفظ الإعدادات</button>"
            "</form>"
        )
        return await layout(r, u, gu, "x", body)

    return app