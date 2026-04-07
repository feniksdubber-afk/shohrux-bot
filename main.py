import os
import asyncio
import requests
import time
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- SOZLAMALAR ---
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
GEMINI_KEY = 'AIzaSyDhzbUS6xl1kUN8rUwAQ-ewpvUVsmhYpqw' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH (SQLITE) ---
def init_db():
    conn = sqlite3.connect('mentor_xotira.db')
    cursor = conn.cursor()
    # Moliya va vazifalar uchun jadval
    cursor.execute('''CREATE TABLE IF NOT EXISTS xotira 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       turi TEXT, 
                       matn TEXT, 
                       sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_to_db(turi, matn):
    conn = sqlite3.connect('mentor_xotira.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO xotira (turi, matn) VALUES (?, ?)", (turi, matn))
    conn.commit()
    conn.close()

# --- GEMINI 2.5 FLASH VA BOSHQALAR ---
def ask_gemini(text):
    # Gemini 2.5 Flash-preview - bu eng yangi versiya
    models = [
        "gemini-2.5-flash-preview-09-2025", # Siz so'ragan eng yangi model
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-pro"
    ]
    
    headers = {'Content-Type': 'application/json'}
    # Mentoringizni aqlli qilish uchun yo'riqnoma
    system_instruction = (
        "Sen Shohruxxonning aqlli mentorsan. U 18 yoshda, usta va dublyajchi. "
        "Unga faqat o'zbekcha, do'stona va professional javob ber. "
        "Agar u pul yoki ish haqida yozsa, 'Buni xotiramga yozib qo'ydim' deb ayt."
    )
    
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            res_json = response.json()
            if 'candidates' in res_json:
                javob = res_json['candidates'][0]['content']['parts'][0]['text']
                # Agar gap moliya yoki ish haqida bo'lsa, bazaga saqlash
                if any(word in text.lower() for word in ["pul", "so'm", "remont", "dublyaj", "tuzatdim"]):
                    save_to_db("ish_moliya", text)
                return javob
        except:
            continue
            
    return "Mentor hozircha band, birozdan keyin urinib ko'ring."

# --- BOT BUYRUQLARI ---
@dp.message(Command("start"))
async def start(message: types.Message):
    init_db()
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="📊 Kunlik Hisobot"), types.KeyboardButton(text="📝 Vazifalar"))
    kb.row(types.KeyboardButton(text="🤖 Mentor bilan suhbat"))
    
    await message.answer(
        "Salom Shohrux! Gemini 2.5 Flash Mentor ishga tushdi. 🚀\n"
        "Men endi sening remontlaring va dublyaj ishlaringni eslab qola olaman.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message()
async def handle_all(message: types.Message):
    if message.text == "📊 Kunlik Hisobot":
        conn = sqlite3.connect('mentor_xotira.db')
        cursor = conn.cursor()
        cursor.execute("SELECT matn FROM xotira ORDER BY sana DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            hisobot = "\n".join([f"- {r[0]}" for r in rows])
            await message.answer(f"Oxirgi qaydlaring:\n{hisobot}")
        else:
            await message.answer("Hozircha hech qanday qayd yo'q.")
        return

    # O'ylash effekti
    wait = await message.answer("⏳...")
    answer = ask_gemini(message.text)
    
    try:
        await wait.edit_text(answer)
    except:
        await message.answer(answer)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())