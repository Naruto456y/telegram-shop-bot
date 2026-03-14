import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
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

# ======================== КОНФИГУРАЦИЯ ========================
ADMIN_IDS = [8095346561]  # Список админов (ваш ID)
USER_ID = 8095346561      # Ваш ID (админ)
SECOND_ADMIN_ID = 8163619171  # Второй админ
TOKEN = "7989661243:AAFZpemxdz9Hy1WEUhW5_p6-lbAHWDj22T8"
DATA_FILE = 'bot_data.pickle'
BACKUP_INTERVAL = 60

# Пароль для доступа к админ-панели
ADMIN_PASSWORD = "1478963"

# Состояния для ConversationHandler
ADDRESS = 1

# ======================== СТРУКТУРЫ ДАННЫХ ========================
users_db = {}             # База данных пользователей
orders_db = []            # История заказов
pending_carts = {}        # Временные корзины с сайта (user_id -> cart_data)

# ======================== ЛОГИРОВАНИЕ ========================
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

class ConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if sys.platform == 'win32':
                msg = msg.replace('✅', '[OK]')
                msg = msg.replace('❌', '[ERROR]')
                msg = msg.replace('📅', '[DATE]')
                msg = msg.replace('🔍', '[SEARCH]')
                msg = msg.replace('🚀', '[START]')
                msg = msg.replace('ℹ️', '[INFO]')
                msg = msg.replace('💾', '[SAVE]')
                msg = msg.replace('📊', '[STATS]')
                msg = msg.replace('👥', '[USERS]')
                msg = msg.replace('🛒', '[CART]')
                msg = msg.replace('📦', '[BOX]')
                msg = msg.replace('📢', '[BROADCAST]')
                msg = msg.replace('⚙️', '[SETTINGS]')
                msg = msg.replace('🔐', '[LOCK]')
                msg = msg.replace('⛔', '[STOP]')
                msg = msg.replace('📝', '[NOTE]')
                msg = msg.replace('💰', '[MONEY]')
                msg = msg.replace('👇', '[DOWN]')
                msg = msg.replace('🆔', '[ID]')
                msg = msg.replace('🧸', '[TOY]')
                msg = msg.replace('🎲', '[DICE]')
                msg = msg.replace('🛠', '[TOOLS]')
                msg = msg.replace('📞', '[PHONE]')
                msg = msg.replace('🚶', '[WALK]')
                msg = msg.replace('🚚', '[TRUCK]')
                msg = msg.replace('🗑', '[TRASH]')
                msg = msg.replace('✉️', '[MAIL]')
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

console_handler = ConsoleHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)

# ======================== СИСТЕМА СОХРАНЕНИЯ ДАННЫХ ========================
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
                last_save = data.get('last_save', 'неизвестно')
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

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {
            "chat_id": USER_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.get(url, params=params)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения админу: {e}")

def update_user_info(user):
    user_id = user.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if user_id not in users_db:
        users_db[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "first_seen": now,
            "last_active": now,
            "orders_count": 0
        }
        save_data()
    else:
        users_db[user_id]["last_active"] = now
        users_db[user_id]["first_name"] = user.first_name
        users_db[user_id]["username"] = user.username

def decode_cart_data(encoded_data):
    """Декодирует данные корзины из параметра start"""
    try:
        print(f"\n🔧 Декодирование: {encoded_data[:100]}...")
        
        # Убираем префикс 'cart_' если он есть
        if encoded_data.startswith('cart_'):
            encoded_data = encoded_data[5:]
            print(f"🔧 После удаления префикса: {encoded_data[:100]}...")
        
        # Декодируем Base64
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_str = decoded_bytes.decode('utf-8')
        print(f"🔧 Декодированная строка: {decoded_str[:200]}...")
        
        cart_data = json.loads(decoded_str)
        print(f"🔧 JSON данные: {cart_data}")
        
        # Преобразуем в формат, который ожидает бот
        items_list = []
        for item in cart_data['items']:
            items_list.append({
                'name': item['name'],
                'price': item['price'],
                'quantity': item['quantity'],
                'total': item['price'] * item['quantity']
            })
        
        result = {
            'items': items_list,
            'total': cart_data['total']
        }
        print(f"🔧 Итоговый результат: {result}")
        return result
        
    except Exception as e:
        print(f"❌ ОШИБКА декодирования: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Ошибка декодирования корзины: {e}")
        return None

def format_order_for_admin(order, user_info, delivery_type, address=None):
    """Форматирует заказ для отправки админу"""
    username = f"@{user_info['username']}" if user_info['username'] else "@нет"
    
    if address:
        text = f"🛒 НОВЫЙ ЗАКАЗ (С АДРЕСОМ)!\n\n"
        text += f"👤 Покупатель:\n"
        text += f"• ID: {order['user_id']}\n"
        text += f"• Имя: {user_info['first_name']}\n"
        text += f"• Username: {username}\n\n"
        text += f"📦 Доставка по адресу: {address}\n\n"
    else:
        text = f"🛒 НОВЫЙ ЗАКАЗ!\n\n"
        text += f"👤 Покупатель:\n"
        text += f"• ID: {order['user_id']}\n"
        text += f"• Имя: {user_info['first_name']}\n"
        text += f"• Username: {username}\n\n"
        text += f"📦 Способ получения: 🚶 Самовывоз (ЖК Дубровка)\n\n"
    
    text += f"Товары:\n"
    for item in order['items']:
        text += f"• {item['name']} x{item['quantity']} - {item['total']} руб\n"
    
    text += f"\n💰 ИТОГО: {order['total']} рублей\n\n"
    text += f"💵 Оплата: только наличные"
    
    return text

def format_order_for_user(order, delivery_type, address=None):
    """Форматирует заказ для отправки пользователю"""
    if delivery_type == "pickup":
        text = f"✅ Заказ успешно оформлен!\n\n"
        text += f"Способ получения: 🚶 Самовывоз (ЖК Дубровка)\n"
        text += f"Ждем вас по адресу: Ясеневая улица, 1к1 (Рядом Яндекс маркета)\n\n"
        text += f"📞 Что дальше?\n"
        text += f"С вами свяжется администратор в ближайшее время.\n"
        text += f"Пожалуйста, ожидайте сообщения от @Yusuf_Guseinov\n\n"
        text += f"💵 Оплата: только наличные"
    else:
        text = f"✅ Заказ оформлен!\n\n"
        text += f"Адрес доставки: {address}\n"
        text += f"Стоимость доставки уточнит администратор.\n\n"
        text += f"📞 Ожидайте сообщения от @Yusuf_Guseinov\n\n"
        text += f"💵 Оплата: только наличные"
    
    return text

# ======================== ОСНОВНЫЕ ФУНКЦИИ БОТА ========================
def get_main_keyboard():
    """Основная клавиатура (только для админа)"""
    keyboard = [
        [KeyboardButton("🔐 Админ-панель")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def get_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения логов (только для админа)"""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Нет доступа")
        return
    
    try:
        with open('/tmp/bot_debug.log', 'r') as f:
            logs = f.read()
        if logs:
            # Отправляем последние 2000 символов
            await update.message.reply_text(f"📋 Логи:\n```\n{logs[-2000:]}\n```", parse_mode='Markdown')
        else:
            await update.message.reply_text("📋 Логи пусты")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка чтения логов: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - принимает корзину с сайта"""
    # ПРИНУДИТЕЛЬНАЯ ЗАПИСЬ В ФАЙЛ
    with open('/tmp/bot_debug.log', 'a') as f:
        f.write(f"\n🔥🔥🔥 START ВЫЗВАН {datetime.now()}\n")
        f.write(f"🔥 User: {update.effective_user.first_name} (ID: {update.effective_user.id})\n")
        f.write(f"🔥 Args: {context.args}\n")
        f.write(f"🔥 Полное сообщение: {update.message.text if update.message else 'Нет сообщения'}\n")
    
    user = update.effective_user
    update_user_info(user)
    
    args = context.args
    cart_data = None
    
    if args and len(args) > 0:
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write(f"🔥 Первый аргумент: {args[0][:100]}...\n")
        cart_data = decode_cart_data(args[0])
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write(f"🔥 Результат декодирования: {cart_data}\n")
    
    if cart_data:
        pending_carts[user.id] = cart_data
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write(f"🔥 Корзина сохранена. Всего корзин: {len(pending_carts)}\n")
        
        items_text = "\n".join([f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']} руб" 
                               for item in cart_data['items']])
        
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
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write(f"🔥 Сообщение с корзиной отправлено пользователю\n")
    else:
        with open('/tmp/bot_debug.log', 'a') as f:
            f.write(f"🔥 Обычный start без корзины\n")
        await update.message.reply_text(
            "Добро пожаловать!\n\n"
            "🛍 Для заказа игрушек посетите наш сайт:\n"
            "https://naruto456y.github.io\n\n"
            "🔐 Для админов: /admin",
            reply_markup=get_main_keyboard()
        )
    with open('/tmp/bot_debug.log', 'a') as f:
        f.write(f"🔥🔥🔥 КОНЕЦ START {datetime.now()}\n\n")

# ======================== АДМИН ПАНЕЛЬ ========================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            "Выберите раздел для управления:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    else:
        context.user_data['awaiting_admin_password'] = True
        await update.message.reply_text(
            "🔐 Введите пароль для доступа к админ-панели:",
            reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True, one_time_keyboard=True)
        )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if not (user.id in ADMIN_IDS or context.user_data.get('admin_authenticated')):
        await query.edit_message_text("⛔ Доступ запрещен.")
        return
    
    data = query.data
    
    if data == "admin_stats":
        await show_admin_stats(query, context)
    elif data == "admin_users":
        await show_admin_users(query, context)
    elif data == "admin_orders":
        await show_admin_orders(query, context)
    elif data == "admin_broadcast":
        await start_broadcast(query, context)
    elif data == "admin_settings":
        await show_admin_settings(query, context)
    elif data == "admin_save":
        if save_data():
            await query.edit_message_text("✅ Данные успешно сохранены")
        else:
            await query.edit_message_text("❌ Ошибка при сохранении")
    elif data.startswith("order_"):
        order_index = int(data.split("_")[1])
        await show_order_details(query, context, order_index)
    elif data.startswith("delete_order_"):
        order_index = int(data.split("_")[2])
        await delete_order(query, context, order_index)
    elif data == "admin_back":
        await show_admin_main_menu(query)

async def show_admin_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        "Выберите раздел для управления:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def show_admin_stats(query, context):
    total_users = len(users_db)
    active_today = sum(1 for u in users_db.values() if u["last_active"].startswith(datetime.now().strftime("%Y-%m-%d")))
    total_orders = len(orders_db)
    
    stats_text = (
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Активных сегодня: {active_today}\n\n"
        f"🛒 <b>Заказы:</b>\n"
        f"• Всего заказов: {total_orders}\n"
        f"• На сумму: {sum(o['total'] for o in orders_db)} руб\n\n"
        f"💾 <b>Последнее сохранение:</b> {datetime.now().strftime('%H:%M:%S')}"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_admin_users(query, context):
    if not users_db:
        await query.edit_message_text(
            "👥 Пользователи пока отсутствуют",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )
        return
    
    sorted_users = sorted(users_db.items(), key=lambda x: x[1]["last_active"], reverse=True)
    
    users_text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
    
    for i, (user_id, info) in enumerate(sorted_users[:10], 1):
        username = f"@{info['username']}" if info['username'] else "нет username"
        users_text += f"{i}. <b>{info['first_name']}</b>\n"
        users_text += f"   ID: <code>{user_id}</code>\n"
        users_text += f"   Заказов: {info['orders_count']}\n"
        users_text += f"   Был: {info['last_active']}\n\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(users_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_admin_orders(query, context):
    if not orders_db:
        await query.edit_message_text(
            "🛒 Заказов пока нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )
        return
    
    recent_orders = orders_db[-10:]
    recent_orders.reverse()
    
    orders_text = "🛒 <b>ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n\n"
    keyboard = []
    
    for i, order in enumerate(recent_orders, 1):
        user_info = users_db.get(order["user_id"], {})
        user_name = user_info.get("first_name", "Неизвестно")
        order_num = len(orders_db) - recent_orders.index(order)
        
        orders_text += f"{i}. <b>{user_name}</b>\n"
        orders_text += f"   Дата: {order['date']}\n"
        orders_text += f"   Сумма: {order['total']} руб\n"
        orders_text += f"   Способ: {order['delivery_type']}\n\n"
        
        order_index = orders_db.index(order)
        keyboard.append([InlineKeyboardButton(f"📦 Заказ #{order_num}", callback_data=f"order_{order_index}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(orders_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_order_details(query, context, order_index):
    if order_index >= len(orders_db):
        await query.edit_message_text(
            "❌ Заказ не найден",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_orders")]])
        )
        return
    
    order = orders_db[order_index]
    user_info = users_db.get(order["user_id"], {})
    
    details_text = (
        f"📦 <b>ДЕТАЛИ ЗАКАЗА #{order_index + 1}</b>\n\n"
        f"<b>Дата:</b> {order['date']}\n"
        f"<b>Покупатель:</b> {user_info.get('first_name', 'Неизвестно')}\n"
        f"<b>ID:</b> <code>{order['user_id']}</code>\n"
        f"<b>Способ:</b> {order['delivery_type']}\n"
    )
    
    if order.get('address'):
        details_text += f"<b>Адрес доставки:</b> {order['address']}\n"
    
    details_text += f"\n<b>Товары:</b>\n"
    
    for item in order['items']:
        if 'price' in item:
            item_price = item['price']
            item_total = item_price * item['quantity']
        elif 'total' in item:
            item_total = item['total']
            item_price = item_total // item['quantity'] if item['quantity'] > 0 else item_total
        else:
            item_price = 0
            item_total = 0
        
        details_text += f"• {item['name']} x{item['quantity']} - {item_total} руб\n"
    
    details_text += f"\n💰 <b>ИТОГО: {order['total']} рублей</b>\n\n"
    details_text += f"💵 Оплата: только наличные"
    
    keyboard = [
        [InlineKeyboardButton("❌ Удалить заказ", callback_data=f"delete_order_{order_index}")],
        [InlineKeyboardButton("◀️ Назад к заказам", callback_data="admin_orders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(details_text, parse_mode='HTML', reply_markup=reply_markup)

async def delete_order(query, context, order_index):
    if order_index < len(orders_db):
        deleted_order = orders_db.pop(order_index)
        save_data()
        
        await query.edit_message_text(
            f"✅ Заказ успешно удален!\n\n"
            f"Удален заказ от {deleted_order['date']} на сумму {deleted_order['total']} руб",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к заказам", callback_data="admin_orders")]])
        )
    else:
        await query.edit_message_text("❌ Ошибка: заказ не найден")

async def start_broadcast(query, context):
    context.user_data['broadcast_mode'] = True
    await query.edit_message_text(
        "📢 <b>РЕЖИМ РАССЫЛКИ</b>\n\n"
        "Введите сообщение для рассылки всем пользователям.\n"
        "Для отмены введите /cancel",
        parse_mode='HTML'
    )

async def show_admin_settings(query, context):
    settings_text = (
        "⚙️ <b>НАСТРОЙКИ БОТА</b>\n\n"
        f"👤 <b>Администраторы:</b>\n"
    )
    
    for admin_id in ADMIN_IDS:
        admin_info = users_db.get(admin_id, {})
        admin_name = admin_info.get('first_name', 'Неизвестно')
        settings_text += f"• {admin_name} (ID: <code>{admin_id}</code>)\n"
    
    settings_text += f"\n📊 <b>Системная информация:</b>\n"
    settings_text += f"• Бот запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    settings_text += f"• Всего пользователей: {len(users_db)}\n"
    settings_text += f"• Всего заказов: {len(orders_db)}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_text, parse_mode='HTML', reply_markup=reply_markup)

# ======================== ОФОРМЛЕНИЕ ЗАКАЗА ========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user = query.from_user
    user_id = user.id
    
    update_user_info(user)
    
    if callback_data == "delivery_pickup":
        await process_order(query, context, "pickup", None)
    
    elif callback_data == "delivery_courier":
        await query.edit_message_text(
            "🚚 <b>Доставка курьером</b>\n\n"
            "Пожалуйста, напишите ваш адрес доставки.\n\n"
            "Например: ул. Ленина, д. 10, кв. 5\n\n"
            "💵 Оплата только наличными при получении",
            parse_mode='HTML'
        )
        context.user_data['awaiting_address'] = True
    
    elif callback_data == "confirm_delivery":
        await confirm_delivery_callback(update, context)

async def process_order(query, context, delivery_type, address):
    user = query.from_user
    user_id = user.id
    
    if user_id not in pending_carts:
        await query.edit_message_text("❌ Корзина не найдена. Пожалуйста, вернитесь на сайт и попробуйте снова.")
        return
    
    cart_data = pending_carts[user_id]
    
    order_record = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_type": "Самовывоз" if delivery_type == "pickup" else "Доставка",
        "address": address,
        "items": cart_data['items'],
        "items_count": len(cart_data['items']),
        "total": cart_data['total']
    }
    
    orders_db.append(order_record)
    
    if user_id in users_db:
        users_db[user_id]["orders_count"] += 1
    
    user_info = users_db[user_id]
    admin_text = format_order_for_admin(order_record, user_info, delivery_type, address)
    
    await context.bot.send_message(chat_id=USER_ID, text=admin_text, parse_mode='HTML')
    await context.bot.send_message(chat_id=SECOND_ADMIN_ID, text=admin_text, parse_mode='HTML')
    
    pending_carts.pop(user_id, None)
    
    save_data()
    
    user_text = format_order_for_user(order_record, delivery_type, address)
    
    await query.edit_message_text(
        user_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Вернуться на сайт", url="https://naruto456y.github.io")]
        ])
    )

async def confirm_delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    if 'temp_address' not in context.user_data:
        await query.edit_message_text("❌ Ошибка: адрес не найден.")
        return
    
    address = context.user_data['temp_address']
    context.user_data.pop('temp_address', None)
    
    await process_order(query, context, "delivery", address)

# ======================== ОБРАБОТЧИК СООБЩЕНИЙ ========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_info(user)
    
    text = update.message.text
    
    if context.user_data.get('awaiting_admin_password'):
        if text == ADMIN_PASSWORD:
            context.user_data['admin_authenticated'] = True
            context.user_data['awaiting_admin_password'] = False
            
            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
                [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
                [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
                [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔐 <b>АДМИН-ПАНЕЛЬ</b>\n\nВыберите раздел для управления:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Неверный пароль.")
        return
    
    if context.user_data.get('broadcast_mode') and (user.id in ADMIN_IDS or context.user_data.get('admin_authenticated')):
        await send_broadcast(update, context)
        return
    
    if context.user_data.get('awaiting_address'):
        address = text
        context.user_data['awaiting_address'] = False
        context.user_data['temp_address'] = address
        
        await update.message.reply_text(
            f"📍 <b>Подтверждение заказа</b>\n\n"
            f"Адрес доставки: {address}\n\n"
            f"Подтверждаете заказ?",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="confirm_delivery")],
                [InlineKeyboardButton("🔄 Ввести другой адрес", callback_data="delivery_courier")],
                [InlineKeyboardButton("🚶 Выбрать самовывоз", callback_data="delivery_pickup")]
            ])
        )
        return
    
    if text == "🔐 Админ-панель":
        if user.id in ADMIN_IDS:
            await admin_panel(update, context)
        else:
            await update.message.reply_text("⛔ У вас нет доступа")
    
    elif text == "/cancel":
        if context.user_data.get('awaiting_admin_password'):
            context.user_data['awaiting_admin_password'] = False
            await update.message.reply_text("❌ Вход в админ-панель отменен")
        elif context.user_data.get('broadcast_mode'):
            context.user_data['broadcast_mode'] = False
            await update.message.reply_text("❌ Рассылка отменена")
        elif context.user_data.get('awaiting_address'):
            context.user_data['awaiting_address'] = False
            await update.message.reply_text("❌ Оформление доставки отменено")
        else:
            await update.message.reply_text("❌ Нет активной операции")
    else:
        await update.message.reply_text(
            "Используйте кнопки меню.\n"
            "Для заказа посетите сайт: https://naruto456y.github.io"
        )

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    if message_text.lower() == '/cancel':
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("❌ Рассылка отменена")
        return
    
    await update.message.reply_text(f"📢 Начинаю рассылку {len(users_db)} пользователям...")
    
    success_count = 0
    fail_count = 0
    
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Рассылка от администратора:</b>\n\n{message_text}",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            fail_count += 1
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n"
        f"• Успешно: {success_count}\n"
        f"• Ошибок: {fail_count}"
    )
    
    context.user_data['broadcast_mode'] = False

# ======================== ЗАПУСК (ДЛЯ RENDER) ========================
def main():
    load_data()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_.*|^user_.*|^order_.*|^delete_order_.*"))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.add_handler(CommandHandler("logs", get_logs))

    print("\n🔍 ПРОВЕРКА БОТА:")
    print("✅ Бот запущен на RENDER...")
    print("✅ Режим: WEBHOOK (для Render)")
    print("✅ Сайт передает корзину через параметр start")
    print(f"👥 Пользователей: {len(users_db)}")
    print(f"📦 Заказов: {len(orders_db)}")
    
    # ВАЖНО: Для Render используем webhook, а не polling
    PORT = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запускаем webhook на порту {PORT}")
    
    # Удаляем старый webhook и устанавливаем новый
    app.bot.delete_webhook()
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://telegram-shop-bot.onrender.com/{TOKEN}"
    )

if __name__ == "__main__":
    main()
