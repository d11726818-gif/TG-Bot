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
BOT_TOKEN = os.getenv("BOT_TOKEN")

class Form(StatesGroup):
    waiting_for_msg = State()

logging.basicConfig(level=logging.INFO)
DB_PATH = "/data/feedback_private.db" if os.path.exists("/data") else "feedback_private.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (user_id INTEGER PRIMARY KEY, name TEXT, count INTEGER DEFAULT 0, is_hidden INTEGER DEFAULT 0)''')
    cur.execute('CREATE TABLE IF NOT EXISTS msgs (admin_msg_id INTEGER PRIMARY KEY, user_id INTEGER, is_read INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    res = None
    try:
        cur.execute(query, params)
        if fetchone:
            res = cur.fetchone()
        elif fetchall:
            res = cur.fetchall()
        if commit:
            conn.commit()
    finally:
        conn.close()
    return res

async def main():
    if not BOT_TOKEN: return
    init_db()
    bot = Bot(token=BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    main_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✍️ Написать сообщение")], [KeyboardButton(text="🏆 Топ активных")]], resize_keyboard=True)

    @dp.message(Command("start"))
    async def cmd_start(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("<b>👋 Привет!</b> Выберите действие:", reply_markup=main_kb)

    @dp.message(F.text == "🏆 Топ активных")
    async def btn_top(m: Message):
        rows = db_query("SELECT name, count FROM users WHERE is_hidden = 0 ORDER BY count DESC LIMIT 10", fetchall=True)
        top_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔒 Скрыть/Показать меня", callback_data="toggle_privacy")]])
        res = "🏆 <b>Топ активных пользователей:</b>\n\n"
        if not rows:
            res += "📊 Список пока пуст."
        else:
            for i, (name, count) in enumerate(rows, 1):
                res += f"{i}. {name} — <code>{count}</code>\n"
        await m.answer(res, reply_markup=top_kb)

    @dp.callback_query(F.data == "toggle_privacy")
    async def toggle_privacy(call: CallbackQuery):
        status = db_query("SELECT is_hidden FROM users WHERE user_id = ?", (call.from_user.id,), fetchone=True)
        if status:
            new_status = 1 if status[0] == 0 else 0
            db_query("UPDATE users SET is_hidden = ? WHERE user_id = ?", (new_status, call.from_user.id), commit=True)
            await call.answer("Настройки приватности изменены ✅", show_alert=True)
        else:
            await call.answer("Вы еще не писали боту!", show_alert=True)

    @dp.message(F.text == "✍️ Написать сообщение")
    async def btn_write(m: Message, state: FSMContext):
        await m.answer("<b>📝 Жду ваше сообщение:</b>")
        await state.set_state(Form.waiting_for_msg)

    @dp.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
    async def admin_reply(m: Message):
        data = db_query("SELECT user_id, is_read FROM msgs WHERE admin_msg_id = ?", (m.reply_to_message.message_id,), fetchone=True)
        if data:
            user_id, is_read = data
            try:
                if is_read == 0:
                    await bot.send_message(user_id, "<b>👀 Ваше сообщение прочитано администратором!</b>")
                    db_query("UPDATE msgs SET is_read = 1 WHERE admin_msg_id = ?", (m.reply_to_message.message_id,), commit=True)
                await bot.send_message(user_id, "<b>📩 Вам пришел ответ от администратора!</b>")
                await m.copy_to(user_id)
                await m.answer("✅ Отправлено!")
            except:
                await m.answer("❌ Ошибка доставки.")

    @dp.message(Form.waiting_for_msg)
    async def handle_msg(m: Message, state: FSMContext):
        if m.from_user.id == ADMIN_ID: return
        user_name = f"@{m.from_user.username}" if m.from_user.username else m.from_user.full_name
        db_query("INSERT INTO users (user_id, name, count) VALUES (?, ?, 1) ON CONFLICT(user_id) DO UPDATE SET name = ?, count = count + 1", 
                 (m.from_user.id, user_name, user_name), commit=True)
        header = "<b>💬 У тебя новое анонимное сообщение!</b>\n\n"
        footer = "\n\n<i>↪️ Свайпни для ответа.</i>"
        try:
            if m.text:
                sent = await bot.send_message(ADMIN_ID, f"{header}<blockquote>{m.text}</blockquote>{footer}")
            else:
                cap = m.caption if m.caption else "(Медиафайл)"
                txt_header = await bot.send_message(ADMIN_ID, f"{header}<blockquote>{cap}</blockquote>{footer}")
                sent = await m.copy_message(ADMIN_ID, m.chat.id, m.message_id, reply_to_message_id=txt_header.message_id)
            db_query("INSERT INTO msgs (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, m.from_user.id), commit=True)
            await m.answer("🚀 <b>Доставлено!</b>", reply_markup=main_kb)
        except:
            await m.answer("❌ Ошибка отправки.")
        await state.clear()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
