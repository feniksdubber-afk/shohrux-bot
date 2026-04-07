import os
import json
import asyncio
import requests
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- SOZLAMALAR ---
# GitHub-da ochiq qoldirishingiz mumkin, lekin kimdir ko'rib qolsa kalitingizni ishlatib qo'yadi
API_TOKEN = '8746895843:AAEqE8KjRxsQi-Blv9Ef2CVvYNKgYmtDYkk'
GEMINI_KEY = 'AIzaSyBJB8sF82xBGl6hKDYalQruL77sVGgIeio' 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def ask_gemini(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt = (
        f"Sen Shohruxxonning mentorisan. U 18 yoshda, usta va dublyajchi. "
        f"Unga qattiqqo'llik bilan, o'zbek tilida javob ber: {text}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        res_json = response.json()
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Mentor band. Sabab: {res_json.get('error', {}).get('message', 'Noma`lum')}"
    except Exception as e:
        return f"Ulanishda xato: {str(e)}"

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="📊 Hisobot"), types.KeyboardButton(text="💰 Moliya"))
    kb.row(types.KeyboardButton(text="📝 Vazifalar"), types.KeyboardButton(text="🤖 AI Mentor"))
    await message.answer("GitHub-da Shohrux Mentor Bot ishga tushdi! 🔥", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message()
async def talk(message: types.Message):
    if message.text in ["📊 Hisobot", "🤖 AI Mentor"]:
        await message.answer("Seni eshityapman...")
        return
    status = await message.answer("⏳...")
    ans = ask_gemini(message.text)
    await status.edit_text(ans)

async def main():
    print("Bot GitHub-da yondi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())