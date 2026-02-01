import os
import csv
import sqlite3
import requests
from datetime import datetime, date

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
    MessageHandler,
    ContextTypes,
    filters
)

# ================= ENV =================

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")

# ================= FILES =================

DB_FILE = "database.db"
CSV_FILE = "orders_backup.csv"
BANK_FEE = 0.002

# ================= DATA =================

COUNTRIES = ["Китай", "Япония", "Южная Корея", "Европа", "США"]

DELIVERY_PRICE_PER_KG = {
    "Китай": 8,
    "Южная Корея": 14,
    "Япония": 18,
    "Европа": 18,
    "США": 18
}

DELIVERY_TIME = {
    "Китай": "≈ 20 дней",
    "Япония": "≈ 1–1.5 месяца",
    "Южная Корея": "≈ 1–1.5 месяца",
    "США": "≈ 1–1.5 месяца",
    "Европа": "≈ 1 месяц"
}

CATEGORIES = {
    "Одежда": {
        "Футболка": 0.25,
        "Толстовка": 0.6,
        "Куртка": 1.2
    },
    "Обувь": {
        "Кроссовки": 1.3,
        "Ботинки": 1.8
    },
    "Аксессуары": {
        "Сумка": 1.2,
        "Мессенджер": 0.6,
        "Часы": 0.3
    }
}

EU_CURRENCIES = ["EUR", "PLN", "GBP"]

# ================= DATABASE =================

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            user_id INTEGER,
            username TEXT,
            country TEXT,
            category TEXT,
            subcategory TEXT,
            price_local REAL,
            currency TEXT,
            total_rub REAL,
            status TEXT,
            created_at TEXT
        )
        """)
        conn.commit()

# ================= UTIL =================

def delete_last_message(context):
    try:
        chat_id = context.user_data["chat_id"]
        msg_id = context.user_data.get("last_message_id")
        if msg_id:
            return context.bot.delete_message(chat_id, msg_id)
    except:
        pass

def save_message(context, message):
    context.user_data["last_message_id"] = message.message_id

def get_rate(base, target):
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/{base}"
    return requests.get(url).json()["conversion_rates"][target]

def calc_commission(rub):
    if rub <= 5000:
        return 450
    if rub <= 9999:
        return 1000
    return 1500

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"country:{c}")]
        for c in COUNTRIES
    ]

    msg = await update.message.reply_text(
        "👋 Калькулятор доставки **Koru Delivery**\n\n"
        "Выбери страну выкупа:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    save_message(context, msg)

# ================= FLOW =================

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last_message(context)
    q = update.callback_query
    await q.answer()

    context.user_data["country"] = q.data.split(":")[1]

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"cat:{c}")]
        for c in CATEGORIES
    ]

    msg = await q.message.reply_text(
        "📦 Выбери категорию:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_message(context, msg)

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last_message(context)
    q = update.callback_query
    await q.answer()

    context.user_data["category"] = q.data.split(":")[1]

    keyboard = [
        [InlineKeyboardButton(k, callback_data=f"sub:{k}")]
        for k in CATEGORIES[context.user_data["category"]]
    ]

    msg = await q.message.reply_text(
        "📦 Выбери товар:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_message(context, msg)

async def choose_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last_message(context)
    q = update.callback_query
    await q.answer()

    context.user_data["subcategory"] = q.data.split(":")[1]
    context.user_data["step"] = "price"

    msg = await q.message.reply_text(
        "💰 Введи стоимость товара **числом**:"
    )
    save_message(context, msg)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "price":
        return

    raw = update.message.text
    cleaned = "".join(c for c in raw if c.isdigit() or c in ".,").replace(",", ".")
    price = float(cleaned)

    country = context.user_data["country"]

    if country == "Китай":
        rub = price * get_rate("CNY", "RUB")
    else:
        usd = price if country != "Европа" else price * get_rate("EUR", "USD")
        rub = usd * get_rate("USD", "RUB")

    rub *= (1 + BANK_FEE)
    commission = calc_commission(rub)
    total = int(rub + commission)

    context.user_data["total"] = total

    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]
    ]

    msg = await update.message.reply_text(
        f"📦 Итог:\n"
        f"Страна: {country}\n"
        f"Товар: {context.user_data['subcategory']}\n"
        f"Цена: ~{total} ₽\n"
        f"Срок: {DELIVERY_TIME[country]}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_message(context, msg)

# ================= CONFIRM =================

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last_message(context)
    q = update.callback_query
    await q.answer()

    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO orders (
            order_number, user_id, username, country,
            category, subcategory, price_local,
            currency, total_rub, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"KD-{int(datetime.now().timestamp())}",
            q.from_user.id,
            q.from_user.username,
            context.user_data["country"],
            context.user_data["category"],
            context.user_data["subcategory"],
            0,
            "",
            context.user_data["total"],
            "В обработке",
            datetime.now().isoformat()
        ))
        conn.commit()

    keyboard = [
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🔁 Новый заказ", callback_data="new_order")]
    ]

    msg = await q.message.reply_text(
        "✅ Заказ принят!\nМенеджер скоро свяжется с вами.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_message(context, msg)
    context.user_data.clear()

# ================= MY ORDERS =================

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT order_number, status FROM orders WHERE user_id=?",
            (q.from_user.id,)
        )
        rows = cur.fetchall()

    text = "📦 Ваши заказы:\n\n"
    for r in rows:
        text += f"{r[0]} — {r[1]}\n"

    await q.message.reply_text(text)

async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ================= ADMIN =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT order_number, username, status FROM orders")
        rows = cur.fetchall()

    text = "📋 Все заказы:\n\n"
    for r in rows:
        text += f"{r[0]} — @{r[1]} — {r[2]}\n"

    await update.message.reply_text(text)

# ================= MAIN =================

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(choose_country, "^country:"))
    app.add_handler(CallbackQueryHandler(choose_category, "^cat:"))
    app.add_handler(CallbackQueryHandler(choose_sub, "^sub:"))
    app.add_handler(CallbackQueryHandler(confirm, "^confirm$"))
    app.add_handler(CallbackQueryHandler(my_orders, "^my_orders$"))
    app.add_handler(CallbackQueryHandler(new_order, "^new_order$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
