#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import numpy as np
from ultralytics import YOLO
import os

class SiteSentryVisionSystem(Node):
    def __init__(self):
        super().__init__('sitesentry_vision_processor')
        
        # إعدادات الموديل والمسارات
        self.model = YOLO('/root/SiteSentry_Project/best.pt')
        self.bridge = CvBridge()
        self.save_path = "/root/SiteSentry_Project/latest_alert.jpg"
        
        # الناشرون (Publishers)
        self.image_pub = self.create_publisher(CompressedImage, '/camera/compressed', 10)
        self.alert_pub = self.create_publisher(String, '/site_alerts', 10)
        
        # إعداد الكاميرا (Hardware Optimization)
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # تايمر المعالجة (10 FPS لضمان عدم التعليق)
        self.timer = self.create_timer(0.1, self.process_and_stream)
        self.get_logger().info('SiteSentry Vision System: FULL MODE ONLINE')

    def process_and_stream(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        # 1. تحليل الذكاء الاصطناعي (على الدقة الكاملة لضمان الجودة)
        results = self.model(frame, conf=0.5, verbose=False)
        annotated_frame = results[0].plot()

        # 2. تحسين البث (هنا السر في إنهاء التعليق)
        # نقوم بتصغير صورة البث فقط وليس صورة التحليل
        stream_img = cv2.resize(annotated_frame, (480, 360)) 
        
        # ضغط JPEG لتقليل حجم البيانات بنسبة 70%
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 35]
        _, buffer = cv2.imencode('.jpg', stream_img, encode_param)
        
        # 3. إرسال الفيديو
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = np.array(buffer).tobytes()
        self.image_pub.publish(msg)

        # 4. منطق التنبيهات وحفظ الصور
        for box in results[0].boxes:
            if int(box.cls[0]) == 0:  # الشخص (Person)
                self.get_logger().warn('!!! INTRUDER DETECTED !!!')
                # حفظ الصورة للبوت
                cv2.imwrite(self.save_path, annotated_frame)
                # إرسال التنبيه للويب
                alert_msg = String()
                alert_msg.data = "SECURITY BREACH: Person Detected!"
                self.alert_pub.publish(alert_msg)
                break

def main(args=None):
    rclpy.init(args=args)
    node = SiteSentryVisionSystem()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cap.release()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()