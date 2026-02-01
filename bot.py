import os
import sqlite3
import requests
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= ENV =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")

# ================= CONSTANTS =================

BANK_FEE = 0.002  # 0.2%

COUNTRIES = ["Китай", "США", "Европа", "Япония", "Южная Корея"]

DELIVERY_PRICE_PER_KG = {
    "Китай": 8,
    "США": 18,
    "Европа": 18,
    "Япония": 18,
    "Южная Корея": 14
}

DELIVERY_TIME = {
    "Китай": "≈ 20 дней",
    "США": "≈ 1–1.5 месяца",
    "Европа": "≈ 1 месяц",
    "Япония": "≈ 1–1.5 месяца",
    "Южная Корея": "≈ 1–1.5 месяца"
}

EU_CURRENCIES = ["EUR", "PLN", "GBP"]

CATEGORIES = {
    "Одежда": {
        "Футболка": 0.25,
        "Толстовка": 0.6,
        "Куртка": 1.2,
        "Штаны": 0.6
    },
    "Обувь": {
        "Кроссовки": 1.3,
        "Ботинки": 1.8
    },
    "Аксессуары": {
        "Сумка": 1.2,
        "Мессенджер": 0.6,
        "Часы": 0.3,
        "Украшения": 0.25
    }
}

DB_FILE = "database.db"

# ================= DATABASE =================

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            user_id INTEGER,
            username TEXT,
            country TEXT,
            category TEXT,
            subcategory TEXT,
            weight REAL,
            price_input REAL,
            total_rub REAL,
            status TEXT,
            created_at TEXT
        )
        """)

# ================= UTILS =================

def get_rate(base: str, target: str) -> float:
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/{base}"
    r = requests.get(url, timeout=10).json()
    return r["conversion_rates"][target]

def calc_commission(rub: float) -> int:
    if rub <= 5000:
        return 450
    if rub <= 9999:
        return 1000
    return 1500

def round_weight(weight: float) -> float:
    remainder = weight % 1
    if remainder == 0:
        return weight
    if remainder <= 0.3:
        return int(weight) + 0.3
    return int(weight) + 1

async def delete_last_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data.get("chat_id")
    message_id = context.user_data.get("last_message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.delete_message(chat_id, message_id)
    except:
        pass
    finally:
        context.user_data["last_message_id"] = None

def save_last_message(context: ContextTypes.DEFAULT_TYPE, msg):
    context.user_data["last_message_id"] = msg.message_id

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"country:{c}")]
        for c in COUNTRIES
    ]

    msg = await update.message.reply_text(
        "Привет!\n\n"
        "Я — калькулятор доставки товаров из-за границы для Telegram-канала Koru Delivery 🌍\n\n"
        "Я помогу рассчитать примерную стоимость заказа.\n\n"
        "⚠️ Важно:\n"
        "— расчёт ориентировочный\n"
        "— курс валют может измениться\n"
        "— финальная цена подтверждается менеджером\n\n"
        "👇 Выбери страну выкупа:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last_message(context, msg)

# ================= COUNTRY =================

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if context.user_data.get("locked"):
        return
    context.user_data["locked"] = True

    await delete_last_message(context)

    context.user_data["country"] = q.data.split(":")[1]

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in CATEGORIES
    ]

    msg = await q.message.reply_text(
        "📦 Выбери категорию товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last_message(context, msg)

    context.user_data["locked"] = False

# ================= CATEGORY =================

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if context.user_data.get("locked"):
        return
    context.user_data["locked"] = True

    await delete_last_message(context)

    category = q.data.split(":")[1]
    context.user_data["category"] = category

    keyboard = [
        [InlineKeyboardButton(sub, callback_data=f"sub:{sub}")]
        for sub in CATEGORIES[category]
    ]

    msg = await q.message.reply_text(
        "📦 Выбери тип товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last_message(context, msg)

    context.user_data["locked"] = False

# ================= SUBCATEGORY =================

async def choose_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if context.user_data.get("locked"):
        return
    context.user_data["locked"] = True

    await delete_last_message(context)

    sub = q.data.split(":")[1]
    category = context.user_data["category"]

    context.user_data["subcategory"] = sub
    context.user_data["weight"] = round_weight(CATEGORIES[category][sub])
    context.user_data["waiting_price"] = True

    msg = await q.message.reply_text(
        "💰 Введи стоимость товара числом:"
    )
    save_last_message(context, msg)

    context.user_data["locked"] = False

# ================= PRICE =================

async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_price"):
        return

    text = update.message.text.strip()
    cleaned = "".join(c for c in text if c.isdigit() or c in ".,").replace(",", ".")

    try:
        price = float(cleaned)
    except:
        return

    context.user_data["waiting_price"] = False
    context.user_data["price_input"] = price

    country = context.user_data["country"]

    if country == "Европа":
        keyboard = [
            [InlineKeyboardButton(cur, callback_data=f"eu:{cur}")]
            for cur in EU_CURRENCIES
        ]
        msg = await update.message.reply_text(
            "💱 Выбери валюту товара:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        save_last_message(context, msg)
        return

    await calculate_total(update, context, base_currency="USD")

# ================= EURO =================

async def choose_eu_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if context.user_data.get("locked"):
        return
    context.user_data["locked"] = True

    await delete_last_message(context)

    currency = q.data.split(":")[1]
    await calculate_total(update, context, base_currency=currency)

    context.user_data["locked"] = False

# ================= CALC =================

async def calculate_total(update: Update, context: ContextTypes.DEFAULT_TYPE, base_currency: str):
    country = context.user_data["country"]
    price = context.user_data["price_input"]
    weight = context.user_data["weight"]

    if country == "Китай":
        rub = price * get_rate("CNY", "RUB")
    else:
        usd = price if base_currency == "USD" else price * get_rate(base_currency, "USD")
        rub = usd * get_rate("USD", "RUB")

    rub *= (1 + BANK_FEE)

    delivery_usd = weight * DELIVERY_PRICE_PER_KG[country]
    delivery_rub = delivery_usd * get_rate("USD", "RUB")

    subtotal = rub + delivery_rub
    commission = calc_commission(subtotal)
    total = int(subtotal + commission)

    context.user_data["total"] = total

    keyboard = [[
        InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel")
    ]]

    msg = await update.effective_chat.send_message(
        f"📦 Итоговый расчёт:\n\n"
        f"🌍 Страна: {country}\n"
        f"🛍 Товар: {context.user_data['subcategory']}\n"
        f"⚖️ Вес: {weight} кг\n"
        f"💰 Итог: ~{total} ₽\n"
        f"🚚 Срок доставки: {DELIVERY_TIME[country]}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last_message(context, msg)

# ================= CONFIRM =================

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    await delete_last_message(context)

    order_number = f"KD-{int(datetime.now().timestamp())}"

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        INSERT INTO orders (
            order_number, user_id, username, country,
            category, subcategory, weight, price_input,
            total_rub, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_number,
            q.from_user.id,
            q.from_user.username,
            context.user_data["country"],
            context.user_data["category"],
            context.user_data["subcategory"],
            context.user_data["weight"],
            context.user_data["price_input"],
            context.user_data["total"],
            "В обработке",
            datetime.now().isoformat()
        ))

    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 Новый заказ {order_number}\n"
        f"👤 @{q.from_user.username}\n"
        f"💰 {context.user_data['total']} ₽"
    )

    keyboard = [
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🔁 Оформить новый заказ", callback_data="new_order")]
    ]

    msg = await q.message.reply_text(
        "✅ Заказ принят! Менеджер скоро свяжется с вами.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last_message(context, msg)
    context.user_data.clear()

# ================= MY ORDERS =================

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT order_number, status FROM orders WHERE user_id=?",
            (q.from_user.id,)
        ).fetchall()

    text = "📦 Мои заказы:\n\n"
    if not rows:
        text += "Пока заказов нет."
    else:
        for r in rows:
            text += f"{r[0]} — {r[1]}\n"

    await q.message.reply_text(text)

# ================= NEW ORDER =================

async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ================= ADMIN =================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT order_number, username, total_rub, status FROM orders"
        ).fetchall()

    text = "📋 Все заказы:\n\n"
    for r in rows:
        text += f"{r[0]} — @{r[1]} — {r[2]} ₽ — {r[3]}\n"

    await update.message.reply_text(text)

# ================= MAIN =================

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(choose_country, pattern="^country:"))
    app.add_handler(CallbackQueryHandler(choose_category, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(choose_subcategory, pattern="^sub:"))
    app.add_handler(CallbackQueryHandler(choose_eu_currency, pattern="^eu:"))
    app.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(new_order, pattern="^new_order$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price))

    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
