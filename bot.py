import os
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# 1. Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. Список стран (наш первый «данные»)
COUNTRIES = [
    "Китай",
    "Япония",
    "Южная Корея",
    "Европа",
    "США"
]

# 3. Функция, которая вызывается при /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # создаём кнопки
    keyboard = []
    for country in COUNTRIES:
        keyboard.append(
            [InlineKeyboardButton(country, callback_data=country)]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    # отправляем сообщение с кнопками
    await update.message.reply_text(
        "👋 Привет!\nВыбери страну выкупа:",
        reply_markup=reply_markup
    )

# 4. Функция, которая срабатывает при нажатии на кнопку
async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    country = query.data  # то, что нажал пользователь
    context.user_data["country"] = country  # сохраняем выбор

    await query.message.reply_text(
        f"🌍 Ты выбрал страну: {country}"
    )

# 5. Запуск бота
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(choose_country))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
