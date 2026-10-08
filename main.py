import os
import asyncio
import logging
import sqlite3
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from openai import OpenAI

# متغیرها از تنظیمات رندر خوانده می‌شوند
BOT_TOKEN = os.getenv("BOT_TOKEN")
AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")
TIMEZONE = pytz.timezone("Asia/Tehran")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# اتصال به سرور هوش مصنوعی AvalAI
ai_client = OpenAI(
    api_key=AVALAI_API_KEY,
    base_url="https://api.avalai.ir/v1"
)

def init_db():
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_name TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(chat_id: int, user_name: str, text: str):
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (chat_id, user_name, text) VALUES (?, ?, ?)", (chat_id, user_name, text))
    conn.commit()
    conn.close()

def get_recent_messages(chat_id: int):
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_name, text FROM messages 
        WHERE chat_id = ? AND timestamp >= datetime('now', '-24 hours')
    """, (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [f"{row[0]}: {row[1]}" for row in rows]

def clear_old_messages():
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE timestamp < datetime('now', '-3 days')")
    conn.commit()
    conn.close()

def save_setting(key: str, value: str):
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str):
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def generate_study_summary(messages: list) -> str:
    if not messages:
        return "امروز پیامی برای استخراج در گروه ثبت نشده است."

    raw_text = "\n".join(messages)

    system_prompt = """
تو دستیار هوشمند مدیریت و خلاصه‌سازی اطلاعیه‌های درسی هستی.
پیام‌های ۲۴ ساعت گذشته گروه دانشجویی را بررسی کن و چت‌های معمولی و احوالپرسی‌ها را کاملاً حذف کن.
فقط مواردی که مربوط به:
۱) کلاس‌ها، اساتید و ساعت تشکیل
۲) تکالیف، گزارش‌کارها و ددلاین تحویل
۳) امتحانات، آزمونک‌ها و کوئیزها
۴) تغییر ساعات کلاس‌ها یا اطلاعیه‌های آموزشی
است را استخراج کن.

الزامات:
- از هشتگ‌های مرتبط مثل #کلاس ، #تکلیف ، #امتحان ، #اطلاعیه استفاده کن.
- در پایان یک بخش «⚠️ کارهای ضروری و مهم فردا» اضافه کن.
- اگر برنامه یا تکلیفی ثبت نشده بود، بگو برنامه‌ای برای فردا اعلام نشده است.
"""

    response = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"پیام‌های ۲۴ ساعت گذشته:\n\n{raw_text}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

async def send_nightly_digest():
    group_id = get_setting("group_id")
    if not group_id:
        return

    recent_msgs = get_recent_messages(int(group_id))
    if not recent_msgs:
        return

    summary = generate_study_summary(recent_msgs)
    now = datetime.now(TIMEZONE).strftime("%Y/%m/%d")
    final_message = f"🌙 **جمع‌بندی برنامه درسی فردا ({now})**\n\n{summary}"
    
    try:
        await bot.send_message(chat_id=int(group_id), text=final_message, parse_mode="Markdown")
        clear_old_messages()
    except Exception as e:
        logging.error(f"خطا در ارسال پیام: {e}")

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    save_setting("group_id", str(message.chat.id))
    
    if message.text and message.text.startswith("/summary"):
        recent_msgs = get_recent_messages(message.chat.id)
        if not recent_msgs:
            await message.reply("پیامی در ۲۴ ساعت گذشته ذخیره نشده است.")
            return
        wait_msg = await message.reply("⏳ در حال استخراج اطلاعیه‌ها و تولید خلاصه...")
        summary = generate_study_summary(recent_msgs)
        await wait_msg.edit_text(summary)
        return

    if message.text:
        sender_name = message.from_user.full_name if message.from_user else "کاربر"
        save_message(message.chat.id, sender_name, message.text)

async def main():
    init_db()
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        send_nightly_digest,
        trigger=CronTrigger(hour=23, minute=59, timezone=TIMEZONE)
    )
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
