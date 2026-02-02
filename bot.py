import asyncio
import logging
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
import aiosqlite

class OrderFSM(StatesGroup):
    country = State()
    category = State()
    product = State()
    quantity = State()

class OrderFSM(StatesGroup):
    country = State()
    category = State()
    product = State()
    quantity = State()



# ================== CONFIG ==================

import os
TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {6691490829}

DATA_DIR = "/app/data"
DB_PATH = f"{DATA_DIR}/orders.db"
BACKUP_PATH = f"{DATA_DIR}/backup_orders.json"

logging.basicConfig(level=logging.INFO)

# ================== BOT ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= FSM =================
class OrderFSM(StatesGroup):
    country = State()
    currency = State()   # 👈 ЭТАП 2


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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def countries_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇨🇳 Китай", callback_data="country_china")],
        [InlineKeyboardButton(text="🇺🇸 США", callback_data="country_usa")],
        [InlineKeyboardButton(text="🇰🇷 Южная Корея", callback_data="country_korea")],
        [InlineKeyboardButton(text="🇯🇵 Япония", callback_data="country_japan")],
        [InlineKeyboardButton(text="🇪🇺 Европа", callback_data="country_europe")]
    ])
def europe_currency_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💶 EUR", callback_data="currency_EUR")],
        [InlineKeyboardButton(text="💷 GBP", callback_data="currency_GBP")],
        [InlineKeyboardButton(text="🇵🇱 PLN", callback_data="currency_PLN")]
    ])

# ================== HANDLERS ==================

@# ================= START / INFO =================

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

# ================= START ORDER =================

@dp.callback_query(F.data == "calculate_order")
async def start_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(OrderFSM.country)

    await callback.message.answer(
        "🌍 Выберите страну покупки товара:",
        reply_markup=countries_kb()
    )
    await callback.answer()

# ================= COUNTRY =================

@dp.callback_query(OrderFSM.country, F.data.startswith("country_"))
async def choose_country(callback: CallbackQuery, state: FSMContext):
    country_map = {
        "country_china": "Китай",
        "country_usa": "США",
        "country_korea": "Южная Корея",
        "country_japan": "Япония",
        "country_europe": "Европа"
    }

    country = country_map.get(callback.data)

    if not country:
        await callback.answer("Ошибка выбора страны", show_alert=True)
        return

    await state.update_data(country=country)

    if country == "Европа":
        await state.set_state(OrderFSM.currency)
        await callback.message.answer(
            "💱 Выберите валюту оплаты:",
            reply_markup=europe_currency_kb()
        )
        await callback.answer()
        return

    auto_currency = {
        "Китай": "CNY",
        "США": "USD",
        "Южная Корея": "KRW",
        "Япония": "JPY"
    }

    currency = auto_currency.get(country)
    await state.update_data(currency=currency)

    await callback.message.answer(
        f"✅ Страна: <b>{country}</b>\n"
        f"💱 Валюта: <b>{currency}</b>\n\n"
        "Двигаемся дальше…"
    )
    await callback.answer()

# ================= CURRENCY (EU) =================

@dp.callback_query(OrderFSM.currency, F.data.startswith("currency_"))
async def choose_currency(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.replace("currency_", "")

    if currency not in {"EUR", "GBP", "PLN"}:
        await callback.answer("Ошибка выбора валюты", show_alert=True)
        return

    await state.update_data(currency=currency)

    await callback.message.answer(
        f"💱 Валюта выбрана: <b>{currency}</b>\n\n"
        "Двигаемся дальше…"
    )
    await callback.answer()

# ================= CATEGORY =================

@dp.callback_query(OrderFSM.category, F.data.startswith("category_"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    category_map = {
        "category_electronics": "Электроника",
        "category_clothes": "Одежда",
        "category_cosmetics": "Косметика",
        "category_toys": "Игрушки"
    }

    category = category_map.get(callback.data)

    await state.update_data(category=category)
    await state.set_state(OrderFSM.product)

    data = await state.get_data()

    await callback.message.answer(
        f"✅ Категория выбрана\n\n"
        f"🌍 Страна: {data['country']}\n"
        f"📦 Категория: {category}\n\n"
        "✏️ Напиши название товара:"
    )

    await callback.answer()

# ================= PRODUCT =================

@dp.message(OrderFSM.product)
async def enter_product(message: Message, state: FSMContext):
    await state.update_data(product=message.text)
    await state.set_state(OrderFSM.quantity)

    await message.answer("🔢 Введи количество товара:")

# ================= QUANTITY =================

@dp.message(OrderFSM.quantity)
async def enter_quantity(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Нужно число")
        return

    await state.update_data(quantity=int(message.text))
    data = await state.get_data()

    await message.answer(
        "✅ ЗАКАЗ ГОТОВ\n\n"
        f"🌍 {data['country']}\n"
        f"📦 {data['category']}\n"
        f"📝 {data['product']}\n"
        f"🔢 {data['quantity']}"
    )

    await state.clear()



# ================== START ==================

aasync def main():
    bot = Bot("TOKEN", parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

