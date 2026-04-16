import telebot
import os
import socket

# 1. إعدادات البوت والشبكة
TOKEN =  "8725258748:AAESMUsA1_OTEcqrOo0E7iii1SQwXQAwu9Y" # استبدله بالتوكن الحقيقي من BotFather
bot = telebot.TeleBot(TOKEN)

UDP_IP = "127.0.0.1" 
UDP_PORT = 5005

# ---------------------------------------------------------
# سطر 14: أمر البدء والترحيب
# ---------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك في نظام SiteSentry!\n\n"
                          "1️⃣ أرسل ملف الـ DXF أولاً.\n"
                          "2️⃣ بعد تأكيد الاستلام، أرسل /run لبدء المهمة.")

# ---------------------------------------------------------
# سطر 23: أمر تشغيل الروبوت (هذا ما سألت عنه)
# ---------------------------------------------------------
@bot.message_handler(commands=['run'])
def start_mission_cmd(message):
    chat_id = message.chat.id
    
    if not os.path.exists("mission.json"):
        bot.reply_to(message, "⚠️ لا يوجد ملف مهام! أرسل المخطط أولاً.")
        return

    bot.send_message(chat_id, "🚀 جاري إعطاء أمر الانطلاق لنظام الملاحة (ROS)...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"START_MISSION", (UDP_IP, UDP_PORT))
        bot.send_message(chat_id, "✅ انطلق الروبوت! يمكنك الآن متابعة الداشبورد.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل الاتصال: {e}")

# ---------------------------------------------------------
# سطر 44: استقبال ملف الكاد
# ---------------------------------------------------------
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    # حفظ الـ ID لرد النتائج لاحقاً
    with open("chat_id.txt", "w") as f: f.write(str(chat_id))

    file_name = message.document.file_name
    if not file_name.endswith('.dxf'):
        bot.reply_to(message, "❌ أرسل ملف DXF فقط.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("site_plan.dxf", 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.send_message(chat_id, "📥 تم استلام المخطط. جاري المعالجة...")
    
    # تشغيل المترجم تلقائياً
    os.system("python cad_to_json.py")
    bot.send_message(chat_id, "✅ جاهز! أرسل أمر /run عندما تريد للروبوت أن يتحرك.")

# ---------------------------------------------------------
# سطر 71: دالة إرسال النتائج النهائية (تُستدعى من generate_map.py)
# ---------------------------------------------------------
def send_results_to_user():
    if not os.path.exists("chat_id.txt"): return
    with open("chat_id.txt", "r") as f: chat_id = f.read().strip()

    if os.path.exists("Final_Inspection_Report.dxf"):
        with open("Final_Inspection_Report.dxf", "rb") as doc:
            bot.send_document(chat_id, doc, caption="🗺️ المخطط النهائي المحدث")
    
    if os.path.exists("final_site_report.json"):
        with open("final_site_report.json", "rb") as doc:
            bot.send_document(chat_id, doc, caption="📄 تقرير الفحص")

if __name__ == "__main__":
    print("🤖 SiteSentry Bot is Listening...")
    bot.polling(none_stop=True)