import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
import requests
from bs4 import BeautifulSoup
import json
import schedule
import time
from threading import Thread
import datetime

nest_asyncio.apply()
load_dotenv()

PORTAL_URL = os.getenv("PORTAL_URL")
PORTAL_USERNAME = os.getenv("PORTAL_USERNAME")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

DATA_FILE = "last_data.json"
REMINDERS_FILE = "reminders.json"

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
    data_text = soup.get_text()
    return data_text

async def notify_update(application, message):
    await application.bot.send_message(chat_id=CHAT_ID, text=message)

def check_for_updates(application):
    old_data = load_data()
    new_data = fetch_portal_data()

    if old_data.get("content") != new_data:
        save_data({"content": new_data})
        asyncio.run_coroutine_threadsafe(
            notify_update(application, "تم تحديث جديد في البوابة! الرجاء التحقق."), asyncio.get_event_loop()
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! البوت يعمل بنجاح.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "الأوامر المتاحة:\n"
        "/start - تشغيل البوت\n"
        "/help - عرض الأوامر\n"
        "/status - حالة البوت والبوابة\n"
        "/addreminder YYYY-MM-DD hh:mmAM/PM رسالة التذكير\n"
        "مثال: /addreminder 2025-10-01 10:30AM بدء التسجيل\n"
        "/listreminders - عرض التذكيرات\n"
        "/delreminder رقم_التذكير - حذف التذكير\n"
    )
    await update.message.reply_text(text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    portal_status = "متصل" if data else "غير متصل"
    reminders = load_reminders()
    reminders_count = len(reminders)
    text = (
        f"حالة البوت: يعمل\n"
        f"حالة البوابة: {portal_status}\n"
        f"عدد التذكيرات: {reminders_count}\n"
        f"التذكيرات يتم التحقق منها كل 10 ثواني.\n"
    )
    await update.message.reply_text(text)

def parse_time_ampm(time_str):
    """
    يحول وقت بصيغة hh:mmAM أو hh:mmPM إلى ساعة ودقيقة 24 ساعة
    """
    try:
        dt = datetime.datetime.strptime(time_str.upper(), "%I:%M%p")
        return dt.hour, dt.minute
    except ValueError:
        return None, None

async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ: استخدم الصيغة: /addreminder YYYY-MM-DD hh:mmAM/PM رسالة التذكير")
        return

    date_str = args[0]  # التاريخ
    time_str = args[1]  # الوقت مع AM/PM
    message = " ".join(args[2:])  # نص التذكير

    hour, minute = parse_time_ampm(time_str)
    if hour is None:
        await update.message.reply_text("خطأ في صيغة الوقت. استخدم hh:mmAM أو hh:mmPM مثل 10:30AM أو 03:15PM")
        return

    try:
        dt_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        dt = datetime.datetime.combine(dt_date, datetime.time(hour, minute))
        if dt < datetime.datetime.now():
            await update.message.reply_text("لا يمكن إضافة تذكير لوقت مضى.")
            return
    except Exception as e:
        await update.message.reply_text(f"خطأ في التاريخ: {e}")
        return

    reminders = load_reminders()
    reminders.append({
        "datetime": dt.isoformat(),
        "message": message
    })
    save_reminders(reminders)
    await update.message.reply_text(f"تم إضافة التذكير: {dt.strftime('%Y-%m-%d %I:%M %p')} - {message}")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminders = load_reminders()
    if not reminders:
        await update.message.reply_text("لا توجد تذكيرات حالياً.")
        return

    text = "التذكيرات:\n"
    for i, r in enumerate(reminders, 1):
        dt = datetime.datetime.fromisoformat(r["datetime"])
        text += f"{i}. {dt.strftime('%Y-%m-%d %I:%M %p')} - {r['message']}\n"
    await update.message.reply_text(text)

async def del_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("استخدم: /delreminder رقم_التذكير")
        return

    index = int(args[0]) - 1
    reminders = load_reminders()

    if index < 0 or index >= len(reminders):
        await update.message.reply_text("رقم التذكير غير صحيح.")
        return

    removed = reminders.pop(index)
    save_reminders(reminders)
    dt = datetime.datetime.fromisoformat(removed["datetime"])
    await update.message.reply_text(f"تم حذف التذكير: {dt.strftime('%Y-%m-%d %I:%M %p')} - {removed['message']}")

def check_reminders(application):
    reminders = load_reminders()
    now = datetime.datetime.now()
    to_keep = []
    for r in reminders:
        dt = datetime.datetime.fromisoformat(r["datetime"])
        if dt <= now:
            # أرسل التذكير
            asyncio.run_coroutine_threadsafe(
                notify_update(application, f"⏰ تذكير: {r['message']} (الوقت: {dt.strftime('%Y-%m-%d %I:%M %p')})"),
                asyncio.get_event_loop()
            )
        else:
            to_keep.append(r)
    if len(to_keep) != len(reminders):
        save_reminders(to_keep)

def run_schedule(application):
    schedule.every(10).seconds.do(check_for_updates, application=application)
    schedule.every(10).seconds.do(check_reminders, application=application)
    while True:
        schedule.run_pending()
        time.sleep(1)

async def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("addreminder", add_reminder))
    application.add_handler(CommandHandler("listreminders", list_reminders))
    application.add_handler(CommandHandler("delreminder", del_reminder))

    thread = Thread(target=run_schedule, args=(application,), daemon=True)
    thread.start()

    print("Bot started.")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
