import os
import asyncio
import requests
import sqlite3
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- XAVFSIZLIK (GitHub Secrets orqali) ---
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('shohrux_mentor.db')
    cursor = conn.cursor()
    # Jadvalda turi, matn va topilgan pul miqdori saqlanadi
    cursor.execute('''CREATE TABLE IF NOT EXISTS kundalik 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       turi TEXT, 
                       matn TEXT, 
                       pul INTEGER,
                       sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def parse_and_save(text):
    """Matndan pul miqdorini ajratish va bazaga yozish"""
    # Raqamlarni qidirish (masalan: 500 000 yoki 500000)
    numbers = re.findall(r'\d+', text.replace(" ", ""))
    pul_miqdori = int(numbers[0]) if numbers else 0
    
    turi = "umumiy"
    text_low = text.lower()
    if any(x in text_low for x in ["tuzatdim", "remont", "ekran", "usta", "almashtirdim"]):
        turi = "remont"
    elif any(x in text_low for x in ["dublyaj", "ovoz", "mikrofon", "rol"]):
        turi = "dublyaj"
    elif any(x in text_low for x in ["sotib oldim", "xarajat", "bozorda", "chiqim"]):
        turi = "chiqim"

    conn = sqlite3.connect('shohrux_mentor.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO kundalik (turi, matn, pul) VALUES (?, ?, ?)", (turi, text, pul_miqdori))
    conn.commit()
    conn.close()
    return turi, pul_miqdori

# --- BEPUL AI BILAN ALOQA ---
def ask_ai(text):
    # Gemini 1.5 Flash - Eng yaxshi bepul variant
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (
        "Sen Shohruxxonning aqlli va do'stona mentorsan. U 18 yoshda, usta va dublyajchi. "
        "U senga qilgan ishlari haqida yozadi. Unga motivatsiya beruvchi, o'zbekcha va qisqa javob ber. "
        f"Foydalanuvchi xabari: {text}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=20).json()
        if 'candidates' in response:
            ai_javob = response['candidates'][0]['content']['parts'][0]['text']
            
            # Agar pul yoki ish haqida gap ketsa, bazaga saqlash
            keywords = ["so'm", "ming", "tuzatdim", "dublyaj", "ish", "remont", "ekran"]
            if any(k in text.lower() for k in keywords):
                turi, miqdor = parse_and_save(text)
                return f"{ai_javob}\n\n✅ [Xotira: {turi.upper()} - {miqdor:,} so'm saqlandi]"
            
            return ai_javob
    except Exception as e:
        return f"Mentor biroz charchadi. (Xato: {str(e)[:30]})"
    return "Xato yuz berdi, lekin ma'lumot saqlangan bo'lishi mumkin."

# --- KOMANDALAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    init_db()
    await message.answer("Salom Shohruxxon! 🚀\nMen sizning aqlli mentoringizman. "
                         "Nima ishlar qildingiz? Yozing, hammasini hisoblab boraman.\n\n"
                         "Hisobot ko'rish: /hisobot")

@dp.message(Command("hisobot"))
async def cmd_report(message: types.Message):
    conn = sqlite3.connect('shohrux_mentor.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, turi, matn, pul, sana FROM kundalik ORDER BY sana DESC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("Hozircha bazada qaydlar yo'q.")
        return
        
    text = "📊 **Oxirgi 5 ta qayd:**\n\n"
    for r in rows:
        text += f"📅 {r[4][5:16]} | **{r[1].upper()}**\n└ {r[2]} ({r[3]:,} so'm)\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message()
async def handle_msg(message: types.Message):
    # Conflict xatosini yashirish uchun
    try:
        status = await message.answer("⏳...")
        ans = ask_ai(message.text)
        await status.edit_text(ans)
    except:
        await message.answer(ask_ai(message.text))

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    print("Bot 100% bepul va aqlli rejimda boshlandi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
