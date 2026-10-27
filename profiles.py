"""profiles.py — بروفايل اللاعب (كارد) + نسبة التوافق + إنشاء/تعديل البروفايل."""
import json, time, collections
import discord
from discord import ui
import db, moderation
from games import GAMES_BY_ID

AGES = [("13-15", "13 – 15"), ("16-18", "16 – 18"), ("19-24", "19 – 24"),
        ("25-30", "25 – 30"), ("30+", "+30")]
AGE_LABEL = dict(AGES)
MICS = [("always", "دايماً"), ("sometimes", "أحياناً"), ("never", "لا")]
MIC_LABEL = dict(MICS)
TIMES = ["صباحاً", "ظهراً", "مساءً", "ليلاً", "ويكند"]
STYLES = ["كاجوال", "تنافسي", "هادئ", "كثير حكي", "هزار", "جدّي", "يلعب مع غرباء"]
MINOR_AGES = {"13-15", "16-18"}
BIO_MAX = 140
MAX_GAMES = 3

# حدود الدعوات الخاصة (في الذاكرة، تتصفّر مع إعادة التشغيل)
INVITE_PAIR_COOLDOWN = 3600      # دعوة واحدة لنفس اللاعب كل ساعة
INVITE_HOURLY_MAX = 5            # أقصى دعوات للمرسل بالساعة
_pair_ts, _sender_ts = {}, collections.defaultdict(list)


def _j(s, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


# ═══════════════════════════════════════════════════════════════
#  قاعدة البيانات
# ═══════════════════════════════════════════════════════════════
async def get_profile(guild, user):
    r = await db.q("SELECT * FROM player_profiles WHERE guild=? AND user=?", (guild, user), one=True)
    if not r:
        return None
    return {"bio": r["bio"] or "", "dialect": r["dialect"] or "", "age": r["age"] or "",
            "mic": r["mic"] or "", "times": _j(r["times"], []), "style": _j(r["style"], []),
            "games": _j(r["games"], {}), "private": bool(r["private"])}


async def save_profile(guild, user, p):
    await db.q(
        "INSERT INTO player_profiles(guild,user,bio,dialect,age,mic,times,style,games,private,updated) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(guild,user) DO UPDATE SET "
        "bio=excluded.bio, dialect=excluded.dialect, age=excluded.age, mic=excluded.mic, "
        "times=excluded.times, style=excluded.style, games=excluded.games, "
        "private=excluded.private, updated=excluded.updated",
        (guild, user, p["bio"], p["dialect"], p["age"], p["mic"], json.dumps(p["times"], ensure_ascii=False),
         json.dumps(p["style"], ensure_ascii=False), json.dumps(p["games"]), int(p["private"]), int(time.time())),
        commit=True)


async def delete_profile(guild, user):
    await db.q("DELETE FROM player_profiles WHERE guild=? AND user=?", (guild, user), commit=True)


async def _teams(guild, since):
    rows = await db.q("SELECT host, joined FROM lfg_posts WHERE guild=? AND done=1 AND ts>?", (guild, since))
    return [{r["host"], *_j(r["joined"], [])} for r in rows]


async def sessions(guild, user):
    """عدد الجلسات المكتملة (LFG) آخر 90 يوم."""
    return sum(1 for t in await _teams(guild, int(time.time()) - 90 * 86400) if user in t)


async def played_together(guild, a, b):
    """هل لعبوا سوا عبر LFG مكتمل خلال آخر 14 يوم؟ (شرط التقييم)"""
    return any(a in t and b in t for t in await _teams(guild, int(time.time()) - 14 * 86400))


# ═══════════════════════════════════════════════════════════════
#  نسبة التوافق (0-100)  — ألعاب 40 + رانك 25 + أوقات 15 + أسلوب 20
# ═══════════════════════════════════════════════════════════════
def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.5          # معلومة ناقصة = حياد
    return len(a & b) / len(a | b)


def compat(a, b):
    if not a or not b:
        return None
    ga, gb = a["games"], b["games"]
    shared = [g for g in ga if g in gb]
    games_s = len(shared) / min(len(ga), len(gb)) if ga and gb else 0
    rank_s = 0
    if shared:
        parts = []
        for g in shared:
            ranks = GAMES_BY_ID.get(g, {}).get("ranks", [])
            ra, rb = ga[g], gb[g]
            if not ranks:
                parts.append(1)
            elif ra in ranks and rb in ranks:
                parts.append(1 - min(abs(ranks.index(ra) - ranks.index(rb)), 4) / 4)
            else:
                parts.append(0.5)
        rank_s = sum(parts) / len(parts)
    score = 40 * games_s + 25 * rank_s + 15 * _jaccard(a["times"], b["times"]) + 20 * _jaccard(a["style"], b["style"])
    return round(score)


# ═══════════════════════════════════════════════════════════════
#  الكارد
# ═══════════════════════════════════════════════════════════════
async def build_card(guild, member, viewer_id):
    p = await get_profile(guild.id, member.id)
    rep = await db.reputation(guild.id, member.id)
    n_sess = await sessions(guild.id, member.id)
    emb = discord.Embed(title=member.display_name, color=discord.Color.blurple())
    emb.set_thumbnail(url=member.display_avatar.url)
    own = viewer_id == member.id

    if not p:
        emb.description = "ما أنشأ بروفايل بعد." + ("\nأنشئ بروفايلك بـ `/profile_edit`" if own else "")
    elif p["private"] and not own:
        emb.description = "🔒 بروفايله مخفي."
    else:
        if p["bio"]:
            emb.description = p["bio"]
        info = []
        if p["dialect"]:
            info.append(f"🗣️ {p['dialect']}")
        if p["age"]:
            info.append(f"🎂 {AGE_LABEL.get(p['age'], p['age'])}")
        if p["mic"]:
            info.append(f"🎙️ ميك: {MIC_LABEL.get(p['mic'], p['mic'])}")
        if info:
            emb.add_field(name="معلومات", value=" · ".join(info), inline=False)
        lines = []
        for gid, rank in p["games"].items():
            g = GAMES_BY_ID.get(gid)
            if g:
                lines.append(f"{g['emoji']} **{g['name']}**" + (f" — {rank}" if rank else ""))
        if lines:
            emb.add_field(name="الألعاب", value="\n".join(lines), inline=False)
        tags = p["times"] + p["style"]
        if tags:
            emb.add_field(name="الأسلوب", value=" · ".join(tags), inline=False)
        if p["private"]:
            emb.set_footer(text="🔒 بروفايلك مخفي عن الآخرين")
        if not own:
            vp = await get_profile(guild.id, viewer_id)
            c = compat(vp, p)
            if c is None:
                emb.set_footer(text="أنشئ بروفايلك بـ /profile_edit لتشوف نسبة التوافق")
            else:
                shared = [g for g in vp["games"] if g in p["games"]]
                note = "" if shared else " (ما عندكم لعبة مشتركة)"
                emb.add_field(name="🤝 التوافق معك", value=f"**{c}%**{note}", inline=False)
                emb.color = (discord.Color.green() if c >= 70 else
                             discord.Color.orange() if c >= 40 else discord.Color.light_grey())

    emb.add_field(name="السمعة",
                  value=f"⭐ **{rep[0]}/100** · 🎮 {n_sess} جلسة · تقييمات: {rep[1]} · إنذارات: {rep[2]}",
                  inline=False)
    return emb


# ═══════════════════════════════════════════════════════════════
#  أزرار الكارد: دعوة / تقييم / تعديل
# ═══════════════════════════════════════════════════════════════
class CardView(ui.View):
    def __init__(self, member, viewer_id):
        super().__init__(timeout=600)
        self.member = member
        if viewer_id == member.id:
            b = ui.Button(label="عدّل بروفايلي", style=discord.ButtonStyle.primary)
            b.callback = self._edit
            self.add_item(b)
        else:
            b1 = ui.Button(label="دعوة للعب 🎮", style=discord.ButtonStyle.success)
            b1.callback = self._invite
            b2 = ui.Button(label="قيّمه ⭐", style=discord.ButtonStyle.secondary)
            b2.callback = self._rate
            self.add_item(b1)
            self.add_item(b2)

    async def _edit(self, i: discord.Interaction):
        if i.user.id != self.member.id:
            return await i.response.send_message("هذا مو بروفايلك.", ephemeral=True)
        await start_edit(i)

    async def _rate(self, i: discord.Interaction):
        t = self.member
        if t.id == i.user.id or t.bot:
            return await i.response.send_message("ما بتقدر تقيّم هالحساب.", ephemeral=True)
        if not await played_together(i.guild_id, i.user.id, t.id):
            return await i.response.send_message(
                "بتقدر تقيّمه بعد ما تلعبوا سوا عبر طلب LFG (خلال آخر 14 يوم).", ephemeral=True)
        await i.response.send_message(f"كم نجمة لـ {t.display_name}؟", view=StarsView(t), ephemeral=True)

    async def _invite(self, i: discord.Interaction):
        s, t, now = i.user, self.member, time.time()
        if s.id == t.id or t.bot:
            return await i.response.send_message("ما بتقدر تدعو هالحساب.", ephemeral=True)
        tp, sp = await get_profile(i.guild_id, t.id), await get_profile(i.guild_id, s.id)
        if tp and tp["private"]:
            return await i.response.send_message("هذا اللاعب مخفي بروفايله، ما بتقدر تدعوه.", ephemeral=True)
        # حماية القاصرين: ما في دعوات بين قاصر وغير قاصر (أو عمر غير معروف)
        s_age, t_age = (sp or {}).get("age", ""), (tp or {}).get("age", "")
        if (s_age in MINOR_AGES) != (t_age in MINOR_AGES):
            return await i.response.send_message(
                "الدعوات الخاصة متاحة بين نفس الفئة العمرية فقط. جرّب طلب LFG عام.", ephemeral=True)
        if now - _pair_ts.get((s.id, t.id), 0) < INVITE_PAIR_COOLDOWN:
            return await i.response.send_message("دعوته قبل شوي، انتظر شوي.", ephemeral=True)
        _sender_ts[s.id] = [x for x in _sender_ts[s.id] if now - x < 3600]
        if len(_sender_ts[s.id]) >= INVITE_HOURLY_MAX:
            return await i.response.send_message("وصلت للحد الأقصى من الدعوات بالساعة.", ephemeral=True)
        where = i.channel.mention if getattr(i.channel, "mention", None) else "السيرفر"
        try:
            await t.send(f"🎮 **{s.display_name}** من «{i.guild.name}» بدّه يلعب معك. رد عليه هون: {where}")
        except discord.Forbidden:
            return await i.response.send_message("ما قدرت أوصله، رسائله الخاصة مغلقة.", ephemeral=True)
        _pair_ts[(s.id, t.id)] = now
        _sender_ts[s.id].append(now)
        await i.response.send_message(f"وصلت دعوتك لـ {t.display_name} ✅", ephemeral=True)


class StarsView(ui.View):
    def __init__(self, target):
        super().__init__(timeout=120)
        self.target = target
        sel = ui.Select(placeholder="اختر التقييم",
                        options=[discord.SelectOption(label="⭐" * n, value=str(n)) for n in range(5, 0, -1)])
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, i: discord.Interaction):
        stars, now = int(i.data["values"][0]), int(time.time())
        dup = await db.q("SELECT 1 FROM ratings WHERE guild=? AND rater=? AND target=? AND ts>?",
                         (i.guild_id, i.user.id, self.target.id, now - 86400), one=True)
        if dup:
            return await i.response.edit_message(content="قيّمته اليوم، جرّب بكرة.", view=None)
        await db.q("INSERT INTO ratings VALUES(?,?,?,?,?)",
                   (i.guild_id, i.user.id, self.target.id, stars, now), commit=True)
        await i.response.edit_message(content=f"تم تقييم {self.target.display_name}: {'⭐' * stars}", view=None)


# ═══════════════════════════════════════════════════════════════
#  إنشاء / تعديل البروفايل
# ═══════════════════════════════════════════════════════════════
class _OwnerView(ui.View):
    def __init__(self, owner_id, timeout=600):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, i):
        if i.user.id != self.owner_id:
            await i.response.send_message("هذا مو إلك.", ephemeral=True)
            return False
        return True


class _Pick(ui.Select):
    def __init__(self, key, placeholder, opts, current, multi, row):
        options = [discord.SelectOption(label=l, value=v, default=(v in current if multi else v == current))
                   for v, l in opts]
        super().__init__(placeholder=placeholder, options=options, row=row,
                         min_values=0 if multi else 1, max_values=len(options) if multi else 1)
        self.key, self.multi = key, multi

    async def callback(self, i):
        self.view.draft[self.key] = list(self.values) if self.multi else self.values[0]
        await i.response.defer()


def _new_draft(p):
    return dict(p) if p else {"bio": "", "dialect": "", "age": "", "mic": "", "times": [],
                              "style": [], "games": {}, "private": False}


async def start_edit(i: discord.Interaction):
    p = _new_draft(await get_profile(i.guild_id, i.user.id))
    await i.response.send_message("📝 بروفايلك — الخطوة 1 من 3", view=EditView(i.user.id, p), ephemeral=True)


class EditView(_OwnerView):
    def __init__(self, owner_id, draft):
        super().__init__(owner_id)
        self.draft = draft
        self.add_item(_Pick("age", "فئتك العمرية (مطلوب)", AGES, draft["age"], False, 0))
        self.add_item(_Pick("mic", "الميكروفون", MICS, draft["mic"], False, 1))
        self.add_item(_Pick("times", "أوقات اللعب", [(t, t) for t in TIMES], draft["times"], True, 2))
        self.add_item(_Pick("style", "أسلوب اللعب", [(s, s) for s in STYLES], draft["style"], True, 3))
        self.privacy_btn = ui.Button(label=self._plabel(), style=discord.ButtonStyle.secondary, row=4)
        self.privacy_btn.callback = self._toggle
        nxt = ui.Button(label="متابعة ➡️", style=discord.ButtonStyle.primary, row=4)
        nxt.callback = self._next
        self.add_item(nxt)
        self.add_item(self.privacy_btn)

    def _plabel(self):
        return "🔒 مخفي عن الآخرين" if self.draft["private"] else "👁️ ظاهر لأعضاء السيرفر"

    async def _toggle(self, i):
        self.draft["private"] = not self.draft["private"]
        self.privacy_btn.label = self._plabel()
        await i.response.edit_message(view=self)

    async def _next(self, i):
        if not self.draft["age"]:
            return await i.response.send_message("اختر فئتك العمرية أول.", ephemeral=True)
        await i.response.send_modal(BioModal(self.draft))


class BioModal(ui.Modal, title="نبذة عنك"):
    bio = ui.TextInput(label="نبذة قصيرة", style=discord.TextStyle.paragraph,
                       max_length=BIO_MAX, required=False, placeholder="مثلاً: بلعب مساءً وبحب الضحك")
    dialect = ui.TextInput(label="لهجتك / منطقتك", max_length=20, required=False,
                           placeholder="شامي، خليجي، مصري...")

    def __init__(self, draft):
        super().__init__()
        self.draft = draft
        self.bio.default = draft["bio"] or None
        self.dialect.default = draft["dialect"] or None

    async def on_submit(self, i: discord.Interaction):
        text = f"{self.bio.value}\n{self.dialect.value}".strip()
        if text:
            try:
                res = await moderation.analyze(text)
            except Exception as e:
                print("profile moderation error:", e)
                res = {"verdict": "ok"}
            if res["verdict"] == "abuse":
                return await i.response.send_message(
                    "النبذة فيها كلام مسيء. عدّلها وجرّب مرة ثانية بـ `/profile_edit`.", ephemeral=True)
        self.draft["bio"], self.draft["dialect"] = self.bio.value.strip(), self.dialect.value.strip()
        enabled = [g for g in await db.get_guild_games(i.guild_id) if g in GAMES_BY_ID]
        if not enabled:
            self.draft["games"] = {}
            return await _finish(i, self.draft, edit=False)
        await i.response.send_message("🎮 اختر ألعابك (حتى 3) — الخطوة 2 من 3",
                                      view=GamesView(i.user.id, self.draft, enabled), ephemeral=True)


class GamesView(_OwnerView):
    def __init__(self, owner_id, draft, enabled):
        super().__init__(owner_id)
        self.draft, self.picked = draft, list(draft["games"])
        opts = [discord.SelectOption(label=GAMES_BY_ID[g]["name"], value=g, emoji=GAMES_BY_ID[g]["emoji"],
                                     default=g in draft["games"]) for g in enabled]
        sel = ui.Select(placeholder="اختر لعبة أو أكثر", options=opts, min_values=1,
                        max_values=min(MAX_GAMES, len(opts)))
        sel.callback = self._pick
        self.add_item(sel)
        ok = ui.Button(label="متابعة ➡️", style=discord.ButtonStyle.primary)
        ok.callback = self._ok
        self.add_item(ok)

    async def _pick(self, i):
        self.picked = list(i.data["values"])
        await i.response.defer()

    async def _ok(self, i):
        if not self.picked:
            return await i.response.send_message("اختر لعبة وحدة على الأقل.", ephemeral=True)
        self.draft["games"] = {g: self.draft["games"].get(g, "") for g in self.picked}
        queue = [g for g in self.picked if GAMES_BY_ID[g]["ranks"]]
        if queue:
            return await i.response.edit_message(content=_rank_text(queue[0]),
                                                  view=RankView(self.owner_id, self.draft, queue))
        await _finish(i, self.draft)


def _rank_text(gid):
    return f"🏅 رانكك في **{GAMES_BY_ID[gid]['name']}** — الخطوة 3 من 3"


class RankView(_OwnerView):
    def __init__(self, owner_id, draft, queue):
        super().__init__(owner_id)
        self.draft, self.queue = draft, queue
        gid = queue[0]
        cur = draft["games"].get(gid, "")
        sel = ui.Select(placeholder="اختر رانكك",
                        options=[discord.SelectOption(label=r, value=r, default=(r == cur))
                                 for r in GAMES_BY_ID[gid]["ranks"]])
        sel.callback = self._pick
        skip = ui.Button(label="تخطي", style=discord.ButtonStyle.secondary)
        skip.callback = self._skip
        self.add_item(sel)
        self.add_item(skip)

    async def _advance(self, i, rank):
        self.draft["games"][self.queue[0]] = rank
        rest = self.queue[1:]
        if rest:
            return await i.response.edit_message(content=_rank_text(rest[0]),
                                                  view=RankView(self.owner_id, self.draft, rest))
        await _finish(i, self.draft)

    async def _pick(self, i):
        await self._advance(i, i.data["values"][0])

    async def _skip(self, i):
        await self._advance(i, "")


async def _finish(i: discord.Interaction, draft, edit=True):
    await save_profile(i.guild_id, i.user.id, draft)
    emb = await build_card(i.guild, i.user, i.user.id)
    if edit:
        await i.response.edit_message(content="✅ تم حفظ بروفايلك", embed=emb, view=None)
    else:
        await i.response.send_message("✅ تم حفظ بروفايلك", embed=emb, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
#  زر «بروفايلات الفريق» داخل طلب LFG
# ═══════════════════════════════════════════════════════════════
async def team_picker(i: discord.Interaction, post):
    ids = [post["host"]] + _j(post["joined"], [])
    vp = await get_profile(i.guild_id, i.user.id)
    opts = []
    for uid in ids[:25]:
        m = i.guild.get_member(uid)
        if not m:
            continue
        p = await get_profile(i.guild_id, uid)
        if uid == i.user.id:
            desc = "أنت"
        elif p and p["private"]:
            desc = "🔒 مخفي"
        else:
            c = compat(vp, p)
            desc = f"توافق {c}%" if c is not None else "بدون بروفايل"
        label = ("👑 " if uid == post["host"] else "") + m.display_name[:90]
        opts.append(discord.SelectOption(label=label, value=str(uid), description=desc))
    if not opts:
        return await i.response.send_message("ما في لاعبين لعرضهم.", ephemeral=True)
    await i.response.send_message("اختر لاعب تشوف بروفايله:", view=_TeamView(opts), ephemeral=True)


class _TeamView(ui.View):
    def __init__(self, opts):
        super().__init__(timeout=300)
        sel = ui.Select(placeholder="اللاعبون في الفريق", options=opts)
        sel.callback = self._pick
        self.add_item(sel)

    async def _pick(self, i: discord.Interaction):
        m = i.guild.get_member(int(i.data["values"][0]))
        if not m:
            return await i.response.send_message("اللاعب ما عاد بالسيرفر.", ephemeral=True)
        await i.response.send_message(embed=await build_card(i.guild, m, i.user.id),
                                      view=CardView(m, i.user.id), ephemeral=True)