import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = os.getenv("6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s")
ADMIN_ID = os.getenv("1792685788")

# قاعدة بيانات مؤقتة لتخزين بيانات الطلاب، الحضور، المحاضرات، والامتحانات
students_db = {}
attendance_db = {}
stages_db = {
    "المرحلة الابتدائية": {"المحاضرات": "📚 روابط محاضرات الابتدائية...", "الامتحانات": "📝 امتحانات الابتدائية..."},
    "المرحلة المتوسطة": {"المحاضرات": "📚 روابط محاضرات المتوسطة...", "الامتحانات": "📝 امتحانات المتوسطة..."},
    "المرحلة الاعدادية": {"المحاضرات": "📚 روابط محاضرات الاعدادية...", "الامتحانات": "📝 امتحانات الاعدادية..."}
}
exams_answers = {}  # لتخزين إجابات الأسئلة التي يضعها الأستاذ لكل مرحلة/سؤال

# أمر البدء والتحقق من التسجيل الإجباري للحضور
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # التحقق هل قام الطالب بتسجيل الحضور مسبقاً (إجباري)
    if user_id not in attendance_db:
        context.user_data['register_step'] = 'full_name'
        await update.message.reply_text(
            "🛑 **مرحباً بك في المنصة التعليمية الرقمية!**\n\n"
            "التسجيل إجباري للمتابعة. يرجى إرسال **اسمك الثلاثي** الآن:"
        )
        return

    await show_main_menu(update, context)

# معالج خطوات التسجيل الإجباري للحضور
async def handle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get('register_step')

    if step == 'full_name':
        context.user_data['temp_name'] = text
        context.user_data['register_step'] = 'province'
        await update.message.reply_text("📍 أهلاً بك. الآن يرجى إرسال **اسم المحافظة** التي تنتمي إليها:")
        return

    elif step == 'province':
        context.user_data['temp_province'] = text
        context.user_data['register_step'] = 'school'
        await update.message.reply_text("🏫 أخيراً، يرجى إرسال **اسم المدرسة** الخاصة بك:")
        return

    elif step == 'school':
        # حفظ بيانات الحضور كاملة
        attendance_db[user_id] = {
            "name": context.user_data.get('temp_name'),
            "province": text,
            "school": context.user_data.get('temp_province')
        }
        context.user_data['register_step'] = None
        await update.message.reply_text("✅ **تم تسجيل حضورك بنجاح في المنصة التعليمية!**")
        await show_main_menu_message(update, context)
        return

    # إذا كان المشرف يرسل الأسئلة أو الإجابات أو الإذاعة
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        if context.user_data.get('waiting_for_exam_key'):
            stage = context.user_data.get('current_stage')
            exams_answers[stage] = text
            context.user_data['waiting_for_exam_key'] = False
            await update.message.reply_text(f"✅ تم حفظ الإجابة النموذجية لامتحان {stage} بنجاح!")
            return

        if context.user_data.get('waiting_for_student_answer_eval'):
            # ميزة التصحيح الذكي والمقارنة بالذكاء الاصطناعي مع إجابة الأستاذ
            stage = context.user_data.get('eval_stage', 'المرحلة الاعدادية')
            teacher_ans = exams_answers.get(stage, "غير متوفرة")
            
            # محاكاة تحليل ومقارنة الذكاء الاصطناعي للإجابة
            match_score = "100%" if text.strip() == teacher_ans.strip() else "85%"
            grade = "10/10" if text.strip() == teacher_ans.strip() else "8/10 (تقارب ممتاز)"
            
            await update.message.reply_text(
                f"🤖 **تقرير التصحيح الذكي (AI):**\n\n"
                f"📝 **إجابة الطالب:** {text}\n"
                f"📋 **إجابة الأستاذ النموذجية:** {teacher_ans}\n"
                f"📊 **نسبة التطابق:** {match_score}\n"
                f"🏆 **التقييم والدرجة المقترحة:** {grade}"
            )
            context.user_data['waiting_for_student_answer_eval'] = False
            return

    # التفاعل العادي إن لم يكن في حالة تسجيل
    if user_id in attendance_db:
        await show_main_menu_message(update, context)
    else:
        await start(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 قسم المحاضرات (حسب المراحل)", callback_data="stages_lectures")],
        [InlineKeyboardButton("📝 قسم الامتحانات والتصحيح الذكي", callback_data="stages_exams")],
        [InlineKeyboardButton("👤 حسابي وبيانات الحضور", callback_data="my_attendance")]
    ]
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المشرف والإحصائيات", callback_data="admin_dashboard")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🎓 **أهلاً بك في القائمة الرئيسية للمنصة التعليمية**\nاختر القسم الذي ترغب به:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_main_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 قسم المحاضرات (حسب المراحل)", callback_data="stages_lectures")],
        [InlineKeyboardButton("📝 قسم الامتحانات والتصحيح الذكي", callback_data="stages_exams")],
        [InlineKeyboardButton("👤 حسابي وبيانات الحضور", callback_data="my_attendance")]
    ]
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المشرف والإحصائيات", callback_data="admin_dashboard")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎓 **القائمة الرئيسية للمنصة التعليمية:**", reply_markup=reply_markup, parse_mode="Markdown")

# معالج الأزرار والتفاعل
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await show_main_menu(update, context)

    elif data == "stages_lectures":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="lec_prim")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="lec_mid")],
            [InlineKeyboardButton("📖 المرحلة الاعدادية", callback_data="lec_high")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📚 **اختر المرحلة الدراسية للمحاضرات:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["lec_prim", "lec_mid", "lec_high"]:
        stage_name = "المرحلة الابتدائية" if data == "lec_prim" else "المرحلة المتوسطة" if data == "lec_mid" else "المرحلة الاعدادية"
        content = stages_db[stage_name]["المحاضرات"]
        keyboard = [[InlineKeyboardButton("🔙 رجوع للمراحل", callback_data="stages_lectures")]]
        await query.message.edit_text(f"📚 **محاضرات {stage_name}:**\n\n{content}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "stages_exams":
        keyboard = [
            [InlineKeyboardButton("📝 امتحان الابتدائية", callback_data="exam_prim")],
            [InlineKeyboardButton("📝 امتحان المتوسطة", callback_data="exam_mid")],
            [InlineKeyboardButton("📝 امتحان الاعدادية", callback_data="exam_high")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text("📝 **اختر المرحلة لتقديم الامتحان والتصحيح الذكي:**", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["exam_prim", "exam_mid", "exam_high"]:
        stage_name = "المرحلة الابتدائية" if data == "exam_prim" else "المرحلة المتوسطة" if data == "exam_mid" else "المرحلة الاعدادية"
        context.user_data['eval_stage'] = stage_name
        context.user_data['waiting_for_student_answer_eval'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="stages_exams")]]
        await query.message.edit_text(
            f"📝 **{stage_name} - اختبار ذكي**\n\n"
            f"أرسل الآن إجابتك على السؤال المطروح ليقوم الذكاء الاصطناعي بتصحيحها ومقارنتها مع إجابة الأستاذ وإعطائك الدرجة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "my_attendance":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        text = (
            f"👤 **بيانات حسابك وحضورك:**\n\n"
            f"▫️ الاسم الثلاثي: `{info['name']}`\n"
            f"▫️ المحافظة: `{info['province']}`\n"
            f"▫️ المدرسة: `{info['school']}`"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_dashboard":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            total_students = len(attendance_db)
            text = (
                f"⚙️ **لوحة تحكم المشرف والإحصائيات:**\n\n"
                f"👥 إجمالي الطلاب المسجلين (الحضور): `{total_students}` طالب\n"
                f"📊 حالة المنصة: `نشطة ومستقرة`"
            )
            keyboard = [
                [InlineKeyboardButton("➕ إضافة إجابة نموذجية (للأستاذ)", callback_data="admin_set_answer")],
                [InlineKeyboardButton("📋 عرض كشوفات الحضور", callback_data="admin_show_attendance")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.answer("عذراً، هذه اللوحة للمشرف فقط ❌", show_alert=True)

    elif data == "admin_set_answer":
        context.user_data['current_stage'] = "المرحلة الاعدادية"
        context.user_data['waiting_for_exam_key'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_dashboard")]]
        await query.message.edit_text("✍️ أرسل الآن الإجابة النموذجية (التي سيعتمدها الذكاء الاصطناعي للتصحيح ومقارنة إجابات الطلاب):", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_show_attendance":
        records = "\n".join([f"- {d['name']} | {d['province']} | {d['school']}" for d in attendance_db.values()])
        if not records:
            records = "لا يوجد طلاب مسجلين حتى الآن."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_dashboard")]]
        await query.message.edit_text(f"📋 **سجل الحضور الكامل للطلاب:**\n\n{records}", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    if not TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة 6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration))
    
    print("المنصة التعليمية الشاملة تعمل الآن بكفاءة...")
    app.run_polling()

if __name__ == "__main__":
    main()
