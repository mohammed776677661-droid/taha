import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = os.getenv("6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s")
ADMIN_ID = os.getenv("1792685788")  # آيدي المطور
CHANNEL_USERNAME = "@YourChannelUsername"  # معرف قناتك للاشتراك الإجباري (مثال: @Channel)
POINTS_PER_REF = 1  # عدد النقاط لكل شخص يدخل عن طريق رابط التمويل

# قاعدة بيانات مؤقتة لتخزين المستخدمين والنقاط
users_db = {}

# التحقق من الاشتراك الإجباري
async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    if not CHANNEL_USERNAME or CHANNEL_USERNAME == "@YourChannelUsername":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

# أمر البدء (/start) مع نظام التمويل وإحالة الأصدقاء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # تسجيل المستخدم إذا كان جديداً
    if user_id not in users_db:
        users_db[user_id] = {"points": 0, "referred": 0}
        
    # التحقق من نظام التمويل (Referral) عبر رابط التمويل
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id and referrer_id in users_db:
                # التأكد أن المستخدم لم يتم احتسابه مسبقاً
                if f"ref_{user_id}" not in context.bot_data:
                    context.bot_data[f"ref_{user_id}"] = True
                    users_db[referrer_id]["points"] += POINTS_PER_REF
                    # إشعار الشخص الداعي
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 دخل شخص جديد عبر رابط التمويل الخاص بك!\n➕ حصلت على {POINTS_PER_REF} نقطة."
                        )
                    except Exception:
                        pass
        except ValueError:
            pass

    # التحقق من الاشتراك الإجباري
    is_subscribed = await check_subscription(user_id, context)
    if not is_subscribed:
        keyboard = [
            [InlineKeyboardButton("📢 اشترك في قناة البوت", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("✅ اشتركت، تحقق من الاشتراك", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            "⚠️ عذراً، يجب عليك الاشتراك في قناة البوت أولاً لاستخدامه.\n\nاشترك في القناة ثم اضغط على زر التحقق:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # عرض القائمة الرئيسية للبوت
    await send_main_menu(update, context)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    points = users_db.get(user_id, {}).get("points", 0)
    
    keyboard = [
        [InlineKeyboardButton("🔗 رابط التمويل (زيادة نقاطك)", callback_data="ref_link")],
        [InlineKeyboardButton("💰 نقاطي ورصيدي", callback_data="my_points")],
        [InlineKeyboardButton("🎁 سحب الأرباح / طلب هدية", callback_data="withdraw")],
        [InlineKeyboardButton("ℹ️ معلومات البوت", callback_data="about")]
    ]
    
    # زر لوحة تحكم المطور
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة تحكم المطور (الآدمن)", callback_data="admin_panel")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        f"🤖 أهلاً بك في بوت التمويل الاحترافي!\n\n"
        f"💎 نقاطك الحالية: **{points}** نقطة\n"
        f"قم بمشاركة رابط التمويل الخاص بك لاكتساب المزيد من النقاط!"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# معالج الأزرار والتفاعل
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "check_sub":
        is_subscribed = await check_subscription(user_id, context)
        if is_subscribed:
            await query.message.delete()
            await send_main_menu(update, context)
        else:
            await query.answer("❌ لم تقم بالاشتراك في القناة بعد!", show_alert=True)
            
    elif data == "main_menu":
        await send_main_menu(update, context)
        
    elif data == "ref_link":
        bot_username = (await context.bot.get_me()).username
        ref_url = f"https://t.me/{bot_username}?start={user_id}"
        text = (
            f"🔗 **رابط التمويل الخاص بك:**\n`{ref_url}`\n\n"
            f"قم بنسخ الرابط ونشره لأصدقائك وفي المجموعات، وكل شخص يدخل عبر رابطك ستحصل مقابلها على نقاط!"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "my_points":
        points = users_db.get(user_id, {}).get("points", 0)
        text = f"💰 **رصيدك الحالي:**\nلديك `{points}` نقطة في حسابك."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "withdraw":
        text = "🎁 **قسم سحب الأرباح:**\nعليك جمع الحد الأدنى من النقاط لطلب الهدية أو التمويل.\nتواصل مع المطور لطلب السحب عند إتمام النقاط."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif data == "about":
        text = "ℹ️ هذا البوت مصمم خصيصاً للتمويل وزيادة الأعضاء بطريقة آمنة وسريعة."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    # لوحة تحكم الآدمن
    elif data == "admin_panel":
        if ADMIN_ID and str(user_id) == str(ADMIN_ID):
            total_users = len(users_db)
            text = f"⚙️ **لوحة تحكم المطور:**\n\n👥 إجمالي المستخدمين في البوت: `{total_users}` مستخدم"
            keyboard = [
                [InlineKeyboardButton("📢 إذاعة رسالة للكل", callback_data="broadcast_prompt")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.answer("عذراً، هذه اللوحة للمطور فقط ❌", show_alert=True)
            
    elif data == "broadcast_prompt":
        context.user_data['waiting_for_broadcast'] = True
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]
        await query.message.edit_text("📢 أرسل الآن الرسالة (نص أو صورة) التي تريد إذاعتها لجميع مشتركي البوت:", reply_markup=InlineKeyboardMarkup(keyboard))

# معالج رسائل الإذاعة للآدمن
async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ADMIN_ID and str(user_id) == str(ADMIN_ID) and context.user_data.get('waiting_for_broadcast'):
        context.user_data['waiting_for_broadcast'] = False
        broadcast_text = update.message.text
        
        success = 0
        failed = 0
        for uid in users_db.keys():
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **إشعار من الإدارة:**\n\n{broadcast_text}", parse_mode="Markdown")
                success += 1
            except Exception:
                failed += 1
                
        await update.message.reply_text(f"✅ تمت الإذاعة بنجاح!\n- وصلت إلى: `{success}` مستخدم\n- فشلت لدى: `{failed}` مستخدم")

def main():
    if not TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة BOT_TOKEN!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_messages))
    
    print("بوت التمويل الاحترافي يعمل الآن بكفاءة...")
    app.run_polling()

if __name__ == "__main__":
    main()
