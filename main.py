import os
import asyncio
import requests
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- SOZLAMALAR (GitHub Secrets orqali o'qiladi) ---
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def ask_gemini(text):
    # Eng barqaror model manzili
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": f"Sen Shohruxxonning shaxsiy mentorsan. Unga o'zbekcha javob ber: {text}"}]}]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        res_json = response.json()
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        return f"Xato: {res_json.get('error', {}).get('message', 'API kalitda muammo bor')}"
    except Exception as e:
        return f"Ulanishda xato: {str(e)[:30]}"

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Mentor xavfsiz rejimda ishga tushdi! 🚀")

@dp.message()
async def handle(message: types.Message):
    wait = await message.answer("⏳...")
    ans = ask_gemini(message.text)
    try:
        await wait.edit_text(ans)
    except:
        await message.answer(ans)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
