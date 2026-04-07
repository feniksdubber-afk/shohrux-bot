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

# Google Gemini Rasmiy SDK ni sozlash
genai.configure(api_key=GEMINI_KEY)
# Eng barqaror modelni tanlaymiz
model = genai.GenerativeModel('gemini-1.5-flash')

def init_db():
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS finance (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, amount INTEGER, note TEXT, date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, status TEXT, date TEXT)''')
    conn.commit()
    conn.close()

# ==========================================
# 2. GEMINI AI YADROSI (RASMIY SDK)
# ==========================================
async def call_gemini(prompt, image=None, context="umumiy"):
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_instruction = (
        f"Sen Shohruxxonning (18 yosh, Farg'onadan) Super Assistentisan. Vaqt: {now_time}. "
        "U telefon ustasi va dublyajchi. "
        "Javoblaring qisqa, do'stona, aniq va motivatsion o'zbek tilida bo'lsin. "
    )

    if context == "usta":
        system_instruction += "Foydalanuvchi hozir usta rejimida. Texnik maslahatlar ber."
    elif context == "dublyaj":
        system_instruction += "Foydalanuvchi dublyaj rejimida. Ovoz va ssenariy bo'yicha yordam ber."
    elif context == "nemis":
        system_instruction += "A2 darajadagi nemis tili o'qituvchisisan."

    full_prompt = f"Instruksiya: {system_instruction}\n\nShohruxxonning so'rovi: {prompt}"

    try:
        if image:
            # Rasm va matnni birga yuborish
            response = await asyncio.to_thread(model.generate_content, [full_prompt, image])
        else:
            # Faqat matn yuborish
            response = await asyncio.to_thread(model.generate_content, full_prompt)
            
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
            return "API limit tugagan ko'rinadi (Google). Iltimos, keyinroq urinib ko'ring."
        elif "overloaded" in error_msg.lower():
             # SDK o'zi qayta urinadi, lekin baribir o'xshamasa:
             return "Google serverlari hozir juda band. 1-2 daqiqadan keyin qayta yozing."
        return f"Gemini Tizimida xatolik yuz berdi: {error_msg[:100]}..."

# ==========================================
# 3. MANTIQ VA BAZA FUNKSIYALARI
# ==========================================
def smart_parser(text):
    text_lower = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_pro.db')
    cursor = conn.cursor()
    
    # Daromad
    if any(x in text_lower for x in ["so'm", "ming", "ishladim", "topdim", "to'ladi"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            note = text.replace(str(amount), "").strip()
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("tushum", amount, note, now))
            conn.commit()
            return f"💰 Tushum: {amount:,} so'm."
            
    # Xarajat
    if any(x in text_lower for x in ["xarajat", "sotib oldim", "ketdi", "chiqim"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("chiqim", amount, text, now))
            conn.commit()
            return f"📉 Xarajat: {amount:,} so'm."
            
    # Vazifalar
    if "reja:" in text_lower or "qilishim kerak" in text_lower:
        cursor.execute("INSERT INTO tasks (task, status, date) VALUES (?, ?, ?)", (text, "pending", now))
        conn.commit()
        return "📝 Yangi vazifa bazaga qo'shildi."
        
    conn.close()
    return None

# ==========================================
# 4. AVTOMATIK ESLATMALAR
# ==========================================
async def send_rem(chat_id, text): 
    await bot.send_message(chat_id, f"🔔 **ESLATMA!**\n\n{text}")

async def auto_reminders(chat_id, task_type):
    if task_type == "morning":
        text = "🌅 Xayrli tong, Shohruxxon! Bugun buyuk ishlar qilamiz. Rejalar qanday?"
    elif task_type == "german":
        word = await call_gemini("A2 darajasi uchun bitta yangi nemischa so'z va bitta misol yoz.", context="nemis")
        text = f"🇩🇪 **Kunlik Nemis Tili:**\n\n{word}"
    elif task_type == "spirt":
        text = "🧴 Yuzingizga spirt surtish vaqti bo'ldi!"
    await bot.send_message(chat_id, text)

# ==========================================
# 5. TELEGRAM TUGMALARI VA HANDLERLAR
# ==========================================
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="🛠️ Usta Rejimi"), types.KeyboardButton(text="🎙️ Dublyaj Rejimi"))
    kb.row(types.KeyboardButton(text="📊 Moliya Hisoboti"), types.KeyboardButton(text="📝 Vazifalar"))
    return kb.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def start_bot(message: types.Message):
    init_db()
    cid = message.chat.id
    scheduler.add_job(auto_reminders, 'cron', hour=8, minute=0, args=[cid, "morning"], id=f"m_{cid}", replace_existing=True)
    scheduler.add_job(auto_reminders, 'cron', hour=9, minute=30, args=[cid, "german"], id=f"g_{cid}", replace_existing=True)
    scheduler.add_job(auto_reminders, 'cron', hour=22, minute=30, args=[cid, "spirt"], id=f"s_{cid}", replace_existing=True)
    
    await message.answer("Tizim Rasmiy Gemini SDK orqali ishga tushdi! 🚀\nEndi qotishlar minimal bo'ladi.", reply_markup=main_menu())

# MULTIMEDIA: Rasm tahlili (Pillow yordamida)
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait = await message.answer("🔍 Rasmni o'rganyapman (Gemini Vision)...")
    try:
        # Rasmni xotiraga yuklash
        file = await bot.get_file(message.photo[-1].file_id)
        img_bytes = io.BytesIO()
        await bot.download_file(file.file_path, destination=img_bytes)
        img_bytes.seek(0)
        
        # PIL formatiga o'tkazish (Google kutubxonasi shuni so'raydi)
        image = Image.open(img_bytes)
        
        prompt = message.caption if message.caption else "Bu rasmda nima bor? Usta sifatida tahlil qilib ber."
        ans = await call_gemini(prompt, image=image, context="usta")
        await wait.edit_text(f"📱 **Tahlil Natijasi:**\n\n{ans}")
    except Exception as e:
        await wait.edit_text(f"Rasm tahlilida xatolik: {e}")

# MULTIMEDIA: Ovoz (Hozircha faqat matnli maslahat)
@dp.message(F.voice)
async def handle_voice(message: types.Voice):
    # Gemini bepul SDK si Telegramning ogg formatini to'g'ridan-to'g'ri tushunishda injiqlik qiladi.
    # To'liq ovoz tahlili uchun qo'shimcha FFmpeg o'rnatish kerak, bu GitHub Actions'ni og'irlashtiradi.
    await message.answer("🎤 Ovozli xabarlar hozircha faqat OpenAI (pullik) orqali to'liq ishlaydi. Iltimos matn yozing yoki rasm yuboring.")

@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    chat_id = message.chat.id
    
    if text == "📊 Moliya Hisoboti":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='tushum'")
        tushum = c.fetchone()[0] or 0
        c.execute("SELECT SUM(amount) FROM finance WHERE type='chiqim'")
        chiqim = c.fetchone()[0] or 0
        foyda = tushum - chiqim
        await message.answer(f"📈 **Moliya:**\n🟩 Daromad: {tushum:,}\n🟥 Xarajat: {chiqim:,}\n💵 **Foyda: {foyda:,} so'm**")
        return
        
    elif text == "📝 Vazifalar":
        conn = sqlite3.connect('shohrux_pro.db')
        c = conn.cursor()
        c.execute("SELECT task FROM tasks WHERE status='pending' LIMIT 5")
        tasks = c.fetchall()
        res = "📋 **Qilinishi kerak bo'lgan ishlar:**\n" + "\n".join([f"🔘 {t[0]}" for t in tasks]) if tasks else "Hozircha vazifalar yo'q."
        await message.answer(res)
        return
        
    elif text in ["🛠️ Usta Rejimi", "🎙️ Dublyaj Rejimi"]:
        await message.answer(f"{text} yoqildi. Savolingizni yozing.")
        return

    # Taymer
    timer_match = re.search(r'(\d+)\s+(daqiqadan|soatdan)\s+keyin\s+(eslat|eslatib qo\'y)\s*(.*)', text.lower())
    if timer_match:
        val = int(timer_match.group(1))
        unit = timer_match.group(2)
        note = timer_match.group(4) if timer_match.group(4) else "Reja!"
        
        delta = timedelta(minutes=val) if unit == "daqiqadan" else timedelta(hours=val)
        scheduler.add_job(send_rem, 'date', run_time=datetime.now() + delta, args=[chat_id, note])
        await message.answer(f"⏳ {val} {unit} keyin eslataman.")
        return

    # Asosiy AI So'rov
    save_msg = smart_parser(text)
    wait = await message.answer("⚡ Gemini o'ylamoqda...")
    ai_ans = await call_gemini(text)
    
    if save_msg:
        await wait.edit_text(f"{ai_ans}\n\n✅ {save_msg}")
    else:
        await wait.edit_text(ai_ans)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    scheduler.start()
    print("Rasmiy Gemini SDK bilan Shohrux OS ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
