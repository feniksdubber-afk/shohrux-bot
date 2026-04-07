import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- SOZLAMALAR ---
# Telegram bot tokeningiz (o'zgarmagan)
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
# Siz yuborgan yangi Gemini API kaliti
GEMINI_KEY = 'AIzaSyDhzbUS6xl1kUN8rUwAQ-ewpvUVsmhYpqw' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def ask_gemini(text):
    # Eng barqaror model manzili (Flash 1.5)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    prompt = (
        f"Sen Shohruxxonning mentorisan. U 18 yoshda, usta va dublyajchi. "
        f"Unga qisqa, aqlli va motivatsiya beruvchi o'zbekcha javob ber: {text}"
    )
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        res_json = response.json()
        
        # Javobni tekshirish
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        elif 'error' in res_json:
            return f"Mentor band. Sabab: {res_json['error']['message']}"
        else:
            return "Mentor: Hozircha javob bera olmayman, tizimda muammo bor."
    except Exception as e:
        return f"Ulanishda xato: {str(e)[:30]}..."

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="📊 Hisobot"), types.KeyboardButton(text="🤖 AI Mentor"))
    kb.row(types.KeyboardButton(text="📝 Vazifalar"), types.KeyboardButton(text="💰 Moliya"))
    
    await message.answer(
        "Shohrux, yangi kalit bilan Mentor qaytdi! 🚀\nSavollaringni kutaman.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message()
async def talk(message: types.Message):
    # Menyu tugmalari uchun qisqa javob
    if message.text in ["📊 Hisobot", "🤖 AI Mentor", "📝 Vazifalar", "💰 Moliya"]:
        await message.answer(f"{message.text} bo'limi ustida ishlayapman...")
        return

    # AI Mentor javobi
    status = await message.answer("⏳ Mentor o'ylamoqda...")
    ans = ask_gemini(message.text)
    
    try:
        await status.edit_text(ans)
    except:
        await message.answer(ans)

async def main():
    print("Bot yangi kalit bilan ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())