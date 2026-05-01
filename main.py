import os
import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

ADMIN_ID = 123456789 
CHANNEL_ID = -100123456789 
BOT_TOKEN = os.getenv("BOT_TOKEN")

class Form(StatesGroup):
    waiting_for_msg = State()

logging.basicConfig(level=logging.INFO)
DB_PATH = "/data/feedback_private.db" if os.path.exists("/data") else "feedback_private.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS msgs (admin_msg_id INTEGER PRIMARY KEY, user_id INTEGER, is_read INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    res = None
    try:
        cur.execute(query, params)
        if fetchone: res = cur.fetchone()
        elif fetchall: res = cur.fetchall()
        if commit: conn.commit()
    finally:
        conn.close()
    return res

async def main():
    if not BOT_TOKEN: return
    init_db()
    bot = Bot(token=BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    main_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✍️ Написать сообщение")]], resize_keyboard=True)

    @dp.message(Command("start"))
    async def cmd_start(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("<b>👋 Привет!</b> Ваша личность скрыта.\nИспользуйте кнопку ниже, чтобы отправить сообщение:", reply_markup=main_kb)

    @dp.message(F.text == "✍️ Написать сообщение")
    async def btn_write(m: Message, state: FSMContext):
        await m.answer("<b>📝 Жду ваше сообщение (текст или медиа):</b>")
        await state.set_state(Form.waiting_for_msg)

    @dp.callback_query(F.data == "publish_to_channel")
    async def publish_post(call: CallbackQuery):
        try:
            await bot.copy_message(chat_id=CHANNEL_ID, from_chat_id=call.message.chat.id, message_id=call.message.message_id)
            await call.answer("✅ Опубликовано в канал!", show_alert=True)
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logging.error(e)
            await call.answer("❌ Ошибка публикации. Проверьте права бота в канале.", show_alert=True)

    @dp.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
    async def admin_reply(m: Message):
        data = db_query("SELECT user_id, is_read FROM msgs WHERE admin_msg_id = ?", (m.reply_to_message.message_id,), fetchone=True)
        if data:
            user_id, is_read = data
            try:
                if is_read == 0:
                    await bot.send_message(user_id, "<b>👀 Ваше сообщение прочитано администратором!</b>")
                    db_query("UPDATE msgs SET is_read = 1 WHERE admin_msg_id = ?", (m.reply_to_message.message_id,), commit=True)
                
                if m.text:
                    await bot.send_message(user_id, f"<b>📩 ОТВЕТ ОТ АДМИНИСТРАТОРА:</b>\n\n<blockquote>{m.text}</blockquote>")
                else:
                    await bot.send_message(user_id, "<b>📩 ОТВЕТ ОТ АДМИНИСТРАТОРА (Медиа):</b>")
                    await bot.copy_message(chat_id=user_id, from_chat_id=m.chat.id, message_id=m.message_id)
                await m.answer("✅ Отправлено!")
            except: await m.answer("❌ Ошибка доставки.")

    @dp.message(Form.waiting_for_msg)
    async def handle_msg(m: Message, state: FSMContext):
        if m.from_user.id == ADMIN_ID: return
        db_query("INSERT INTO users (user_id, count) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1", (m.from_user.id,), commit=True)
        
        header = "<b>💬 Новая предложка!</b>\n\n"
        footer = "\n\n<i>↪️ Свайпни для ответа или нажми кнопку для публикации.</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Опубликовать в канал", callback_data="publish_to_channel")]])

        try:
            if m.text:
                sent = await bot.send_message(chat_id=ADMIN_ID, text=f"{header}<blockquote>{m.text}</blockquote>{footer}", reply_markup=kb)
            else:
                cap = m.caption if m.caption else "(Медиафайл)"
                txt_header = await bot.send_message(chat_id=ADMIN_ID, text=f"{header}<blockquote>{cap}</blockquote>{footer}")
                sent = await bot.copy_message(chat_id=ADMIN_ID, from_chat_id=m.chat.id, message_id=m.message_id, reply_to_message_id=txt_header.message_id, reply_markup=kb)
            
            db_query("INSERT INTO msgs (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, m.from_user.id), commit=True)
            await m.answer("🚀 <b>Доставлено анонимно!</b>", reply_markup=main_kb)
        except Exception as e:
            logging.error(e)
            await m.answer("❌ Ошибка отправки.")
        await state.clear()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
