import telebot
import os

# ضع المفتاح (Token) الذي أخذته من BotFather هنا
TOKEN = "8725258748:AAESMUsA1_OTEcqrOo0E7iii1SQwXQAwu9Y"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك مهندس سامي! الروبوت جاهز للعمل.\nأرسل لي ملف المخطط بصيغة (.dxf) لنبدأ.")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    # 1. حفظ رقم الشات (Chat ID) لكي نرسل لك النتائج عليه لاحقاً
    chat_id = message.chat.id
    with open("chat_id.txt", "w") as f:
        f.write(str(chat_id))

    # 2. التأكد من أن الملف هو مخطط كاد
    file_name = message.document.file_name
    if not file_name.endswith('.dxf'):
        bot.reply_to(message, "❌ خطأ: الرجاء إرسال ملف بصيغة DXF فقط.")
        return

    # 3. تحميل الملف وتسميته site_plan.dxf
    bot.reply_to(message, "⏳ جاري استلام المخطط...")
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("site_plan.dxf", 'wb') as new_file:
        new_file.write(downloaded_file)

    # 4. تشغيل كود المترجم (cad_to_json) فوراً
    bot.send_message(chat_id, "✅ تم الحفظ! يتم الآن استخراج المسار والأهداف...")
    os.system("python cad_to_json.py")
    
    bot.send_message(chat_id, "🚀 المهام جاهزة! يمكنك إعطاء الأمر للروبوت بالتحرك الآن.")

# ==========================================
# دالة إرسال النتائج (سيتم استدعاؤها في نهاية المهمة)
# ==========================================
def send_results_to_user():
    if not os.path.exists("chat_id.txt"):
        return
        
    with open("chat_id.txt", "r") as f:
        chat_id = f.read().strip()

    bot.send_message(chat_id, "🏁 اكتملت المهمة! جاري إعداد الخريطة النهائية والتقرير...")

    # إرسال خريطة الكاد النهائية
    if os.path.exists("Final_Inspection_Report.dxf"):
        with open("Final_Inspection_Report.dxf", "rb") as doc:
            bot.send_document(chat_id, doc, caption="🗺️ خريطة الكاد النهائية (As-Built)")

    # إرسال التقرير
    if os.path.exists("final_site_report.json"):
        with open("final_site_report.json", "rb") as doc:
            bot.send_document(chat_id, doc, caption="📄 تقرير الفحص الشامل")

if __name__ == "__main__":
    print("🤖 Telegram Bot is running and listening...")
    bot.polling(none_stop=True)