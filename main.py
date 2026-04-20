import asyncio
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "ВАШ_ТОКЕН"
MY_ID = 0

bot = Bot(token=TOKEN)
dp = Dispatcher()

u_map = {}
stats = {}

class Form(StatesGroup):
    wait_msg = State()

def main_kb():
    kb = [
        [KeyboardButton(text="📝 Написать анонимно")],
        [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="🔑 Мой ID")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_hash(uid: int):
    h = hashlib.sha256(str(uid).encode()).hexdigest()[:12]
    u_map[h] = uid
    return h

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "Приватный чат. Твой профиль скрыт хешем.\n"
        "Админ видит только ID-тикета. Никаких логов нет.",
        reply_markup=main_kb()
    )

@dp.message(F.text == "🔑 Мой ID")
async def my_id(msg: types.Message):
    tid = get_hash(msg.from_user.id)
    await msg.answer(f"Твой ID: {tid}")

@dp.message(F.text == "🏆 Топ")
async def show_top(msg: types.Message):
    if not stats:
        return await msg.answer("Топ пуст")
    
    top = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:5]
    res = "🏆 ТОП АКТИВНОСТИ:\n\n"
    for i, (uid, count) in enumerate(top, 1):
        res += f"{i}. {get_hash(uid)} — {count} сообщ.\n"
    await msg.answer(res)

@dp.message(F.text == "📝 Написать анонимно")
async def go_send(msg: types.Message, state: FSMContext):
    await msg.answer("Жду сообщение (текст/фото/кружок/гиф):")
    await state.set_state(Form.wait_msg)

@dp.message(Form.wait_msg)
async def send_msg(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    tid = get_hash(uid)
    head = f"От: {tid}\n"
    
    try:
        stats[uid] = stats.get(uid, 0) + 1
        await msg.copy_to(MY_ID, caption=head)
        
        if not msg.caption and not any([msg.photo, msg.video, msg.voice, msg.video_note, msg.animation]):
            if msg.text:
                await bot.send_message(MY_ID, head + msg.text)

        await msg.answer(f"Отправлено. Твой ID: {tid}")
    except:
        await msg.answer("Ошибка")
    
    await state.clear()

@dp.message(F.reply_to_message & (F.chat.id == MY_ID))
async def answer(msg: types.Message):
    try:
        text = msg.reply_to_message.text or msg.reply_to_message.caption
        tid = text.split('От: ')[1].split('\n')[0].strip()
        uid = u_map.get(tid)
        
        if uid:
            await msg.copy_to(uid)
            await msg.answer("Ок, ушло.")
        else:
            await msg.answer("ID не найден в памяти")
    except:
        await msg.answer("Нужно ответить на сообщение")

async def run():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(run())
