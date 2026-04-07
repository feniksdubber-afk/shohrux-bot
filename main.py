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
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==========================================
# 1. SOZLAMALAR
# ==========================================
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
MY_ID = 8746895843 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS finance (id INTEGER PRIMARY KEY, type TEXT, amount INTEGER, note TEXT, date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, task TEXT, status TEXT, date TEXT)')
    conn.commit()
    conn.close()

# ==========================================
# 2. AQLLI MODEL QIDIRUVCHI (ANTI-404)
# ==========================================
async def call_gemini(prompt, media_b64=None, mime_type=None, context="umumiy"):
    # Google tan oladigan barcha mumkin bo'lgan model nomlari
    models_to_test = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    
    sys_ins = (
        "Sen Shohruxxonning (18 yosh, usta va dublyajchi) mentorsan. "
        "Javobing qisqa va faqat o'zbek tilida bo'lsin."
    )

    parts = [{"text": f"{sys_ins}\n\nShohrux: {prompt}"}]
    if media_b64:
        parts.append({"inline_data": {"mime_type": mime_type, "data": media_b64}})

    payload = {"contents": [{"parts": parts}]}
    
    # Har bir modelni birma-bir tekshirib ko'ramiz
    for model_name in models_to_test:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_KEY}"
        try:
            response = requests.post(url, json=payload, timeout=20)
            res_json = response.json()
            
            if response.status_code == 200:
                # Muvaffaqiyatli javob kelsa, darhol qaytaramiz
                return res_json['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 404:
                # 404 bo'lsa, keyingi modelga o'tamiz
                logging.warning(f"{model_name} topilmadi, keyingisini sinayapman...")
                continue
            else:
                logging.error(f"Xato {response.status_code}: {res_json}")
        except Exception as e:
            logging.error(f"Ulanishda xato: {e}")
            continue

    return "Hozircha Google modellari bilan ulanib bo'lmadi. Keyinroq urinib ko'ring yoki API kalitni tekshiring."

# ==========================================
# 3. MOLIYA VA VAZIFA FUNKSIYALARI
# ==========================================
def smart_save(text):
    text_l = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    msg = None

    if any(x in text_l for x in ["so'm", "ming", "topdim", "ishladim"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("in", int(nums[0]), text, now))
            msg = f"💰 {int(nums[0]):,} so'm daromad yozildi."
            
    conn.commit()
    conn.close()
    return msg

# ==========================================
# 4. HANDLERLAR (BOT QULOQLARI)
# ==========================================
@dp.message(Command("start"))
async def start(message: types.Message):
    init_db()
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="📊 Hisobot"), types.KeyboardButton(text="📝 Vazifalar"))
    await message.answer("Shohrux OS v5.0 (Anti-404) faol! 🔥\nBarchasi avtomatik sozlangan.", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.photo)
async def photo_msg(message: types.Message):
    wait = await message.answer("🔎 Rasm tahlil qilinmoqda...")
    file = await bot.get_file(message.photo[-1].file_id)
    img_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    b64 = base64.b64encode(img_data).decode('utf-8')
    
    ans = await call_gemini(message.caption or "Rasmda nima bor?", media_b64=b64, mime_type="image/jpeg")
    await wait.edit_text(ans)

@dp.message()
async def text_msg(message: types.Message):
    text = message.text
    
    if text == "📊 Hisobot":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='in'")
        total = c.fetchone()[0] or 0
        await message.answer(f"📈 Jami daromad: {total:,} so'm.")
        return

    parsed = smart_save(text)
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
