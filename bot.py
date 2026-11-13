"""
bot.py — GamerGuard
تحسينات:
  - logging رسمي (module-level) بدل print في كل مكان
  - إصلاح /lfg_list: يستخدم lfg_posts بدل الجدول القديم lfg
  - _handle_voice_message: يستخدم get_guild_voice_enabled من translation
  - تنظيف بسيط في on_message
"""

import os, asyncio, time, json, collections, logging, discord, uvicorn
from discord import app_commands, ui
from dotenv import load_dotenv

load_dotenv()

import db, moderation
import db_migration
from dashboard import make_app
from games import GAMES_BY_ID, GAMES
import translation as tr

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gg.bot")

# ── Discord intents ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.voice_states    = True
NOPING = discord.AllowedMentions.none()


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree   = app_commands.CommandTree(self)
        self.hist   = collections.defaultdict(lambda: collections.deque(maxlen=5))
        self.sem    = asyncio.Semaphore(5)
        self.tr_sem = asyncio.Semaphore(3)

    async def setup_hook(self):
        await db.init()
        await db_migration.migrate()
        await db.purge(int(os.getenv("RETENTION_DAYS", "30")))
        await self.tree.sync()
        cfg = uvicorn.Config(
            make_app(self),
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            log_level="warning",
        )
        asyncio.create_task(uvicorn.Server(cfg).serve())
        log.info("Bot setup complete")


bot = Bot()
T   = bot.tree


async def notify(guild, text):
    s  = await db.q("SELECT mod_channel FROM settings WHERE guild=?", (guild.id,), one=True)
    ch = s and guild.get_channel(s["mod_channel"])
    if ch:
        await ch.send(text, allowed_mentions=NOPING)


def rep_line(r):
    return f"⭐ السمعة: **{r[0]}/100** | تقييمات: {r[1]} | إنذارات: {r[2]} | بلاغات: {r[3]}"


# ════════════════════════════════════════════════════════════════
#  on_ready
# ════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    log.info("Bot ready: %s", bot.user)


# ════════════════════════════════════════════════════════════════
#  on_message  — مراقبة + ترجمة
# ════════════════════════════════════════════════════════════════
@bot.event
async def on_message(m: discord.Message):
    if m.author.bot or not m.guild:
        return

    # ── 1. ترجمة الرسائل الصوتية ────────────────────────────────
    if m.attachments:
        for att in m.attachments:
            ct = att.content_type or ""
            if ct.startswith("audio/") or att.filename.endswith(
                (".ogg", ".mp3", ".wav", ".m4a", ".opus")
            ):
                asyncio.create_task(_handle_voice_message(m, att))

    if not m.content:
        return

    h      = bot.hist[m.channel.id]
    before = list(h)
    h.append(f"{m.author.display_name}: {m.content[:200]}")

    # ── 2. مراقبة المحتوى ───────────────────────────────────────
    try:
        async with bot.sem:
            cfg = await db.get_guild_config(m.guild.id)
            res = await moderation.analyze(m.content, before, cfg=cfg)
    except Exception:
        log.exception("analyze error in guild %s", m.guild.id)
        res = {"verdict": "ok"}

    if res["verdict"] == "abuse":
        g, u, now = m.guild.id, m.author.id, int(time.time())
        prior = (await db.q(
            "SELECT COUNT(*) c FROM flags WHERE guild=? AND user=? AND fp=0 AND ts>?",
            (g, u, now - 7 * 86400), one=True,
        ))["c"]
        action = "warn" if prior == 0 else "alert"
        await db.q(
            "INSERT INTO flags(guild,user,channel,snippet,score,reason,action,ts) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (g, u, m.channel.id, m.content[:200], res["score"], res["reason"], action, now),
            commit=True,
        )
        if action == "warn":
            try:
                await m.author.send(
                    f"⚠️ تنبيه من «{m.guild.name}»: رسالتك بدت مسيئة "
                    f"({res['reason']}). هذا تحذير ودّي 🙏"
                )
            except discord.Forbidden:
                pass
        else:
            await notify(
                m.guild,
                f"🚨 {m.author.mention} تكررت منه إساءة في {m.channel.mention}: "
                f"{res['reason']}\n> {m.content[:150]}",
            )

    # ── 3. ترجمة النص التلقائية ─────────────────────────────────
    asyncio.create_task(_handle_text_translation(m))


# ════════════════════════════════════════════════════════════════
#  ترجمة نص
# ════════════════════════════════════════════════════════════════
async def _handle_text_translation(m: discord.Message):
    try:
        if not await tr.get_guild_translate_enabled(m.guild.id):
            return
        text = m.content.strip()
        if not tr.should_translate(text):
            return

        async with bot.tr_sem:
            result = await tr.detect_and_translate(text)

        if not result:
            return
        if result.get("is_english") or result.get("is_arabic"):
            return

        lang_name = result.get("lang_name_ar", result.get("detected_lang", ""))
        ar_text   = result.get("ar", "")
        en_text   = result.get("en", "")

        if not ar_text and not en_text:
            return

        lines = [f"🌐 **ترجمة تلقائية** | {lang_name}"]
        if ar_text:
            lines.append(f"🇸🇦 {ar_text}")
        if en_text:
            lines.append(f"🇬🇧 {en_text}")

        embed = discord.Embed(description="\n".join(lines), color=0x5B6AF0)
        embed.set_footer(text="GamerGuard Translate • /setlang لتخصيص لغتك")
        await m.reply(embed=embed, mention_author=False)

    except Exception:
        log.exception("text translation error")


# ════════════════════════════════════════════════════════════════
#  ترجمة صوت
# ════════════════════════════════════════════════════════════════
async def _handle_voice_message(m: discord.Message, att: discord.Attachment):
    try:
        # يستخدم الكاش عبر get_guild_voice_enabled
        if not await tr.get_guild_voice_enabled(m.guild.id):
            return

        audio_bytes = await att.read()
        if len(audio_bytes) > 25 * 1024 * 1024:
            return

        async with bot.tr_sem:
            transcript = await tr.transcribe_audio(audio_bytes, att.filename)

        if not transcript or len(transcript.strip()) < 2:
            return

        async with bot.tr_sem:
            translated = await tr.translate_text(transcript)

        ar_text = translated.get("ar", "") if translated else ""
        en_text = translated.get("en", "") if translated else ""

        lines = ["🎙️ **رسالة صوتية — نص تلقائي**",
                 f"📝 `{transcript[:300]}`"]
        if ar_text and ar_text.strip() != transcript.strip():
            lines.append(f"🇸🇦 {ar_text}")
        if en_text and en_text.strip() != transcript.strip():
            lines.append(f"🇬🇧 {en_text}")

        embed = discord.Embed(description="\n".join(lines), color=0x22C97A)
        embed.set_footer(text="GamerGuard Translate • Whisper AI")
        await m.reply(embed=embed, mention_author=False)

    except Exception:
        log.exception("voice translation error")


# ════════════════════════════════════════════════════════════════
#  LFG helpers
# ════════════════════════════════════════════════════════════════
AGE_OPTIONS = [
    discord.SelectOption(label="أي عمر",    value="any"),
    discord.SelectOption(label="13 – 15",   value="13-15"),
    discord.SelectOption(label="16 – 18",   value="16-18"),
    discord.SelectOption(label="19 – 24",   value="19-24"),
    discord.SelectOption(label="25 – 30",   value="25-30"),
    discord.SelectOption(label="+30",       value="30+"),
]

REP_OPTIONS = [
    discord.SelectOption(label="أي تقييم",        value="any"),
    discord.SelectOption(label="50+ (مقبول)",     value="50"),
    discord.SelectOption(label="60+ (جيد)",       value="60"),
    discord.SelectOption(label="75+ (ممتاز)",     value="75"),
    discord.SelectOption(label="90+ (مميز)",      value="90"),
]


def _lfg_embed(host_id, gname, emoji, needed, current, joined_ids, guild,
               done=False, filters=None):
    members = []
    host = guild.get_member(host_id)
    if host:
        members.append(f"👑 {host.display_name}")
    for jid in joined_ids:
        mem = guild.get_member(jid)
        if mem:
            members.append(f"• {mem.display_name}")

    color = discord.Color.green() if done else discord.Color.blurple()
    title = f"{emoji} {gname} — {'اكتمل الفريق! 🎉' if done else 'دوّر على فريق'}"
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="اللاعبون", value="\n".join(members) or "—", inline=True)
    embed.add_field(name="العدد",    value=f"{current} / {needed}",   inline=True)

    if filters:
        f = filters
        parts = []
        if f.get("age") and f["age"] != "any":
            parts.append(f"🎂 العمر: **{f['age']}**")
        rep = f.get("min_rep", "any")
        if rep and rep != "any":
            parts.append(f"⭐ التقييم: **{rep}+**")
        rank_from = f.get("rank_from")
        rank_to   = f.get("rank_to")
        if rank_from and rank_to:
            parts.append(f"🏅 الرانك: **{rank_from}** ← **{rank_to}**")
        elif rank_from:
            parts.append(f"🏅 الرانك: من **{rank_from}**")
        elif rank_to:
            parts.append(f"🏅 الرانك: حتى **{rank_to}**")
        if parts:
            embed.add_field(name="الشروط", value="\n".join(parts), inline=False)

    if not done:
        embed.set_footer(text="اضغط «انضم» للانضمام للفريق")
    return embed


async def _delete_vc_later(vc: discord.VoiceChannel, delay: int):
    await asyncio.sleep(delay)
    try:
        if len(vc.members) == 0:
            await vc.delete(reason="LFG room expired")
    except Exception:
        pass


def _parse_filters(post):
    try:
        return json.loads(post["filters"] or "{}")
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════════
#  LFGView
# ════════════════════════════════════════════════════════════════
class LFGView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="انضم 🎮", style=discord.ButtonStyle.success, custom_id="lfg_join")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        post = await db.q("SELECT * FROM lfg_posts WHERE message=? AND guild=?",
                          (interaction.message.id, interaction.guild_id), one=True)
        if not post or post["done"]:
            return await interaction.response.send_message("هالطلب انتهى أو ما لقيناه.", ephemeral=True)
        joined = json.loads(post["joined"] or "[]")
        uid = interaction.user.id
        if uid == post["host"]:
            return await interaction.response.send_message("أنت صاحب الطلب 😄", ephemeral=True)
        if uid in joined:
            return await interaction.response.send_message("أنت انضميت أصلاً ✅", ephemeral=True)
        filters = _parse_filters(post)
        if filters:
            rep_row = await db.reputation(interaction.guild_id, uid)
            min_rep = filters.get("min_rep", "any")
            if min_rep and min_rep != "any":
                if rep_row[0] < int(min_rep):
                    return await interaction.response.send_message(
                        f"⛔ تقييمك ({rep_row[0]}/100) أقل من الحد المطلوب ({min_rep}+).",
                        ephemeral=True,
                    )
        joined.append(uid)
        total  = 1 + len(joined)
        needed = post["needed"]
        await db.q("UPDATE lfg_posts SET joined=? WHERE id=?",
                   (json.dumps(joined), post["id"]), commit=True)
        game  = GAMES_BY_ID.get(post["game_id"], {})
        emoji = game.get("emoji", "🎮")
        gname = game.get("name",  post["game_id"])
        if total < needed:
            embed = _lfg_embed(post["host"], gname, emoji, needed, total,
                               joined, interaction.guild, filters=filters)
            await interaction.message.edit(embed=embed, view=self)
            await interaction.response.send_message(
                f"انضميت! ننتظر {needed - total} لاعب كمان.", ephemeral=True)
        else:
            await interaction.response.defer()
            all_ids  = [post["host"]] + joined
            mentions = " ".join(f"<@{i}>" for i in all_ids)
            vc = None
            lfg_cfg  = await db.get_lfg_settings(interaction.guild_id)
            category = None
            if lfg_cfg and lfg_cfg["vc_category"]:
                category = interaction.guild.get_channel(lfg_cfg["vc_category"])
            try:
                vc = await interaction.guild.create_voice_channel(
                    name=f"🎮 {gname} — فريق", category=category, user_limit=needed)
            except discord.Forbidden:
                pass
            moved, mentioned = [], []
            for mid in all_ids:
                member = interaction.guild.get_member(mid)
                if not member:
                    continue
                if vc and member.voice and member.voice.channel:
                    try:
                        await member.move_to(vc)
                        moved.append(member.mention)
                    except discord.Forbidden:
                        mentioned.append(member.mention)
                else:
                    mentioned.append(member.mention)
            embed = _lfg_embed(post["host"], gname, emoji, needed, total,
                               joined, interaction.guild, done=True, filters=filters)
            done_view = ui.View()
            done_view.add_item(ui.Button(label="اكتمل الفريق ✅",
                                         style=discord.ButtonStyle.secondary, disabled=True))
            await interaction.message.edit(embed=embed, view=done_view)
            ann = f"🎉 **اكتمل الفريق!** {emoji} **{gname}**\n{mentions}"
            if vc:
                ann += f"\n🔊 الروم جاهز: {vc.mention}"
                if mentioned:
                    ann += f"\n📢 {' '.join(mentioned)} — انضموا للروم يا شباب!"
            await interaction.channel.send(ann, allowed_mentions=discord.AllowedMentions(users=True))
            await db.q("UPDATE lfg_posts SET done=1 WHERE id=?", (post["id"],), commit=True)
            if vc:
                asyncio.create_task(_delete_vc_later(vc, delay=7200))

    @ui.button(label="✏️ تعديل", style=discord.ButtonStyle.primary, custom_id="lfg_edit_btn")
    async def edit_btn(self, interaction: discord.Interaction, button: ui.Button):
        post = await db.q("SELECT * FROM lfg_posts WHERE message=? AND guild=?",
                          (interaction.message.id, interaction.guild_id), one=True)
        if not post or post["done"]:
            return await interaction.response.send_message("هالطلب انتهى.", ephemeral=True)
        if interaction.user.id != post["host"]:
            return await interaction.response.send_message("بس صاحب الطلب يقدر يعدّل.", ephemeral=True)
        await interaction.response.send_message(
            "اختر ما تريد تعديله:", view=EditChoiceView(post), ephemeral=True)

    @ui.button(label="❌ إلغاء", style=discord.ButtonStyle.danger, custom_id="lfg_cancel_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: ui.Button):
        post = await db.q("SELECT * FROM lfg_posts WHERE message=? AND guild=?",
                          (interaction.message.id, interaction.guild_id), one=True)
        if not post or post["done"]:
            return await interaction.response.send_message("هالطلب انتهى أصلاً.", ephemeral=True)
        if interaction.user.id != post["host"]:
            return await interaction.response.send_message("بس صاحب الطلب يقدر يلغي.", ephemeral=True)
        await db.q("UPDATE lfg_posts SET done=1 WHERE id=?", (post["id"],), commit=True)
        game = GAMES_BY_ID.get(post["game_id"], {})
        embed = discord.Embed(
            title=f"{game.get('emoji','🎮')} {game.get('name', post['game_id'])} — ❌ ألغي الطلب",
            color=discord.Color.red())
        embed.set_footer(text="تم إلغاء هذا الطلب من صاحبه.")
        done_view = ui.View()
        done_view.add_item(ui.Button(label="ألغي الطلب ❌",
                                     style=discord.ButtonStyle.danger, disabled=True))
        await interaction.message.edit(embed=embed, view=done_view)
        await interaction.response.send_message("✅ تم إلغاء طلبك.", ephemeral=True)


# ════════════════════════════════════════════════════════════════
#  Edit views
# ════════════════════════════════════════════════════════════════
class EditChoiceView(ui.View):
    def __init__(self, post):
        super().__init__(timeout=60)
        self.post = post

    @ui.button(label="🎮 اللعبة",         style=discord.ButtonStyle.secondary)
    async def change_game(self, interaction, button):
        enabled = await db.get_guild_games(interaction.guild_id)
        options = [
            discord.SelectOption(label=GAMES_BY_ID[g]["name"], value=g,
                                 emoji=GAMES_BY_ID[g]["emoji"],
                                 description=GAMES_BY_ID[g]["category"],
                                 default=(g == self.post["game_id"]))
            for g in enabled if g in GAMES_BY_ID
        ]
        if not options:
            return await interaction.response.send_message("ما في ألعاب مفعّلة.", ephemeral=True)
        await interaction.response.send_message(
            "اختر اللعبة الجديدة:", view=GameChangeView(self.post, options), ephemeral=True)

    @ui.button(label="👥 عدد اللاعبين",   style=discord.ButtonStyle.secondary)
    async def change_players(self, interaction, button):
        await interaction.response.send_message(
            "اختر العدد الجديد:", view=PlayersChangeView(self.post), ephemeral=True)

    @ui.button(label="🎂 العمر المطلوب",  style=discord.ButtonStyle.secondary)
    async def change_age(self, interaction, button):
        await interaction.response.send_message(
            "اختر الفئة العمرية:", view=AgeChangeView(self.post), ephemeral=True)

    @ui.button(label="⭐ الحد الأدنى للتقييم", style=discord.ButtonStyle.secondary)
    async def change_rep(self, interaction, button):
        await interaction.response.send_message(
            "اختر الحد الأدنى للتقييم:", view=RepChangeView(self.post), ephemeral=True)

    @ui.button(label="🏅 الرانك المطلوب", style=discord.ButtonStyle.secondary)
    async def change_rank(self, interaction, button):
        ranks = GAMES_BY_ID.get(self.post["game_id"], {}).get("ranks", [])
        if not ranks:
            return await interaction.response.send_message(
                "هاللعبة ما عندها رانكات رسمية.", ephemeral=True)
        await interaction.response.send_message(
            "اختر نطاق الرانك:", view=RankChangeView(self.post), ephemeral=True)


class GameChangeView(ui.View):
    def __init__(self, post, options):
        super().__init__(timeout=60)
        self.post = post
        sel = ui.Select(placeholder="اختر اللعبة...", options=options)
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        new_id = self._sel.values[0]
        post   = self.post
        await db.q("UPDATE lfg_posts SET game_id=? WHERE id=?", (new_id, post["id"]), commit=True)
        filters   = _parse_filters(post)
        new_ranks = GAMES_BY_ID.get(new_id, {}).get("ranks", [])
        if filters.get("rank_from") not in new_ranks:
            filters.pop("rank_from", None)
        if filters.get("rank_to") not in new_ranks:
            filters.pop("rank_to", None)
        await db.q("UPDATE lfg_posts SET filters=? WHERE id=?",
                   (json.dumps(filters), post["id"]), commit=True)
        game   = GAMES_BY_ID.get(new_id, {})
        joined = json.loads(post["joined"] or "[]")
        ch     = interaction.guild.get_channel(post["channel"])
        if ch:
            try:
                msg = await ch.fetch_message(post["message"])
                embed = _lfg_embed(post["host"], game.get("name", new_id),
                                   game.get("emoji", "🎮"), post["needed"],
                                   1 + len(joined), joined, interaction.guild, filters=filters)
                await msg.edit(embed=embed, view=LFGView())
            except (discord.NotFound, discord.Forbidden):
                pass
        await interaction.response.send_message(
            f"✅ تغيّرت اللعبة إلى {game.get('emoji','')} **{game.get('name', new_id)}**",
            ephemeral=True)


class PlayersChangeView(ui.View):
    def __init__(self, post):
        super().__init__(timeout=60)
        self.post = post
        joined = json.loads(post["joined"] or "[]")
        self.current_count = 1 + len(joined)
        options = [
            discord.SelectOption(label="لاعبان (أنا + 1)", value="2", default=post["needed"]==2),
            discord.SelectOption(label="3 لاعبين",          value="3", default=post["needed"]==3),
            discord.SelectOption(label="4 لاعبين",          value="4", default=post["needed"]==4),
            discord.SelectOption(label="5 لاعبين",          value="5", default=post["needed"]==5),
        ]
        sel = ui.Select(placeholder="اختر عدد اللاعبين...", options=options)
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        new_needed = int(self._sel.values[0])
        post = self.post
        if new_needed < self.current_count:
            return await interaction.response.send_message(
                f"⚠️ في {self.current_count} لاعبين انضموا، ما تقدر تخفض.", ephemeral=True)
        await db.q("UPDATE lfg_posts SET needed=? WHERE id=?", (new_needed, post["id"]), commit=True)
        game    = GAMES_BY_ID.get(post["game_id"], {})
        joined  = json.loads(post["joined"] or "[]")
        filters = _parse_filters(post)
        ch = interaction.guild.get_channel(post["channel"])
        if ch:
            try:
                msg = await ch.fetch_message(post["message"])
                embed = _lfg_embed(post["host"], game.get("name", post["game_id"]),
                                   game.get("emoji", "🎮"), new_needed,
                                   self.current_count, joined, interaction.guild, filters=filters)
                await msg.edit(embed=embed, view=LFGView())
            except (discord.NotFound, discord.Forbidden):
                pass
        await interaction.response.send_message(
            f"✅ تغيّر العدد إلى **{new_needed}** لاعبين.", ephemeral=True)


class AgeChangeView(ui.View):
    def __init__(self, post):
        super().__init__(timeout=60)
        self.post = post
        filters = _parse_filters(post)
        cur_age = filters.get("age", "any")
        opts = [discord.SelectOption(label=o.label, value=o.value, default=(o.value == cur_age))
                for o in AGE_OPTIONS]
        sel = ui.Select(placeholder="اختر الفئة العمرية...", options=opts)
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        post    = self.post
        filters = _parse_filters(post)
        filters["age"] = self._sel.values[0]
        await db.q("UPDATE lfg_posts SET filters=? WHERE id=?",
                   (json.dumps(filters), post["id"]), commit=True)
        await _refresh_embed(interaction, post, filters)
        await interaction.response.send_message(
            f"✅ الفئة العمرية: **{self._sel.values[0]}**", ephemeral=True)


class RepChangeView(ui.View):
    def __init__(self, post):
        super().__init__(timeout=60)
        self.post = post
        filters  = _parse_filters(post)
        cur_rep  = filters.get("min_rep", "any")
        opts = [discord.SelectOption(label=o.label, value=o.value, default=(o.value == cur_rep))
                for o in REP_OPTIONS]
        sel = ui.Select(placeholder="اختر الحد الأدنى للتقييم...", options=opts)
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        post    = self.post
        filters = _parse_filters(post)
        filters["min_rep"] = self._sel.values[0]
        await db.q("UPDATE lfg_posts SET filters=? WHERE id=?",
                   (json.dumps(filters), post["id"]), commit=True)
        await _refresh_embed(interaction, post, filters)
        await interaction.response.send_message(
            f"✅ الحد الأدنى للتقييم: **{self._sel.values[0]}**", ephemeral=True)


class RankChangeView(ui.View):
    def __init__(self, post):
        super().__init__(timeout=120)
        self.post    = post
        self.filters = _parse_filters(post)
        ranks = GAMES_BY_ID.get(post["game_id"], {}).get("ranks", [])
        chunk = ranks[:25]
        from_opts = [discord.SelectOption(label=r, value=r,
                     default=(r == self.filters.get("rank_from"))) for r in chunk]
        to_opts   = [discord.SelectOption(label=r, value=r,
                     default=(r == self.filters.get("rank_to")))   for r in chunk]
        sel_from = ui.Select(placeholder="🏅 من رانك...", options=from_opts, custom_id="rank_from")
        sel_to   = ui.Select(placeholder="🏅 إلى رانك...", options=to_opts,   custom_id="rank_to")
        sel_from.callback = self._cb_from
        sel_to.callback   = self._cb_to
        self.add_item(sel_from)
        self.add_item(sel_to)
        self._from = sel_from
        self._to   = sel_to
        self._chosen_from = self.filters.get("rank_from")
        self._chosen_to   = self.filters.get("rank_to")

    async def _cb_from(self, interaction):
        self._chosen_from = self._from.values[0]
        await interaction.response.send_message(
            f"✅ من رانك: **{self._chosen_from}** — اختر «إلى رانك» الآن.", ephemeral=True)

    async def _cb_to(self, interaction):
        self._chosen_to = self._to.values[0]
        post    = self.post
        filters = self.filters
        filters["rank_from"] = self._chosen_from or self._chosen_to
        filters["rank_to"]   = self._chosen_to
        await db.q("UPDATE lfg_posts SET filters=? WHERE id=?",
                   (json.dumps(filters), post["id"]), commit=True)
        await _refresh_embed(interaction, post, filters)
        await interaction.response.send_message(
            f"✅ نطاق الرانك: **{filters['rank_from']}** ← **{filters['rank_to']}**", ephemeral=True)


async def _refresh_embed(interaction, post, filters):
    game   = GAMES_BY_ID.get(post["game_id"], {})
    joined = json.loads(post["joined"] or "[]")
    ch = interaction.guild.get_channel(post["channel"])
    if ch:
        try:
            msg = await ch.fetch_message(post["message"])
            embed = _lfg_embed(post["host"], game.get("name", post["game_id"]),
                               game.get("emoji", "🎮"), post["needed"],
                               1 + len(joined), joined, interaction.guild, filters=filters)
            await msg.edit(embed=embed, view=LFGView())
        except (discord.NotFound, discord.Forbidden):
            pass


# ════════════════════════════════════════════════════════════════
#  LFG Wizard
# ════════════════════════════════════════════════════════════════
class LFGWizard:
    def __init__(self, guild_id, user_id, players):
        self.guild_id  = guild_id
        self.user_id   = user_id
        self.players   = players
        self.game_id   = None
        self.age       = "any"
        self.min_rep   = "any"
        self.rank_from = None
        self.rank_to   = None


class WizardGameView(ui.View):
    def __init__(self, wizard, options):
        super().__init__(timeout=120)
        self.wizard = wizard
        sel = ui.Select(placeholder="اختر اللعبة...", options=options)
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        await interaction.response.defer()
        self.wizard.game_id = self._sel.values[0]
        await interaction.edit_original_response(
            content="🎂 اختر الفئة العمرية للاعبين:",
            view=WizardAgeView(self.wizard))


class WizardAgeView(ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=120)
        self.wizard = wizard
        sel = ui.Select(placeholder="الفئة العمرية...", options=list(AGE_OPTIONS))
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        await interaction.response.defer()
        self.wizard.age = self._sel.values[0]
        await interaction.edit_original_response(
            content="⭐ الحد الأدنى للتقييم المطلوب:",
            view=WizardRepView(self.wizard))


class WizardRepView(ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=120)
        self.wizard = wizard
        sel = ui.Select(placeholder="التقييم الأدنى...", options=list(REP_OPTIONS))
        sel.callback = self._cb
        self.add_item(sel)
        self._sel = sel

    async def _cb(self, interaction):
        await interaction.response.defer()
        self.wizard.min_rep = self._sel.values[0]
        ranks = GAMES_BY_ID.get(self.wizard.game_id, {}).get("ranks", [])
        if ranks:
            await interaction.edit_original_response(
                content="🏅 اختر نطاق الرانك (اختياري):",
                view=WizardRankView(self.wizard))
        else:
            await _wizard_finish(interaction, self.wizard)


class WizardRankView(ui.View):
    def __init__(self, wizard):
        super().__init__(timeout=120)
        self.wizard = wizard
        ranks = GAMES_BY_ID.get(wizard.game_id, {}).get("ranks", [])[:25]
        from_opts = [discord.SelectOption(label="بدون تحديد", value="any")] + \
                    [discord.SelectOption(label=r, value=r) for r in ranks]
        to_opts   = [discord.SelectOption(label="بدون تحديد", value="any")] + \
                    [discord.SelectOption(label=r, value=r) for r in ranks]
        self._sel_from = ui.Select(placeholder="🏅 من رانك...", options=from_opts)
        self._sel_to   = ui.Select(placeholder="🏅 إلى رانك...", options=to_opts)
        self._sel_from.callback = self._noop
        self._sel_to.callback   = self._noop
        self.add_item(self._sel_from)
        self.add_item(self._sel_to)

    async def _noop(self, interaction):
        await interaction.response.defer()

    @ui.button(label="✅ تأكيد وإنشاء الطلب", style=discord.ButtonStyle.success, row=2)
    async def confirm(self, interaction, button):
        rf = self._sel_from.values[0] if self._sel_from.values else "any"
        rt = self._sel_to.values[0]   if self._sel_to.values   else "any"
        self.wizard.rank_from = None if rf == "any" else rf
        self.wizard.rank_to   = None if rt == "any" else rt
        await _wizard_finish(interaction, self.wizard)

    @ui.button(label="تخطّي الرانك", style=discord.ButtonStyle.secondary, row=2)
    async def skip(self, interaction, button):
        await _wizard_finish(interaction, self.wizard)


async def _wizard_finish(interaction: discord.Interaction, wizard: LFGWizard):
    game = GAMES_BY_ID[wizard.game_id]
    filters = {
        "age":       wizard.age,
        "min_rep":   wizard.min_rep,
        "rank_from": wizard.rank_from,
        "rank_to":   wizard.rank_to,
    }
    lfg_cfg   = await db.get_lfg_settings(wizard.guild_id)
    target_ch = interaction.channel
    if lfg_cfg and lfg_cfg["lfg_channel"]:
        ch = interaction.guild.get_channel(lfg_cfg["lfg_channel"])
        if ch:
            target_ch = ch
    embed = _lfg_embed(wizard.user_id, game["name"], game["emoji"],
                       wizard.players, 1, [], interaction.guild, filters=filters)
    msg = await target_ch.send(embed=embed, view=LFGView())
    await db.q(
        "INSERT INTO lfg_posts(guild,channel,message,host,game_id,needed,joined,filters,ts) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (wizard.guild_id, target_ch.id, msg.id, wizard.user_id,
         wizard.game_id, wizard.players, "[]", json.dumps(filters), int(time.time())),
        commit=True,
    )
    reply = f"✅ نزل طلبك في {target_ch.mention}!" if target_ch != interaction.channel else "✅ نزل طلبك!"
    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(content=reply, view=None)
        else:
            await interaction.response.edit_message(content=reply, view=None)
    except Exception:
        try:
            await interaction.followup.send(reply, ephemeral=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
#  Slash Commands
# ════════════════════════════════════════════════════════════════

# ── ترجمة ─────────────────────────────────────────────────────
@T.command(name="setlang", description="حدد لغتك المفضلة للترجمة")
@app_commands.describe(lang="كود اللغة مثل: ar, en, fr, tr, ru, es, de ...")
async def setlang(interaction: discord.Interaction, lang: str):
    lang = lang.strip().lower()[:5]
    if lang not in tr.SUPPORTED_LANGS:
        supported = ", ".join(f"`{k}` {v}" for k, v in tr.SUPPORTED_LANGS.items())
        return await interaction.response.send_message(
            f"❌ كود لغة غير معروف.\n**اللغات المدعومة:**\n{supported}", ephemeral=True)
    await tr.set_user_lang(interaction.guild_id, interaction.user.id, lang)
    lang_name = tr.SUPPORTED_LANGS[lang]
    await interaction.response.send_message(
        f"✅ تم حفظ لغتك المفضلة: **{lang_name}** (`{lang}`)\n"
        f"البوت سيترجم الرسائل بلغات أخرى تلقائياً.", ephemeral=True)


@T.command(name="translate", description="ترجم رسالة محددة يدوياً")
@app_commands.describe(text="النص المراد ترجمته")
async def translate_cmd(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=False)
    result = await tr.detect_and_translate(text)
    if not result:
        return await interaction.followup.send("⚠️ تعذّرت الترجمة، جرّب مرة ثانية.", ephemeral=True)
    lang_name = result.get("lang_name_ar", result.get("detected_lang", ""))
    ar_text   = result.get("ar", "")
    en_text   = result.get("en", "")
    embed = discord.Embed(title="🌐 ترجمة", color=0x5B6AF0)
    embed.add_field(name=f"النص الأصلي ({lang_name})", value=f"```{text[:500]}```", inline=False)
    if ar_text:
        embed.add_field(name="🇸🇦 العربية", value=ar_text[:500], inline=False)
    if en_text:
        embed.add_field(name="🇬🇧 English", value=en_text[:500], inline=False)
    embed.set_footer(text="GamerGuard Translate")
    await interaction.followup.send(embed=embed)


# ── LFG ───────────────────────────────────────────────────────
@T.command(description="دوّر على فريق للعب")
@app_commands.describe(players="عدد اللاعبين الكلي المطلوب (أنت + غيرك)")
@app_commands.choices(players=[
    app_commands.Choice(name="لاعبان (أنا + 1)", value=2),
    app_commands.Choice(name="3 لاعبين",          value=3),
    app_commands.Choice(name="4 لاعبين",          value=4),
    app_commands.Choice(name="5 لاعبين",          value=5),
])
async def lfg(interaction: discord.Interaction, players: int):
    enabled = await db.get_guild_games(interaction.guild_id)
    if not enabled:
        return await interaction.response.send_message(
            "⚠️ ما في ألعاب مفعّلة. اطلب من الأدمن يفعّل ألعاب من لوحة التحكم.", ephemeral=True)
    options = [
        discord.SelectOption(label=GAMES_BY_ID[g]["name"], value=g,
                             emoji=GAMES_BY_ID[g]["emoji"],
                             description=GAMES_BY_ID[g]["category"])
        for g in enabled if g in GAMES_BY_ID
    ]
    wizard = LFGWizard(interaction.guild_id, interaction.user.id, players)
    await interaction.response.send_message(
        "🎮 اختر اللعبة:", view=WizardGameView(wizard, options), ephemeral=True)


@T.command(description="بلّغ عن لاعب")
async def report(i: discord.Interaction, user: discord.Member, reason: str):
    await db.q("INSERT INTO reports VALUES(?,?,?,?,?)",
               (i.guild_id, i.user.id, user.id, reason[:200], int(time.time())), commit=True)
    await i.response.send_message("وصل بلاغك للمشرفين ✅", ephemeral=True)
    await notify(i.guild, f"📢 بلاغ على {user.mention} من {i.user.mention}: {reason[:200]}")


@T.command(description="قيّم لاعب بعد الجلسة (1-5)")
async def rate(i: discord.Interaction, user: discord.Member, stars: app_commands.Range[int, 1, 5]):
    if user.id == i.user.id or user.bot:
        return await i.response.send_message("ما بتقدر تقيّم هالحساب", ephemeral=True)
    now = int(time.time())
    dup = await db.q(
        "SELECT 1 FROM ratings WHERE guild=? AND rater=? AND target=? AND ts>?",
        (i.guild_id, i.user.id, user.id, now - 86400), one=True)
    if dup:
        return await i.response.send_message("قيّمته اليوم، جرّب بكرة", ephemeral=True)
    await db.q("INSERT INTO ratings VALUES(?,?,?,?,?)",
               (i.guild_id, i.user.id, user.id, stars, now), commit=True)
    await i.response.send_message(f"تم تقييم {user.display_name}: {'⭐' * stars}", ephemeral=True)


@T.command(description="شوف سمعة لاعب")
async def profile(i: discord.Interaction, user: discord.Member):
    await i.response.send_message(
        f"**{user.display_name}**\n{rep_line(await db.reputation(i.guild_id, user.id))}",
        allowed_mentions=NOPING)


@T.command(description="شوف مين يدوّر على فريق (آخر 24 ساعة)")
@app_commands.describe(game="اللعبة", min_rep="أقل سمعة مقبولة (0-100)")
async def lfg_list(i: discord.Interaction, game: str, min_rep: int = 0):
    """
    إصلاح: الآن يستخدم lfg_posts بدل الجدول القديم lfg.
    يعرض الطلبات المفتوحة فقط (done=0) خلال آخر 24 ساعة.
    """
    rows = await db.q(
        "SELECT * FROM lfg_posts "
        "WHERE guild=? AND done=0 AND ts>? ORDER BY ts DESC LIMIT 20",
        (i.guild_id, int(time.time()) - 86400),
    )
    out = []
    for x in rows:
        game_data = GAMES_BY_ID.get(x["game_id"], {})
        if game.lower() not in game_data.get("name", x["game_id"]).lower():
            continue
        r = await db.reputation(i.guild_id, x["host"])
        if r[0] < min_rep:
            continue
        joined = json.loads(x["joined"] or "[]")
        current = 1 + len(joined)
        emoji   = game_data.get("emoji", "🎮")
        gname   = game_data.get("name", x["game_id"])
        out.append(
            f"{emoji} **{gname}** — <@{x['host']}> "
            f"({current}/{x['needed']}) ⭐{r[0]}"
        )
    await i.response.send_message(
        "\n".join(out[:10]) or "ما في حدا يدوّر هلأ. انشر طلبك بـ /lfg",
        allowed_mentions=NOPING,
    )


@T.command(description="حدّد روم المشرفين لاستقبال التنبيهات")
@app_commands.default_permissions(manage_guild=True)
async def setup(i: discord.Interaction, channel: discord.TextChannel):
    await db.q(
        "INSERT INTO settings VALUES(?,?) ON CONFLICT(guild) DO UPDATE SET mod_channel=excluded.mod_channel",
        (i.guild_id, channel.id), commit=True)
    await i.response.send_message(f"تمام، التنبيهات رح توصل لـ {channel.mention}", ephemeral=True)


@T.command(description="إحصائيات آخر 7 أيام (للمشرفين)")
@app_commands.default_permissions(manage_messages=True)
async def stats(i: discord.Interaction):
    w = int(time.time()) - 7 * 86400
    f  = (await db.q("SELECT COUNT(*) c, SUM(fp) p FROM flags WHERE guild=? AND ts>?",   (i.guild_id, w), one=True))
    rp = (await db.q("SELECT COUNT(*) c FROM reports WHERE guild=? AND ts>?",             (i.guild_id, w), one=True))["c"]
    await i.response.send_message(
        f"📊 إنذارات: **{f['c']}** | إنذارات كاذبة: **{f['p'] or 0}** | بلاغات: **{rp}**",
        ephemeral=True)


@T.command(description="شو بيجمع البوت من بيانات؟")
async def privacy(i: discord.Interaction):
    await i.response.send_message(
        "🔒 البوت بيفحص الرسائل النصية ويترجمها تلقائياً. الرسائل العادية ما بتنحفظ. "
        "الرسائل المصنّفة مسيئة بنحفظ منها مقتطف (200 حرف). "
        "تقييمات/بلاغات اللاعبين وتفضيلات اللغة محفوظة. "
        "النص ينرسل لـ OpenAI للتصنيف والترجمة. ما في حظر تلقائي أبداً.",
        ephemeral=True)


bot.add_view(LFGView())
bot.run(os.environ["DISCORD_TOKEN"], log_handler=None)  # logging مُعدّ يدوياً فوق