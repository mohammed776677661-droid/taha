import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # الآيدي الخاص بك

# قواعد بيانات مؤقتة لتخزين بيانات المنصة
# المراحل الدراسية الأساسية
stages_db = ["المرحلة الابتدائية", "المرحلة المتوسطة", "المرحلة الاعدادية"]
# الأزرار الديناميكية (يمكن إضافتها من الآدمن)
dynamic_buttons = []
# قسم الامتحانات
exams_db = {"امتحان الرياضيات - الأول متوسط": "رابط أو أسئلة الامتحان هنا..."}

# القائمة الرئيسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📚 المراحل الدراسية", callback_data="stages_menu")],
        [InlineKeyboardButton("📝 قسم الامتحانات", callback_data="exams_menu")],
        [InlineKeyboardButton("ℹ️ حول المنصة", callback_data="about_platform")]
    ]
    
    # إضافة الأزرار الديناميكية المضافة من قبل الآدمن
    for btn in dynamic_buttons:
        keyboard.append([InlineKeyboardButton(btn['text'], callback_data=f"dyn_{btn['id']}")])
        
    # زر لوحة التحكم يظهر للمطور فقط
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم الآدمن", callback_data="admin_panel")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = "🎓 أهلاً بك في المنصة التعليمية الشاملة لجميع المراحل!\nاختر ما يناسبك من القائمة أدناه:"
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

# معالج الأزرار التفاعلية
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
        
    elif data == "stages_menu":
        keyboard = [[InlineKeyboardButton(stage, callback_data=f"stage_{stage}")] for stage in stages_db]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        await query.message.edit_text("📚 اختر المرحلة الدراسية المطلوبة:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("stage_"):
        stage_name = data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("📖 الملازم والكتب", callback_data=f"books_{stage_name}")],
            [InlineKeyboardButton("🎥 الشروحات والدروس", callback_data=f"videos_{stage_name}")],
            [InlineKeyboardButton("🔙 رجوع للمراحل", callback_data="stages_menu")]
        ]
        await query.message.edit_text(f"📌 أنت الآن في: {stage_name}\nاختر القسم المطلوب:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("books_") or data.startswith("videos_"):
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="stages_menu")]]
        await query.message.edit_text("📂 عذراً، جاري رفع المناهج والملازم لهذه المرحلة قريباً...", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "exams_menu":
        keyboard = []
        for exam_title in exams_db.keys():
            keyboard.append([InlineKeyboardButton(f"📝 {exam_title}", callback_data=f"exam_detail")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        await query.message.edit_text("📝 قسم الامتحانات والاختبارات الوزارية والمدرسية:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "exam_detail":
        keyboard = [[InlineKeyboardButton("🔙 رجوع للامتحانات", callback_data="exams_menu")]]
        await query.message.edit_text("📄 تفاصيل الامتحان: يُرجى الإجابة على الأسئلة وإرسالها للمدرس المختص.\n\n(هنا يتم وضع تفاصيل الامتحان أو الأسئلة)", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "about_platform":
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text("ℹ️ منصة تعليمية متكاملة تهدف لخدمة الطلاب في جميع المراحل الدراسية وتوفير كافة المناهج والامتحانات.", reply_markup=InlineKeyboardMarkup(keyboard))
        
    # --- لوحة تحكم الآدمن ---
    elif data == "admin_panel":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            keyboard = [
                [InlineKeyboardButton("➕ إضافة زر جديد بالقائمة", callback_data="add_btn_prompt")],
                [InlineKeyboardButton("🗑 حذف زر من القائمة", callback_data="del_btn_menu")],
                [InlineKeyboardButton("➕ إضافة امتحان جديد", callback_data="add_exam_prompt")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text("⚙️ **لوحة تحكم الآدمن الرئيسية:**\nتحكم بكل محتويات المنصة من هنا:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("عذراً، هذه اللوحة للمطور فقط ❌", show_alert=True)
            
    elif data == "add_btn_prompt":
        context.user_data['waiting_for_btn'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("✍️ أرسل الآن **عنوان الزر ورابطه** بهذا الشكل:\n`اسم الزر | https://t.me/...`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "del_btn_menu":
        if not dynamic_buttons:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
            await query.message.edit_text("لا توجد أزرار مخصصة لحذفها حالياً.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton(f"حذف: {btn['text']}", callback_data=f"remove_btn_{btn['id']}")] for btn in dynamic_buttons]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
        await query.message.edit_text("اختر الزر الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("remove_btn_"):
        btn_id = int(data.split("_")[2])
        global dynamic_buttons
        dynamic_buttons = [b for b in dynamic_buttons if b['id'] != btn_id]
        await query.answer("تم حذف الزر بنجاح! ✅", show_alert=True)
        await admin_panel_direct(query)
        
    elif data == "add_exam_prompt":
        context.user_data['waiting_for_exam'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("✍️ أرسل الآن تفاصيل الامتحان الجديد بهذا الشكل:\n`اسم الامتحان - الوصف`", reply_markup=InlineKeyboardMarkup(keyboard))

# دالة مساعدة للرجوع السريع للآدمن
async def admin_panel_direct(query):
    keyboard = [
        [InlineKeyboardButton("➕ إضافة زر جديد بالقائمة", callback_data="add_btn_prompt")],
        [InlineKeyboardButton("🗑 حذف زر من القائمة", callback_data="del_btn_menu")],
        [InlineKeyboardButton("➕ إضافة امتحان جديد", callback_data="add_exam_prompt")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    await query.message.edit_text("⚙️ **لوحة تحكم الآدمن الرئيسية:**", reply_markup=InlineKeyboardMarkup(keyboard))

# استقبال رسائل الآدمن لإضافة الأزرار أو الامتحانات ديناميكياً
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not ADMIN_ID or str(user_id) != str(ADMIN_ID):
        return
        
    text = update.message.text
    
    if context.user_data.get('waiting_for_btn'):
        try:
            parts = text.split("|")
            btn_text = parts[0].strip()
            btn_link = parts[1].strip()
            
            new_id = len(dynamic_buttons) + 1
            dynamic_buttons.append({"id": new_id, "text": btn_text, "link": btn_link})
            context.user_data['waiting_for_btn'] = False
            
            await update.message.reply_text(f"✅ تم إضافة الزر ({btn_text}) بنجاح للقائمة الرئيسية!")
            await start(update, context)
        except Exception:
            await update.message.reply_text("❌ الصيغة غير خاطئة. يا ريت ترسلها بهذا الشكل: `اسم الزر | الرابط`", parse_mode="Markdown")
            
    elif context.user_data.get('waiting_for_exam'):
        exams_db[text] = "تمت الإضافة عبر لوحة التحكم"
        context.user_data['waiting_for_exam'] = False
        await update.message.reply_text(f"✅ تم إضافة الامتحان ({text}) بنجاح لقسم الامتحانات!")
        await start(update, context)

def main():
    if not TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة BOT_TOKEN!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
    
    print("المنصة التعليمية تعمل الآن بكفاءة...")
    app.run_polling()

if __name__ == "__main__":
    main()
