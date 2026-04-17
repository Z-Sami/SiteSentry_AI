import socket
import json
import threading
import os
from dotenv import load_dotenv

# تحميل الإعدادات المركزية
load_dotenv()
DEFAULT_IP = os.getenv("BRAIN_IP", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("BRAIN_PORT", 5006))

class LidarReceiver:
    # نغير القيم الافتراضية هنا
    def __init__(self, host=DEFAULT_IP, port=DEFAULT_PORT):
        self.host = host
        self.port = port
         
        # غير هذه الأسطر
        self.current_x = 10.0
        self.current_y = 10.0
        self.running = False
        
        # تجهيز قناة الاتصال (UDP Socket)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))

    def _listen(self):
        """هذه الدالة تعمل في الخلفية لتحديث الإحداثيات باستمرار"""
        while self.running:
            try:
                # استقبال البيانات من كود محمد
                data, _ = self.sock.recvfrom(1024)
                coords = json.loads(data.decode('utf-8'))
                
                # تحديث موقع الروبوت الحالي
                self.current_x = coords.get('x', self.current_x)
                self.current_y = coords.get('y', self.current_y)
            except Exception as e:
                pass

    def start(self):
        """تشغيل المستمع في Thread منفصل لكي لا يوقف الكود الأساسي"""
        self.running = True
        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()
        print(f"[LiDAR] Receiver is listening on {self.host}:{self.port}...")

    def get_position(self):
        """دالة يستدعيها كودك لمعرفة مكان الروبوت في هذه اللحظة"""
        return self.current_x, self.current_y

    def stop(self):
        """إيقاف المستمع عند انتهاء المهمة"""
        self.running = False
        self.sock.close()

# --- تجربة بسيطة للملف ---
if __name__ == "__main__":
    import time
    receiver = LidarReceiver()
    receiver.start()
    
    print("Waiting for Mohammad's LiDAR data... (Press Ctrl+C to stop)")
    try:
        while True:
            x, y = receiver.get_position()
            print(f"Current Position -> X: {x:.2f}, Y: {y:.2f}", end='\r')
            time.sleep(0.5)
    except KeyboardInterrupt:
        receiver.stop()
        print("\nReceiver stopped.")