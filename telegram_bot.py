import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

# این import پروکسی رو (از طریق rag_core) قبل از ساخت اتصال تلگرام ست می‌کنه
from bot_logic import handle_message

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters ,CallbackQueryHandler

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SECRETARY = os.getenv("SECRETARY_CHAT_ID")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋 من دستیار هوشمند مطب دکتر ایکس (فوق تخصص درد) هستم. "
        "می‌تونم درباره‌ی ساعت کاری، خدمات و اطلاعات مطب راهنمایی‌تون کنم یا درخواست نوبت ثبت کنم.\n"
        "توجه: من پزشک نیستم و توصیه‌ی دارویی یا تشخیص بیماری نمی‌دم."
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"chat id: {update.effective_chat.id}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    reply, alert = await asyncio.to_thread(handle_message, uid, update.message.text)
    await update.message.reply_text(reply)
    if alert and SECRETARY:
        # اگر هشدار شامل اطلاعات نوبت باشد (دیکشنری)
        if isinstance(alert, dict):
            patient_id = alert["patient_id"]
            alert_text = alert["text"]

            # ساخت دکمه‌های تأیید و رد
            keyboard = [
                [
                    InlineKeyboardButton("✅ تأیید نوبت", callback_data=f"confirm:{patient_id}"),
                    InlineKeyboardButton("❌ رد نوبت", callback_data=f"reject:{patient_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=int(SECRETARY),
                text=alert_text,
                reply_markup=reply_markup,
            )
        else:
            # هشدارهای متنی عادی (مثل خط قرمز و علائم خطر)
            await context.bot.send_message(chat_id=int(SECRETARY), text=str(alert))


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک منشی روی دکمه‌های شیشه‌ای"""
    query = update.callback_query
    await query.answer()
# بررسی اینکه فقط منشی بتواند دکمه را بزند
    if SECRETARY and str(query.from_user.id) != str(SECRETARY):
        await query.message.reply_text("⛔ شما دسترسی منشی ندارید.")
        return

    action, patient_id = query.data.split(":")
    patient_id = int(patient_id)

    if action == "confirm":
        # به‌روزرسانی متن پیام برای منشی و حذف دکمه‌ها
        await query.edit_message_text(
            text=f"{query.message.text}\n\n✅ وضعیت: توسط منشی تأیید شد."
        )
        # ارسال پیام به بیمار
        try:
            await context.bot.send_message(
                chat_id=patient_id,
                text="سلام، درخواست نوبت شما توسط منشی مطب تأیید شد. منتظر دیدار شما در ساعت مقرر هستیم. 🩺",
            )
        except Exception as e:
            print(f"خطا در ارسال پیام به بیمار: {e}")

    elif action == "reject":
        await query.edit_message_text(
            text=f"{query.message.text}\n\n❌ وضعیت: توسط منشی رد / لغو شد."
        )
        try:
            await context.bot.send_message(
                chat_id=patient_id,
                text="سلام، متأسفانه زمان انتخابی مقدور نبود. لطفاً جهت هماهنگی زمان دیگر در ربات پیام دهید یا با مطب تماس بگیرید.",
            )
        except Exception as e:
            print(f"خطا در ارسال پیام به بیمار: {e}")



def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_button_click))
    
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()