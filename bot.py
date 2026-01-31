import os
import csv
import sqlite3
import requests
from datetime import datetime, date

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

# ================== ENV ==================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")

# ================== FILES ==================

DB_FILE = "database.db"
CSV_FILE = "orders_backup.csv"

BANK_FEE = 0.002  # 0.2%

# ================== CONSTANTS ==================

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
        "Толстовка / худи": 0.6,
        "Свитшот": 0.5,
        "Куртка": 1.2,
        "Ветровка": 0.8,
        "Штаны / джинсы": 0.7
    },
    "Обувь": {
        "Кроссовки": 1.3,
        "Ботинки": 1.8,
        "Лоферы / туфли": 1.2
    },
    "Аксессуары": {
        "Сумка (маленькая)": 0.7,
        "Сумка (средняя)": 1.2,
        "Мессенджер (Eastpak JR 11.5)": 0.6,
        "Рюкзак": 1.0,
        "Часы": 0.3,
        "Украшения": 0.2,
        "Ремни / кошельки": 0.4
    }
}

EU_CURRENCIES = ["EUR", "PLN", "GBP"]

# ================== DATABASE ==================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS exchange_rates (
        base TEXT,
        target TEXT,
        rate REAL,
        date TEXT,
        PRIMARY KEY (base, target, date)
    )
    """)

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
        price_rub REAL,
        weight REAL,
        commission INTEGER,
        status TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

# ================== CSV ==================

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "date", "order_number", "username", "user_id",
                "country", "category", "subcategory",
                "price_local", "currency", "price_rub",
                "weight", "commission", "status"
            ])

def write_csv(row):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# ================== RATES ==================

def get_rate(base, target):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
        "SELECT rate FROM exchange_rates WHERE base=? AND target=? AND date=?",
        (base, target, today)
    )
    row = cur.fetchone()

    if row:
        conn.close()
        return row[0]

    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/{base}"
    data = requests.get(url, timeout=10).json()

    rate = data["conversion_rates"][target]

    cur.execute(
        "INSERT INTO exchange_rates VALUES (?, ?, ?, ?)",
        (base, target, rate, today)
    )
    conn.commit()
    conn.close()
    return rate

def convert_to_rub(country, price, currency=None):
    if country == "Китай":
        rate = get_rate("CNY", "RUB")
        return price * rate * (1 + BANK_FEE)

    if currency:
        usd = price * get_rate(currency, "USD")
    else:
        usd = price

    rub = usd * get_rate("USD", "RUB")
    return rub * (1 + BANK_FEE)

# ================== COMMISSION ==================

def calc_commission(rub):
    if rub <= 5000:
        return 450
    if rub <= 9999:
        return 1000
    return 1500

# ================== ORDER NUMBER ==================

def generate_order_number():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders")
    count = cur.fetchone()[0] + 1
    conn.close()
    return f"KD-{count:04d}"

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    text = (
        "👋 Привет!\n\n"
        "Я — калькулятор доставки товаров из-за границы для Telegram-канала "
        "**Koru Delivery** 🌍\n\n"
        "Я помогу рассчитать **примерную стоимость** заказа.\n\n"
        "⚠️ Важно:\n"
        "— расчёт ориентировочный\n"
        "— курс валют может измениться\n"
        "— финальная цена подтверждается менеджером\n\n"
        "👇 Выбери страну выкупа:"
    )

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"country:{c}")]
        for c in COUNTRIES
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================== FLOW ==================

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["country"] = q.data.split(":")[1]

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"cat:{c}")]
        for c in CATEGORIES
    ]

    await q.message.reply_text(
        "📦 Выбери категорию товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["category"] = q.data.split(":")[1]

    subs = CATEGORIES[context.user_data["category"]]
    keyboard = [
        [InlineKeyboardButton(k, callback_data=f"sub:{k}")]
        for k in subs
    ]

    await q.message.reply_text(
        "📦 Выбери тип товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def choose_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    sub = q.data.split(":")[1]
    context.user_data["subcategory"] = sub
    context.user_data["weight"] = CATEGORIES[context.user_data["category"]][sub]

    await q.message.reply_text(
        "🔗 Пришли ссылку или любое описание товара."
    )
    context.user_data["step"] = "description"

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    if step == "description":
        context.user_data["description"] = update.message.text

        if context.user_data["country"] == "Европа":
            keyboard = [
                [InlineKeyboardButton(c, callback_data=f"cur:{c}")]
                for c in EU_CURRENCIES
            ]
            await update.message.reply_text(
                "💱 Выбери валюту:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data["step"] = "currency"
        else:
            await update.message.reply_text(
                "💰 Укажи стоимость товара числом:"
            )
            context.user_data["step"] = "price"

    elif step == "price":
        price = float(update.message.text.replace(",", "."))
        context.user_data["price"] = price
        await show_final(update, context)

async def choose_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["currency"] = q.data.split(":")[1]
    await q.message.reply_text("💰 Укажи стоимость товара числом:")
    context.user_data["step"] = "price"

# ================== FINAL ==================

async def show_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = context.user_data["country"]
    price = context.user_data["price"]
    currency = context.user_data.get("currency")

    rub = convert_to_rub(country, price, currency)
    commission = calc_commission(rub)
    delivery = context.user_data["weight"] * DELIVERY_PRICE_PER_KG[country] * get_rate("USD", "RUB")
    total = int(rub + commission + delivery)

    context.user_data["total_rub"] = total

    text = (
        f"📦 **Расчёт заказа (примерный)**\n\n"
        f"🌍 Страна: {country}\n"
        f"🛍 Товар: {context.user_data['category']} / {context.user_data['subcategory']}\n\n"
        f"💰 Цена товара: {price} {currency or ''}\n"
        f"💰 Итого: ~{total} ₽\n"
        f"🚚 Срок доставки: {DELIVERY_TIME[country]}\n"
        f"🧾 Комиссия: {commission} ₽\n\n"
        f"⬇️ Подтвердить заказ?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================== CONFIRM / CANCEL ==================

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    order_number = generate_order_number()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO orders (
        order_number, user_id, username, country,
        category, subcategory, price_local, currency,
        price_rub, weight, commission, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number,
        q.from_user.id,
        q.from_user.username,
        context.user_data["country"],
        context.user_data["category"],
        context.user_data["subcategory"],
        context.user_data["price"],
        context.user_data.get("currency"),
        context.user_data["total_rub"],
        context.user_data["weight"],
        calc_commission(context.user_data["total_rub"]),
        "В обработке",
        now
    ))

    conn.commit()
    conn.close()

    write_csv([
        now.split(" ")[0],
        order_number,
        q.from_user.username,
        q.from_user.id,
        context.user_data["country"],
        context.user_data["category"],
        context.user_data["subcategory"],
        context.user_data["price"],
        context.user_data.get("currency"),
        context.user_data["total_rub"],
        context.user_data["weight"],
        calc_commission(context.user_data["total_rub"]),
        "В обработке"
    ])

    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 Новый заказ {order_number}\n"
        f"👤 @{q.from_user.username}"
    )

    await q.message.reply_text(
        f"✅ Заказ **{order_number}** принят.\n"
        f"Менеджер скоро свяжется с вами.",
        parse_mode="Markdown"
    )

    context.user_data.clear()

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("❌ Заказ отменён.")
    context.user_data.clear()

# ================== ADMIN ==================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📦 Все заказы", callback_data="admin:all")],
        [InlineKeyboardButton("🟡 В обработке", callback_data="admin:processing")],
        [InlineKeyboardButton("🟢 Завершённые", callback_data="admin:done")],
        [InlineKeyboardButton("🔴 Отменённые", callback_data="admin:canceled")]
    ]

    await update.message.reply_text(
        "📋 **Админ-панель**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def admin_show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_ID:
        return

    mode = q.data.split(":")[1]

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if mode == "all":
        cur.execute("SELECT order_number, username, status FROM orders")
    else:
        status_map = {
            "processing": "В обработке",
            "done": "Завершён",
            "canceled": "Отменён"
        }
        cur.execute(
            "SELECT order_number, username, status FROM orders WHERE status=?",
            (status_map[mode],)
        )

    rows = cur.fetchall()
    conn.close()

    for o in rows:
        await q.message.reply_text(f"{o[0]} — @{o[1]} — {o[2]}")

# ================== MAIN ==================

def main():
    init_db()
    init_csv()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(choose_country, "^country:"))
    app.add_handler(CallbackQueryHandler(choose_category, "^cat:"))
    app.add_handler(CallbackQueryHandler(choose_sub, "^sub:"))
    app.add_handler(CallbackQueryHandler(choose_currency, "^cur:"))
    app.add_handler(CallbackQueryHandler(confirm_order, "^confirm$"))
    app.add_handler(CallbackQueryHandler(cancel_order, "^cancel$"))
    app.add_handler(CallbackQueryHandler(admin_show_orders, "^admin:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
