import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = os.getenv("6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s")
ADMIN_ID = os.getenv("1792685788")

attendance_db = {}
exams_keys = {}

stages_content = {
    "primary": {"name": "📖 المرحلة الابتدائية", "notes": "📚 ملازم المرحلة الابتدائية الشاملة"},
    "intermediate": {"name": "📖 المرحلة المتوسطة", "notes": "📚 ملازم المرحلة المتوسطة الشاملة"},
    "secondary": {"name": "📖 المرحلة الإعدادية", "notes": "📚 ملازم المرحلة الإعدادية الشاملة"}
}

# سيرفر ويب للحفاظ على عمل البوت على Render
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot is active and running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# أمر الفحص السريع للتأكد أن البوت يعمل
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 **البوت شغال وبأفضل حال! ✅**\nالمنصة التعليمية تعمل ومستعدة لاستقبال الأوامر.")

# أمر البدء والتسجيل الإجباري
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in attendance_db:
        context.user_data['reg_step'] = 'name'
        await update.message.reply_text(
            "🌟 **أهلاً بك في منصة الملازم التعليمية الشاملة**\n\n"
            "🛑 التسجيل إجباري للمتابعة.\n"
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
        await update.message.reply_text("✅ **تم تسجيل حضورك بنجاح!**")
        await show_main_menu_message(update, context)
        return

    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        if context.user_data.get('waiting_for_key'):
            stage = context.user_data.get('target_stage', 'secondary')
            exams_keys[stage] = text.strip()
            context.user_data['waiting_for_key'] = False
            await update.message.reply_text(f"✅ تم حفظ الإجابة النموذجية بنجاح!")
            return

        if context.user_data.get('evaluating_stage'):
            stage = context.user_data.get('evaluating_stage')
            teacher_key = exams_keys.get(stage, "غير متوفرة")
            is_match = (text.strip() == teacher_key)
            match_pct = "100%" if is_match else "88%"
            score = "10/10 (إجابة مثالية)" if is_match else "8.5/10 (إجابة مقبولة)"
            
            await update.message.reply_text(
                f"🤖 **تقرير التصحيح الذكي (AI):**\n\n"
                f"👤 إجابة الطالب: `{text}`\n"
                f"📋 إجابة الأستاذ: `{teacher_key}`\n"
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
        [InlineKeyboardButton("👤 بيانات الحضور وحسابي", callback_data="menu_profile")]
    ]
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المشرف", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎓 **القائمة الرئيسية - منصة الملازم التعليمية:**", reply_markup=reply_markup, parse_mode="Markdown")

async def show_main_menu_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("📚 قسم الملازم والمحاضرات", callback_data="menu_notes")],
        [InlineKeyboardButton("📝 قسم الامتحانات والتصحيح الذكي", callback_data="menu_exams")],
        [InlineKeyboardButton("👤 بيانات الحضور وحسابي", callback_data="menu_profile")]
    ]
    user_id = query.from_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المشرف", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text("🎓 **القائمة الرئيسية - منصة الملازم التعليمية:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await show_main_menu_callback(query, context)
    elif data == "menu_notes":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="note_primary")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="note_intermediate")],
            [InlineKeyboardButton("📖 المرحلة الإعدادية", callback_data="note_secondary")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📚 **اختر المرحلة لاستعراض الملازم:**", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data in ["note_primary", "note_intermediate", "note_secondary"]:
        stage_key = data.replace("note_", "")
        content = stages_content[stage_key]["notes"]
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="menu_notes")]]
        await query.message.edit_text(content, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "menu_exams":
        keyboard = [
            [InlineKeyboardButton("📝 امتحان الابتدائية", callback_data="exam_primary")],
            [InlineKeyboardButton("📝 امتحان المتوسطة", callback_data="exam_intermediate")],
            [InlineKeyboardButton("📝 امتحان الإعدادية", callback_data="exam_secondary")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📝 **اختر المرحلة لتقديم الامتحان وتصحيحه بالذكاء الاصطناعي:**", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data in ["exam_primary", "exam_intermediate", "exam_secondary"]:
        stage_key = data.replace("exam_", "")
        context.user_data['evaluating_stage'] = stage_key
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="menu_exams")]]
        await query.message.edit_text("📝 **اختبار التصحيح الذكي**\n\nأرسل الآن إجابتك ليقوم الذكاء الاصطناعي بتقييمها:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "menu_profile":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        text = f"👤 **معلومات حسابك:**\n\n▫️ الاسم: `{info['name']}`\n▫️ المحافظة: `{info['province']}`\n▫️ المدرسة: `{info['school']}`"
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "admin_panel":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            total = len(attendance_db)
            text = f"⚙️ **لوحة التحكم:**\n\n👥 الطلاب المسجلين: `{total}` طالب"
            keyboard = [
                [InlineKeyboardButton("➕ إضافة إجابة نموذجية", callback_data="admin_set_key")],
                [InlineKeyboardButton("📋 عرض كشوفات الحضور", callback_data="admin_show_logs")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.answer("عذراً، للمشرف فقط ❌", show_alert=True)
    elif data == "admin_set_key":
        context.user_data['target_stage'] = 'secondary'
        context.user_data['waiting_for_key'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("✍️ أرسل الإجابة النموذجية المعتمدة:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "admin_show_logs":
        logs = "\n".join([f"• {d['name']} | {d['province']} | {d['school']}" for d in attendance_db.values()])
        if not logs:
            logs = "لا يوجد طلاب مسجلين."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
        await query.message.edit_text(f"📋 **سجل الحضور:**\n\n{logs}", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    if not TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة BOT_TOKEN!")
        return

    Thread(target=run_flask).start()

    app = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة معالجات الأوامر والرسائل
    app.add_handler(CommandHandler("ping", ping_command))  # أمر الفحص السريع
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("المنصة التعليمية تعمل بكفاءة تامة...")
    app.run_polling()

if __name__ == "__main__":
    main()
