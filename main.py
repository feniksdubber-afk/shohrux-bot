import os
import asyncio
import requests
import sqlite3
import re
import base64
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==========================================
# 1. SOZLAMALAR VA BAZA (SHOHRUX OS)
# ==========================================
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

def init_db():
    conn = sqlite3.connect('shohrux_the_best.db')
    cursor = conn.cursor()
    # Moliya (Tushum, Chiqim, Qarz)
    cursor.execute('''CREATE TABLE IF NOT EXISTS finance 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       type TEXT, amount INTEGER, note TEXT, date TEXT)''')
    # Vazifalar va Eslatmalar
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       task TEXT, status TEXT, date TEXT)''')
    # Mijozlar (Ustachilik uchun)
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT, phone_model TEXT, issue TEXT, price INTEGER)''')
    # Dublyaj proyektlari
    cursor.execute('''CREATE TABLE IF NOT EXISTS dubbing 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       project_name TEXT, status TEXT)''')
    conn.commit()
    conn.close()

# ==========================================
# ==========================================
# 2. SUPER AI YADROSI (XATOLARGA CHIDAMLI)
# ==========================================
async def call_gemini(prompt, media_b64=None, mime_type=None, context_type="umumiy"):
    # Boya ishlagan Gemini 2.5 Flash modelini qidiramiz
    models_to_try = [
        "gemini-2.5-flash", 
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-pro"
    ]
    
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_instruction = (
        f"Sen Shohruxxonning (18 yosh, Farg'onadan) Super Assistentisan. Hozirgi vaqt: {now_time}. "
        "U usta (telefon platasi, ekran almashtirish) va 'Uzdubgo' jamoasida dublyajchi. "
        "Javoblaring qisqa, aniq va motivatsion o'zbek tilida bo'lsin."
    )

    if context_type == "usta":
        system_instruction += " Usta rejimidasan. Tahlil qil."
    elif context_type == "dublyaj":
        system_instruction += " Dublyaj rejimidasan."
    elif context_type == "nemis":
        system_instruction += " Nemis tili (A2) o'qituvchisisan."

    parts = [{"text": f"{system_instruction}\n\nFoydalanuvchi: {prompt}"}]
    if media_b64:
        parts.append({"inlineData": {"mimeType": mime_type, "data": media_b64}})

    payload = {"contents": [{"parts": parts}]}
    
    # Har bir modelni tekshirib ko'rish
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        try:
            resp = requests.post(url, json=payload, timeout=20)
            res_json = resp.json()
            
            if resp.status_code == 200 and 'candidates' in res_json:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            
            # Agar xato bo'lsa, xato matnini logga yozamiz (terminalda ko'rinadi)
            error_msg = res_json.get('error', {}).get('message', 'Noma`lum API xatosi')
            logging.warning(f"Model {model} xatosi: {error_msg}")
            
        except Exception as e:
            logging.error(f"Ulanish xatosi ({model}): {e}")
            continue
            
    # Agar hamma modellar xato bersa, aniq sababni chiqarish
    return "Miyaga ulanib bo'lmadi (Gemini API). Kalitni yoki ulanishni tekshiring."
# ==========================================
# 3. MANTIQ VA BAZA FUNKSIYALARI
# ==========================================
def smart_parser(text):
    """Matnni aqlli tahlil qilib, kerakli bazaga joylaydi"""
    text_lower = text.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('shohrux_the_best.db')
    cursor = conn.cursor()
    
    # 1. Moliya tahlili (Daromad)
    if any(x in text_lower for x in ["so'm", "ming", "ishladim", "topdim", "to'ladi"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            note = text.replace(str(amount), "").strip()
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("tushum", amount, note, now))
            conn.commit()
            return f"💰 Tushum saqlandi: {amount:,} so'm.\nIzoh: {note[:20]}..."
            
    # 2. Xarajat tahlili
    if any(x in text_lower for x in ["xarajat", "sotib oldim", "ketdi", "chiqim"]):
        nums = re.findall(r'\d+', text.replace(" ", ""))
        if nums:
            amount = int(nums[0])
            cursor.execute("INSERT INTO finance (type, amount, note, date) VALUES (?, ?, ?, ?)", ("chiqim", amount, text, now))
            conn.commit()
            return f"📉 Xarajat saqlandi: {amount:,} so'm."
            
    # 3. Vazifa / Reja
    if "reja" in text_lower or "qilishim kerak" in text_lower or "vazifa" in text_lower:
        cursor.execute("INSERT INTO tasks (task, status, date) VALUES (?, ?, ?)", (text, "pending", now))
        conn.commit()
        return "📝 Yangi vazifa ro'yxatga qo'shildi."
        
    conn.close()
    return None

# ==========================================
# 4. AVTOMATIK ESLATMALAR (KUN TARTIBI)
# ==========================================
async def auto_reminders(chat_id, task_type):
    if task_type == "morning":
        text = "🌅 **Xayrli tong, Shohruxxon!**\nBugun buyuk ishlar qilamiz! Kunlik rejalaringizni yozib qoldiring."
    elif task_type == "german":
        word = await call_gemini("A2 darajasi uchun bitta yangi nemischa so'z, o'zbekcha tarjimasi va bitta misol gap yoz.", context_type="nemis")
        text = f"🇩🇪 **Kunlik Nemis Tili:**\n\n{word}"
    elif task_type == "spirt":
        text = "🧴 **Salomatlik:** Yuzingizga (ugrilarga) spirt surtish vaqti bo'ldi!"
    elif task_type == "cats":
        text = "🐈 **Mushuklar:** Mushuklaringizga ovqat berishni unutmang!"
    
    await bot.send_message(chat_id, text)

# ==========================================
# 5. TELEGRAM INTERFEYSI (TUGMALAR)
# ==========================================
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="🛠️ Usta Rejimi"), types.KeyboardButton(text="🎙️ Dublyaj Rejimi"))
    kb.row(types.KeyboardButton(text="📊 Moliya Hisoboti"), types.KeyboardButton(text="📝 Vazifalar"))
    kb.row(types.KeyboardButton(text="🇩🇪 Nemis Tili"), types.KeyboardButton(text="💡 AI Maslahat"))
    return kb.as_markup(resize_keyboard=True)

# ==========================================
# 6. HANDLERLAR (BOT QULOQLARI)
# ==========================================
@dp.message(Command("start"))
async def start_bot(message: types.Message):
    init_db()
    # Kunlik avtomatik eslatmalarni sozlash (Sizning Telegram ID'ingiz bo'yicha)
    cid = message.chat.id
    scheduler.add_job(auto_reminders, 'cron', hour=8, minute=0, args=[cid, "morning"], id=f"m_{cid}", replace_existing=True)
    scheduler.add_job(auto_reminders, 'cron', hour=9, minute=30, args=[cid, "german"], id=f"g_{cid}", replace_existing=True)
    scheduler.add_job(auto_reminders, 'cron', hour=19, minute=0, args=[cid, "cats"], id=f"c_{cid}", replace_existing=True)
    scheduler.add_job(auto_reminders, 'cron', hour=22, minute=30, args=[cid, "spirt"], id=f"s_{cid}", replace_existing=True)
    
    await message.answer("Tizim ishga tushirildi. Shohrux OS v3.0 🚀\nMen sizning eng aqlli yordamchingizman.", reply_markup=main_menu())

# MULTIMEDIA: Rasm
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    wait = await message.answer("🔍 Rasmni skaner qilyapman (AI Vision)...")
    file = await bot.get_file(message.photo[-1].file_id)
    img_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    b64_img = base64.b64encode(img_data).decode('utf-8')
    
    prompt = message.caption if message.caption else "Bu qanday qurilma yoki plata? Usta ko'zi bilan tahlil qil va maslahat ber."
    ans = await call_gemini(prompt, media_b64=b64_img, mime_type="image/jpeg", context_type="usta")
    await wait.edit_text(f"📱 **Tahlil Natijasi:**\n\n{ans}")

# MULTIMEDIA: Ovoz
@dp.message(F.voice)
async def handle_voice(message: types.Voice):
    wait = await message.answer("🎧 Ovozni stenogramma qilyapman...")
    file = await bot.get_file(message.voice.file_id)
    voice_data = requests.get(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}").content
    b64_voice = base64.b64encode(voice_data).decode('utf-8')
    
    prompt = "Ovozli xabarni so'zma-so'z matnga o'gir (transkripsiya qil). Keyin qisqacha xulosasini yoz."
    ans = await call_gemini(prompt, media_b64=b64_voice, mime_type="audio/ogg")
    
    # Ovoz ichida ham pul bo'lsa saqlaymiz
    saved_info = smart_parser(ans)
    extra = f"\n\n*(Tizim: {saved_info})*" if saved_info else ""
    
    await wait.edit_text(f"🎙 **Ovozdan Matnga:**\n\n{ans}{extra}")

# TUGMALAR VA MATN
@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    chat_id = message.chat.id
    
    # TUGMALAR REAKSIYASI
    if text == "📊 Moliya Hisoboti":
        conn = sqlite3.connect('shohrux_the_best.db')
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM finance WHERE type='tushum'")
        tushum = c.fetchone()[0] or 0
        c.execute("SELECT SUM(amount) FROM finance WHERE type='chiqim'")
        chiqim = c.fetchone()[0] or 0
        foyda = tushum - chiqim
        await message.answer(f"📈 **Sizning Moliyaviy Holatingiz:**\n\n🟩 Jami daromad: {tushum:,} so'm\n🟥 Jami xarajat: {chiqim:,} so'm\n\n💵 **Sof foyda: {foyda:,} so'm**")
        return
        
    elif text == "📝 Vazifalar":
        conn = sqlite3.connect('shohrux_the_best.db')
        c = conn.cursor()
        c.execute("SELECT task FROM tasks WHERE status='pending' LIMIT 5")
        tasks = c.fetchall()
        res = "📋 **Qilinishi kerak bo'lgan ishlar:**\n\n" + "\n".join([f"🔘 {t[0]}" for t in tasks]) if tasks else "Hozircha vazifalar yo'q. Dam oling! ☕"
        await message.answer(res)
        return
        
    elif text == "🛠️ Usta Rejimi":
        await message.answer("Siz 'Usta Rejimi'dasiz. Menga telefon modeli, muammosi yoki platasi haqida yozing, men yechim topaman.")
        return
    elif text == "🎙️ Dublyaj Rejimi":
        await message.answer("Siz 'Dublyaj Rejimi'dasiz. Menga matn yuboring, men unga qanday his-tuyg'u bilan ovoz berish kerakligini tahlil qilib beraman.")
        return
    elif text == "🇩🇪 Nemis Tili":
        word = await call_gemini("Menga A2 darajasida qisqacha dialog yoki grammatika qoidasini tushuntir.", context_type="nemis")
        await message.answer(word)
        return

    # VAQT BЕLGILASH (Masalan: 15 daqiqadan keyin eslat nemis tili)
    timer_match = re.search(r'(\d+)\s+(daqiqadan|soatdan)\s+keyin\s+(eslat|eslatib qo\'y|eslatarsan)\s*(.*)', text.lower())
    if timer_match:
        val = int(timer_match.group(1))
        unit = timer_match.group(2)
        note = timer_match.group(4) if timer_match.group(4) else "Rejalashtirilgan ish!"
        
        delta = timedelta(minutes=val) if unit == "daqiqadan" else timedelta(hours=val)
        run_time = datetime.now() + delta
        
        async def send_rem(cid, txt): await bot.send_message(cid, f"🔔 **ESLATMA VAQTI KELDI!**\n\nShohruxxon, siz buni so'ragandingiz:\n👉 {txt}")
        scheduler.add_job(send_rem, 'date', run_time=run_time, args=[chat_id, note])
        await message.answer(f"⏳ Zo'r! {val} {unit} keyin sizni bezovta qilaman: '{note}'")
        return

    # ODDIY MATNNI TAHLIL QILISH (Aqlli yozish)
    save_msg = smart_parser(text)
    if save_msg:
        ai_ans = await call_gemini(f"Foydalanuvchi quyidagi ishni qildi: '{text}'. Unga qisqa motivatsiya ber.")
        await message.answer(f"{ai_ans}\n\n{save_msg}")
        return

    # UMUMIY AI SUHBAT
    wait = await message.answer("⚡ Tahlil qilyapman...")
    ai_ans = await call_gemini(text)
    await wait.edit_text(ai_ans)

# ==========================================
# MAIN LOOP
# ==========================================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    init_db()
    scheduler.start()
    print("Shohrux OS The Best ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
