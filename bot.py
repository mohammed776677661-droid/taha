import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# استدعاء التوكن من إعدادات المنصة (Render Environment Variables)
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! تم تشغيل البوت بنجاح على منصة Render 🎉")

def main():
    if not TOKEN:
        print("خطأ: لم يتم العثور على التوكن (BOT_TOKEN)!")
        return

    # إنشاء وتشغيل البوت
    app = ApplicationBuilder().token(TOKEN).build()
    
    # إضافة أمر /start
    app.add_handler(CommandHandler("start", start))
    
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
