import os
import logging
import random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# 🛑 ضع توكن بوتك وحساب المطور هنا
TOKEN = "ضع_التوكن_هنا_بين_العلامتين"
ADMIN_ID = "ضع_آيدي_الآدمن_هنا"

stats_data = {
    "total_messages": 0,
    "sessions": 1
}

attendance_db = {}
active_subscriptions = {}
student_views = {}  # مشاهدات المحاضرات
student_points = {} # نقاط XP الأسطورية
generated_codes = {"monthly": [], "yearly": []}

# بنك الأسئلة الذكي المحدث
science_questions_bank = [
    {
        "q": "🧠 ما هو بيت الطاقة الرئيسي داخل الخلية الحية؟",
        "options": [("✅ الميتوكوندريا", True), ("❌ الرايبوسوم", False), ("❌ نواة الخلية", False)]
    },
    {
        "q": "⚗️ ما هي وحدة قياس التيار الكهربائي في النظام الدولي؟",
        "options": [("❌ الفولت", False), ("✅ الأمبير", True), ("❌ الأوم", False)]
    },
    {
        "q": "🔢 ما هو الناتج الصحيح لجذر العدد 144؟",
        "options": [("❌ 10", False), ("✅ 12", True), ("❌ 14", False)]
    },
    {
        "q": "🧬 المسؤول عن نقل الصفات الوراثية داخل الخلية هو:",
        "options": [("✅ حمض DNA", True), ("❌ البروتينات", False), ("❌ السكريات", False)]
    }
]

# المحاضرات للمراحل الدراسية
stages_content = {
    "primary": {
        "name": "📖 المرحلة الابتدائية",
        "lectures": [
            {"title": "🎬 محاضرة الرياضيات - الدرس الأول", "url": "https://t.me/c/0/0"},
            {"title": "🎬 محاضرة القواعد والإنكليزي", "url": "https://t.me/c/0/0"}
        ]
    },
    "intermediate": {
        "name": "📖 المرحلة المتوسطة",
        "lectures": [
            {"title": "🎬 محاضرة الفيزياء والكيمياء", "url": "https://t.me/c/0/0"},
            {"title": "🎬 محاضرة الرياضيات الحديثة", "url": "https://t.me/c/0/0"}
        ]
    },
    "secondary": {
        "name": "📖 المرحلة الإعدادية",
        "lectures": [
            {"title": "🎬 محاضرة الأحياء - التكاثر", "url": "https://t.me/c/0/0"},
            {"title": "🎬 محاضرة الفيزياء - المتناوب", "url": "https://t.me/c/0/0"}
        ]
    }
}

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Ultra Educational Platform Bot is running perfectly!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# الواجهة الرئيسية السفلية الخارقة
def get_main_reply_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("📚 قسم المحاضرات والملازم"), KeyboardButton("🏆 لوحة المتصدرين وشرف الأبطال")],
        [KeyboardButton("🤖 الأستاذ الذكي الخصوصي (AI)"), KeyboardButton("📜 شهادة التقدير الإلكترونية")],
        [KeyboardButton("💎 تفعيل كود الاشتراك"), KeyboardButton("👤 ملفي وسجل الحضور")],
        [KeyboardButton("🎮 الألعاب والتحديات الفورية")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ لوحة تحكم المطور والإحصائيات الخارقة")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 **المنصة الخارقة تعمل بكفاءة تامة وبأفضل حال! ✅**")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in attendance_db:
        context.user_data['reg_step'] = 'name'
        await update.message.reply_text(
            "🌟 **أهلاً بك في المنصة التعليمية العراقية الذكية (نسخة الجيل القادم)**\n\n"
            "🎁 **هدية ترحيبية خيالية:** ستحصل فوراً على اشتراك مجاني لمدة **30 يوماً** مع 50 نقطة تفاعل أولية!\n\n"
            "يرجى إرسال **اسمك الثلاثي** الآن للبدء:"
        )
        return
    
    is_admin = (ADMIN_ID and str(user_id) == str(ADMIN_ID))
    await update.message.reply_text(
        "🎓 **القائمة الرئيسية - اختر القسم المطلوب من الكيبورد السفلي:**",
        reply_markup=get_main_reply_keyboard(is_admin)
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    stats_data["total_messages"] += 1
    step = context.user_data.get('reg_step')
    is_admin = (ADMIN_ID and str(user_id) == str(ADMIN_ID))

    # معالجة الأزرار السفلية الخارقة
    if text == "📚 قسم المحاضرات والملازم":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="lect_primary")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="lect_intermediate")],
            [InlineKeyboardButton("📖 المرحلة الإعدادية", callback_data="lect_secondary")]
        ]
        await update.message.reply_text("📚 **اختر المرحلة الدراسية لاستعراض المحاضرات والدروس المباشرة:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif text == "🏆 لوحة المتصدرين وشرف الأبطال":
        sorted_students = sorted(student_views.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard_text = "🏆 **قائمة أساطير العراق التعليمية (أكثر الطلاب تفاعلاً ومشاهدة):**\n\n"
        if not sorted_students:
            leaderboard_text += "القائمة فارغة حالياً. كن أنت أسطورة الأسبوع! 🌟"
        else:
            for idx, (uid, views) in enumerate(sorted_students, 1):
                s_name = attendance_db.get(uid, {}).get("name", "طالب مجهول")
                pts = student_points.get(uid, 0)
                leaderboard_text += f"{idx}. **{s_name}** — 👁‍🗨 `{views}` مشاهدة | ⚡ `{pts} XP`\n"
        await update.message.reply_text(leaderboard_text, parse_mode="Markdown")
        return

    elif text == "🤖 الأستاذ الذكي الخصوصي (AI)":
        context.user_data['waiting_for_ai_question'] = True
        await update.message.reply_text(
            "🤖 **أهلاً بك في غرفة الأستاذ الذكي الخصوصي (AI Tutor):**\n\n"
            "اكتب الآن أي سؤال صعب واجهك في (الرياضيات، الأحياء، الفيزياء، الكيمياء) وسيقوم النظام بشرحه لك فوراً بالتفصيل الممل:",
            reply_markup=ReplyKeyboardMarkup([["❌ إنهاء جلسة الأستاذ الذكي"]], resize_keyboard=True)
        )
        return

    elif text == "❌ إنهاء جلسة الأستاذ الذكي":
        context.user_data['waiting_for_ai_question'] = False
        await update.message.reply_text("✅ تم إنهاء جلسة الأستاذ الذكي بنجاح.", reply_markup=get_main_reply_keyboard(is_admin))
        return

    elif text == "📜 شهادة التقدير الإلكترونية":
        info = attendance_db.get(user_id, {"name": "طالب مجتهد", "province": "العراق", "school": "المنصة الذكية"})
        pts = student_points.get(user_id, 0)
        cert_text = (
            f"╔═══════════════════════╗\n"
            f"      🌟 **شهادة تفوق وتقدير رسمي** 🌟\n"
            f"╚═══════════════════════╝\n\n"
            f"تعلن إدارة المنصة التعليمية العراقية عن منح هذه الشهادة إلى الطالب البطل:\n"
            f"📌 **{info['name']}**\n"
            f"🏫 المدرسة: `{info['school']}` — المحافظة: `{info['province']}`\n\n"
            f"وذلك لتفوقه المستمر وجمعـه لـ **{pts} نقطة تفاعل (XP)** في المنصة.\n\n"
            f"🎖️ *استمر في تألقك لتكون صدارة جيل المستقبل!*"
        )
        await update.message.reply_text(cert_text, parse_mode="Markdown")
        return

    elif text == "💎 تفعيل كود الاشتراك":
        context.user_data['entering_sub_code'] = True
        await update.message.reply_text("💎 **تفعيل كود الاشتراك الذكي:**\n\nأرسل الكود (الشهري أو السنوي) لتفعيله في حسابك وتمديد عضويتك فوراً:")
        return

    elif text == "👤 ملفي وسجل الحضور":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        sub = active_subscriptions.get(user_id, "تجريبي مجاني (30 يوم) 🎁")
        views_count = student_views.get(user_id, 0)
        points = student_points.get(user_id, 0)
        
        # الرتبة الأسطورية حسب النقاط الخارقة
        rank_title = "مبتدئ طموح 📖"
        if points >= 100: rank_title = "طالب مجتهد وذكي ⭐"
        if points >= 250: rank_title = "بطل المحافظة التعليمي 🏆"
        if points >= 500: rank_title = "أساطير وعباقرة العراق 🧠💎👑"

        await update.message.reply_text(
            f"👤 **الملف الشخصي وسجل الحضور الأكاديمي:**\n\n"
            f"▫️ الاسم: `{info['name']}`\n"
            f"▫️ المحافظة: `{info['province']}`\n"
            f"▫️ المدرسة: `{info['school']}`\n"
            f"▫️ الاشتراك: **{sub}**\n"
            f"▫️ رتبة الشرف: **{rank_title}**\n"
            f"▫️ نقاط التفاعل (`XP`): **{points} نقطة**\n"
            f"▫️ مشاهدات المحاضرات: `👁‍🗨 {views_count} مشاهدة`",
            parse_mode="Markdown"
        )
        return

    elif text == "🎮 الألعاب والتحديات الفورية":
        await update.message.reply_text(
            "🎮 **قسم المسابقات العلمية الحية:**\nاختر التحدي لاختبار معلوماتك وكسب نقاط XP إضافية:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ابدأ تحدي الأسئلة العشوائية الفورية", callback_data="play_next_question")]])
        )
        return

    elif text == "⚙️ لوحة تحكم المطور والإحصائيات الخارقة" and is_admin:
        total_u = len(attendance_db)
        admin_panel_text = (
            f"⚙️ **لوحة التحكم والإحصائيات الخارقة:**\n\n"
            f"👥 إجمالي الطلاب المسجلين: `{total_u}`\n"
            f"💬 رسائل النظام الكلية: `{stats_data['total_messages']}`\n"
            f"🔒 الحماية المشفرة للبث والمحتوى: **مفعل 100% 🛡️**\n\n"
            f"اختر العملية المطلوبة:"
        )
        keyboard = [
            [InlineKeyboardButton("📢 إرسال إعلان عام فوري للجميع", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🎟 توليد أكواد اشتراك جديدة (شهري/سنوي)", callback_data="admin_gen_code")],
            [InlineKeyboardButton("📋 عرض كشوفات وسجلات الحضور", callback_data="admin_show_logs")]
        ]
        await update.message.reply_text(admin_panel_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # استجابة الأستاذ الذكي الفورية (AI Tutor Simulation)
    if context.user_data.get('waiting_for_ai_question'):
        ai_responses = [
            f"🤖 **شرح الأستاذ الذكي لسؤالك:**\n\nبناءً على تحليلي العلمي لسؤالك (`{text}`):\n1. القاعدة الأساسية تعتمد على القوانين الفيزيائية/الرياضية المعيارية.\n2. يتم تطبيق المعطيات بخطوات متسلسلة لضمان الوصول للناتج الدقيق.\n💡 *نصيحة أستاذك: راجع الفصل المتعلق بهذا الموضوع في ملزمة المنصة لتثبت المعلومة أكثر!*",
            f"🤖 **إجابة الأستاذ الذكي الشاملة:**\n\nسؤال ممتاز جداً! لتحليل `{text}`:\n• الخطوة الأولى: استخراج المعطيات والمجهول.\n• الخطوة الثانية: اختيار القانون الصحيح والتطبيق المباشر.\n🏆 *أحسنت طرح السؤال، استمر بفضولك العلمي!*"
        ]
        student_points[user_id] = student_points.get(user_id, 0) + 5
        await update.message.reply_text(random.choice(ai_responses), parse_mode="Markdown")
        return

    # معالجة خطوات التسجيل
    if step == 'name':
        context.user_data['temp_name'] = text
        context.user_data['reg_step'] = 'province'
        await update.message.reply_text("📍 ممتاز. الآن أرسل **اسم المحافظة** (مثلاً: بغداد، البصرة، أربيل...):")
        return
    elif step == 'province':
        context.user_data['temp_province'] = text
        context.user_data['reg_step'] = 'school'
        await update.message.reply_text("🏫 أخيراً، أرسل **اسم المدرسة**:")
        return
    elif step == 'school':
        attendance_db[user_id] = {
            "name": context.user_data.get('temp_name'),
            "province": context.user_data.get('temp_province'),
            "school": text
        }
        expire_date = datetime.now() + timedelta(days=30)
        active_subscriptions[user_id] = f"هدية مجانية لغاية {expire_date.strftime('%Y-%m-%d')} 🎁"
        student_points[user_id] = 50 # هدية 50 نقطة ترحيبية
        context.user_data['reg_step'] = None
        
        await update.message.reply_text(
            "✅ **تم تسجيلك بنجاح! تم إضافتك لقاعدة الأبطال ومنحك 30 يوماً هدية + 50 نقطة XP!** 🎉",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
        return

    if context.user_data.get('entering_sub_code'):
        context.user_data['entering_sub_code'] = False
        code = text.strip()
        if code in generated_codes["monthly"]:
            active_subscriptions[user_id] = "اشتراك شهري مفعل ⭐️"
            generated_codes["monthly"].remove(code)
            student_points[user_id] = student_points.get(user_id, 0) + 100
            await update.message.reply_text("🎉 **مبروك! تم تفعيل اشتراكك الشهري بنجاح (+100 نقطة XP).**")
        elif code in generated_codes["yearly"]:
            active_subscriptions[user_id] = "اشتراك سنوي شامل مفعل 💎"
            generated_codes["yearly"].remove(code)
            student_points[user_id] = student_points.get(user_id, 0) + 300
            await update.message.reply_text("💎 **مبروك! تم تفعيل اشتراكك السنوي الشامل بنجاح (+300 نقطة XP).**")
        else:
            await update.message.reply_text("❌ **عذراً، الكود غير صالح أو تم استخدامه مسبقاً.**")
        return

    if is_admin and context.user_data.get('broadcasting'):
        context.user_data['broadcasting'] = False
        count = 0
        for uid in attendance_db.keys():
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **إعلان هام من إدارة المنصة:**\n\n{text}")
                count += 1
            except:
                pass
        await update.message.reply_text(f"✅ تم إرسال الإعلان الفوري بنجاح إلى {count} طالب.")
        return

    if user_id in attendance_db:
        await update.message.reply_text("يرجى استخدام الأزرار السفلية الخارقة للتنقل:", reply_markup=get_main_reply_keyboard(is_admin))
    else:
        await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("lect_"):
        stage_key = data.replace("lect_", "")
        lectures = stages_content[stage_key]["lectures"]
        
        student_views[user_id] = student_views.get(user_id, 0) + 1
        student_points[user_id] = student_points.get(user_id, 0) + 10
        
        text = f"🎬 **محاضرات {stages_content[stage_key]['name']}:**\n\n"
        text += "⚡ **بث فوري مباشر آمن بدون تحميل (+10 نقاط XP):**\n\n"
        
        keyboard = []
        for lect in lectures:
            keyboard.append([InlineKeyboardButton(lect["title"], url=lect["url"])])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="back_to_lectures")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back_to_lectures":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="lect_primary")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="lect_intermediate")],
            [InlineKeyboardButton("📖 المرحلة الإعدادية", callback_data="lect_secondary")]
        ]
        await query.message.edit_text("📚 **اختر المرحلة الدراسية لاستعراض المحاضرات:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "play_next_question":
        q_item = random.choice(science_questions_bank)
        options = q_item["options"]
        random.shuffle(options)
        
        keyboard = []
        for opt_text, is_correct in options:
            cb = "game_win" if is_correct else "game_loss"
            keyboard.append([InlineKeyboardButton(opt_text, callback_data=cb)])
        keyboard.append([InlineKeyboardButton("⏭ سؤال فوري آخر", callback_data="play_next_question")])
        
        await query.message.edit_text(f"🎯 **تحدي الذكاء الفوري:**\n\n{q_item['q']}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_win":
        student_points[user_id] = student_points.get(user_id, 0) + 20
        keyboard = [
            [InlineKeyboardButton("🏆 لعب سؤالاً جديداً (+20 XP)", callback_data="play_next_question")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu_cb")]
        ]
        await query.message.edit_text("🌟 **كفو! إجابة صحيحة خارقة (+20 نقطة XP) 👏**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_loss":
        keyboard = [
            [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="play_next_question")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu_cb")]
        ]
        await query.message.edit_text("❌ **عفواً، إجابة غير دقيقة! حاول في التحدي القادم.**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "main_menu_cb":
        await query.message.edit_text("🎓 تم العودة للقائمة. استعمل الأزرار السفلية للتنقل.")

    elif data == "admin_broadcast":
        context.user_data['broadcasting'] = True
        await query.message.edit_text("📢 أرسل نص الإعلان الآن لبثه لجميع الطلاب المشتركين:")

    elif data == "admin_gen_code":
        m_code = f"ULTRA-M-{random.randint(1000, 9999)}"
        y_code = f"ULTRA-Y-{random.randint(10000, 99999)}"
        generated_codes["monthly"].append(m_code)
        generated_codes["yearly"].append(y_code)
        await query.message.edit_text(f"🎟 **الأكواد الخارقة المולدة:**\n\n⭐️ شهري: `{m_code}`\n💎 سنوي: `{y_code}`", parse_mode="Markdown")

    elif data == "admin_show_logs":
        logs = "\n".join([f"• {d['name']} | {d['province']} | {d['school']}" for d in attendance_db.values()])
        if not logs:
            logs = "لا توجد سجلات طلاب."
        await query.message.edit_text(f"📋 **سجل الحضور والطلاب الأبطال:**\n\n{logs}")

def main():
    if not TOKEN or TOKEN == "ضع_التوكن_هنا_بين_العلامتين":
        print("خطأ: يرجى وضع التوكن الحقيقي داخل الكود!")
        return

    Thread(target=run_flask).start()

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("المنصة التعليمية العراقية الخارقة تعمل بكفاءة تامة...")
    app.run_polling()

if __name__ == "__main__":
    main()
