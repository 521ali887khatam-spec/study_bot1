import os
import asyncio
import sqlite3
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI

# 1. سرور برای زنده نگه داشتن در Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

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

# 3. دیتابیس
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

# 4. پاسخ به دستور استارت (برای اینکه بفهمی ربات روشنه!)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply("سلام علی جان! من روشنم و آماده کارم 🚀\nمنو ادد کن به گروه درسی‌تون و ادمینم کن تا پیام‌ها رو جمع کنم.")

# 5. هوش مصنوعی و تابع جمع‌بندی
async def process_and_send_summary(chat_id: int):
    messages = get_and_clear_messages(chat_id)
    if not messages:
        await bot.send_message(chat_id=chat_id, text="هنوز پیامی توی گروه ثبت نشده که خلاصه‌ش کنم!")
        return

    text_data = "\n".join(messages)
    prompt = f"""
    تو دستیار دانشجویی علوم آزمایشگاهی و دروس دانشگاهی هستی. پیام‌های امروز گروه ارسال شده است.
    چت‌های معمولی، سلام و احوالپرسی و شوخی‌ها رو نادیده بگیر.
    اطلاعیه‌های درسی، ساعت و روز کلاس‌ها، کوئیزها، امتحانات، جزوه‌ها و تکالیف رو استخراج کن.
    یک گزارش خیلی منظم و شیک با بالت‌پوینت و هشتگ‌های مناسب بساز:

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
        await bot.send_message(chat_id=chat_id, text=f"📋 **جمع‌بندی برنامه‌های گروه:**\n\n{summary}")
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"خطا در ارتباط با هوش مصنوعی: {e}")

# 6. دستور تست دستی
@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    await message.reply("در حال بررسی پیام‌ها و فرستادن به AvalAI... چند ثانیه صبر کن...")
    await process_and_send_summary(message.chat.id)

# 7. دریافت و ذخیره پیام‌های گروه
@dp.message()
async def handle_group_message(message: types.Message):
    if message.chat.type in ["group", "supergroup"] and message.text:
        # اگر پیام دستور تلگرامی نبود ذخیره‌ش کن
        if not message.text.startswith("/"):
            save_message(message.chat.id, message.text)

# 8. اجرای خودکار در ساعت ۲۳:۵۹
async def run_daily_summary():
    conn = sqlite3.connect("study_bot.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id FROM messages")
    chats = [r[0] for r in c.fetchall()]
    conn.close()

    for c_id in chats:
        await process_and_send_summary(c_id)

async def main():
    init_db()
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    scheduler.add_job(run_daily_summary, "cron", hour=23, minute=59)
    scheduler.start()
    print("Bot is listening...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
