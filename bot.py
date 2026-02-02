import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

# ====== ВАЖНО: ИМПОРТЫ FSM ======
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================================================
# ❗❗❗ ВОТ ЭТО И ЕСТЬ FSM + КЛАСС ❗❗❗
# ==================================================

class OrderFSM(StatesGroup):
    choosing_country = State()

# ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
# ЭТО:
# - class = "коробка"
# - OrderFSM = имя коробки
# - choosing_country = шаг №1
# ==================================================

# ====== КНОПКИ СТРАН (НЕ FSM, ПРОСТО КНОПКИ) ======

ccountry_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇨🇳 Китай", callback_data="country_china")],
        [InlineKeyboardButton(text="🇺🇸 США", callback_data="country_usa")],
        [InlineKeyboardButton(text="🇰🇷 Южная Корея", callback_data="country_korea")],
        [InlineKeyboardButton(text="🇯🇵 Япония", callback_data="country_japan")],
        [InlineKeyboardButton(text="🇪🇺 Европа", callback_data="country_europe")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
)


# ==================================================
# ХЕНДЛЕРЫ (ЛОГИКА)
# ==================================================

@dp.message(CommandStart())
@dp.message(CommandStart())
async def start(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Рассчитать заказ")]
        ],
        resize_keyboard=True
    )

   await message.answer(
    "👋 Добро пожаловать в *Kory Delivery*\n\n"
    "Я помогу рассчитать *полную стоимость доставки заказа* "
    "с учётом цены товара, доставки, комиссий и актуального курса валют.\n\n"
    "📌 Расчёт предварительный, курс фиксируется на день запроса.\n\n"
    "Выберите действие ниже ⬇️\n\n"
    "⚡ Не хотите ждать доставку?\n"
    "Сочные товары в наличии: @Slv17sSs",
    reply_markup=kb,
    parse_mode=\"Markdown\"
)


# ====== КНОПКА «РАССЧИТАТЬ ЗАКАЗ» ======

@dp.message(F.text == "📦 Рассчитать заказ")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(OrderFSM.choosing_country)

    await message.answer(
        "Выбери страну отправления:",
        reply_markup=country_keyboard
    )

# ====== НАЖАТИЕ НА КНОПКУ СТРАНЫ ======

@dp.callback_query(F.data.startswith("country_"))
@dp.callback_query(F.data.startswith("country_"))
async def choose_country(callback: CallbackQuery, state: FSMContext):
    # 🔹 ВОТ ОН — СЛОВАРЬ СТРАН
    country_map = {
        "country_china": "Китай",
        "country_usa": "США",
        "country_korea": "Южная Корея",
        "country_japan": "Япония",
        "country_europe": "Европа"
    }

    # берём то, что пришло от кнопки
    country = country_map.get(callback.data)

    # сохраняем в FSM
    await state.update_data(country=country)

    await callback.message.answer(
        f"✅ Страна выбрана: {country}\n\n"
        "Дальше будем выбирать категорию товара."
    )

    await callback.answer()

# ====== ОТМЕНА ======

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено ❌")
    await callback.answer()

# ==================================================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
