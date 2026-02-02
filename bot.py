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

country_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇨🇳 Китай", callback_data="country_china")],
        [InlineKeyboardButton(text="🇺🇸 США", callback_data="country_usa")],
        [InlineKeyboardButton(text="🇪🇺 Европа", callback_data="country_europe")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ]
)

# ==================================================
# ХЕНДЛЕРЫ (ЛОГИКА)
# ==================================================

@dp.message(CommandStart())
async def start(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Рассчитать заказ")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Привет 👋\nНажми кнопку ниже, чтобы начать расчёт",
        reply_markup=kb
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
async def choose_country(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Страна выбрана ✅")
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
