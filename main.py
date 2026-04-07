import os
import asyncio
import requests
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- SOZLAMALAR ---
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
GEMINI_KEY = 'AIzaSyDhzbUS6xl1kUN8rUwAQ-ewpvUVsmhYpqw' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Global o'zgaruvchi - ishlaydigan model nomini saqlash uchun
WORKING_MODEL = None

def find_working_model():
    """Mavjud modellardan eng mosini avtomatik topish"""
    global WORKING_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        if 'models' in response:
            # Ustuvorlik bo'yicha modellar ro'yxati
            priority = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
            
            # Google bergan modellarni tekshirish
            available_models = [m['name'] for m in response['models'] if 'generateContent' in m['supportedGenerationMethods']]
            
            for p in priority:
                full_name = f"models/{p}"
                if full_name in available_models:
                    WORKING_MODEL = full_name
                    return full_name
                # Ba'zan models/ siz ham bo'lishi mumkin
                if any(p in m for m in available_models):
                    found = [m for m in available_models if p in m][0]
                    WORKING_MODEL = found
                    return found
            
            # Hech biri o'xshama qolsa, birinchisini oladi
            if available_models:
                WORKING_MODEL = available_models[0]
                return available_models[0]
    except Exception as e:
        print(f"Model qidirishda xato: {e}")
    return "models/gemini-pro"

def ask_gemini(text):
    global WORKING_MODEL
    if not WORKING_MODEL:
        find_working_model()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{WORKING_MODEL}:generateContent?key={GEMINI_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Sen Shohruxxonning aqlli mentorsan. Javobing qisqa va o'zbekcha bo'lsin: {text}"}]}]
    }
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=20).json()
            if 'candidates' in response:
                return response['candidates'][0]['content']['parts'][0]['text']
            
            error_msg = response.get('error', {}).get('message', 'Noma`lum xato')
            if "high demand" in error_msg.lower():
                time.sleep(3)
                continue
            
            # Agar model topilmasa, qaytadan qidirib ko'radi
            if "not found" in error_msg.lower():
                find_working_model()
                return ask_gemini(text) # Qayta urinish
                
            return f"Mentor xatosi: {error_msg}"
        except:
            time.sleep(2)
            
    return "Hozir ulanib bo'lmadi, birozdan keyin urinib ko'ring."

@dp.message(Command("start"))
async def start(message: types.Message):
    find_working_model()
    await message.answer(f"Bot tayyor! Ishlayotgan model: {WORKING_MODEL}")

@dp.message()
async def handle(message: types.Message):
    wait = await message.answer("⏳...")
    ans = ask_gemini(message.text)
    try:
        await wait.edit_text(ans)
    except:
        await message.answer(ans)

async def main():
    find_working_model()
    print(f"Tanlangan model: {WORKING_MODEL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())