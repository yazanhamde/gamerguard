# GamerGuard، بوت إشراف ذكي للمجتمعات العربية

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Yazan%20Hamdi-blue?logo=linkedin)](https://www.linkedin.com/in/yazan-hamdi/)

## التشغيل
1. Discord Developer Portal: أنشئ بوت، فعّل **Message Content Intent** و **Server Members Intent**، وادعُه بصلاحية `bot` + `applications.commands`.
2. `cp .env.example .env` واملأ DISCORD_TOKEN و OPENAI_API_KEY وغيّر DASH_PASSWORD و SECRET_KEY.
3. `pip install -r requirements.txt` ثم `python bot.py`
4. بالسيرفر: `/setup #روم-المشرفين` ثم جرّب `/report` `/rate` `/profile` `/lfg` `/lfg_list`.
5. اللوحة: http://localhost:8000 (حط خلفها HTTPS قبل ما تعرضها للعامة وفعّل `HTTPS_ONLY=1`).

## حسابات اللوحة
- أول تشغيل بينشئ حساب **admin** بكلمة السر من `DASH_PASSWORD` (لو ضعيفة أو افتراضية، بيجبرك تغيّرها عند أول دخول).
- **المدير** بيضيف المشرفين من تبويب «المستخدمون» (كلمة سر مؤقتة بتظهر مرة وحدة، والمشرف لازم يغيّرها عند أول دخول).
- **المشرف**: الإنذارات، البلاغات، سجل اللاعب، الملاحظات. **المدير**: كل شي + إدارة المستخدمين + سجل النشاط.
- تعطيل مستخدم أو إعادة تعيين كلمة سره بينهي جلساته فوراً. كل إجراء بينسجّل في «سجل النشاط».

## المنطق
رسالة → فلتر OpenAI المجاني → (عند الشك فقط) GPT مع آخر 5 رسائل → أول مخالفة تحذير خاص، التكرار تنبيه للمشرفين. **لا حظر تلقائي.**
عدّل SEED في moderation.py والعتبات MOD_LOW / MOD_HIGH حسب مجتمعك، وحدّد حد إنفاق شهري في لوحة OpenAI.

## cPanel
البوت لازم يضل شغال 24/7. على استضافة مشتركة غالباً بتنقتل العملية، فاستخدم VPS أو Railway، وخلّي cPanel للموقع وصفحة الخصوصية.
---

## 👨‍💻 المطوّر
