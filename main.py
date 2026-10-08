import os
import asyncio
import sqlite3
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI

# 1. سرور پورت مجازی برای اینکه Render سرویس رو نبنده
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and healthy!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# اجرای سرور وب در یک ترد جداگانه
Thread(target=run_dummy_server, daemon=True).start()

# 2. دریافت متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN")
AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(
    api_key=AVALAI_API_KEY,
    base_url="https://api.avalai.ir/v1"
)

# 3. راه‌اندازی دیتابیس محلی
def init_db():
    conn = sqlite3.connect("study_bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_message(chat_id: int, text: str):
    conn = sqlite3.connect("study_bot.db")
    c = conn.cursor()
    c.execute("INSERT INTO messages (chat_id, text) VALUES (?, ?)", (chat_id, text))
    conn.commit()
    conn.close()

def get_and_clear_messages(chat_id: int):
    conn = sqlite3.connect("study_bot.db")
    c = conn.cursor()
    c.execute("SELECT text FROM messages WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return [r[0] for r in rows]

# 4. دریافت پیام‌ها از گروه‌ها
@dp.message()
async def handle_group_message(message: types.Message):
    # ذخیره پیام‌هایی که داخل گروه فرستاده می‌شن
    if message.chat.type in ["group", "supergroup"] and message.text:
        save_message(message.chat.id, message.text)

# 5. هوش مصنوعی و جمع‌بندی ساعت ۲۳:۵۹
async def generate_summary(chat_id: int):
    messages = get_and_clear_messages(chat_id)
    if not messages:
        return

    text_data = "\n".join(messages)
    prompt = f"""
    تو دستیار گروه‌های درسی دانشگاهی هستی. پیام‌های امروز گروه ارسال شده است.
    لطفاً پیام‌های چت معمولی، احوالپرسی و شوخی‌ها را حذف کن.
    فقط و فقط اطلاعیه‌های درسی، ساعت و روز کلاس‌ها، امتحانات، کوئیزها و تکالیف را به شکل یک برنامه منظم، ساختاریافته و با بولت‌پوینت و هشتگ‌های مناسب (#امتحان #تکلیف #برنامه_کلاسی) بنویس:

    پیام‌ها:
    {text_data}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        summary = response.choices[0].message.content
        await bot.send_message(chat_id=chat_id, text=f"📋 **جمع‌بندی برنامه‌های درسی امروز:**\n\n{summary}")
    except Exception as e:
        print(f"AI Summary Error: {e}")

async def run_daily_summary():
    conn = sqlite3.connect("study_bot.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id FROM messages")
    chats = [r[0] for r in c.fetchall()]
    conn.close()

    for chat_id in chats:
        await generate_summary(chat_id)

# 6. اجرای ربات و زمان‌بند
async def main():
    init_db()
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    # زمان‌بندی روی ساعت ۲۳:۵۹ هر شب
    scheduler.add_job(run_daily_summary, "cron", hour=23, minute=59)
    scheduler.start()

    print("Bot is up and polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


