import os
import asyncio
import requests
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- XAVFSIZLIK ---
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def ask_gemini(text):
    # Tekshiriladigan modellar ro'yxati (ustuvorlik tartibida)
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"Sen Shohruxxonning aqlli mentorsan. Unga o'zbekcha javob ber: {text}"}]
        }]
    }

    # Har bir modelni birma-bir tekshirib ko'ramiz
    for model_name in models_to_try:
        # Ikkala variantda ham sinab ko'ramiz: prefiks bilan va prefiksiz
        for url_pattern in [f"models/{model_name}", model_name]:
            url = f"https://generativelanguage.googleapis.com/v1beta/{url_pattern}:generateContent?key={GEMINI_KEY}"
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                res_json = response.json()
                
                if 'candidates' in res_json:
                    return res_json['candidates'][0]['content']['parts'][0]['text']
                
                # Agar aynan shu model topilmasa, keyingisiga o'tamiz
                error_msg = res_json.get('error', {}).get('message', '')
                if "not found" in error_msg.lower() or "not supported" in error_msg.lower():
                    continue
                
                # Agar band bo'lsa, 2 soniya kutib keyingi modelga o'tamiz
                if "demand" in error_msg.lower():
                    time.sleep(2)
                    continue

            except Exception:
                continue
                
    return "Mentor hozircha barcha modellar bilan bog'lana olmadi. API kalit yoki internet aloqasini tekshiring."

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Shohruxxon, Mentor Bot universal rejimda ishga tushdi! 🚀")

@dp.message()
async def handle_msg(message: types.Message):
    wait_msg = await message.answer("⏳...")
    answer = ask_gemini(message.text)
    try:
        await wait_msg.edit_text(answer)
    except:
        await message.answer(answer)

async def main():
    print("Bot polling boshladi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
