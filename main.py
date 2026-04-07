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
    # Eng barqaror va hozir hamma uchun ochiq model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # AI-ga shaxsiyat beramiz
    prompt = f"Sen Shohruxxon ismli 18 yoshli usta va dublyajchining aqlli mentorsan. Unga faqat o'zbekcha javob ber: {text}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    # 3 marta qayta urinish (Retry logic)
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            res_json = response.json()
            
            if 'candidates' in res_json:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            
            # Agar yuklama katta bo'lsa (High Demand)
            if 'error' in res_json and "demand" in res_json['error']['message'].lower():
                time.sleep(3) # 3 soniya kutiladi
                continue
                
            return f"Mentor hozircha javob bera olmadi. Xato: {res_json.get('error', {}).get('message', 'Noma`lum')}"
        except Exception as e:
            if attempt == 2: return f"Ulanishda muammo: {str(e)[:30]}"
            time.sleep(2)
            
    return "Mentor hozir juda band, birozdan keyin yozib ko'ring."

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Salom Shohruxxon! Mentor onlayn. Savolingizni yozing. 🚀")

@dp.message()
async def handle_msg(message: types.Message):
    # Kutish belgisi
    wait_msg = await message.answer("⏳...")
    
    # Javobni olish
    answer = ask_gemini(message.text)
    
    # Edit qilish (faqat matn o'zgarganda)
    try:
        await wait_msg.edit_text(answer)
    except:
        await message.answer(answer)

async def main():
    print("Bot 100% barqaror rejimda ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())