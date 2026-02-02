import asyncio
import logging
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
import aiosqlite

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {6691490829}

DATA_DIR = "/app/data"
DB_PATH = f"{DATA_DIR}/orders.db"
BACKUP_PATH = f"{DATA_DIR}/backup_orders.json"

logging.basicConfig(level=logging.INFO)

# ================== BOT ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== DATABASE ==================

async def init_storage():
    os.makedirs(DATA_DIR, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            country TEXT,
            category TEXT,
            subcategory TEXT,
            item_description TEXT,
            weight REAL,
            item_price REAL,
            currency TEXT,
            goods_rub REAL,
            bank_commission REAL,
            service_commission REAL,
            delivery_rub REAL,
            final_price REAL,
            delivery_time TEXT,
            status TEXT,
            created_at TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_currency TEXT,
            to_currency TEXT,
            rate REAL,
            date TEXT
        )
        """)
        await db.commit()

    # создаём backup-файл, если его нет
    if not os.path.exists(BACKUP_PATH):
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

# ================== KEYBOARDS ==================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Рассчитать заказ")],
        [KeyboardButton(text="🧾 Мои заказы")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

# ================== HANDLERS ==================

@dp.message(CommandStart())
async def start_handler(message: Message):
    text = (
        "👋 Добро пожаловать в *Kory Delivery*\n\n"
        "Я помогу рассчитать *полную стоимость доставки заказа* "
        "с учётом цены товара, доставки, комиссий и актуального курса валют.\n\n"
        "📌 Расчёт предварительный, курс фиксируется на день запроса.\n\n"
        "Выберите действие ниже ⬇️\n\n"
        "⚡ Не хотите ждать доставку?\n"
        "Сочные товары в наличии: @Slv17sSs"
    )
    await message.answer(text, reply_markup=main_keyboard, parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Информация")
async def info_handler(message: Message):
    await message.answer(
        "ℹ️ *Информация*\n\n"
        "• Бот считает предварительную стоимость доставки\n"
        "• Итоговая цена может немного отличаться\n"
        "• После подтверждения заказа менеджер свяжется с вами",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🧾 Мои заказы")
async def my_orders_placeholder(message: Message):
    await message.answer(
        "🧾 У вас пока нет оформленных заказов.\n\n"
        "Нажмите «📦 Рассчитать заказ», чтобы создать новый."
    )

# ================== START ==================

async def main():
    await init_storage()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
