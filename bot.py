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

COUNTRIES = ["Китай", "Япония", "Южная Корея", "Европа", "США"]

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

WAIT_PRICE = "WAIT_PRICE"

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

async def delete_last(context: ContextTypes.DEFAULT_TYPE):
    cid = context.user_data.get("chat_id")
    mid = context.user_data.get("last_msg")
    if not cid or not mid:
        return
    try:
        await context.bot.delete_message(chat_id=cid, message_id=mid)
    except:
        pass

def save_last(context: ContextTypes.DEFAULT_TYPE, msg):
    context.user_data["last_msg"] = msg.message_id

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["chat_id"] = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton(c, callback_data=f"country:{c}")]
        for c in COUNTRIES
    ]

    msg = await update.message.reply_text(
        "👋 **Koru Delivery**\n\n"
        "Я рассчитаю *примерную* стоимость доставки.\n"
        "Курс и комиссия могут измениться.\n\n"
        "Выбери страну выкупа:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    save_last(context, msg)

# ================= COUNTRY =================
async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last(context)
    q = update.callback_query
    await q.answer()

    context.user_data["country"] = q.data.split(":")[1]

    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in CATEGORIES
    ]

    msg = await q.message.reply_text(
        "📦 Выбери категорию товара:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    save_last(context, msg)

# ================= CATEGORY =================
async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last(context)
    q = update.callback_query
    await q.answer()

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
    save_last(context, msg)

# ================= SUBCATEGORY =================
async def choose_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last(context)
    q = update.callback_query
    await q.answer()

    context.user_data["subcategory"] = q.data.split(":")[1]
    context.user_data["state"] = WAIT_PRICE

    msg = await q.message.reply_text(
        "💰 Введи стоимость товара **числом**:"
    )
    save_last(context, msg)

# ================= PRICE =================
async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != WAIT_PRICE:
        return

    raw = update.message.text.strip()
    cleaned = "".join(c for c in raw if c.isdigit() or c in ".,").replace(",", ".")

    try:
        price = float(cleaned)
    except:
        await update.message.reply_text("❌ Введи цену **числом**, например: 12000")
        return

    country = context.user_data["country"]

    # ---- currency logic ----
    if country == "Китай":
        rub = price * get_rate("CNY", "RUB")
    else:
        usd = price
        rub = usd * get_rate("USD", "RUB")

    rub *= (1 + BANK_FEE)
    commission = calc_commission(rub)
    total = int(rub + commission)

    context.user_data["total"] = total
    context.user_data["price_input"] = price
    context.user_data["state"] = None

    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]
    ]

    msg = await update.message.reply_text(
        f"📦 **Итог расчёта**\n\n"
        f"🌍 Страна: {country}\n"
        f"🛍 Товар: {context.user_data['subcategory']}\n"
        f"💰 Итого: ~{total} ₽\n"
        f"🚚 Срок: {DELIVERY_TIME[country]}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    save_last(context, msg)

# ================= CONFIRM =================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_last(context)
    q = update.callback_query
    await q.answer()

    order_id = f"KD-{int(datetime.now().timestamp())}"

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        INSERT INTO orders (
            order_number, user_id, username, country,
            category, subcategory, price_input,
            total_rub, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            q.from_user.id,
            q.from_user.username,
            context.user_data["country"],
            context.user_data["category"],
            context.user_data["subcategory"],
            context.user_data["price_input"],
            context.user_data["total"],
            "В обработке",
            datetime.now().isoformat()
        ))

    keyboard = [
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("🔁 Новый заказ", callback_data="new_order")]
    ]

    msg = await q.message.reply_text(
        f"✅ Заказ **{order_id}** принят.\n"
        "Менеджер скоро свяжется с вами.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    save_last(context, msg)
    context.user_data.clear()

# ================= USER ORDERS =================
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT order_number, status FROM orders WHERE user_id=?",
            (q.from_user.id,)
        ).fetchall()

    text = "📦 **Мои заказы**\n\n"
    if not rows:
        text += "Пока нет заказов."
    else:
        for r in rows:
            text += f"{r[0]} — {r[1]}\n"

    await q.message.reply_text(text, parse_mode="Markdown")

async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT order_number, username, status FROM orders"
        ).fetchall()

    text = "📋 **Все заказы**\n\n"
    for r in rows:
        text += f"{r[0]} — @{r[1]} — {r[2]}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price))

    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
