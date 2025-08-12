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

nest_asyncio.apply()
load_dotenv()

PORTAL_URL = os.getenv("PORTAL_URL")
PORTAL_USERNAME = os.getenv("PORTAL_USERNAME")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

DATA_FILE = "last_data.json"

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
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
    await update.message.reply_text("الأوامر المتاحة:\n/start\n/help")

def run_schedule(application):
    schedule.every(10).minutes.do(check_for_updates, application=application)
    while True:
        schedule.run_pending()
        time.sleep(1)

async def main():
    # الرابط الكامل للويب هوك - مهم جداً! Replace with your actual Render hostname env variable
    RENDER_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    PORT = int(os.getenv("PORT", 8443))

    if not RENDER_HOSTNAME:
        print("Environment variable RENDER_EXTERNAL_HOSTNAME is missing!")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # شغل الجدولة بفصل Thread
    thread = Thread(target=run_schedule, args=(application,), daemon=True)
    thread.start()

    # شغل البوت كـ webhook (استبدال polling)
    await application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_BOT_TOKEN,
        webhook_url=f"https://{RENDER_HOSTNAME}/{TELEGRAM_BOT_TOKEN}"
    )

if __name__ == "__main__":
    asyncio.run(main())
