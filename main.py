import os
import asyncio
import requests
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- SOZLAMALAR ---
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
# AI Studio'dan olingan kalit
GEMINI_KEY = 'AIzaSyDhzbUS6xl1kUN8rUwAQ-ewpvUVsmhYpqw' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def ask_gemini(text):
    # Siz yuborgan cURL'dagi model manzili
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_KEY}"
    
    # cURL -H sarlavhalari
    headers = {
        'Content-Type': 'application/json'
    }
    
    # cURL -d ma'lumotlar strukturasi
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Sen Shohruxxonning shaxsiy mentorsan. Unga o'zbek tilida, qisqa va foydali javob ber: {text}"
                    }
                ]
            }
        ]
    }

    # 3 marta qayta urinish (agar server band bo'lsa)
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            res_json = response.json()
            
            # Agar muvaffaqiyatli bo'lsa
            if 'candidates' in res_json:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            
            # Xatolikni aniqlash
            error_info = res_json.get('error', {})
            error_message = error_info.get('message', 'Noma`lum xato')
            
            # Agar yuklama katta bo'lsa
            if "demand" in error_message.lower():
                time.sleep(3)
                continue
            
            # Agar model nomi topilmasa, zaxira modelga o'tadi
            if "not found" in error_message.lower():
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
                response = requests.post(fallback_url, json=payload, headers=headers, timeout=25)
                res_json = response.json()
                if 'candidates' in res_json:
                    return res_json['candidates'][0]['content']['parts'][0]['text']

            return f"Mentor hozircha javob bera olmadi. Sabab: {error_message}"
            
        except Exception as e:
            if attempt == 2: return f"Ulanish xatosi: {str(e)[:40]}"
            time.sleep(2)
            
    return "Mentor juda band, birozdan keyin urinib ko'ring."

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Shohrux, Mentor Bot AI Studio formatida ishga tushdi! 🚀\nSavolingizni yozing.")

@dp.message()
async def handle_message(message: types.Message):
    # "O'ylash" animatsiyasi
    status_msg = await message.answer("⏳...")
    
    # AIdan javob olish
    answer = ask_gemini(message.text)
    
    # Xabarni yangilash
    try:
        await status_msg.edit_text(answer)
    except:
        await message.answer(answer)

async def main():
    print("Bot AI Studio Quickstart rejimida ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())