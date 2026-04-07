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
# 1. SOZLAMALAR VA BAZA
# ==========================================
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS finance (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, amount INTEGER, note TEXT, date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, status TEXT, date TEXT)''')
    conn.commit()
    conn.close()

# ==========================================
# 2. GEMINI AI YADROSI (REST v1 - ENG BARQAROR)
# ==========================================
async def call_gemini(prompt, media_b64=None, mime_type=None):
    # Biz v1beta emas, barqaror v1 dan foydalanamiz
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    system_instruction = (
        "Sen Shohruxxonning (18 yosh, usta va dublyajchi) mentorsan. "
        "Javoblaring qisqa, aqlli va o'zbek tilida bo'lsin."
    )

    contents = [{
        "parts": [{"text": f"{system_instruction}\n\nShohruxxon: {prompt}"}]
    }]

    if media_b64:
        contents[0]["parts"].append({
            "inline_data": {
                "mime_type": mime_type,
                "data": media_b64
            }
        })

    payload = {"contents": contents}

    try:
        # Retry (3 marta urinish)
        for _ in range(3):
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                res_json = response.json()
                return res_json['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 404:
                # Agar v1 da topilmasa, v1beta ni oxirgi chora sifatida ko'ramiz
                url = url.replace("/v1/", "/v1beta/")
            await asyncio.sleep(1)
            
        return f"Xatolik yuz berdi (Kod: {response.status_code}). Keyinroq urinib ko'ring."
    except Exception as e:
        return f"Ulanishda xatolik: {str(e)[:50]}"

# ==========================================
# 3. MOLIYA VA VAZIFALAR LOGIKASI
# ==========================================
def smart_parser(text):
    text_lower = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    res = None
    
    if any(x in text_lower for x in ["so'm", "topdim", "ishladim", "tushum"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("tushum", amount, text, now))
            res = f"💰 {amount:,} so'm saqlandi."
            
    conn.commit()
    conn.close()
    return res

# ==========================================
# 4. HANDLERLAR
# ==========================================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    init_db()
    await message.answer(
        "Salom Shohruxxon! 🚀\nTizim REST API v1 ga o'tkazildi. Endi 404 xatosi bo'lmasligi kerak.",
        reply_markup=ReplyKeyboardBuilder().row(
            types.KeyboardButton(text="📊 Moliya Hisoboti"),
            types.KeyboardButton(text="📝 Vazifalar")
        ).as_markup(resize_keyboard=True)
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait = await message.answer("🖼️ Rasmni tahlil qilyapman...")
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        img_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}"
        img_data = requests.get(img_url).content
        b64_img = base64.b64encode(img_data).decode('utf-8')
        
        prompt = message.caption if message.caption else "Bu rasmda nima bor?"
        ans = await call_gemini(prompt, media_b64=b64_img, mime_type="image/jpeg")
        await wait.edit_text(ans)
    except Exception as e:
        await wait.edit_text(f"Xato: {e}")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    if text == "📊 Moliya Hisoboti":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='tushum'")
        jami = c.fetchone()[0] or 0
        await message.answer(f"📈 Jami: {jami:,} so'm.")
        return

    parsed = smart_parser(text)
    wait = await message.answer("⚡...")
    ans = await call_gemini(text)
    
    final = f"{ans}\n\n✅ {parsed}" if parsed else ans
    await wait.edit_text(final)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
