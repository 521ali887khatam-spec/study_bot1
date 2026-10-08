import os
import asyncio
import sqlite3
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from aiogram import Bot, Dispatcher, types, F
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI

# 1. خواندن کلیدها از متغیرهای رندر
BOT_TOKEN = os.getenv("BOT_TOKEN")
AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# اتصال به AvalAI
client = OpenAI(
    api_key=AVALAI_API_KEY,
    base_url="https://api.avalai.ir/v1"
)

# 2. راه‌اندازی دیتابیس برای ذخیره پیام‌های گروه
def init_db():
    conn = sqlite3.connect("study_bot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

