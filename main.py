import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

# --- SOZLAMALAR ---
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
GEMINI_KEY = 'AIzaSyDhzbUS6xl1kUN8rUwAQ-ewpvUVsmhYpqw' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def get_working_model():
    """Google'dan mavjud va ishlaydigan modelni aniqlash"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        if 'models' in res:
            # generateContent funksiyasini qo'llaydigan modellarni saralash
            for m in res['models']:
                if 'generateContent' in m['supportedGenerationMethods']:
                    return m['name'] # Masalan: models/gemini-1.5-flash-latest
    except:
        pass
    return "models/gemini-pro" # Zaxira varianti

def ask_gemini(text):
    model_path = get_working_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GEMINI_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Sen Shohruxxonning mentorisan: {text}"}]}]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15).json()
        if 'candidates' in response:
            return response['candidates'][0]['content']['parts'][0]['text']
        return f"Mentor band. Xato: {response.get('error', {}).get('message', 'Noma`lum')}"
    except Exception as e:
        return f"Ulanish xatosi: {str(e)[:30]}"

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Mentor bot 100% tayyor! Savolingizni yozing. 🚀")

@dp.message()
async def talk(message: types.Message):
    wait = await message.answer("⏳ Mentor o'ylamoqda...")
    answer = ask_gemini(message.text)
    await wait.edit_text(answer)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())