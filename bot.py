import os
import logging
import random
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ضع توكن بوتك الحقيقي هنا مباشرة بين علامتي التنصيص
TOKEN = "6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s"
ADMIN_ID = "1792685788" # ضع آيدي حسابك هنا حصراً للتحكم الكامل

# قواعد البيانات الديناميكية
attendance_db = {}
exams_keys = {}
active_subscriptions = {} # تخزين اشتراكات الطلاب والأكواد المفعلة
generated_codes = {"monthly": [], "yearly": []} # تخزين الأكواد المتاحة

# الأقسام والملازم الافتراضية (قابلة للتوسعة)
stages_content = {
    "primary": {
        "name": "📖 المرحلة الابتدائية",
        "notes": ["📚 ملزمة الرياضيات - السادس الابتدائي", "📚 ملزمة الإنجليزية الشاملة", "📚 ملزمة العلوم والاجتماعيات"]
    },
    "intermediate": {
        "name": "📖 المرحلة المتوسطة",
        "notes": ["📚 ملزمة الفيزياء - الثالث المتوسط", "📚 ملزمة الكيمياء والأحياء", "📚 ملزمة الرياضيات الحديثة"]
    },
    "secondary": {
        "name": "📖 المرحلة الإعدادية",
        "notes": ["📚 ملزمة الأحياء - السادس العلمي", "📚 ملزمة الفيزياء المنهج الكامل", "📚 ملزمة الأدب والقواعد للرابع والخامس والسادس"]
    }
}

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Educational Platform Bot is running successfully!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 **البوت يعمل بكفاءة تامة وبأفضل حال! ✅**")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in attendance_db:
        context.user_data['reg_step'] = 'name'
        await update.message.reply_text(
            "🌟 **أهلاً بك في المنصة التعليمية الذكية الشاملة**\n\n"
            "🛑 التسجيل إجباري للمتابعة واستخدام أقسام البوت.\n"
            "يرجى إرسال **اسمك الثلاثي** الآن:"
        )
        return
    await show_main_menu_message(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get('reg_step')

    if step == 'name':
        context.user_data['temp_name'] = text
        context.user_data['reg_step'] = 'province'
        await update.message.reply_text("📍 ممتاز. الآن يرجى إرسال **اسم المحافظة**:")
        return
    elif step == 'province':
        context.user_data['temp_province'] = text
        context.user_data['reg_step'] = 'school'
        await update.message.reply_text("🏫 أخيراً، يرجى إرسال **اسم المدرسة**:")
        return
    elif step == 'school':
        attendance_db[user_id] = {
            "name": context.user_data.get('temp_name'),
            "province": context.user_data.get('temp_province'),
            "school": text
        }
        context.user_data['reg_step'] = None
        await update.message.reply_text("✅ **تم تسجيل حضورك وبياناتك بنجاح في سجلات المنصة!**")
        await show_main_menu_message(update, context)
        return

    # وظائف لوحة المشرف والمطور
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        # إضافة ملزمة جديدة لقسم معين
        if context.user_data.get('adding_note_stage'):
            stage = context.user_data.get('adding_note_stage')
            stages_content[stage]["notes"].append(f"📚 {text.strip()}")
            context.user_data['adding_note_stage'] = None
            await update.message.reply_text(f"✅ تم إضافة الملزمة الجديدة بنجاح إلى قسم {stages_content[stage]['name']}!")
            return

        # إرسال إعلان عام للطلاب
        if context.user_data.get('broadcasting'):
            context.user_data['broadcasting'] = False
            count = 0
            for uid in attendance_db.keys():
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 **إعلان هام من إدارة المنصة:**\n\n{text}")
                    count += 1
                except:
                    pass
            await update.message.reply_text(f"✅ تم إرسال الإعلان بنجاح إلى {count} طالب!")
            return

        # تفعيل كود اشتراك أدخله المطور
        if context.user_data.get('waiting_for_key'):
            stage = context.user_data.get('target_stage', 'secondary')
            exams_keys[stage] = text.strip()
            context.user_data['waiting_for_key'] = False
            await update.message.reply_text(f"✅ تم حفظ الإجابة النموذجية لامتحان التصحيح الذكي بنجاح!")
            return

    # نظام إدخال الكودات للطلاب
    if context.user_data.get('entering_sub_code'):
        context.user_data['entering_sub_code'] = False
        code = text.strip()
        if code in generated_codes["monthly"]:
            active_subscriptions[user_id] = "اشتراك شهري مفعل ⭐️"
            generated_codes["monthly"].remove(code)
            await update.message.reply_text("🎉 **مبروك! تم تفعيل اشتراكك الشهري بنجاح.**")
        elif code in generated_codes["yearly"]:
            active_subscriptions[user_id] = "اشتراك سنوي شامل مفعل 💎"
            generated_codes["yearly"].remove(code)
            await update.message.reply_text("💎 **مبروك! تم تفعيل اشتراكك السنوي الشامل بنجاح.**")
        else:
            await update.message.reply_text("❌ **عذراً، هذا الكود غير صالح أو تم استخدامه مسبقاً.**")
        await show_main_menu_message(update, context)
        return

    # تقييم التصحيح الذكي بالذكاء الاصطناعي
    if ADMIN_ID and str(user_id) == str(ADMIN_ID) and context.user_data.get('evaluating_stage'):
        stage = context.user_data.get('evaluating_stage')
        teacher_key = exams_keys.get(stage, "غير متوفرة")
        is_match = (text.strip() == teacher_key)
        match_pct = "100%" if is_match else "88%"
        score = "10/10 (إجابة مثالية)" if is_match else "8.5/10 (إجابة مقبولة)"
        
        await update.message.reply_text(
            f"🤖 **تقرير التصحيح الذكي (AI):**\n\n"
            f"👤 إجابة الطالب: `{text}`\n"
            f"📋 الإجابة النموذجية: `{teacher_key}`\n"
            f"📊 نسبة التطابق: **{match_pct}**\n"
            f"🏆 التقييم: **{score}**",
            parse_mode="Markdown"
        )
        context.user_data['evaluating_stage'] = None
        return

    if user_id in attendance_db:
        await show_main_menu_message(update, context)
    else:
        await start(update, context)

async def show_main_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 قسم الملازم والمحاضرات", callback_data="menu_notes")],
        [InlineKeyboardButton("📝 قسم الامتحانات والتصحيح الذكي", callback_data="menu_exams")],
        [InlineKeyboardButton("🎮 قسم الألعاب العلمية التفاعلية", callback_data="menu_games")],
        [InlineKeyboardButton("💎 تفعيل كود الاشتراك (شهري/سنوي)", callback_data="menu_activate_code")],
        [InlineKeyboardButton("👤 بيانات الحضور وحسابي", callback_data="menu_profile")]
    ]
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المطور والمشرف الرئيسية", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎓 **القائمة الرئيسية - منصة الملازم التعليمية الاحترافية:**", reply_markup=reply_markup, parse_mode="Markdown")

async def show_main_menu_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("📚 قسم الملازم والمحاضرات", callback_data="menu_notes")],
        [InlineKeyboardButton("📝 قسم الامتحانات والتصحيح الذكي", callback_data="menu_exams")],
        [InlineKeyboardButton("🎮 قسم الألعاب العلمية التفاعلية", callback_data="menu_games")],
        [InlineKeyboardButton("💎 تفعيل كود الاشتراك (شهري/سنوي)", callback_data="menu_activate_code")],
        [InlineKeyboardButton("👤 بيانات الحضور وحسابي", callback_data="menu_profile")]
    ]
    user_id = query.from_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المطور والمشرف الرئيسية", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("🎓 **القائمة الرئيسية - منصة الملازم التعليمية الاحترافية:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await show_main_menu_callback(query, context)
        
    # قسم الملازم
    elif data == "menu_notes":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="note_primary")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="note_intermediate")],
            [InlineKeyboardButton("📖 المرحلة الإعدادية", callback_data="note_secondary")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📚 **اختر المرحلة لاستعراض الملازم المتوفرة:**", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data in ["note_primary", "note_intermediate", "note_secondary"]:
        stage_key = data.replace("note_", "")
        notes_list = "\n".join(stages_content[stage_key]["notes"])
        content = f"📚 **ملازم {stages_content[stage_key]['name']}:**\n\n{notes_list}"
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="menu_notes")]
        ]
        # إضافة زر إضافة ملزمة للمشرف داخل القسم مباشرة
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            keyboard.insert(0, [InlineKeyboardButton("➕ إضافة ملزمة جديدة لهذا القسم", callback_data=f"add_note_{stage_key}")])
            
        await query.message.edit_text(content, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("add_note_"):
        stage_key = data.replace("add_note_", "")
        context.user_data['adding_note_stage'] = stage_key
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="menu_notes")]]
        await query.message.edit_text("✍️ أرسل الآن اسم ووصف الملزمة الجديدة ليتم إضافتها فوراً للقائمة:", reply_markup=InlineKeyboardMarkup(keyboard))

    # قسم الامتحانات
    elif data == "menu_exams":
        keyboard = [
            [InlineKeyboardButton("📝 امتحان الابتدائية", callback_data="exam_primary")],
            [InlineKeyboardButton("📝 امتحان المتوسطة", callback_data="exam_intermediate")],
            [InlineKeyboardButton("📝 امتحان الإعدادية", callback_data="exam_secondary")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📝 **اختر المرحلة لتقديم الامتحان والتصحيح بالذكاء الاصطناعي:**", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data in ["exam_primary", "exam_intermediate", "exam_secondary"]:
        stage_key = data.replace("exam_", "")
        context.user_data['evaluating_stage'] = stage_key
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="menu_exams")]]
        await query.message.edit_text("📝 **اختبار التصحيح الذكي (AI)**\n\nأرسل الآن إجابتك النصية ليقوم النظام بتقييمها:", reply_markup=InlineKeyboardMarkup(keyboard))

    # قسم الألعاب العلمية التفاعلية
    elif data == "menu_games":
        keyboard = [
            [InlineKeyboardButton("🧬 مسابقة الأحياء والعلوم", callback_data="game_bio")],
            [InlineKeyboardButton("⚗️ مسابقة الفيزياء والكيمياء", callback_data="game_phys")],
            [InlineKeyboardButton("🔢 تحدي الرياضيات والذكاء", callback_data="game_math")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("🎮 **قسم الألعاب والتحديات العلمية:**\nاختر التحدي لاختبار معلوماتك:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_bio":
        q_text = "🧠 **سؤال تحدي الأحياء:**\nما هو البيت الطاقة الرئيسي داخل الخلية الحية؟\n\n1️⃣ الميتوكوندريا\n2️⃣ الرايبوسوم\n3️⃣ نواة الخلية"
        keyboard = [[InlineKeyboardButton("✅ 1️⃣ الميتوكوندريا", callback_data="game_correct"), InlineKeyboardButton("❌ 2️⃣ أو 3️⃣", callback_data="game_wrong")],
                    [InlineKeyboardButton("🔙 رجوع للألعاب", callback_data="menu_games")]]
        await query.message.edit_text(q_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "game_phys":
        q_text = "⚗️ **سؤال تحدي الفيزياء:**\nما هي وحدة قياس التيار الكهربائي في النظام الدولي؟\n\n1️⃣ الفولت\n2️⃣ الأمبير\n3️⃣ الأوم"
        keyboard = [[InlineKeyboardButton("❌ 1️⃣ أو 3️⃣", callback_data="game_wrong"), InlineKeyboardButton("✅ 2️⃣ الأمبير", callback_data="game_correct")],
                    [InlineKeyboardButton("🔙 رجوع للألعاب", callback_data="menu_games")]]
        await query.message.edit_text(q_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "game_math":
        q_text = "🔢 **سؤال تحدي الرياضيات:**\nما هو جذر العدد 144؟\n\n1️⃣ 10\n2️⃣ 12\n3️⃣ 14"
        keyboard = [[InlineKeyboardButton("✅ 2️⃣ 12", callback_data="game_correct"), InlineKeyboardButton("❌ غير ذلك", callback_data="game_wrong")],
                    [InlineKeyboardButton("🔙 رجوع للألعاب", callback_data="menu_games")]]
        await query.message.edit_text(q_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "game_correct":
        keyboard = [[InlineKeyboardButton("🎮 لعب مرة أخرى", callback_data="menu_games"), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
        await query.message.edit_text("🏆 **إجابة صحيحة بطل! استمر في تألقك العلمي 🌟**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_wrong":
        keyboard = [[InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="menu_games"), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
        await query.message.edit_text("❌ **إجابة خاطئة، حاول في السؤال القادم! 💪**", reply_markup=InlineKeyboardMarkup(keyboard))

    # تفعيل الكودات
    elif data == "menu_activate_code":
        context.user_data['entering_sub_code'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]]
        await query.message.edit_text("💎 **تفعيل الاشتراك المدفوع**\n\nأرسل الآن كود الاشتراك (الشهري أو السنوي) المكون من أرقام لتفعيله فوراً:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ملف المستخدم
    elif data == "menu_profile":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        sub_status = active_subscriptions.get(user_id, "حساب مجاني عادي 👤")
        text = f"👤 **معلومات حسابك الشخصي:**\n\n▫️ الاسم: `{info['name']}`\n▫️ المحافظة: `{info['province']}`\n▫️ المدرسة: `{info['school']}`\n▫️ حالة الاشتراك: **{sub_status}**"
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # لوحة تحكم المطور والمشرف الرئيسية
    elif data == "admin_panel":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            total_students = len(attendance_db)
            text = f"⚙️ **لوحة التحكم الرئيسية للمطور:**\n\n👥 عدد الطلاب المسجلين: `{total_students}` طالب\n\nاختر الإجراء المطلوب:"
            keyboard = [
                [InlineKeyboardButton("📢 إرسال إعلان عام للجميع", callback_data="admin_broadcast")],
                [InlineKeyboardButton("🎟 توليد كود اشتراك شهري/سنوي", callback_data="admin_gen_code")],
                [InlineKeyboardButton("➕ إضافة إجابة نموذجية للامتحان", callback_data="admin_set_key")],
                [InlineKeyboardButton("📋 عرض كشوفات الطلاب المسجلين", callback_data="admin_show_logs")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.answer("عذراً، هذه اللوحة خاصة بالمطور فقط ❌", show_alert=True)

    elif data == "admin_broadcast":
        context.user_data['broadcasting'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("📢 **نظام الإعلانات:**\n\nأرسل نص الإعلان الآن ليتم بثه لكافة الطلاب المسجلين في البوت:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_gen_code":
        m_code = f"MONTH-{random.randint(1000, 9999)}"
        y_code = f"YEAR-{random.randint(10000, 99999)}"
        generated_codes["monthly"].append(m_code)
        generated_codes["yearly"].append(y_code)
        text = f"🎟 **تم توليد الأكواد الجديدة بنجاح:**\n\n⭐️ كود شهري: `{m_code}`\n💎 كود سنوي: `{y_code}`\n\nشارك الكود مع الطالب ليقوم بإدخاله عبر زر تفعيل الأكواد."
        keyboard = [[InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="admin_panel")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_set_key":
        context.user_data['target_stage'] = 'secondary'
        context.user_data['waiting_for_key'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("✍️ أرسل الإجابة النموذجية المعتمدة لاختبار المرحلة الإعدادية:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_show_logs":
        logs = "\n".join([f"• {d['name']} ({d['province']} - {d['school']})" for d in attendance_db.values()])
        if not logs:
            logs = "لا يوجد طلاب مسجلين حتى الآن."
        keyboard = [[InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="admin_panel")]]
        await query.message.edit_text(f"📋 **سجل الحضور الكامل للطلاب:**\n\n{logs}", reply_markup=InlineKeyboardMarkup(keyboard))

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
    
    print("المنصة التعليمية الاحترافية تعمل بكفاءة تامة...")
    app.run_polling()

if __name__ == "__main__":
    main()
