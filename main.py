Import asyncio
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = "ВАШ_ТОКЕН_БОТА"
ADMIN_ID = 000000000 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Словарь для временного хранения соответствия хеша и ID (только в оперативной памяти)
# После перезагрузки бота сопоставить старые сообщения с пользователями будет невозможно
user_map = {}

class FeedbackForm(StatesGroup):
    waiting_for_message = State()

def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Отправить анонимное сообщение")]],
        resize_keyboard=True
    )

def generate_ticket_id(user_id: int) -> str:
    """Создает анонимный Ticket-ID, который скрывает реальный профиль."""
    hash_object = hashlib.sha256(str(user_id).encode())
    ticket_id = hash_object.hexdigest()[:12]  # Берем первые 12 символов для удобства
    user_map[ticket_id] = user_id
    return ticket_id

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "<b>Добро пожаловать в анонимный чат!</b>\n\n"
        "Ваша личность защищена хешированием. Администратор видит только временный Ticket-ID.\n"
        "Связь с вашим реальным профилем отсутствует в базе данных.",
        reply_markup=get_main_kb(),
        parse_mode="HTML"
    )

@dp.message(F.text == "📝 Отправить анонимное сообщение")
async def process_start_feedback(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите ваше сообщение:")
    await state.set_state(FeedbackForm.waiting_for_message)

@dp.message(FeedbackForm.waiting_for_message, F.content_type.in_({'text', 'photo', 'video', 'animation'}))
async def handle_feedback(message: types.Message, state: FSMContext):
    # Генерируем анонимный ID
    t_id = generate_ticket_id(message.from_user.id)
    header = f"📩 <b>Новое анонимное сообщение</b>\nTicket-ID: <code>{t_id}</code>\n\n"
    
    try:
        if message.text:
            await bot.send_message(ADMIN_ID, f"{header}{message.text}", parse_mode="HTML")
        elif message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=header, parse_mode="HTML")
        elif message.video:
            await bot.send_video(ADMIN_ID, message.video.file_id, caption=header, parse_mode="HTML")
        
        await message.answer(f"✅ Сообщение доставлено. Ваш анонимный ID: {t_id}")
    except Exception:
        await message.answer("❌ Ошибка отправки.")
    
    await state.clear()

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply(message: types.Message):
    try:
        source = message.reply_to_message.text or message.reply_to_message.caption
        t_id = source.split('Ticket-ID: ')[1].split('\n')[0].strip()
        
        # Получаем реальный ID из временной карты
        user_id = user_map.get(t_id)
        
        if user_id:
            await bot.send_message(user_id, f"<b>💬 Ответ от администрации:</b>\n\n{message.text}", parse_mode="HTML")
            await message.answer("🚀 Ответ отправлен анонимно.")
        else:
            await message.answer("❌ Ошибка: срок действия сессии истек или ID неверный.")
    except Exception:
        await message.answer("❌ Не удалось определить получателя.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
