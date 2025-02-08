import logging
import time
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
from aiogram.types import ContentType
import aiogram  # Add this import

# Остальной код...

import asyncio
import os
from aiogram import types
from aiogram.types import CallbackQuery
from aiogram.filters import StateFilter
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from selenium import webdriver
from aiogram.types.input_file import FSInputFile  # Импорт FSInputFile для локальных файлов
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup  # Добавьте в импорты
import gc  # для сборки мусора

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
ADMIN_ID = 6422360534  # Укажи Telegram ID администратора

class States(StatesGroup):
    add_product = State()
    delete_product = State()
    purchase_quantity = State()
    purchase_contact = State()
    purchase_name = State()
    payment_confirm = State()
    manager_order_id = State()  # Состояние для менеджера
    update_card = State()  # Состояние для обновления реквизитов
    update_price = State()  # Состояние для обновления цены

# Конфигурация бота
BOT_TOKEN = "8191990835:AAEReLkV4uOLjwwT3FN-67qpnti7WWy7MiA"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для хранения драйверов пользователей
user_drivers = {}

# Словарь для хранения URL пользователей
user_urls = {}

# Настройка Selenium
chrome_options = Options()

# Основные настройки для работы на сервере
chrome_options.add_argument("--headless=new")  # Новый режим headless
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.binary_location = "/usr/bin/chromium-browser"  # Изменённый путь к браузеру

# Дополнительные настройки для стабильности
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-setuid-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Изменение инициализации драйвера
try:
    service = Service('/usr/bin/chromedriver')  # Указываем путь к chromedriver
    driver = webdriver.Chrome(service=service, options=chrome_options)
except Exception as e:
    logging.error(f"Ошибка при инициализации драйвера: {e}")
    # Попробуем альтернативный путь к chromedriver
    try:
        service = Service('/snap/bin/chromium.chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        logging.error(f"Ошибка при инициализации драйвера (альтернативный путь): {e}")
        raise

# Глобальное множество для хранения отправленных ссылок
global_sent_links = set()

# Словарь для отслеживания активных парсеров
active_parsers = {}

async def download_image(image_url, user_id):
    image_path = f"temp_image_{user_id}.jpg"
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                with open(image_path, "wb") as file:
                    file.write(await response.read())
    return image_path

def parse_ads_sync(driver, user_id, url, sent_links):
    """Синхронная функция для выполнения парсинга"""
    try:
        driver.get(url)
        driver.execute_script("window.scrollBy(0, 500);")
        
        items = driver.find_elements(By.CSS_SELECTOR, '.iva-item-root-Se7z4')[:3]  # Берем только первые 3 элемента
        results = []

        for item in reversed(items):
            try:
                title_element = item.find_element(By.CSS_SELECTOR, 'h3[itemprop="name"]')
                title = title_element.text if title_element else "Без названия"

                link_element = item.find_element(By.CSS_SELECTOR, 'a[itemprop="url"]')
                link = link_element.get_attribute('href') if link_element else None

                if link and link not in sent_links:
                    price_element = item.find_element(By.CSS_SELECTOR, 'span.price-root-IfnJI meta[itemprop="price"]')
                    price = price_element.get_attribute('content') if price_element else "Цена не указана"

                    image_element = item.find_element(By.CSS_SELECTOR, 'img')
                    image_url = image_element.get_attribute('src') if image_element else None

                    sent_links.add(link)
                    results.append((title, price, link, image_url))

            except Exception as e:
                logging.error(f"Ошибка обработки объявления: {e}")
                continue

            # Очищаем неиспользуемые объекты
            del title_element, link_element, price_element, image_element
            gc.collect()

        return results
    except Exception as e:
        logging.error(f"Ошибка парсинга для пользователя {user_id}: {e}")
        return []
    finally:
        # Очищаем память
        gc.collect()

# Создаем кнопку "Стоп"
stop_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Стоп", callback_data="stop_parsing")]
])

def create_driver():
    """Создание нового экземпляра драйвера с оптимизированными настройками"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")  # Отключаем загрузку изображений
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-javascript")  # Отключаем JavaScript
    chrome_options.add_argument("--window-size=800,600")  # Уменьшаем размер окна
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.page_load_strategy = 'eager'  # Ускоряем загрузку страницы
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    
    try:
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logging.error(f"Ошибка при создании драйвера: {e}")
        return None

@dp.callback_query(lambda c: c.data == "start_parser")
async def start_parser_callback(call: CallbackQuery):
    """Запуск парсера по сохранённой ссылке."""
    user_id = call.from_user.id
    url = get_last_link(user_id)

    if not url:
        logging.error(f"Ссылка для пользователя {user_id} не найдена.")
        await call.message.answer("Сохранённая ссылка не найдена. Добавьте ссылку перед началом работы.")
        return

    # Создаем клавиатуру с кнопкой "Стоп"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Стоп", callback_data="stop_parsing"),
        ],
        [
            types.InlineKeyboardButton(text="Назад", callback_data="back_to_start"),
        ],
    ])

    # Логируем запуск
    logging.info(f"Запуск парсера для пользователя {user_id} с URL: {url}")

    # Запускаем парсер
    await call.message.edit_text(f"Парсер запущен по ссылке: {url}", reply_markup=keyboard)
    try:
        asyncio.create_task(start_parser(user_id, url))
    except Exception as e:
        logging.error(f"Ошибка при запуске парсера для пользователя {user_id}: {e}")

async def start_parser(user_id, url):
    """Запуск парсера для пользователя"""
    global global_sent_links
    
    if not url:
        logging.error(f"URL не указан для пользователя {user_id}")
        return
        
    # Добавляем пользователя в активные парсеры
    active_parsers[user_id] = True
        
    while active_parsers.get(user_id, False):  # Проверяем флаг активности
        try:
            # Проверяем подписку перед каждой итерацией
            if not has_active_subscription(user_id):
                await bot.send_message(user_id, "Ваша подписка истекла. Парсинг остановлен.")
                return

            driver = create_driver()
            try:
                # Получаем актуальную ссылку из базы данных
                current_url = get_last_link(user_id)
                if current_url != url:
                    url = current_url  # Обновляем URL если он изменился
                
                driver.get(url)
                await asyncio.sleep(2)
                
                # Добавляем обработку ошибок при парсинге
                try:
                    items = driver.find_elements(By.CSS_SELECTOR, '.iva-item-root-Se7z4')
                    if not items:
                        logging.warning(f"Не найдены элементы на странице для пользователя {user_id}")
                        await asyncio.sleep(30)
                        continue
                        
                    # Парсинг объявлений
                    for item in items[:3]:  # Берем первые 3 объявления
                        try:
                            title = item.find_element(By.CSS_SELECTOR, 'h3[itemprop="name"]').text
                            link = item.find_element(By.CSS_SELECTOR, 'a[itemprop="url"]').get_attribute('href')
                            
                            # Проверяем, не отправляли ли мы уже это объявление
                            if link in global_sent_links:
                                continue
                                
                            price = item.find_element(By.CSS_SELECTOR, 'span.price-root-IfnJI meta[itemprop="price"]').get_attribute('content')
                            
                            # Получаем URL изображения
                            image_element = item.find_element(By.CSS_SELECTOR, 'img[class*="photo-slider-image"]')
                            image_url = image_element.get_attribute('src')
                            
                            # Добавляем ссылку в множество отправленных
                            global_sent_links.add(link)
                            
                            message = f"📌 {title}\n\n💰 Цена: {price} ₽\n\n🔗Ссылка: {link}"
                            
                            # Создаем клавиатуру с кнопкой "Стоп"
                            stop_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="Остановить парсер", callback_data="stop_parsing")]
                            ])
                            
                            if image_url:
                                try:
                                    image_path = await download_image(image_url, user_id)
                                    await bot.send_photo(
                                        chat_id=user_id,
                                        photo=FSInputFile(image_path),
                                        caption=message,
                                        reply_markup=stop_keyboard
                                    )
                                    os.remove(image_path)
                                except aiogram.exceptions.TelegramForbiddenError:
                                    logging.warning(f"Пользователь {user_id} заблокировал бота")
                                    # Очищаем ресурсы и останавливаем парсер для этого пользователя
                                    if user_id in user_drivers:
                                        try:
                                            driver = user_drivers.pop(user_id)
                                            driver.quit()
                                        except:
                                            pass
                                    return
                                except Exception as img_error:
                                    logging.error(f"Ошибка при отправке изображения: {img_error}")
                                    await bot.send_message(user_id, message, reply_markup=stop_keyboard)
                            else:
                                try:
                                    await bot.send_message(user_id, message, reply_markup=stop_keyboard)
                                except aiogram.exceptions.TelegramForbiddenError:
                                    logging.warning(f"Пользователь {user_id} заблокировал бота")
                                    # Очищаем ресурсы и останавливаем парсер для этого пользователя
                                    if user_id in user_drivers:
                                        try:
                                            driver = user_drivers.pop(user_id)
                                            driver.quit()
                                        except:
                                            pass
                                    return
                                    
                        except Exception as e:
                            logging.error(f"Ошибка при обработке объявления: {e}")
                            continue
                            
                except Exception as e:
                    logging.error(f"Ошибка при парсинге элементов: {e}")
                    continue
                    
            finally:
                try:
                    driver.quit()
                except:
                    pass
                    
            # Увеличиваем интервал между проверками
            await asyncio.sleep(60)  # Увеличиваем до 60 секунд
            
        except Exception as e:
            logging.error(f"Критическая ошибка в парсере для пользователя {user_id}: {e}")
            await asyncio.sleep(30)

def get_last_link(user_id):
    """Получаем последнюю сохранённую ссылку пользователя."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_link FROM user_links WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ... existing code ...

@dp.callback_query(lambda c: c.data == "stop_parsing")
async def stop_parsing_callback(call: CallbackQuery):
    """Остановка парсера и возврат к меню основного поиска."""
    user_id = call.from_user.id

    # Останавливаем парсер
    active_parsers[user_id] = False

    # Останавливаем драйвер
    if user_id in user_drivers:
        try:
            driver = user_drivers.pop(user_id)
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Ошибка при закрытии драйвера: {e}")
        except Exception as e:
            logging.error(f"Ошибка при остановке парсера: {e}")
    
    try:
        # Получаем ссылку из базы данных
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_link FROM user_links WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

        url = f"Ваша ссылка: {result[0]}" if result and result[0] else "Ваша ссылка еще не добавлена,\nдобавьте ссылку для поиска"

        # Создаем клавиатуру для меню парсера
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="Добавить ссылку", callback_data="add_link"),
                types.InlineKeyboardButton(text="Начать поиск", callback_data="start_parser"),
            ],
            [
                types.InlineKeyboardButton(text="Заменить ссылку", callback_data="replace_link"),
                types.InlineKeyboardButton(text="Личный кабинет", callback_data="back_to_start"),
            ],
        ])

        # Отправляем новое сообщение вместо редактирования
        await call.message.answer(
            f"Парсер остановлен.\n\nВыберите действие для управления парсером.\n{url}", 
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Ошибка при отображении меню: {e}")
        await call.message.answer(
            "Произошла ошибка. Пожалуйста, попробуйте еще раз или используйте команду /start"
        )

    # Отвечаем на callback
    await call.answer("Парсер остановлен")

# ... existing code ...

import sqlite3

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Таблица для пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            subscription_status TEXT,
            subscription_end TEXT,
            selected_subscription TEXT
        )
    """)

    # Таблица для настроек (например, карта и цена)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Таблица для сохранения ссылок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_links (
            user_id INTEGER PRIMARY KEY,
            last_link TEXT
        )
    """)

    conn.commit()
    conn.close()

def add_column_to_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Добавляем столбец selected_subscription, если он не существует
    try:
        cursor.execute("""
            ALTER TABLE users ADD COLUMN selected_subscription TEXT
        """)
        print("Столбец selected_subscription успешно добавлен.")
    except sqlite3.OperationalError:
        print("Столбец selected_subscription уже существует.")
    
    conn.commit()
    conn.close()

    # Обновляем структуру таблицы users, если требуется
    update_users_table()
def is_trial_notified(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT trial_notified FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False
# Сохранение ссылки для пользователя
def save_user_url(user_id, url):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_urls (user_id, url) VALUES (?, ?)
    """, (user_id, url))
    conn.commit()
    conn.close()

# Получение ссылки пользователя
def get_user_url(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT url FROM user_urls WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def set_trial_notified(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET trial_notified = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

import sqlite3

def update_db():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()

        # Проверяем наличие столбца subscription_end_date в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "subscription_end_date" not in columns:
            # Добавляем столбец subscription_end_date, если он отсутствует
            cursor.execute("ALTER TABLE users ADD COLUMN subscription_end_date TEXT")
            print("Столбец subscription_end_date успешно добавлен.")
        else:
            print("Столбец subscription_end_date уже существует.")

        conn.commit()
# Функция для добавления нового пользователя
def add_user_if_not_exists(user_id, username):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Проверяем, существует ли уже такой пользователь
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone() is None:
            # Добавляем нового пользователя с подпиской на 1 день
            end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO users (id, username, subscription_status, subscription_end_date)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, "active", end_date))
            conn.commit()

def save_last_link(user_id, link):
    """Сохраняем последнюю ссылку пользователя."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_links (user_id, last_link)
        VALUES (?, ?)
    """, (user_id, link))
    conn.commit()
    conn.close()
    print(f"Ссылка '{link}' сохранена для пользователя {user_id}")


def check_table_user_links():
    """Проверка существования таблицы user_links."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_links'")
    table_exists = cursor.fetchone()
    conn.close()
    if table_exists:
        print("Таблица user_links существует.")
    else:
        print("Таблица user_links не найдена.")


def update_users_table():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Добавляем столбец subscription_end, если он не существует
    try:
        cursor.execute("""
            ALTER TABLE users ADD COLUMN subscription_end TEXT
        """)
    except sqlite3.OperationalError:
        # Игнорируем ошибку, если столбец уже существует
        pass
    
    conn.commit()
    conn.close()


from datetime import datetime, timedelta

def update_subscription(user_id, days):
    """Обновляет дату окончания подписки для пользователя."""
    end_date = datetime.now() + timedelta(days=days)
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET subscription_end = ?
        WHERE user_id = ?
    """, (end_date.strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()
    conn.close()

def get_subscription_end(user_id: int):
    with sqlite3.connect("users.db") as conn:  # Здесь заменено на 'users.db'
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_end FROM users WHERE id = ?
        """, (user_id,))  # Убедитесь, что поле называется `id`, а не `user_id`
        result = cursor.fetchone()
        return result[0] if result else None




def save_info(photo_id, info_text):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES ('info_photo', ?), ('info_text', ?)
    """, (photo_id, info_text))
    conn.commit()
    conn.close()

def get_info():
    """Получаем информацию для отображения."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Получаем данные из базы
    cursor.execute("""SELECT value FROM settings WHERE key = 'info_photo'""")
    photo = cursor.fetchone()

    cursor.execute("""SELECT value FROM settings WHERE key = 'info_text'""")
    text = cursor.fetchone()

    conn.close()

    # Проверяем и возвращаем данные
    photo_path = photo[0] if photo else None
    info_text = text[0] if text else "Информация пока не доступна."
    return photo_path, info_text



import sqlite3
from datetime import datetime

def get_subscription_status(user_id: int):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_status, subscription_end_date 
            FROM users 
            WHERE id = ?
        """, (user_id,))
        result = cursor.fetchone()

        if result:
            status, end_date = result
            if status == "active":
                # Проверяем, не истекла ли дата подписки
                if end_date and datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") > datetime.now():
                    return "active"  # Подписка активна
                else:
                    return "expired"  # Подписка истекла
        return "inactive"  # Подписки нет



def update_card(card):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES ('card', ?)
    """, (card,))
    conn.commit()
    conn.close()

def update_info(photo_file_id, info_text):
    """Сохраняем информацию в базу данных."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Обновляем или вставляем фото
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value) VALUES ('info_photo', ?)
    """, (photo_file_id,))

    # Обновляем или вставляем текст
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value) VALUES ('info_text', ?)
    """, (info_text,))

    conn.commit()
    conn.close()




def get_card():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT value FROM settings WHERE key = 'card'
    """)
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Реквизиты не заданы."

def get_subscription_status(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT subscription_status FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "inactive"

def update_subscription_status(user_id, status):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscription_status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    conn.close()




def update_price(key, price):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES (?, ?)
    """, (key, price))
    conn.commit()
    conn.close()


def get_price(key):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT value FROM settings WHERE key = ?
    """, (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Цена не задана."



def add_user(user_id, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, subscription_status)
        VALUES (?, ?, ?)
    """, (user_id, username, "inactive"))
    conn.commit()
    conn.close()

def update_subscription_status(user_id, status):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET subscription_status = ? WHERE id = ?
    """, (status, user_id))
    conn.commit()
    conn.close()

def get_subscription_status(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subscription_status, subscription_end
        FROM users
        WHERE id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        return "inactive"

    subscription_status, subscription_end = result

    # Проверяем, истек ли срок подписки
    if subscription_end and datetime.datetime.now() > datetime.datetime.fromisoformat(subscription_end):
        # Если подписка истекла, обновляем статус в базе данных
        set_subscription_inactive(user_id)
        return "inactive"

    return subscription_status
def set_subscription_inactive(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET subscription_status = 'inactive', subscription_end = NULL
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

import datetime
from datetime import datetime, timedelta
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError






def add_user_with_trial(user_id, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Проверяем, есть ли пользователь в базе
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    user_exists = cursor.fetchone()

    if not user_exists:
        # Добавляем пользователя с тестовой подпиской на 1 день
        trial_end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat()
        cursor.execute("""
            INSERT INTO users (id, username, subscription_status, subscription_end)
            VALUES (?, ?, 'active', ?)
        """, (user_id, username, trial_end_date))
        conn.commit()

    conn.close()

update_db()

# Функция для инициализации базы данных и добавления пользователя
def initialize_db():
    with sqlite3.connect("user1s.db") as conn:
        cursor = conn.cursor()
        # Создаем таблицу пользователей, если ее нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_status TEXT,
                subscription_end_date TEXT
            )
        """)
        conn.commit()

async def check_subscription(user_id):
    chat_id = "@PEREKUP_63"  # Замени на нужный канал
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ["member", "administrator", "creator"]

from datetime import datetime, timedelta
import sqlite3
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
# Обработчик команды start
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Без имени"

    # Проверка подписки на канал
    if not await check_subscription(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Подписаться", url="https://t.me/PEREKUP_63")
        ]])
        await message.answer(
            "Вы не подписаны на канал. Пожалуйста, подпишитесь на канал, а затем нажмите /start снова.",
            reply_markup=keyboard,
        )
        return

    # Добавляем пользователя в базу данных, если его там нет
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        
        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        user_exists = cursor.fetchone()
        
        if not user_exists:
            # Добавляем нового пользователя с тестовой подпиской
            test_end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO users (id, username, subscription_status, subscription_end_date)
                VALUES (?, ?, 'active', ?)
            """, (user_id, username, test_end_date))
            conn.commit()
            logging.info(f"Новый пользователь добавлен: {user_id} с тестовой подпиской до {test_end_date}")

    # Получаем актуальный статус подписки
    cursor.execute("""
        SELECT subscription_status, subscription_end_date 
        FROM users 
        WHERE id = ?
    """, (user_id,))
    result = cursor.fetchone()
    
    if result:
        status, end_date = result
        if status == "active" and end_date:
            subscription_end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            subscription_text = f"активна до {subscription_end_date.strftime('%d.%m.%Y')}"
        else:
            subscription_text = "не активна"
    else:
        subscription_text = "не активна"

    # Создаем клавиатуру для личного кабинета
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Основной поиск", callback_data="main_search"),
            InlineKeyboardButton(text="Приобрести подписку", callback_data="buy_subscription")
        ],
        [
            InlineKeyboardButton(text="Информация", callback_data="info")
        ]
    ])

    # Отправляем фото и информацию
    photo_path = "ava.png"
    try:
        photo = FSInputFile(photo_path)
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                f"ℹ️ <b>Личный кабинет:</b>\n\n"
                f"👤<b>ID пользователя:</b> {user_id}\n\n"
                f"🔑<b>Имя пользователя:</b> {username}\n\n"
                f"🗂<b>Подписка:</b> {subscription_text}\n\n"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(user_id, "Ошибка при загрузке изображения. Проверьте наличие файла 'ava.png'.")

@dp.message(Command("card"))
async def set_card(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна только администратору.")
        return

    # Получаем номер карты из команды
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Пожалуйста, укажите номер карты. Пример: /card 1234567890123456")
        return

    card = parts[1]
    update_card(card)  # Обновляем карту в базе данных
    await message.answer(f"Номер карты успешно обновлён на <b>{card}</b>.", parse_mode="HTML")

@dp.message(Command("price"))
async def set_price(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна только администратору.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /price <тип> <цена>. Пример: /price month 1200")
        return

    key, price = args[1], args[2]
    if key not in ["month", "week"]:
        await message.answer("Допустимые типы: month, week")
        return

    update_price(key, price)
    await message.answer(f"Цена для '{key}' успешно обновлена на {price} рублей.")


@dp.message()
async def handle_user_link(message: Message):
    user_id = message.from_user.id
    link = message.text.strip()

    # Проверка, что это валидная ссылка (можно дополнить)
    if not link.startswith("http"):
        await message.answer("Пожалуйста, отправьте корректную ссылку.")
        return

    # Сохраняем ссылку
    save_last_link(user_id, link)
    await message.answer("Ссылка сохранена. Парсер запущен!")

    
    # Запускаем парсер (ваш код для запуска)
    # start_parser(user_id, link)







@dp.callback_query(lambda c: c.data == "buy_subscription")
async def buy_subscription_callback(call: CallbackQuery):
    """Обработчик кнопки 'Приобрести подписку'."""
    # Создаем клавиатуру с кнопками для подписок
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Подписка на месяц", callback_data="subscribe_month"),
            types.InlineKeyboardButton(text="Подписка на неделю", callback_data="subscribe_week"),
        ],
        [
            types.InlineKeyboardButton(text="Назад", callback_data="back_to_start"),
        ],
    ])

    # Отправляем новое сообщение вместо редактирования
    await call.message.answer(
        "Выберите тип подписки:",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start_callback(call: CallbackQuery):
    """Обработчик кнопки 'Назад'."""
    user_id = call.from_user.id
    username = call.from_user.username or "Без имени"

    # Удаляем текущее сообщение
    await call.message.delete()

    # Проверяем статус подписки
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_status, subscription_end_date 
            FROM users 
            WHERE id = ?
        """, (user_id,))
        result = cursor.fetchone()

    if result:
        status, end_date = result
        if status == "active" and end_date and datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") > datetime.now():
            subscription_text = f"активна до {datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')}"
        else:
            subscription_text = "истекла"
    else:
        subscription_text = "не активна"

    # Создаем клавиатуру для личного кабинета
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Основной поиск", callback_data="main_search"),
            types.InlineKeyboardButton(text="Приобрести подписку", callback_data="buy_subscription")
        ],
        [
            types.InlineKeyboardButton(text="Информация", callback_data="info")
        ]
    ])

    # Отправляем фото, текст и кнопки
    photo_path = "ava.png"  # Указываем путь к фото
    try:
        photo = FSInputFile(photo_path)
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                f"ℹ️ <b>Личный кабинет:</b>\n\n"
                f"👤<b>ID пользователя:</b> {user_id}\n\n"
                f"🔑<b>Имя пользователя:</b> {username}\n\n"
                f"🗂<b>Подписка:</b> {subscription_text}\n\n"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(user_id, "Ошибка при загрузке изображения. Проверьте наличие файла 'ava.png'.")


@dp.callback_query(lambda c: c.data == "subscribe_month")
async def subscribe_month_callback(call: CallbackQuery):
    """Обработчик кнопки 'Подписка на месяц'."""
    price = get_price("month")
    card = get_card()
    user_id = call.from_user.id

    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET selected_subscription = ?
            WHERE id = ?
        """, ("month", user_id))
        conn.commit()

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Назад", callback_data="buy_subscription")]
    ])

    message_text = (
        f"Для оплаты подписки на месяц используйте следующие реквизиты:\n\n"
        f"💳 <b>Карта:</b> {card}\n"
        f"💰 <b>Сумма:</b> {price} рублей\n\n"
        f"Пожалуйста, отправьте скриншот перевода после оплаты."
    )

    try:
        await call.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
    except aiogram.exceptions.TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # If content is the same, just answer the callback
            await call.answer()
        else:
            raise


@dp.callback_query(lambda c: c.data == "subscribe_week")
async def subscribe_week_callback(call: CallbackQuery):
    """Обработчик кнопки 'Подписка на неделю'."""
    price = get_price("week")  # Получаем цену для подписки на неделю
    card = get_card()  # Получаем реквизиты карты
    user_id = call.from_user.id

    # Сохраняем выбранный тип подписки в базе данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET selected_subscription = ?
            WHERE id = ?
        """, ("week", user_id))
        conn.commit()

    # Клавиатура с кнопкой "Назад"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Назад", callback_data="buy_subscription")]
    ])

    # Отправляем сообщение с реквизитами
    await call.message.edit_text(
        f"Для оплаты подписки на неделю используйте следующие реквизиты:\n\n"
        f"💳 <b>Карта:</b> {card}\n"
        f"💰 <b>Сумма:</b> {price} рублей\n\n"
        f"Пожалуйста, отправьте скриншот перевода после оплаты.",
        parse_mode="HTML",
        reply_markup=keyboard
    )




from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class SetInfoState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text = State()

@dp.message(Command("set_info"))
async def set_info_start(message: Message, state: FSMContext):
    """Начало процесса обновления информации (запрос фото)."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна только администратору.")
        return

    await message.answer("Пожалуйста, отправьте фото для информации.")
    await state.set_state(SetInfoState.waiting_for_photo)  # Устанавливаем состояние ожидания фото

@dp.message(SetInfoState.waiting_for_photo)
async def set_info_photo(message: Message, state: FSMContext):
    """Обработка полученного фото."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фотографию.")
        return

    try:
        # Получаем наиболее качественную фотографию
        photo = message.photo[-1]
        file_path = f"info_photo.jpg"  # Сохраняем под фиксированным именем

        # Скачиваем фотографию через bot.download()
        await bot.download(photo.file_id, destination=file_path)

        # Сохраняем file_id фото в состоянии
        await state.update_data(photo_file_id=photo.file_id)

        # Переход к следующему шагу (ожидание текста)
        await message.answer("Фотография успешно сохранена. Теперь отправьте текст для информации.")
        await state.set_state(SetInfoState.waiting_for_text)
    except Exception as e:
        logging.error(f"Ошибка при сохранении фотографии: {e}")
        await message.answer("Произошла ошибка при сохранении фотографии. Попробуйте снова.")


@dp.message(SetInfoState.waiting_for_text)
async def set_info_text(message: Message, state: FSMContext):
    """Обработка текста и завершение процесса."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна только администратору.")
        return

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        photo_file_id = data.get("photo_file_id")
        text = message.text.strip()

        # Сохраняем данные в базу
        save_info(photo_file_id, text)

        # Сбрасываем состояние
        await state.clear()
        await message.answer("Информация успешно обновлена!")
    except Exception as e:
        logging.error(f"Ошибка при обновлении информации: {e}")
        await message.answer("Произошла ошибка при обновлении информации. Попробуйте снова.")

def save_info(photo_file_id, text):
    """Сохраняем информацию в базу данных."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Сохраняем фото file_id
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value) VALUES ('info_photo', ?)
    """, (photo_file_id,))

    # Сохраняем текст
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value) VALUES ('info_text', ?)
    """, (text,))

    conn.commit()
    conn.close()




@dp.callback_query(lambda c: c.data == "info")
async def info_callback(call: CallbackQuery):
    """Отображаем информацию с кнопкой 'Назад'."""
    # Текст для отображения
    info_text = (
        "\n👨‍💻 Тех. Поддержка - @PEREKUP_manager\n"
        "ℹ️ ТГ канал бота - @PROFIT_HUNTER_CHANNEL\n\n"
        "🗂️ Инструкция по использованию:\n\n"
        "1 - Откройте Личный кабинет\n"
        "2 - Нажмите кнопку «Основной поиск»\n"
        "3 - Нажмите кнопку «Добавить ссылку»\n"
        "4 - Отправьте ссылку поиска Avito по заданным фильтрам:\n"
        "➡️Откройте в браузере Avito https://avito.ru\n"
        "➡️Выберите категорию товара, настройте фильтр и отправьте боту ссылку на поисковую выдачу.\n\n"
        "Пример:\n"
        "- https://m.avito.ru/moskva/avtomobili/mercedes-benz-ASgBAgICAUTgtg3omCg?cd=1&radius=0&s=104\n"
        "(Автомобили с пробегом марки Mercedes-Benz в Москве отсортированные по дате размещения объявлений)\n\n"
        "5 - Ссылка успешно добавлена, теперь нажмите кнопку «Начать» и бот начнет отслеживать объявления"
    )

    # Путь к фото
    photo_path = "info_photo.jpg"

    # Создаем клавиатуру с кнопкой "Назад"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Назад", callback_data="back_to_start")]
    ])

    if os.path.exists(photo_path):  # Проверяем, существует ли фото
        try:
            # Отправляем фото с текстом
            photo = FSInputFile(photo_path)
            await call.message.answer_photo(photo=photo, caption=info_text, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при отправке информации: {e}")
            await call.message.answer("Произошла ошибка при отправке информации.", reply_markup=keyboard)
    else:
        # Если фото отсутствует, отправляем только текст
        await call.message.answer(info_text, reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start_callback(call: CallbackQuery):
    """Обработчик кнопки 'Назад'."""
    user_id = call.from_user.id
    username = call.from_user.username or "Без имени"

    # Удаляем текущее сообщение
    await call.message.delete()

    # Проверяем статус подписки
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_status, subscription_end_date 
            FROM users 
            WHERE id = ?
        """, (user_id,))
        result = cursor.fetchone()

    if result:
        status, end_date = result
        if status == "active" and end_date and datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") > datetime.now():
            subscription_text = f"активна до {datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')}"
        else:
            subscription_text = "истекла"
    else:
        subscription_text = "не активна"

    # Создаем клавиатуру для личного кабинета
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Основной поиск", callback_data="main_search"),
            types.InlineKeyboardButton(text="Приобрести подписку", callback_data="buy_subscription")
        ],
        [
            types.InlineKeyboardButton(text="Информация", callback_data="info")
        ]
    ])

    # Отправляем фото, текст и кнопки
    photo_path = "ava.png"  # Указываем путь к фото
    try:
        photo = FSInputFile(photo_path)
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                f"ℹ️ <b>Личный кабинет:</b>\n\n"
                f"👤<b>ID пользователя:</b> {user_id}\n\n"
                f"🔑<b>Имя пользователя:</b> {username}\n\n"
                f"🗂<b>Подписка:</b> {subscription_text}\n\n"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(user_id, "Ошибка при загрузке изображения. Проверьте наличие файла 'ava.png'.")

    

from aiogram.types import ContentType


from aiogram import F

@dp.message(F.content_type == ContentType.PHOTO)
async def handle_screenshot(message: Message):
    admin_id = 6422360534  # ID администратора
    username = message.from_user.username or "Без имени"
    user_id = message.from_user.id  # Получаем ID пользователя
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Получаем выбранный тип подписки из базы данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT selected_subscription FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        selected_subscription = result[0] if result else None

    if not selected_subscription:
        await message.answer("Вы не выбрали тип подписки. Пожалуйста, выберите её в разделе 'Приобрести подписку'.")
        return

    # Получаем фотографию
    photo = message.photo[-1]  # Берем самое качественное изображение
    caption = f"Пользователь @{username} отправил скриншот перевода в {timestamp}.\nВыбранная подписка: {selected_subscription}."

    # Клавиатура для подтверждения или отклонения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Подтвердить", callback_data=f"confirm_payment:{user_id}:{selected_subscription}"),
            types.InlineKeyboardButton(text="Отклонить", callback_data=f"decline_payment:{user_id}")
        ]
    ])

    # Отправляем фотографию администратору
    await bot.send_photo(chat_id=admin_id, photo=photo.file_id, caption=caption, reply_markup=keyboard)

    # Уведомляем пользователя
    await message.answer("Ваш скриншот отправлен на проверку. Ожидайте подтверждения.")


from datetime import datetime, timedelta

from datetime import datetime, timedelta

@dp.callback_query(lambda c: c.data.startswith("confirm_payment:"))
async def confirm_payment_callback(call: CallbackQuery):
    data = call.data.split(":")
    user_id = int(data[1])
    subscription_type = data[2]  # 'month' или 'week'

    # Устанавливаем дату окончания подписки в зависимости от типа
    from datetime import datetime, timedelta
    if subscription_type == "month":
        subscription_end_date = datetime.now() + timedelta(days=30)
        period_text = "месяц"
    elif subscription_type == "week":
        subscription_end_date = datetime.now() + timedelta(days=7)
        period_text = "неделя"
    else:
        await call.answer("Неизвестный тип подписки!", show_alert=True)
        return

    # Обновляем статус подписки в базе данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET subscription_status = 'active', subscription_end_date = ? 
            WHERE id = ?
        """, (subscription_end_date.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()

    # Уведомляем пользователя о подписке
    await bot.send_message(
        user_id,
        f"Ваша подписка активирована до {subscription_end_date.strftime('%d.%m.%Y')} ({period_text})!"
    )

    # Отправляем личный кабинет
    username = "Без имени"
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            username = result[0]

    # Проверяем статус подписки
    subscription_text = f"активна до {subscription_end_date.strftime('%d.%m.%Y')} ({period_text})"

    # Создаем клавиатуру для личного кабинета
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Основной поиск", callback_data="main_search"),
            types.InlineKeyboardButton(text="Приобрести подписку", callback_data="buy_subscription")
        ],
        [
            types.InlineKeyboardButton(text="Информация", callback_data="info")
        ]
    ])

    # Отправляем фото, текст и кнопки
    photo_path = "ava.png"  # Указываем путь к фото
    try:
        photo = FSInputFile(photo_path)
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                f"ℹ️ <b>Личный кабинет:</b>\n\n"
                f"👤<b>ID пользователя:</b> {user_id}\n\n"
                f"🔑<b>Имя пользователя:</b> {username}\n\n"
                f"🗂<b>Подписка:</b> {subscription_text}\n\n"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке фото: {e}")
        await bot.send_message(user_id, "Ошибка при загрузке изображения. Проверьте наличие файла 'ava.png'.")

    # Уведомляем администратора
    if call.message.text:
        await call.message.edit_text("Подписка успешно подтверждена.")
    else:
        await call.message.answer("Подписка успешно подтверждена.")


@dp.callback_query(lambda c: c.data.startswith("decline_payment:"))
async def decline_payment_callback(call: CallbackQuery):
    user_id = int(call.data.split(":")[1])

    # Обновляем статус подписки в базе данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users 
            SET subscription_status = 'inactive', subscription_end_date = NULL 
            WHERE id = ?
            """,
            (user_id,)
        )
        conn.commit()

    # Уведомляем пользователя об отклонении подписки
    await bot.send_message(user_id, "Ваша подписка не активирована. Администратор отклонил ваш запрос.")

    # Проверяем наличие текста в сообщении перед редактированием
    if call.message and call.message.text:
        await call.message.edit_text("Подписка не подтверждена.")
    else:
        await call.message.answer("Подписка не подтверждена.")


from aiogram.exceptions import TelegramForbiddenError

from aiogram import exceptions

@dp.message(Command("r"))
async def broadcast_message(message: Message):
    """Функция для рассылки сообщений всем пользователям."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна только администратору.")
        return

    # Получаем текст для рассылки
    broadcast_text = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else None
    if not broadcast_text:
        await message.answer("Пожалуйста, добавьте текст для рассылки.")
        return

    users = get_all_user_ids()  # Получаем список всех user_id из базы данных
    successful = 0
    failed = 0

    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_text)
            successful += 1
        except exceptions.TelegramForbiddenError:
            failed += 1
            logging.warning(f"Не удалось отправить сообщение пользователю {user_id}: пользователь заблокировал бота.")
        except exceptions.TelegramBadRequest as e:
            failed += 1
            logging.error(f"Ошибка при отправке пользователю {user_id}: {e}")

    await message.answer(f"Рассылка завершена. Успешно отправлено: {successful}. Ошибок: {failed}.")



def get_all_user_ids():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users





def has_active_subscription(user_id):
    """Проверяет наличие активной подписки у пользователя"""
    try:
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT subscription_status, subscription_end_date 
                FROM users 
                WHERE id = ?
            """, (user_id,))
            result = cursor.fetchone()

            if not result:
                return False

            status, end_date = result
            
            if not status or not end_date:
                return False

            # Проверяем статус и дату окончания подписки
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
                return status == "active" and end_date > datetime.now()
            except (ValueError, TypeError) as e:
                logging.error(f"Ошибка при проверке подписки для пользователя {user_id}: {e}")
                return False

    except Exception as e:
        logging.error(f"Ошибка при проверке подписки для пользователя {user_id}: {e}")
        return False
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

# Определяем состояния
class LinkStates(StatesGroup):
    waiting_for_add_link = State()
    waiting_for_replace_link = State()

@dp.callback_query(lambda c: c.data == "main_search")
async def main_search_callback(call: CallbackQuery):
    user_id = call.from_user.id

    # Получаем ссылку из базы данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_link FROM user_links WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

    if result and result[0]:
        url = f"Ваша ссылка: {result[0]}"  # Ссылка пользователя, если она есть
    else:
        url = "Ваша ссылка еще не добавлена,\nдобавьте ссылку для поиска"  # Если ссылки нет

    # Проверяем активность подписки
    if not has_active_subscription(user_id):  # Проверка на активную подписку
        await call.message.answer("Эта функция доступна только для пользователей с активной подпиской.")
        return

    # Создаем клавиатуру с кнопками для управления
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Добавить ссылку", callback_data="add_link"),
            types.InlineKeyboardButton(text="Начать поиск", callback_data="start_parser"),
        ],
        [
            types.InlineKeyboardButton(text="Заменить ссылку", callback_data="replace_link"),
            types.InlineKeyboardButton(text="Личный кабинет", callback_data="back_to_start"),
        ],
    ])

    # Отправляем сообщение с информацией
    await call.message.answer(f"Выберите действие для управления парсером.\n{url}", reply_markup=keyboard)



@dp.callback_query(lambda c: c.data == "add_link")
async def add_link_callback(call: CallbackQuery, state: FSMContext):
    # Создаём клавиатуру с кнопкой "Назад"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Назад", callback_data="main_search")]
    ])

    # Редактируем сообщение, добавляя инструкцию и кнопку "Назад"
    try:
        await call.message.edit_text("Отправьте ссылку на Avito.", reply_markup=keyboard)
    except exceptions.TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.message.answer("Отправьте ссылку на Avito.", reply_markup=keyboard)
        else:
            raise
    await state.set_state(LinkStates.waiting_for_add_link)

@dp.message(StateFilter(LinkStates.waiting_for_add_link))
async def save_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    url = message.text.strip()

    if "avito.ru" not in url:
        await message.answer("Пожалуйста, отправьте корректную ссылку на Avito.")
        return
    
    # Сначала сохраняем оригинальную ссылку в базу
    save_last_link(user_id, url)
    
    # Получаем сохраненную ссылку для отображения
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_link FROM user_links WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

    display_url = f"Ваша ссылка: {result[0]}" if result and result[0] else "Ваша ссылка еще не добавлена,\nдобавьте ссылку для поиска"

    # Вызов меню "Основной поиск"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Добавить ссылку", callback_data="add_link"),
            types.InlineKeyboardButton(text="Начать поиск", callback_data="start_parser"),
        ],
        [
            types.InlineKeyboardButton(text="Заменить ссылку", callback_data="replace_link"),
            types.InlineKeyboardButton(text="Личный кабинет", callback_data="back_to_start"),
        ],
    ])

    await message.answer(f"Выберите действие для управления парсером.\n{display_url}", reply_markup=keyboard)
    await message.answer("Ссылка успешно добавлена!")
    await state.clear()


@dp.callback_query(lambda c: c.data == "start_parser")
async def start_parser_callback(call: CallbackQuery):
    """Запуск парсера по сохранённой ссылке."""
    user_id = call.from_user.id
    url = get_last_link(user_id)

    if not url:
        logging.error(f"Ссылка для пользователя {user_id} не найдена.")
        await call.message.answer("Сохранённая ссылка не найдена. Добавьте ссылку перед началом работы.")
        return

    # Создаем клавиатуру с кнопкой "Стоп"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Стоп", callback_data="stop_parsing"),
        ],
        [
            types.InlineKeyboardButton(text="Назад", callback_data="back_to_start"),
        ],
    ])

    # Логируем запуск
    logging.info(f"Запуск парсера для пользователя {user_id} с URL: {url}")

    # Запускаем парсер
    await call.message.edit_text(f"Парсер запущен по ссылке: {url}", reply_markup=keyboard)
    try:
        asyncio.create_task(start_parser(user_id, url))
    except Exception as e:
        logging.error(f"Ошибка при запуске парсера для пользователя {user_id}: {e}")





@dp.callback_query(lambda c: c.data == "replace_link")
async def replace_link_callback(call: CallbackQuery, state: FSMContext):
    # Создаём клавиатуру с кнопкой "Назад"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Назад", callback_data="main_search")]
    ])

    # Редактируем сообщение, добавляя инструкцию и кнопку "Назад"
    await call.message.edit_text("Отправьте новую ссылку на Avito.", reply_markup=keyboard)
    await state.set_state(LinkStates.waiting_for_replace_link)

@dp.message(StateFilter(LinkStates.waiting_for_replace_link))
async def replace_link(message: Message, state: FSMContext):
    """Замена сохранённой ссылки и переход в меню 'Основной поиск'."""
    user_id = message.from_user.id
    url = message.text.strip()

    if "avito.ru" not in url:
        await message.answer("Пожалуйста, отправьте корректную ссылку на Avito.")
        return

    # Заменяем ссылку в базе
    save_last_link(user_id, url)
    await message.answer("Ссылка успешно заменена!")
    await state.clear()

    # Получаем ссылку из базы данных
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
    cursor.execute("SELECT last_link FROM user_links WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result and result[0]:
        url = f"Ваша ссылка: {result[0]}"  # Ссылка пользователя, если она есть
    else:
        url = "Ваша ссылка еще не добавлена,\nдобавьте ссылку для поиска"  # Если ссылки нет

    # Вызов меню "Основной поиск"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Добавить ссылку", callback_data="add_link"),
            types.InlineKeyboardButton(text="Начать поиск", callback_data="start_parser"),
        ],
        [
            types.InlineKeyboardButton(text="Заменить ссылку", callback_data="replace_link"),
            types.InlineKeyboardButton(text="Назад", callback_data="back_to_start"),
        ],
    ])

    await message.answer(f"Выберите действие для управления парсером.\n{url}", reply_markup=keyboard)


def save_last_link(user_id, link):
    """Сохраняем последнюю ссылку пользователя."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_links (user_id, last_link)
        VALUES (?, ?)
    """, (user_id, link))
    conn.commit()
    conn.close()


def get_last_link(user_id):
    """Получаем последнюю сохранённую ссылку пользователя."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_link FROM user_links WHERE user_id = ?
    """, (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None





from aiogram.fsm.storage.memory import MemoryStorage
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация обработчиков
async def main():
    init_db()
    
    # Регистрация обработчиков callback_query
# Регистрация хендлеров для callback_query
    dp.callback_query.register(main_search_callback, lambda c: c.data == "main_search")  # Кнопка "Основной поиск"
    dp.callback_query.register(info_callback, lambda c: c.data == "info")
    dp.callback_query.register(back_to_start_callback, lambda c: c.data == "back_to_start")

    dp.callback_query.register(buy_subscription_callback, lambda c: c.data == "buy_subscription")
    dp.callback_query.register(confirm_payment_callback, lambda c: c.data.startswith("confirm_payment:"))
    dp.callback_query.register(decline_payment_callback, lambda c: c.data.startswith("decline_payment:"))

# Для ссылок (добавить, начать, заменить)
    dp.callback_query.register(add_link_callback, lambda c: c.data == "add_link")
    dp.callback_query.register(start_parser_callback, lambda c: c.data == "start_parser")
    dp.callback_query.register(replace_link_callback, lambda c: c.data == "replace_link")
    dp.callback_query.register(stop_parsing_callback, lambda c: c.data == "stop_parsing")

# Для работы с состояниями
    dp.message.register(save_link, StateFilter(LinkStates.waiting_for_add_link))
    dp.message.register(replace_link, StateFilter(LinkStates.waiting_for_replace_link))


# Регистрация обработчиков сообщений
    dp.message.register(start_command, Command("start"))

    dp.message.register(broadcast_message, Command("r"))
    dp.message.register(set_card, Command("card"))  # Регистрация команды /card
    dp.message.register(set_price, Command("price"))  # Регистрация команды /price
    dp.message.register(set_info_start, Command("set_info"))
    dp.message.register(set_info_photo, SetInfoState.waiting_for_photo)
    dp.message.register(set_info_text, SetInfoState.waiting_for_text)
    dp.callback_query.register(info_callback, lambda c: c.data == "info")
    dp.callback_query.register(subscribe_month_callback, lambda c: c.data == "subscribe_month")
    dp.callback_query.register(subscribe_week_callback, lambda c: c.data == "subscribe_week")


# Callback для информации
    dp.callback_query.register(info_callback, lambda c: c.data == "info")

    dp.message.register(handle_screenshot, F.content_type == ContentType.PHOTO)


    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    init_db()
    print("База данных инициализирована.")
if __name__ == "__main__":
    add_column_to_users()
    print("Проверка и добавление столбца selected_subscription завершены.")
if __name__ == "__main__":
    init_db()
    add_column_to_users()
    print("База данных инициализирована, все необходимые столбцы добавлены.")

if __name__ == "__main__":
    init_db()
    asyncio.run(main())
