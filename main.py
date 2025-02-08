from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from yookassa import Configuration, Payment
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated

# Состояния FSM
class OrderStates(StatesGroup):
    waiting_for_project_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

class PaymentStates(StatesGroup):
    waiting_for_order_number = State()

# Структура для хранения заказов
orders = {}

# Добавьте словарь для отслеживания платежей
pending_payments = {}  # {order_id: {'payment_id': '...', 'created_at': datetime}}

# База данных пользователей (можно заменить на реальную БД)
users_db = {}
CHANNEL_ID = "@madexxxchanel"  # Замените на ID вашего канала
CHANNEL_LINK = "https://t.me/madexxxchanel"  # Замените на ссылку на ваш канал

# Инициализация бота
bot = Bot(token='7894399587:AAGPNLILuCjCqPGZiooLZ1yAA_zlQlAc0i4')
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
ADMIN_ID = 7830802188  # ID администратора

# Настройка ЮKassa
Configuration.account_id = 'YOUR_SHOP_ID'
Configuration.secret_key = 'YOUR_SECRET_KEY'

# Функция проверки подписки
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in ["left", "kicked", "banned"]
    except Exception:
        return False

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Добавляем пользователя в базу данных
    if user_id not in users_db:
        users_db[user_id] = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'joined_date': datetime.now()
        }
    
    # Проверяем подписку на канал
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="Подписаться на канал",
                        url=CHANNEL_LINK
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="Проверить подписку",
                        callback_data="check_subscription"
                    )
                ]
            ]
        )
        
        await message.answer(
            "Для использования бота необходимо подписаться на наш канал!",
            reply_markup=keyboard
        )
        return
    
    # Если пользователь подписан, отправляем приветствие
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Добро пожаловать в систему оплаты заказов.\n"
        "Пожалуйста, введите номер вашего заказа:"
    )
    await state.set_state(PaymentStates.waiting_for_order_number)

# Обработчик проверки подписки
@dp.callback_query(F.data == "check_subscription")
async def subscription_check(callback: CallbackQuery, state: FSMContext):
    is_subscribed = await check_subscription(callback.from_user.id)
    
    if is_subscribed:
        await callback.message.delete()  # Удаляем сообщение с кнопками
        await callback.message.answer(
            f"Привет, {callback.from_user.first_name}! 👋\n"
            "Добро пожаловать в систему оплаты заказов.\n"
            "Пожалуйста, введите номер вашего заказа:"
        )
        await state.set_state(PaymentStates.waiting_for_order_number)
    else:
        await callback.answer(
            "Вы все еще не подписаны на канал! Подпишитесь и нажмите кнопку проверки снова.",
            show_alert=True
        )

# Обработчик команды /add (только для админа)
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    await message.answer("Введите название проекта:")
    await state.set_state(OrderStates.waiting_for_project_name)

# Получение названия проекта
@dp.message(StateFilter(OrderStates.waiting_for_project_name))
async def process_project_name(message: Message, state: FSMContext):
    await state.update_data(project_name=message.text)
    await message.answer("Теперь введите полное описание/ТЗ проекта:")
    await state.set_state(OrderStates.waiting_for_description)

# Получение описания
@dp.message(StateFilter(OrderStates.waiting_for_description))
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Укажите стоимость проекта (в рублях):")
    await state.set_state(OrderStates.waiting_for_price)

# Получение цены и сохранение заказа
@dp.message(StateFilter(OrderStates.waiting_for_price))
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        data = await state.get_data()
        order_id = len(orders) + 1
        orders[order_id] = {
            'project_name': data['project_name'],
            'description': data['description'],
            'price': price,
            'status': 'new'
        }
        await message.answer(f"Заказ сохранен под номером: {order_id}")
        await state.clear()
    except ValueError:
        await message.answer("Пожалуйста, введите корректную цену")

# Обработка номера заказа от пользователя
@dp.message(StateFilter(PaymentStates.waiting_for_order_number))
async def process_order_number(message: Message, state: FSMContext):
    try:
        order_id = int(message.text)
        if order_id in orders:
            order = orders[order_id]
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text="Оплатить",
                        callback_data=f"pay_{order_id}"
                    )
                ]]
            )
            
            await message.answer(
                f"Информация о заказе:\n"
                f"Название: {order['project_name']}\n"
                f"Описание: {order['description']}\n"
                f"Стоимость: {order['price']} руб.",
                reply_markup=keyboard
            )
        else:
            await message.answer("Заказ с таким номером не найден")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный номер заказа")
    await state.clear()

# Обработка нажатия кнопки оплаты
@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    order_id = int(callback.data.split('_')[1])
    order = orders[order_id]
    
    payment = Payment.create({
        "amount": {
            "value": str(order['price']),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/ваш_username_бота"
        },
        "capture": True,
        "description": f'Оплата заказа #{order_id}',
        "metadata": {
            "order_id": order_id
        }
    })
    
    # Сохраняем информацию о платеже
    pending_payments[order_id] = {
        'payment_id': payment.id,
        'created_at': datetime.now()
    }
    
    await callback.message.answer(
        f"Ссылка для оплаты: {payment.confirmation.confirmation_url}\n"
        "После оплаты статус заказа будет обновлен в течение минуты."
    )
    await callback.answer()

# Добавьте функцию проверки платежей
async def check_payments():
    while True:
        try:
            current_time = datetime.now()
            payments_to_remove = []
            
            for order_id, payment_info in pending_payments.items():
                # Проверяем только платежи не старше 1 часа
                if current_time - payment_info['created_at'] > timedelta(hours=1):
                    payments_to_remove.append(order_id)
                    continue
                
                # Получаем информацию о платеже
                payment = Payment.find_one(payment_info['payment_id'])
                
                if payment.status == 'succeeded':
                    # Платёж успешен
                    orders[order_id]['status'] = 'paid'
                    payments_to_remove.append(order_id)
                    
                    # Уведомляем админа
                    await bot.send_message(
                        ADMIN_ID,
                        f"✅ Получена оплата за заказ #{order_id}\n"
                        f"Сумма: {payment.amount.value} {payment.amount.currency}"
                    )
                
                elif payment.status in ['canceled', 'expired']:
                    # Платёж отменён или истёк
                    payments_to_remove.append(order_id)
            
            # Удаляем обработанные платежи
            for order_id in payments_to_remove:
                pending_payments.pop(order_id, None)
                
        except Exception as e:
            logging.error(f"Ошибка при проверке платежей: {e}")
        
        # Проверяем каждые 30 секунд
        await asyncio.sleep(30)

# Измените функцию main
async def main():
    # Запускаем бота и проверку платежей
    await asyncio.gather(
        dp.start_polling(bot),
        check_payments()
    )

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())