import socket
import json
import time

# إعداد قناة الإرسال
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_address = ('127.0.0.1', 5005)

print("--- Mohammad LiDAR Simulator Started ---")

# محاكاة حركة الروبوت نحو المقبس الأول (10, 10)
for i in range(10):
    # الروبوت يقترب تدريجياً
    current_pos = {
        "x": 9.5 + (i * 0.05), # سيبدأ من 9.5 ويصل إلى 10.0
        "y": 9.5 + (i * 0.05)
    }
    
    # إرسال البيانات لسامي
    message = json.dumps(current_pos).encode('utf-8')
    sock.sendto(message, server_address)
    
    print(f"Sent coordinates: X={current_pos['x']:.2f}, Y={current_pos['y']:.2f}")
    time.sleep(1) # يرسل قراءة كل ثانية