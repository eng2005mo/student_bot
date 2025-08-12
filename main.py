import os
import asyncio
import json
import datetime
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
import requests
from bs4 import BeautifulSoup

# قراءة متغيرات البيئة حسب ما وضحت
PORTAL_URL = os.getenv("PORTAL_URL")  # http://appserver.fet.edu.jo:7778/reg_new/index.jsp
PORTAL_USERNAME = os.getenv("PORTAL_USERNAME")  # 32315125016
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD")  # 2001160162

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # توكن البوت
CHAT_ID = int(os.getenv("CHAT_ID"))  # رقم الشات كرقم صحيح

PORT = int(os.getenv("PORT", 8443))
RENDER_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

DATA_FILE = os.getenv("DATA_FILE", "last_data.json")
REMINDERS_FILE = os.getenv("REMINDERS_FILE", "reminders.json")

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_portal_data():
    session = requests.Session()
    login_payload = {
        "username": PORTAL_USERNAME,
        "password": PORTAL_PASSWORD,
    }
    session.post(PORTAL_URL, data=login_payload)
    response = session.get(PORTAL_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()

async def notify_update(application, message):
    await application.bot.send_message(chat_id=CHAT_ID, text=message)

async def check_for_updates(application):
    old_data = load_data()
    new_data = fetch_portal_data()
    if old_data.get("content") != new_data:
        save_data({"content": new_data})
        await notify_update(application, "📢 تم تحديث جديد في البوابة! الرجاء التحقق.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً! البوت يعمل بنجاح.\n"
        "استخدم /help لرؤية الأوامر المتاحة."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "الأوامر المتاحة:\n"
        "/start - تشغيل البوت\n"
        "/help - قائمة الأوامر\n"
        "/status - حالة البوت والبوابة\n"
        "/addreminder YYYY-MM-DD H M رسالة - إضافة تذكير\n"
        "   مثال: /addreminder 2025-10-01 1 0 بدء التسجيل\n"
        "/listreminders - عرض التذكيرات\n"
        "/delreminder رقم - حذف التذكير بالرقم\n"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت يعمل.\n🔄 يتم مراقبة البوابة والتذكيرات.")

async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "خطأ في الصيغة.\n"
            "استخدم: /addreminder YYYY-MM-DD H M رسالة\n"
            "مثال: /addreminder 2025-10-01 1 0 بدء التسجيل"
        )
        return
    try:
        date_str = args[0]
        hour = int(args[1])
        minute = int(args[2])
        message = " ".join(args[3:])
        dt = datetime.datetime.fromisoformat(date_str)
        dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt < datetime.datetime.now():
            await update.message.reply_text("لا يمكن إضافة تذكير لوقت مضى.")
            return
    except Exception as e:
        await update.message.reply_text(f"خطأ في التاريخ أو الوقت: {e}")
        return

    reminders = load_reminders()
    reminders.append({"datetime": dt.isoformat(), "message": message})
    reminders.sort(key=lambda x: x["datetime"])
    save_reminders(reminders)
    await update.message.reply_text(f"✅ تم إضافة التذكير: {dt.strftime('%Y-%m-%d %H:%M')} - {message}")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminders = load_reminders()
    if not reminders:
        await update.message.reply_text("لا توجد تذكيرات حالياً.")
        return
    text = "📅 قائمة التذكيرات:\n"
    for i, r in enumerate(reminders, 1):
        dt = datetime.datetime.fromisoformat(r["datetime"])
        text += f"{i}. {dt.strftime('%Y-%m-%d %H:%M')} - {r['message']}\n"
    await update.message.reply_text(text)

async def del_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("استخدم: /delreminder رقم التذكير")
        return
    idx = int(args[0]) - 1
    reminders = load_reminders()
    if idx < 0 or idx >= len(reminders):
        await update.message.reply_text("رقم التذكير غير صحيح.")
        return
    removed = reminders.pop(idx)
    save_reminders(reminders)
    dt = datetime.datetime.fromisoformat(removed["datetime"])
    await update.message.reply_text(f"✅ تم حذف التذكير: {dt.strftime('%Y-%m-%d %H:%M')} - {removed['message']}")

async def reminders_checker(application):
    while True:
        now = datetime.datetime.now()
        reminders = load_reminders()
        new_reminders = []
        for r in reminders:
            reminder_time = datetime.datetime.fromisoformat(r["datetime"])
            if now >= reminder_time:
                await notify_update(application, f"⏰ تذكير: {r['message']}")
            else:
                new_reminders.append(r)
        if len(new_reminders) != len(reminders):
            save_reminders(new_reminders)
        await asyncio.sleep(10)

async def portal_checker(application):
    while True:
        try:
            await check_for_updates(application)
        except Exception as e:
            print(f"خطأ في فحص البوابة: {e}")
        await asyncio.sleep(10)

async def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("addreminder", add_reminder))
    application.add_handler(CommandHandler("listreminders", list_reminders))
    application.add_handler(CommandHandler("delreminder", del_reminder))

    asyncio.create_task(reminders_checker(application))
    asyncio.create_task(portal_checker(application))

    await application.start()
    await application.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"https://{RENDER_HOSTNAME}/{TELEGRAM_BOT_TOKEN}"
    )
    print("Webhook running...")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
