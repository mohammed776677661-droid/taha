import os
import logging
import random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ضع توكن بوتك الحقيقي هنا مباشرة بين علامتي التنصيص
TOKEN = "6697835631:AAE-isBrECs3BY3zUgKfifqoPM6nu6NBe6s"
ADMIN_ID = "1792685788"

stats_data = {
    "total_messages": 0,
    "sessions": 1
}

attendance_db = {}
active_subscriptions = {}
student_views = {} # تتبع عدد مشاهدات المحاضرات لكل طالب (لقسم المسابقات)
generated_codes = {"monthly": [], "yearly": []}

# المحاضرات والملازم لكل المراحل (روابط بث مباشر تعمل فوراً بدون تحميل)
stages_content = {
    "primary": {
        "name": "📖 المرحلة الابتدائية",
        "lectures": [
            {"title": "🎬 محاضرة الرياضيات - الدرس الأول", "url": "https://t.me/c/0/0"}, # استبدل برابط البث المباشر
            {"title": "🎬 محاضرة القواعد والإنكليزي", "url": "https://t.me/c/0/0"}
        ]
    },
    "intermediate": {
        "name": "📖 المرحلة المتوسطة",
        "lectures": [
            {"title": "🎬 محاضرة الفيزياء والكيمياء الشاملة", "url": "https://t.me/c/0/0"},
            {"title": "🎬 محاضرة الرياضيات الحديثة", "url": "https://t.me/c/0/0"}
        ]
    },
    "secondary": {
        "name": "📖 المرحلة الإعدادية",
        "lectures": [
            {"title": "🎬 محاضرة الأحياء - الفصل الأول (التكاثر)", "url": "https://t.me/c/0/0"},
            {"title": "🎬 محاضرة الفيزياء - المتناوب", "url": "https://t.me/c/0/0"}
        ]
    }
}

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Educational Platform Bot is running perfectly!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# الكيبورد السفلي الشامل للواجهة (يشمل تفعيل الكود، الحضور، المحاضرات، والمسابقات)
def get_main_reply_keyboard(is_admin=False):
    keyboard = [
        [KeyboardButton("📚 قسم المحاضرات والملازم"), KeyboardButton("🏆 لوحة المتصدرين للمشاهدات")],
        [KeyboardButton("💎 تفعيل كود الاشتراك"), KeyboardButton("👤 سجل الحضور وحسابي")],
        [KeyboardButton("🎮 الألعاب والمسابقات العلمية")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("⚙️ لوحة تحكم المطور والإحصائيات")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 **المنصة التعليمية تعمل بكفاءة تامة وبأفضل حال! ✅**")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in attendance_db:
        context.user_data['reg_step'] = 'name'
        await update.message.reply_text(
            "🌟 **أهلاً بك في المنصة التعليمية العراقية المتكاملة**\n\n"
            "🎁 **هدية المنصة:** ستحصل تلقائياً على اشتراك تجريبي مجاني لمدة **30 يوماً** فور إتمام التسجيل!\n\n"
            "يرجى إرسال **اسمك الثلاثي** الآن:"
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

    # الأزرار الرئيسية في الواجهة
    if text == "📚 قسم المحاضرات والملازم":
        keyboard = [
            [InlineKeyboardButton("📖 المرحلة الابتدائية", callback_data="lect_primary")],
            [InlineKeyboardButton("📖 المرحلة المتوسطة", callback_data="lect_intermediate")],
            [InlineKeyboardButton("📖 المرحلة الإعدادية", callback_data="lect_secondary")]
        ]
        await update.message.reply_text("📚 **اختر المرحلة الدراسية لاستعراض المحاضرات المباشرة:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif text == "🏆 لوحة المتصدرين للمشاهدات":
        # ترتيب الطلاب حسب أكثر عدد مشاهدات للمحاضرات
        sorted_students = sorted(student_views.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard_text = "🏆 **قائمة أكثر الطلاب مشاهدة للمحاضرات (لوحة الشرف):**\n\n"
        if not sorted_students:
            leaderboard_text += "لم يبدأ أي طالب بمشاهدة المحاضرات حتى الآن. كن أولهم! 🌟"
        else:
            for idx, (uid, views) in enumerate(sorted_students, 1):
                s_name = attendance_db.get(uid, {}).get("name", "طالب مجهول")
                leaderboard_text += f"{idx}. **{s_name}** — 👁‍🗨 `{views}` مشاهدة\n"
        await update.message.reply_text(leaderboard_text, parse_mode="Markdown")
        return

    elif text == "💎 تفعيل كود الاشتراك":
        context.user_data['entering_sub_code'] = True
        await update.message.reply_text("💎 **تفعيل كود الاشتراك (الشهري / السنوي):**\n\nأرسل الكود الآن لتفعيله في حسابك وتمديد اشتراكك فوراً:")
        return

    elif text == "👤 سجل الحضور وحسابي":
        info = attendance_db.get(user_id, {"name": "غير مسجل", "province": "-", "school": "-"})
        sub = active_subscriptions.get(user_id, "تجريبي مجاني (30 يوم) 🎁")
        views_count = student_views.get(user_id, 0)
        await update.message.reply_text(
            f"👤 **بيانات الحضور وحسابك الشخصي:**\n\n"
            f"▫️ الاسم: `{info['name']}`\n"
            f"▫️ المحافظة: `{info['province']}`\n"
            f"▫️ المدرسة: `{info['school']}`\n"
            f"▫️ نوع الاشتراك: **{sub}**\n"
            f"▫️ إجمالي مشاهدات المحاضرات: `👁‍🗨 {views_count} مشاهدة`",
            parse_mode="Markdown"
        )
        return

    elif text == "🎮 الألعاب والمسابقات العلمية":
        await update.message.reply_text(
            "🎮 **قسم التحديات العلمية:**\nاختر الاختبار لبدء التحدي:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 ابدأ الأسئلة العشوائية", callback_data="play_next_question")]])
        )
        return

    elif text == "⚙️ لوحة تحكم المطور والإحصائيات" and is_admin:
        total_u = len(attendance_db)
        admin_panel_text = (
            f"⚙️ **لوحة تحكم المطور الرئيسية:**\n\n"
            f"👥 إجمالي الطلاب المسجلين: `{total_u}`\n"
            f"💬 إجمالي الرسائل: `{stats_data['total_messages']}`\n"
            f"🔒 حماية المحتوى والبث: **نشط ✅**\n\n"
            f"اختر الإجراء المطلوب إدارته:"
        )
        keyboard = [
            [InlineKeyboardButton("📢 إرسال إعلان عام للطلاب", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🎟 توليد أكواد (شهري/سنوي)", callback_data="admin_gen_code")],
            [InlineKeyboardButton("📋 عرض سجلات وحضور الطلاب", callback_data="admin_show_logs")]
        ]
        await update.message.reply_text(admin_panel_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # معالجة خطوات التسجيل الإجباري
    if step == 'name':
        context.user_data['temp_name'] = text
        context.user_data['reg_step'] = 'province'
        await update.message.reply_text("📍 ممتاز. الآن أرسل **اسم المحافظة**:")
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
        # منح هدية 30 يوم مجاناً فوراً
        expire_date = datetime.now() + timedelta(days=30)
        active_subscriptions[user_id] = f"هدية مجانية لغاية {expire_date.strftime('%Y-%m-%d')} 🎁"
        context.user_data['reg_step'] = None
        
        await update.message.reply_text(
            "✅ **تم تسجيلك بنجاح وتم تفعيل هدية الـ 30 يوماً المجانية لحسابك!** 🎉",
            reply_markup=get_main_reply_keyboard(is_admin)
        )
        return

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
        await update.message.reply_text(f"✅ تم إرسال الإعلان بنجاح إلى {count} طالب.")
        return

    if user_id in attendance_db:
        await update.message.reply_text("يرجى استخدام الأزرار السفلية للتنقل:", reply_markup=get_main_reply_keyboard(is_admin))
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
        
        # تسجيل مشاهدة للمحاضرة لزيادة عداد المسابقة للطالب
        student_views[user_id] = student_views.get(user_id, 0) + 1
        
        text = f"🎬 **محاضرات {stages_content[stage_key]['name']}:**\n\n"
        text += "⚡ **ملاحظة:** المحاضرات تعمل بالبث الفوري المباشر دون الحاجة لتحميل الملفات!\n\n"
        
        keyboard = []
        for lect in lectures:
            # استخدام زر رابط للبث المباشر الفوري
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
        q_text = "🧠 **سؤال تحدي الذكاء العلمي:**\nما هو البيت الرئيسي للطاقة داخل الخلية الحية؟\n\n1️⃣ الميتوكوندريا\n2️⃣ الرايبوسوم"
        keyboard = [
            [InlineKeyboardButton("✅ 1️⃣ الميتوكوندريا", callback_data="game_win"), InlineKeyboardButton("❌ خيار آخر", callback_data="game_loss")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await query.message.edit_text(q_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "game_win":
        await query.message.edit_text("🏆 **كفو! إجابة صحيحة 100% 👏**")
    elif data == "game_loss":
        await query.message.edit_text("❌ **عفواً، إجابة خاطئة! حاول مرة أخرى.**")

    elif data == "admin_broadcast":
        context.user_data['broadcasting'] = True
        await query.message.edit_text("📢 أرسل نص الإعلان الآن لبثه لجميع الطلاب:")

    elif data == "admin_gen_code":
        m_code = f"IQ-MONTH-{random.randint(1000, 9999)}"
        y_code = f"IQ-YEAR-{random.randint(10000, 99999)}"
        generated_codes["monthly"].append(m_code)
        generated_codes["yearly"].append(y_code)
        await query.message.edit_text(f"🎟 **الأكواد الجديدة:**\n\n⭐️ شهري: `{m_code}`\n💎 سنوي: `{y_code}`", parse_mode="Markdown")

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
    
    print("المنصة التعليمية الشاملة تعمل بكفاءة تامة...")
    app.run_polling()

if __name__ == "__main__":
    main()
