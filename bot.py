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
student_views = {}
student_points = {}
generated_codes = {"monthly": [], "yearly": []}

# قواعد البيانات الديناميكية القابلة للتعديل الكامل من داخل البوت
dynamic_stages = {
    "primary": {
        "name": "📖 المرحلة الابتدائية",
        "lectures": [{"title": "🎬 محاضرة الرياضيات - الأساسية", "url": "https://t.me/c/0/0"}]
    },
    "intermediate": {
        "name": "📖 المرحلة المتوسطة",
        "lectures": [{"title": "🎬 محاضرة الفيزياء والكيمياء", "url": "https://t.me/c/0/0"}]
    },
    "secondary": {
        "name": "📖 المرحلة الإعدادية",
        "lectures": [{"title": "🎬 محاضرة الأحياء - التكاثر", "url": "https://t.me/c/0/0"}]
    }
}

science_questions_bank = [
    {
        "q": "🧠 ما هو بيت الطاقة الرئيسي داخل الخلية الحية؟",
        "options": [("✅ الميتوكوندريا", True), ("❌ الرايبوسوم", False), ("❌ نواة الخلية", False)]
    },
    {
        "q": "⚗️ ما هي وحدة قياس التيار الكهربائي في النظام الدولي؟",
        "options": [("❌ الفولت", False), ("✅ الأمبير", True), ("❌ الأوم", False)]
    }
]

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Ultimate CMS Educational Bot is running perfectly!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def get_main_reply_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("📚 قسم المحاضرات والملازم"), KeyboardButton("🏆 لوحة المتصدرين والأبطال")],
        [KeyboardButton("🤖 الأستاذ الذكي (AI)"), KeyboardButton("📜 شهادة التقدير الإلكترونية")],
        [KeyboardButton("💎 تفعيل كود الاشتراك"), KeyboardButton("👤 ملفي وسجل الحضور")],
        [KeyboardButton("🎮 الألعاب والتحديات الفورية")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ لوحة تحكم المطور والـ CMS الشاملة")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 **المنصة تعمل بكفاءة تامة وبأفضل حال! ✅**")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in attendance_db:
        context.user_data['reg_step'] = 'name'
        await update.message.reply_text(
            "🌟 **أهلاً بك في المنصة التعليمية العراقية الذكية**\n\n"
            "🎁 **هدية ترحيبية:** ستحصل فوراً على اشتراك مجاني لمدة **30 يوماً** + 50 نقطة XP!\n\n"
            "يرجى إرسال **اسمك الثلاثي** الآن للبدء:"
        )
        return
    
    is_admin = (ADMIN_ID and str(user_id) == str(ADMIN_ID))
    await update.message.reply_text(
        "🎓 **القائمة الرئيسية - اختر القسم المطلوب:**",
        reply_markup=get_main_reply_keyboard(is_admin)
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    stats_data["total_messages"] += 1
    step = context.user_data.get('reg_step')
    is_admin = (ADMIN_ID and str(user_id) == str(ADMIN_ID))

    # معالجة أزرار الواجهة
    if text == "📚 قسم المحاضرات والملازم":
        keyboard = [[InlineKeyboardButton(data["name"], callback_data=f"lect_{key}")] for key, data in dynamic_stages.items()]
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu_cb")])
        await update.message.reply_text("📚 **اختر المرحلة الدراسية لاستعراض المحاضرات:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif text == "🏆 لوحة المتصدرين والأبطال":
        sorted_students = sorted(student_views.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard_text = "🏆 **قائمة أساطير العراق التعليمية:**\n\n"
        if not sorted_students:
            leaderboard_text += "القائمة فارغة حالياً. كن البطل الأول! 🌟"
        else:
            for idx, (uid, views) in enumerate(sorted_students, 1):
                s_name = attendance_db.get(uid, {}).get("name", "طالب مجهول")
                pts = student_points.get(uid, 0)
                leaderboard_text += f"{idx}. **{s_name}** — 👁‍🗨 `{views}` مشاهدة | ⚡ `{pts} XP`\n"
        await update.message.reply_text(leaderboard_text, parse_mode="Markdown")
        return

    elif text == "🤖 الأستاذ الذكي (AI)":
        context.user_data['waiting_for_ai_question'] = True
        await update.message.reply_text("🤖 **الأستاذ الذكي الخصوصي:**\nاكتب أي سؤال علمي واجهك (رياضيات، فيزياء، أحياء...) وسأشرحه لك فوراً:", reply_markup=ReplyKeyboardMarkup([["❌ إنهاء جلسة الأستاذ الذكي"]], resize_keyboard=True))
        return

    elif text == "❌ إنهاء جلسة الأستاذ الذكي":
        context.user_data['waiting_for_ai_question'] = False
        await update.message.reply_text("✅ تم الإنهاء.", reply_markup=get_main_reply_keyboard(is_admin))
        return

    elif text == "📜 شهادة التقدير الإلكترونية":
        info = attendance_db.get(user_id, {"name": "طالب مجتهد", "province": "العراق", "school": "المنصة الذكية"})
        pts = student_points.get(user_id, 0)
        cert = f"╔═══════════════════════╗\n      🌟 **شهادة تقدير وتفوق رسمي** 🌟\n╚═══════════════════════╝\n\nتعلن المنصة عن منح الشهادة إلى البطل:\n📌 **{info['name']}**\n🏫 المدرسة: `{info['school']}`\n⚡ نقاط التفاعل: `{pts} XP`"
        await update.message.reply_text(cert, parse_mode="Markdown")
        return

    elif text == "💎 تفعيل كود الاشتراك":
        context.user_data['entering_sub_code'] = True
        await update.message.reply_text("💎 **تفعيل كود الاشتراك:**\nأرسل الكود (الشهري أو السنوي) لتفعيله فوراً:")
        return

    elif text == "👤 ملفي وسجل الحضور":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        sub = active_subscriptions.get(user_id, "تجريبي مجاني (30 يوم) 🎁")
        pts = student_points.get(user_id, 0)
        await update.message.reply_text(f"👤 **ملفك الشخصي:**\n\n▫️ الاسم: `{info['name']}`\n▫️ المحافظة: `{info['province']}`\n▫️ المدرسة: `{info['school']}`\n▫️ الاشتراك: **{sub}**\n▫️ النقاط: `{pts} XP`", parse_mode="Markdown")
        return

    elif text == "🎮 الألعاب والتحديات الفورية":
        await update.message.reply_text("🎮 **قسم المسابقات العلمية الحية:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ابدأ التحدي العشوائي", callback_data="play_next_question")]]))
        return

    elif text == "⚙️ لوحة تحكم المطور والـ CMS الشاملة" and is_admin:
        panel_text = f"⚙️ **لوحة التحكم الإدارية الداخلية (CMS):**\n\n👥 الطلاب المسجلين: `{len(attendance_db)}`\n💬 رسائل البوت: `{stats_data['total_messages']}`\n\nاختر العملية الإدارية المطلوبة:"
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مرحلة أو قسم جديد", callback_data="cms_add_stage")],
            [InlineKeyboardButton("📚 إضافة محاضرة/ملزمة لقسم", callback_data="cms_add_lecture")],
            [InlineKeyboardButton("🎟 توليد كود اشتراك جديد", callback_data="admin_gen_code")],
            [InlineKeyboardButton("📢 إرسال إعلان عام للجميع", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📋 عرض كشوفات الطلاب", callback_data="admin_show_logs")]
        ]
        await update.message.reply_text(panel_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # معالجة المدخلات الديناميكية للوحة التحكم (CMS)
    if is_admin and context.user_data.get('cms_step') == 'getting_stage_id':
        key = text.strip().lower()
        context.user_data['temp_stage_key'] = key
        context.user_data['cms_step'] = 'getting_stage_name'
        await update.message.reply_text(f"📍 ممتاز. الآن أرسل **اسم القسم الظاهري** (مثلاً: 📖 المرحلة الابتدائية):")
        return

    elif is_admin and context.user_data.get('cms_step') == 'getting_stage_name':
        s_name = text.strip()
        s_key = context.user_data.get('temp_stage_key')
        dynamic_stages[s_key] = {"name": s_name, "lectures": []}
        context.user_data['cms_step'] = None
        await update.message.reply_text(f"✅ تم إضافة القسم الجديد ({s_name}) بنجاح وتفعيله في البوت فوراً!", reply_markup=get_main_reply_keyboard(is_admin))
        return

    elif is_admin and context.user_data.get('cms_step') == 'getting_lect_title':
        context.user_data['temp_lect_title'] = text.strip()
        context.user_data['cms_step'] = 'getting_lect_url'
        await update.message.reply_text("🔗 الآن أرسل **رابط المحاضرة أو الملزمة** (رابط مباشر أو تليجرام):")
        return

    elif is_admin and context.user_data.get('cms_step') == 'getting_lect_url':
        l_url = text.strip()
        l_title = context.user_data.get('temp_lect_title')
        s_key = context.user_data.get('temp_target_stage')
        if s_key in dynamic_stages:
            dynamic_stages[s_key]["lectures"].append({"title": l_title, "url": l_url})
            context.user_data['cms_step'] = None
            await update.message.reply_text(f"✅ تم إضافة المحاضرة ({l_title}) بنجاح إلى القسم المطلوب!", reply_markup=get_main_reply_keyboard(is_admin))
        else:
            await update.message.reply_text("❌ حدث خطأ، القسم غير موجود.")
        return

    if context.user_data.get('waiting_for_ai_question'):
        await update.message.reply_text(f"🤖 **إجابة الأستاذ الذكي:**\n\nبناءً على سؤالك (`{text}`): القاعدة العلمية واضحة وتتطلب تطبيق المعطيات بخطوات دقيقة. استمر في التفوق!", parse_mode="Markdown")
        return

    if step == 'name':
        context.user_data['temp_name'] = text
        context.user_data['reg_step'] = 'province'
        await update.message.reply_text("📍 أرسل **اسم المحافظة**:")
        return
    elif step == 'province':
        context.user_data['temp_province'] = text
        context.user_data['reg_step'] = 'school'
        await update.message.reply_text("🏫 أرسل **اسم المدرسة**:")
        return
    elif step == 'school':
        attendance_db[user_id] = {"name": context.user_data.get('temp_name'), "province": context.user_data.get('temp_province'), "school": text}
        expire_date = datetime.now() + timedelta(days=30)
        active_subscriptions[user_id] = f"هدية مجانية لغاية {expire_date.strftime('%Y-%m-%d')} 🎁"
        student_points[user_id] = 50
        context.user_data['reg_step'] = None
        await update.message.reply_text("✅ **تم تسجيلك بنجاح ومنحك هدية 30 يوماً!** 🎉", reply_markup=get_main_reply_keyboard(is_admin))
        return

    if context.user_data.get('entering_sub_code'):
        context.user_data['entering_sub_code'] = False
        code = text.strip()
        if code in generated_codes["monthly"]:
            active_subscriptions[user_id] = "اشتراك شهري مفعل ⭐️"
            generated_codes["monthly"].remove(code)
            student_points[user_id] = student_points.get(user_id, 0) + 100
            await update.message.reply_text("🎉 **تم تفعيل اشتراكك الشهري بنجاح!**")
        elif code in generated_codes["yearly"]:
            active_subscriptions[user_id] = "اشتراك سنوي مفعل 💎"
            generated_codes["yearly"].remove(code)
            student_points[user_id] = student_points.get(user_id, 0) + 300
            await update.message.reply_text("💎 **تم تفعيل اشتراكك السنوي بنجاح!**")
        else:
            await update.message.reply_text("❌ **الكود غير صالح أو مستخدم مسبقاً.**")
        return

    if is_admin and context.user_data.get('broadcasting'):
        context.user_data['broadcasting'] = False
        count = 0
        for uid in attendance_db.keys():
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **إعلان هام:**\n\n{text}")
                count += 1
            except:
                pass
        await update.message.reply_text(f"✅ تم الإرسال إلى {count} طالب.")
        return

    if user_id in attendance_db:
        await update.message.reply_text("يرجى استخدام الأزرار السفلية:", reply_markup=get_main_reply_keyboard(is_admin))
    else:
        await start(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("lect_"):
        stage_key = data.replace("lect_", "")
        stage_info = dynamic_stages.get(stage_key)
        if not stage_info:
            await query.message.edit_text("❌ القسم غير موجود.")
            return
            
        student_views[user_id] = student_views.get(user_id, 0) + 1
        student_points[user_id] = student_points.get(user_id, 0) + 10
        
        text = f"🎬 **{stage_info['name']}:**\n\n⚡ بث فوري مباشر آمن:\n\n"
        keyboard = [[InlineKeyboardButton(lect["title"], url=lect["url"])] for lect in stage_info["lectures"]]
        keyboard.append([InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="back_to_lectures")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back_to_lectures":
        keyboard = [[InlineKeyboardButton(d["name"], callback_data=f"lect_{k}")] for k, d in dynamic_stages.items()]
        await query.message.edit_text("📚 **اختر المرحلة الدراسية:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "cms_add_stage":
        context.user_data['cms_step'] = 'getting_stage_id'
        await query.message.edit_text("➕ أرسل الآن **معرف القسم بالإنجليزية** (مثلاً: `university` أو `third_grade` بدون مسافات):")

    elif data == "cms_add_lecture":
        if not dynamic_stages:
            await query.message.edit_text("❌ لا توجد أقسام مضافة حالياً. أضف قسماً أولاً.")
            return
        keyboard = [[InlineKeyboardButton(d["name"], callback_data=f"select_stage_{k}")] for k, d in dynamic_stages.items()]
        await query.message.edit_text("📚 اختر القسم الذي تريد إضافة المحاضرة إليه:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_stage_"):
        s_key = data.replace("select_stage_", "")
        context.user_data['temp_target_stage'] = s_key
        context.user_data['cms_step'] = 'getting_lect_title'
        await query.message.edit_text("✍️ أرسل الآن **عنوان المحاضرة أو الملزمة**:")

    elif data == "play_next_question":
        q_item = random.choice(science_questions_bank)
        options = q_item["options"]
        random.shuffle(options)
        keyboard = [[InlineKeyboardButton(opt_text, callback_data="game_win" if is_c else "game_loss")] for opt_text, is_c in options]
        keyboard.append([InlineKeyboardButton("⏭ سؤال آخر", callback_data="play_next_question")])
        await query.message.edit_text(f"🎯 **تحدي الذكاء:**\n\n{q_item['q']}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_win":
        student_points[user_id] = student_points.get(user_id, 0) + 20
        await query.message.edit_text("🌟 **إجابة صحيحة (+20 XP)!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 لعب مجدداً", callback_data="play_next_question")]]))

    elif data == "game_loss":
        await query.message.edit_text("❌ **إجابة خاطئة!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 محاولة أخرى", callback_data="play_next_question")]]))

    elif data == "admin_gen_code":
        m_code = f"CMS-M-{random.randint(1000, 9999)}"
        y_code = f"CMS-Y-{random.randint(10000, 99999)}"
        generated_codes["monthly"].append(m_code)
        generated_codes["yearly"].append(y_code)
        await query.message.edit_text(f"🎟 **الأكواد المולدة بنجاح:**\n\n⭐️ شهري: `{m_code}`\n💎 سنوي: `{y_code}`", parse_mode="Markdown")

    elif data == "admin_broadcast":
        context.user_data['broadcasting'] = True
        await query.message.edit_text("📢 أرسل نص الإعلان الآن لبثه لجميع الطلاب:")

    elif data == "admin_show_logs":
        logs = "\n".join([f"• {d['name']} | {d['province']} | {d['school']}" for d in attendance_db.values()])
        if not logs:
            logs = "لا توجد سجلات."
        await query.message.edit_text(f"📋 **سجل الحضور والطلاب:**\n\n{logs}")

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
    
    print("نظام المنصة التعليمية مع لوحة تحكم CMS داخلية يعمل بكفاءة تامة...")
    app.run_polling()

if __name__ == "__main__":
    main()
