import os
import asyncio
import sqlite3
import re
import base64
import requests
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==========================================
# 1. KONFIGURATSIYA
# ==========================================
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
MY_ID = 8746895843 # Sizning ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    # Moliya, Vazifalar, Dublyaj va Nemis tili jadvallari
    cursor.execute('CREATE TABLE IF NOT EXISTS finance (id INTEGER PRIMARY KEY, type TEXT, amount INTEGER, note TEXT, date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, task TEXT, status TEXT, date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS diary (id INTEGER PRIMARY KEY, note TEXT, date TEXT)')
    conn.commit()
    conn.close()

# ==========================================
# 2. GEMINI REST API (BARQAROR v1)
# ==========================================
async def call_gemini(prompt, media_b64=None, mime_type=None, context="umumiy"):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    # Mentor Shaxsiyati
    sys_ins = (
        f"Sen Shohruxxonning (18 yosh, Farg'ona, usta va dublyajchi) shaxsiy assistentisan. "
        f"Hozir vaqt: {datetime.now().strftime('%H:%M')}. "
        "Javoblaring o'ta aqlli, qisqa (3-4 gap), o'zbekcha va do'stona bo'lsin. "
        "Unga 'Shohruxbek' yoki 'Usta' deb murojaat qil."
    )

    if context == "usta": sys_ins += " Hozir usta rejimidasan. Sxemalar va remont haqida gaplash."
    if context == "nemis": sys_ins += " Nemis tili o'qituvchisisan. A2 darajada yordam ber."

    parts = [{"text": f"{sys_ins}\n\nShohrux: {prompt}"}]
    if media_b64:
        parts.append({"inline_data": {"mime_type": mime_type, "data": media_b64}})

    payload = {"contents": [{"parts": parts}]}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"Tizim xatosi ({response.status_code}). Iltimos qayta urinib ko'ring."
    except:
        return "Ulanishda muammo bo'ldi. Internetni tekshiring."

# ==========================================
# 3. AQLLI PARSER (AUTOMATION)
# ==========================================
def auto_save(text):
    text_l = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    msg = None

    # Moliya (Pul tushumi)
    if any(x in text_l for x in ["so'm", "ming", "ishladim", "berdi"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("in", int(nums[0]), text, now))
            msg = f"💰 {int(nums[0]):,} so'm saqlandi."
    
    # Vazifa (To-do)
    if "reja:" in text_l or "qilishim kerak" in text_l:
        cursor.execute("INSERT INTO tasks (task, status, date) VALUES (?, ?, ?)", (text, "pending", now))
        msg = "📝 Vazifa ro'yxatga qo'shildi."

    conn.commit()
    conn.close()
    return msg

# ==========================================
# 4. AVTOMATIK ESLATMALAR (CRON)
# ==========================================
async def periodic_task(mode):
    if mode == "morning":
        await bot.send_message(MY_ID, "🌅 **Xayrli tong, Usta!**\nBugun qanday rejalarimiz bor? Men tayyorman!")
    elif mode == "german":
        ans = await call_gemini("Menga bitta nemischa yangi so'z va misol yubor (A2).", context="nemis")
        await bot.send_message(MY_ID, f"🇩🇪 **Nemis tili vaqti:**\n\n{ans}")
    elif mode == "spirt":
        await bot.send_message(MY_ID, "🧴 **Eslatma:** Yuzingizni tozalash (spirt) vaqti keldi!")

# ==========================================
# 5. HANDLERLAR
# ==========================================
def get_main_kb():
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="🛠️ Usta Rejimi"), types.KeyboardButton(text="🎙️ Dublyaj"))
    kb.row(types.KeyboardButton(text="📊 Hisobotlar"), types.KeyboardButton(text="📝 Vazifalar"))
    kb.row(types.KeyboardButton(text="🇩🇪 Nemis Tili"), types.KeyboardButton(text="🐈 Mushuklar"))
    return kb.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    init_db()
    # Eslatmalarni o'rnatish
    scheduler.add_job(periodic_task, 'cron', hour=8, minute=0, args=["morning"], id="morn", replace_existing=True)
    scheduler.add_job(periodic_task, 'cron', hour=10, minute=0, args=["german"], id="ger", replace_existing=True)
    scheduler.add_job(periodic_task, 'cron', hour=22, minute=30, args=["spirt"], id="spir", replace_existing=True)
    
    await message.answer("Shohrux OS Ultimate v4.0 Ishga tushdi! 🚀\nSizni tushunadigan yagona tizim.", reply_markup=get_main_kb())

@dp.message(F.photo)
async def photo_msg(message: types.Message):
    wait = await message.answer("🔎 Skaner qilyapman...")
    file = await bot.get_file(message.photo[-1].file_id)
    img_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    b64 = base64.b64encode(img_data).decode('utf-8')
    
    ans = await call_gemini(message.caption or "Tahlil qil", media_b64=b64, mime_type="image/jpeg", context="usta")
    await wait.edit_text(ans)

@dp.message()
async def text_msg(message: types.Message):
    text = message.text
    
    # Maxsus tugmalar
    if text == "📊 Hisobotlar":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='in'")
        total = c.fetchone()[0] or 0
        await message.answer(f"📈 Jami daromad: {total:,} so'm.\nBaraka bersin!")
        return

    # Taymer (Masalan: 10 daqiqadan keyin eslat choy ichish)
    timer = re.search(r'(\d+)\s+(daqiqadan|soatdan)\s+keyin\s+(eslat)\s*(.*)', text.lower())
    if timer:
        val = int(timer.group(1))
        unit = timer.group(2)
        note = timer.group(4) or "Vaqt bo'ldi!"
        run_at = datetime.now() + (timedelta(minutes=val) if unit == "daqiqadan" else timedelta(hours=val))
        scheduler.add_job(lambda: bot.send_message(message.chat.id, f"🔔 **ESLATMA:** {note}"), 'date', run_time=run_at)
        await message.answer(f"✅ {val} {unit} keyin eslataman.")
        return

    # Avtomatik saqlash va AI javobi
    parsed = auto_save(text)
    wait = await message.answer("⚡...")
    ans = await call_gemini(text)
    
    final = f"{ans}\n\n✅ {parsed}" if parsed else ans
    await wait.edit_text(final)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    if not scheduler.running: scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
