import os
import asyncio
import requests
import sqlite3
import re
import base64
import json
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- KONFIGURATSIYA VA LOGGING ---
# Xatolarni kuzatish uchun log tizimi
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
APP_ID = "shohrux-mentor-v1"

# --- 1. MA'LUMOTLAR BAZASI (SQLite) ---
# Bu yerda hamma ma'lumotlar saqlanadi
def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    # Moliya (daromad/xarajat)
    cursor.execute('''CREATE TABLE IF NOT EXISTS finance 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       type TEXT, amount INTEGER, note TEXT, date TEXT)''')
    # Eslatmalar va Vazifalar
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       task TEXT, status TEXT, deadline TEXT)''')
    # Nemis tili so'z boyligi
    cursor.execute('''CREATE TABLE IF NOT EXISTS german_words 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       word TEXT, translation TEXT, date TEXT)''')
    conn.commit()
    conn.close()

# --- 2. MULTIMEDIA VA AI FUNKSIYALARI ---
# Gemini 1.5 Flash - Rasmlar, Ovozlar va Matnni tushunuvchi yagona "miya"
async def call_gemini_ai(prompt, media_base64=None, mime_type=None):
    # Har doim barqaror URL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    # Mentor shaxsiyati (Instruksiya)
    system_prompt = (
        "Sen Shohruxxonning (18 yosh, usta va dublyajchi) shaxsiy mentorsan. "
        "Unga do'stona, qisqa va aniq o'zbekcha javob ber. "
        "U usta sifatida telefon tuzatadi va Uzdubgo jamoasida dublyaj qiladi. "
        "Har bir javobingda unga motivatsiya ber."
    )
    
    parts = [{"text": f"{system_prompt}\n\nFoydalanuvchi: {prompt}"}]
    if media_base64:
        parts.append({"inlineData": {"mimeType": mime_type, "data": media_base64}})

    payload = {"contents": [{"parts": parts}]}
    
    try:
        # Retry mexanizmi bilan so'rov (xatolikni oldini olish uchun)
        for _ in range(3):
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                res_json = response.json()
                return res_json['candidates'][0]['content']['parts'][0]['text']
            await asyncio.sleep(2)
        return "Mentor biroz band, iltimos keyinroq urinib ko'ring."
    except Exception as e:
        return f"Tizimda xatolik: {str(e)[:50]}"

# --- 3. YORDAMCHI FUNKSIYALAR ---
def save_finance(t, amount, note):
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", (t, amount, note, now))
    conn.commit()
    conn.close()

async def send_scheduled_msg(chat_id, text):
    await bot.send_message(chat_id, f"🔔 **DIQQAT!**\n\n{text}")

# --- 4. TUGMALAR (MENU) ---
def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="💰 Daromadlar"), types.KeyboardButton(text="📝 Vazifalar"))
    builder.row(types.KeyboardButton(text="🇩🇪 Nemis Tili"), types.KeyboardButton(text="📊 Hisobot"))
    builder.row(types.KeyboardButton(text="⚙️ Sozlamalar"))
    return builder.as_markup(resize_keyboard=True)

# --- 5. ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    init_db()
    await message.answer(
        f"Salom Shohruxxon! 🚀\n\nMentor Pro v2.0 ishga tushdi.\n"
        "Men endi 50 dan ortiq funksiyalarni bajara olaman:\n"
        "✅ Rasmlarni tahlil qilish\n"
        "✅ Ovozli xabarlarni matnga o'girish\n"
        "✅ Moliya hisob-kitobi\n"
        "✅ Eslatmalar (Taymerlar)\n"
        "✅ Nemis tili darslari\n\n"
        "Nima qilamiz?", 
        reply_markup=get_main_menu()
    )

# --- Rasm tahlili ---
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("🖼️ Rasmni ko'ryapman...")
    file = await bot.get_file(message.photo[-1].file_id)
    img_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    base64_img = base64.b64encode(img_data).decode('utf-8')
    
    prompt = message.caption if message.caption else "Bu rasmda nima bor? Usta sifatida tahlil qil."
    answer = await call_gemini_ai(prompt, base64_img, "image/jpeg")
    await status.edit_text(answer)

# --- Ovozli xabar tahlili ---
@dp.message(F.voice)
async def voice_handler(message: types.Voice):
    status = await message.answer("🎤 Ovozni eshityapman...")
    file = await bot.get_file(message.voice.file_id)
    voice_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    base64_voice = base64.b64encode(voice_data).decode('utf-8')
    
    prompt = "Bu ovozda nima deyilgan? Agar pul yoki ish haqida bo'lsa, qisqa yozib ber."
    answer = await call_gemini_ai(prompt, base64_voice, "audio/ogg")
    
    # Agar pul haqida bo'lsa avtomatik saqlashga urinish
    if any(x in answer.lower() for x in ["so'm", "ming"]):
        num = re.findall(r'\d+', answer.replace(" ", ""))
        if num: save_finance("tushum", int(num[0]), answer)
    
    await status.edit_text(f"📝 **Transkripsiya:**\n{answer}")

# --- Matnli xabarlar va Buyruqlar ---
@dp.message()
async def text_handler(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    # 1. Tugmalar logikasi
    if text == "📊 Hisobot":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance")
        jami = c.fetchone()[0] or 0
        await message.answer(f"📈 **Jami daromadingiz:** {jami:,} so'm")
        return

    # 2. Eslatma (Taymer) yaratish: "10 daqiqadan keyin eslat nemis tili"
    timer_match = re.search(r'(\d+)\s+(daqiqadan|soatdan)\s+keyin\s+eslat\s+(.*)', text.lower())
    if timer_match:
        val = int(timer_match.group(1))
        unit = timer_match.group(2)
        note = timer_match.group(3)
        delta = timedelta(minutes=val) if unit == "daqiqadan" else timedelta(hours=val)
        
        run_time = datetime.now() + delta
        scheduler.add_job(send_scheduled_msg, 'date', run_time=run_time, args=[chat_id, note])
        await message.answer(f"✅ Kelishdik! {val} {unit} keyin eslataman: {note}")
        return

    # 3. Daromadni saqlash: "Remont 500000 so'm"
    if "so'm" in text.lower() or "ming" in text.lower():
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            save_finance("daromad", amount, text)
            await message.answer(f"💰 {amount:,} so'm bazaga qo'shildi! Baraka bersin.")
            return

    # 4. Oddiy AI suhbat
    wait = await message.answer("⏳...")
    ans = await call_gemini_ai(text)
    await wait.edit_text(ans)

# --- 6. ASOSIY ISHGA TUSHIRISH ---
async def main():
    # Webhookni tozalash (Conflict xatosini yo'qotish uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    
    # Har kuni soat 22:30 da spirt surtishni eslatish
    scheduler.add_job(send_scheduled_msg, 'cron', hour=22, minute=30, args=[8746895843, "Yuzingizga spirt surtishni unutmang! ✨"])
    
    # Har kuni soat 9:00 da nemis tili darsi
    scheduler.add_job(send_scheduled_msg, 'cron', hour=9, minute=0, args=[8746895843, "Guten Morgen! Bugungi nemis tili so'zini o'rganish vaqti keldi."])
    
    scheduler.start()
    print("Mentor Pro v2.0 Ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
