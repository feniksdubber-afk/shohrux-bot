import os
import asyncio
import requests
import sqlite3
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- SOZLAMALAR (GitHub Secrets) ---
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('shohrux_mentor.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS kundalik 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       turi TEXT, matn TEXT, pul INTEGER,
                       sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def parse_and_save(text):
    numbers = re.findall(r'\d+', text.replace(" ", ""))
    pul_miqdori = int(numbers[0]) if numbers else 0
    turi = "umumiy"
    text_low = text.lower()
    if any(x in text_low for x in ["tuzatdim", "remont", "ekran", "usta"]): turi = "remont"
    elif any(x in text_low for x in ["dublyaj", "ovoz", "mikrofon"]): turi = "dublyaj"
    
    conn = sqlite3.connect('shohrux_mentor.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO kundalik (turi, matn, pul) VALUES (?, ?, ?)", (turi, text, pul_miqdori))
    conn.commit()
    conn.close()
    return turi, pul_miqdori

# --- GEMINI 2.5 FLASH BILAN ALOQA ---
def ask_gemini(text):
    # Rasmingizda ko'ringan aynan o'sha model nomi
    # Agar 2.5 ishlamasa, avtomatik 1.5 ga o'tish mantiqi qo'shildi
    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        payload = {
            "contents": [{"parts": [{"text": f"Sen Shohruxxonning mentorsan. O'zbekcha javob ber: {text}"}]}]
        }
        try:
            response = requests.post(url, json=payload, timeout=20)
            res_data = response.json()
            if 'candidates' in res_data:
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except:
            continue
    return "Mentor hozircha javob bera olmadi. API kalitni tekshiring."

# --- MENU TUGMALARI ---
def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="📊 Kunlik Hisobot"), types.KeyboardButton(text="📝 Vazifalar"))
    builder.row(types.KeyboardButton(text="🤖 Mentor bilan suhbat"))
    return builder.as_markup(resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    init_db()
    await message.answer("Salom Shohruxxon! 🚀\nMentor Gemini 2.5 Flash ishga tushdi.", reply_markup=main_menu())

@dp.message()
async def handle_all(message: types.Message):
    if message.text == "📊 Kunlik Hisobot":
        conn = sqlite3.connect('shohrux_mentor.db')
        cursor = conn.cursor()
        cursor.execute("SELECT matn, sana FROM kundalik ORDER BY sana DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        res = "📊 Oxirgi qaydlar:\n" + "\n".join([f"- {r[0]}" for r in rows]) if rows else "Hali ma'lumot yo'q."
        await message.answer(res)
        return

    # AI tahlil va saqlash
    keywords = ["so'm", "ming", "tuzatdim", "remont", "dublyaj"]
    if any(k in message.text.lower() for k in keywords):
        turi, miqdor = parse_and_save(message.text)
        extra = f"\n\n✅ [{turi.upper()} saqlandi: {miqdor:,} so'm]"
    else:
        extra = ""

    wait = await message.answer("⏳...")
    answer = ask_gemini(message.text)
    await wait.edit_text(answer + extra)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
