import telebot
import os
import socket
import subprocess
from dotenv import load_dotenv

# 1. تحميل الأسرار من ملف .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# حماية إضافية: التأكد من أن التوكن موجود فعلاً
if not TOKEN:
    raise ValueError("❌ خطأ: لم يتم العثور على TELEGRAM_BOT_TOKEN في ملف .env")

bot = telebot.TeleBot(TOKEN)

# إعدادات الشبكة (يمكن نقلها لـ .env لاحقاً إذا أردت)
UDP_IP = os.getenv("ROS_IP", "127.0.0.1")
UDP_PORT = int(os.getenv("ROS_PORT", 5005))

# ---------------------------------------------------------
# أمر البدء والترحيب
# ---------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 أهلاً بك مهندس سامي في نظام SiteSentry!\n\n"
                          "1️⃣ أرسل المخطط بصيغة (DXF).\n"
                          "2️⃣ بعد المعالجة، أرسل /run لبدء المهمة الميدانية.")

# ---------------------------------------------------------
# أمر تشغيل الروبوت عن بُعد
# ---------------------------------------------------------
@bot.message_handler(commands=['run'])
def start_mission_cmd(message):
    chat_id = message.chat.id
    
    if not os.path.exists("mission.json"):
        bot.reply_to(message, "⚠️ خطأ: لا يوجد ملف مهام! أرسل المخطط أولاً.")
        return

    bot.send_message(chat_id, "🚀 جاري إرسال إشارة الانطلاق لنظام الملاحة (ROS)...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"START_MISSION", (UDP_IP, UDP_PORT))
        bot.send_message(chat_id, "✅ انطلق الروبوت! راقب الداشبورد الآن.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل الاتصال بنظام ROS: {e}")

# ---------------------------------------------------------
# استقبال ملف الكاد ومعالجته
# ---------------------------------------------------------
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    # حفظ الـ ID لرد النتائج لاحقاً
    with open("chat_id.txt", "w") as f: 
        f.write(str(chat_id))

    file_name = message.document.file_name
    if not file_name.endswith('.dxf'):
        bot.reply_to(message, "❌ خطأ: أرسل ملف DXF فقط.")
        return

    # تحميل الملف من تليجرام
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("site_plan.dxf", 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.send_message(chat_id, "📥 تم استلام المخطط بنجاح. جاري استخراج الأهداف...")
    
    # تشغيل المترجم بطريقة آمنة باستخدام subprocess
    try:
        # ملاحظة: استخدم python3 إذا كنت تعمل على نظام لينكس/راسبيري
        subprocess.run(["python", "cad_to_json.py"], check=True)
        bot.send_message(chat_id, "✅ المهام جاهزة! الروبوت بانتظار أمر /run للتحرك.")
    except subprocess.CalledProcessError as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء قراءة المخطط المرفق.\nالتفاصيل: {e}")

# ---------------------------------------------------------
# دالة إرسال النتائج النهائية
# ---------------------------------------------------------
def send_results_to_user():
    if not os.path.exists("chat_id.txt"): 
        return
        
    with open("chat_id.txt", "r") as f: 
        chat_id = f.read().strip()

    bot.send_message(chat_id, "🏁 اكتملت المهمة الميدانية! جاري إرسال التوثيق...")

    if os.path.exists("Final_Inspection_Report.dxf"):
        with open("Final_Inspection_Report.dxf", "rb") as doc:
            bot.send_document(chat_id, doc, caption="🗺️ المخطط النهائي المحدث (As-Built)")
    
    if os.path.exists("final_site_report.json"):
        with open("final_site_report.json", "rb") as doc:
            bot.send_document(chat_id, doc, caption="📄 التقرير الرقمي الشامل")

if __name__ == "__main__":
    print("🤖 SiteSentry SECURE Bot is Running...")
    bot.polling(none_stop=True)