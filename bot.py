import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import json
import os
import asyncio
from datetime import datetime
from collections import defaultdict
import pickle
import threading
import time
import base64
import re
import sys
import io

# ======================== КОНФИГУРАЦИЯ ========================
ADMIN_IDS = [8095346561, 8163619171]
USER_ID = 8095346561
SECOND_ADMIN_ID = 8163619171
TOKEN = os.environ.get('TOKEN', "7989661243:AAFZpemxdz9Hy1WEUhW5_p6-lbAHWDj22T8")
DATA_FILE = 'bot_data.pickle'
BACKUP_INTERVAL = 60
ADMIN_PASSWORD = "1478963"

# ======================== НАСТРОЙКА ЛОГОВ ========================
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================== СТРУКТУРЫ ДАННЫХ ========================
users_db = {}
orders_db = []
pending_carts = {}

# ======================== СИСТЕМА СОХРАНЕНИЯ ========================
def save_data():
    try:
        data = {
            'users_db': users_db,
            'orders_db': orders_db,
            'last_save': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✅ Данные сохранены. Пользователей: {len(users_db)}, Заказов: {len(orders_db)}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")
        return False

def load_data():
    global users_db, orders_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                users_db = data.get('users_db', {})
                orders_db = data.get('orders_db', [])
            logger.info(f"✅ Данные загружены. Пользователей: {len(users_db)}, Заказов: {len(orders_db)}")
        else:
            logger.info("ℹ️ Файл данных не найден, создаем новые структуры")
            save_data()
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")

def auto_save():
    while True:
        time.sleep(BACKUP_INTERVAL)
        save_data()

save_thread = threading.Thread(target=auto_save, daemon=True)
save_thread.start()

# ======================== ДЕКОДИРОВАНИЕ КОРЗИНЫ ========================
def decode_cart_data(encoded_data):
    """Декодирует данные корзины из параметра start"""
    try:
        logger.info(f"🔧 Декодирование данных корзины...")
        if encoded_data.startswith('cart_'):
            encoded_data = encoded_data[5:]
        
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_str = decoded_bytes.decode('utf-8')
        cart_data = json.loads(decoded_str)
        logger.info(f"✅ Корзина декодирована: {len(cart_data.get('items', []))} товаров")
        return cart_data
    except Exception as e:
        logger.error(f"❌ Ошибка декодирования корзины: {e}")
        return None

# ======================== ОБРАБОТЧИКИ КОМАНД ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем пользователя
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if user_id not in users_db:
        users_db[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "first_seen": now,
            "last_active": now,
            "orders_count": 0
        }
    else:
        users_db[user_id]["last_active"] = now
        users_db[user_id]["first_name"] = user.first_name
        users_db[user_id]["username"] = user.username
    
    # Проверяем, есть ли данные корзины
    args = context.args
    if args and len(args) > 0:
        cart_data = decode_cart_data(args[0])
        if cart_data:
            pending_carts[user_id] = cart_data
            
            items_text = "\n".join([
                f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']} руб"
                for item in cart_data['items']
            ])
            
            await update.message.reply_text(
                f"🛒 <b>Корзина с сайта</b>\n\n"
                f"{items_text}\n\n"
                f"💰 <b>Итого: {cart_data['total']} руб</b>\n\n"
                f"📦 Выберите способ получения:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚶 Самовывоз (ЖК Дубровка)", callback_data="delivery_pickup")],
                    [InlineKeyboardButton("🚚 Доставка курьером", callback_data="delivery_courier")]
                ])
            )
            return
    
    # Обычный start без корзины
    keyboard = [[KeyboardButton("🔐 Админ-панель")]]
    await update.message.reply_text(
        "Добро пожаловать в магазин игрушек ЖК Дубровка!\n\n"
        "🛍 Для заказа посетите наш сайт:\n"
        "https://telegram-shop-bot.onrender.com",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    if query.data == "delivery_pickup":
        await process_order(query, context, "pickup", None)
    
    elif query.data == "delivery_courier":
        await query.edit_message_text(
            "🚚 <b>Доставка курьером</b>\n\n"
            "Пожалуйста, напишите ваш адрес доставки.\n\n"
            "Например: ул. Ленина, д. 10, кв. 5",
            parse_mode='HTML'
        )
        context.user_data['awaiting_address'] = True
    
    elif query.data == "confirm_delivery":
        if 'temp_address' in context.user_data:
            await process_order(query, context, "delivery", context.user_data['temp_address'])
            context.user_data.pop('temp_address', None)

async def process_order(query, context, delivery_type, address):
    """Обработка заказа"""
    user = query.from_user
    user_id = user.id
    
    if user_id not in pending_carts:
        await query.edit_message_text("❌ Корзина не найдена. Пожалуйста, вернитесь на сайт и попробуйте снова.")
        return
    
    cart_data = pending_carts.pop(user_id)
    
    order = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_type": "Самовывоз" if delivery_type == "pickup" else "Доставка",
        "address": address,
        "items": cart_data['items'],
        "total": cart_data['total']
    }
    
    orders_db.append(order)
    users_db[user_id]["orders_count"] += 1
    save_data()
    
    # Уведомление админам
    admin_text = f"🛒 НОВЫЙ ЗАКАЗ!\n\n"
    admin_text += f"👤 Покупатель: {users_db[user_id]['first_name']} (@{users_db[user_id]['username']})\n"
    if address:
        admin_text += f"📍 Адрес: {address}\n"
    admin_text += f"\n📦 Товары:\n"
    for item in order['items']:
        admin_text += f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']} руб\n"
    admin_text += f"\n💰 Итого: {order['total']} руб"
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text)
        except:
            pass
    
    # Ответ пользователю
    user_text = "✅ Заказ оформлен!\n\n"
    if delivery_type == "pickup":
        user_text += "Самовывоз: ЖК Дубровка, Ясеневая улица, 1к1\n"
    else:
        user_text += f"Адрес доставки: {address}\n"
    user_text += "\n📞 Ожидайте сообщения от администратора.\n💵 Оплата наличными."
    
    await query.edit_message_text(
        user_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 На сайт", url="https://telegram-shop-bot.onrender.com")]
        ])
    )

# ======================== ЗАПУСК ========================
if __name__ == "__main__":
    load_data()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    PORT = int(os.environ.get('PORT', 10000))
    WEBHOOK_URL = f"https://telegram-shop-bot.onrender.com/{TOKEN}"
    
    logger.info(f"🚀 Запуск бота на порту {PORT}")
    logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL
    )
