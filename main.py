import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = "ВАШ_ТОКЕН_БОТА"
ADMIN_ID = 000000000 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class FeedbackForm(StatesGroup):
    waiting_for_message = State()

def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Отправить анонимное сообщение")]],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "<b>Добро пожаловать в анонимный чат!</b>\n\n"
        "Ваша личность скрыта. Администратор получит только текст сообщения.\n"
        "Исходный код бота открыт для проверки на GitHub.",
        reply_markup=get_main_kb(),
        parse_mode="HTML"
    )

@dp.message(F.text == "📝 Отправить анонимное сообщение")
async def process_start_feedback(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите ваше сообщение (текст, фото или видео):")
    await state.set_state(FeedbackForm.waiting_for_message)

@dp.message(FeedbackForm.waiting_for_message, F.content_type.in_({'text', 'photo', 'video', 'animation'}))
async def handle_feedback(message: types.Message, state: FSMContext):
    header = f"📩 <b>Новое сообщение</b>\nTicket-ID: <code>{message.from_user.id}</code>\n\n"
    
    try:
        if message.text:
            await bot.send_message(ADMIN_ID, f"{header}{message.text}", parse_mode="HTML")
        elif message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=header, parse_mode="HTML")
        elif message.video:
            await bot.send_video(ADMIN_ID, message.video.file_id, caption=header, parse_mode="HTML")
        
        await message.answer(f"✅ Сообщение успешно доставлено администратору!")
    except Exception:
        await message.answer("❌ Произошла ошибка при отправке. Попробуйте позже.")
    
    await state.clear()

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def admin_reply(message: types.Message):
    try:
        source = message.reply_to_message.text or message.reply_to_message.caption
        user_id = int(source.split('Ticket-ID: ')[1].split('\n')[0])
        
        await bot.send_message(user_id, f"<b>💬 Ответ от администрации:</b>\n\n{message.text}", parse_mode="HTML")
        await message.answer("🚀 Ответ отправлен.")
    except Exception:
        await message.answer("❌ Ошибка: не удалось определить получателя.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
