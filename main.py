import os
import asyncio
import sqlite3
import re
import io
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import google.generativeai as genai
from PIL import Image

# ==========================================
# 1. SOZLAMALAR VA BAZA
# ==========================================
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Google Gemini Sozlash
genai.configure(api_key=GEMINI_KEY)

def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS finance (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, amount INTEGER, note TEXT, date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, status TEXT, date TEXT)''')
    conn.commit()
    conn.close()

# ==========================================
# 2. GEMINI AI YADROSI (404 XATOSI TUZATILGAN)
# ==========================================
async def call_gemini(prompt, image=None, context="umumiy"):
    # Eng barqaror modellarni ketma-ketlikda tekshirish
    # 404 xatosini oldini olish uchun nomlarni aniqlashtirdik
    models_to_try = ['gemini-1.5-flash-latest', 'gemini-1.5-flash', 'gemini-pro']
    
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_instruction = (
        f"Sen Shohruxxonning (18 yosh, usta va dublyajchi) shaxsiy mentorsan. Vaqt: {now_time}. "
        "O'zbek tilida qisqa, aqlli va motivatsion javob ber."
    )

    full_prompt = f"{system_instruction}\n\nKontekst: {context}\nShohruxxon: {prompt}"

    for model_name in models_to_try:
        try:
            # Modelni yuklash
            model = genai.GenerativeModel(model_name)
            
            if image:
                # Rasmli so'rov
                response = await asyncio.to_thread(model.generate_content, [full_prompt, image])
            else:
                # Matnli so'rov
                response = await asyncio.to_thread(model.generate_content, full_prompt)
            
            if response and response.text:
                return response.text
        except Exception as e:
            logging.warning(f"Model {model_name} xatosi: {e}")
            continue # Keyingi modelga o'tish
            
    return "Kechirasiz, Google AI hozirda javob bera olmayapti. API kalitni yoki internetni tekshiring."

# ==========================================
# 3. MOLIYA VA VAZIFALAR LOGIKASI
# ==========================================
def smart_parser(text):
    text_lower = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    res = None
    
    # Pul tushumi
    if any(x in text_lower for x in ["so'm", "topdim", "ishladim", "berdi"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("tushum", amount, text, now))
            res = f"💰 {amount:,} so'm daromad saqlandi."
            
    # Vazifa qo'shish
    if "reja:" in text_lower or "qilishim kerak" in text_lower:
        cursor.execute("INSERT INTO tasks (task, status, date) VALUES (?, ?, ?)", (text, "pending", now))
        res = "📝 Vazifa ro'yxatga olindi."
        
    conn.commit()
    conn.close()
    return res

# ==========================================
# 4. ESLATMALAR VA HANDLERLAR
# ==========================================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    init_db()
    await message.answer(
        "Xush kelibsiz! Tizim to'liq yangilandi va 404 xatosi tuzatildi. 🚀\n"
        "Men sizning eng aqlli yordamchingizman.",
        reply_markup=ReplyKeyboardBuilder().row(
            types.KeyboardButton(text="📊 Moliya"),
            types.KeyboardButton(text="📝 Vazifalar")
        ).as_markup(resize_keyboard=True)
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait = await message.answer("🖼️ Rasmni tahlil qilyapman...")
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        img_bytes = io.BytesIO()
        await bot.download_file(file.file_path, destination=img_bytes)
        img_bytes.seek(0)
        image = Image.open(img_bytes)
        
        prompt = message.caption if message.caption else "Bu rasmda nima bor? Usta sifatida tushuntir."
        ans = await call_gemini(prompt, image=image, context="usta")
        await wait.edit_text(ans)
    except Exception as e:
        await wait.edit_text(f"Xatolik: {e}")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    
    # 1. Tugma hisoboti
    if text == "📊 Moliya":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='tushum'")
        jami = c.fetchone()[0] or 0
        await message.answer(f"📈 Jami daromadingiz: {jami:,} so'm.")
        return

    # 2. Aqlli parser (Pul/Vazifa)
    parsed = smart_parser(text)
    
    # 3. AI bilan suhbat
    wait = await message.answer("⚡...")
    ans = await call_gemini(text)
    
    result_text = f"{ans}\n\n✅ {parsed}" if parsed else ans
    await wait.edit_text(result_text)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
