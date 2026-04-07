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

def ask_gemini(text):
    # Eng yangi va barqaror model nomi
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": f"Sen Shohruxxonning aqlli mentorsan. Unga qisqa va aniq o'zbekcha javob ber: {text}"}]
        }]
    }
    headers = {'Content-Type': 'application/json'}

    # 3 marta urinib ko'rish (agar band bo'lsa)
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            res_json = response.json()
            
            if 'candidates' in res_json:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            
            error_msg = res_json.get('error', {}).get('message', '')
            if "high demand" in error_msg.lower():
                time.sleep(3) # 3 soniya kutib qayta urinamiz
                continue
            
            return f"Mentor hozircha javob bera olmadi. Sabab: {error_msg}"
        except Exception as e:
            if attempt == 2: return f"Aloqa xatosi: {str(e)[:40]}"
            time.sleep(2)
            
    return "Mentor hozir juda band, birozdan keyin yozib ko'ring."

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Shohruxxon, Mentor Bot yangilandi va tayyor! 🚀")

@dp.message()
async def handle_message(message: types.Message):
    # Javob berishdan oldin "o'ylayotgan" belgisini chiqarish
    status = await message.answer("⏳...")
    
    # AI dan javob olish
    answer = ask_gemini(message.text)
    
    # "..." xabarini haqiqiy javobga aylantirish
    try:
        await status.edit_text(answer)
    except:
        await message.answer(answer)

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())