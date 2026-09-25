import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# إعدادات التسجيل لمتابعة الأخطاء
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# جلب المتغيرات من إعدادات المنصة
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # ضع الآيدي الخاص بك هنا في متغيرات البيئة

# قاعدة بيانات مؤقتة لتخزين النقاط والمشتركين (للبوت البسيط)
# في المشاريع الكبيرة يُفضل استخدام قاعدة بيانات مثل SQLite أو MongoDB
users_db = {}

# أمر البدء (Start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # تسجيل المستخدم إذا كان جديداً
    if user_id not in users_db:
        users_db[user_id] = {"balance": 0, "invited": 0}
        
        # فحص إذا دخل عن طريق رابط دعوة شخص آخر
        if context.args:
            ref_id = context.args[0]
            if ref_id.isdigit() and int(ref_id) in users_db and int(ref_id) != user_id:
                users_db[int(ref_id)]["balance"] += 1  # زيادة نقطة للمُحيل
                users_db[int(ref_id)]["invited"] += 1
    
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # بناء الأزرار التفاعلية (لوحة التحكم)
    keyboard = [
        [InlineKeyboardButton("📊 حسابي ونقاطي", callback_data="my_account")],
        [InlineKeyboardButton("🔗 رابط التمويل الخاص بي", callback_data="get_link")],
        [InlineKeyboardButton("⚙️ قسم التمويل والاشتراك", callback_data="earning_section")]
    ]
    
    # إضافة زر لوحة التحكم الخاصة بالمطور إذا كان المستخدم هو أنت
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("🛠 لوحة تحكم المطور (الآدمن)", callback_data="admin_panel")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = (
        f"مرحباً بك يا {user.first_name} في بوت التمويل الاحترافي! 🚀\n\n"
        "قم بدعوة أصدقائك عبر رابط التمويل الخاص بك لجمع النقاط وزيادة تفاعل قناتك أو حسابك."
    )
    
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_msg, reply_markup=reply_markup)

# التعامل مع الأزرار الشفافة
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "my_account":
        user_data = users_db.get(user_id, {"balance": 0, "invited": 0})
        text = (
            f"👤 معلومات حسابك:\n\n"
            f"💰 رصيدك الحالي: {user_data['balance']} نقطة\n"
            f"👥 عدد الأشخاص الذين دعوتهم: {user_data['invited']} شخص"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "get_link":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        text = (
            f"🔗 إليك رابط التمويل الخاص بك:\n\n`{ref_link}`\n\n"
            "قم بنسخه وضعه أصدقائك أو في المجموعات لتربح نقاط عن كل شخص يدخل من خلالك!"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == "earning_section":
        text = "💡 قسم التمويل:\n\nقريباً يمكنك استخدام نقاطك لطلب أعضاء أو مشاهدات لقناتك عبر البوت!"
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == "admin_panel":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            total_users = len(users_db)
            text = (
                f"🛠 أهلاً بك يا مطوري في لوحة الآدمن:\n\n"
                f"👥 إجمالي المستخدمين المسجلين في الذاكرة: {total_users}\n"
                f"⚡️ البوت يعمل بكفاءة عالية على منصة Render."
            )
            keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("عذراً، هذه اللوحة مخصصة لمطور البوت فقط! ❌", show_alert=True)
            
    elif query.data == "main_menu":
        # العودة للقائمة الرئيسية
        await start(update, context)

def main():
    if not TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة BOT_TOKEN!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # المعالجات (Handlers)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("البوت الاحترافي يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
