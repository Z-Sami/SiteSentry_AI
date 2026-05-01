import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import cv2
from ultralytics import YOLO

class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        
        # 1. إعداد الـ Publisher (الفم اللي ببعث التنبيهات لباقي أجزاء الروبوت)
        self.publisher_ = self.create_publisher(String, 'sitesentry_alerts', 10)

        # 2. تحميل العقل (YOLO)
        self.model = YOLO('best.pt')
        self.cap = cv2.VideoCapture(0)

        # إعدادات الكاميرا لقتل التأخير (Lag)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 3. تشغيل الكاميرا والتحليل كل 0.1 ثانية
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.frame_count = 0

        self.get_logger().info('SiteSentry Vision Node is Awake and Running in Background! 👀')

    def timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        self.frame_count += 1

        # تحليل فريم وتجاهل فريم لتخفيف الضغط على معالج الراسبيري باي
        if self.frame_count % 2 != 0:
            # التحليل مخصص لمسافة متر (imgsz=320, conf=0.4)
            results = self.model.predict(frame, conf=0.4, imgsz=320, verbose=False)

            # 4. فحص النتائج وإرسال التنبيهات
            for box in results[0].boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                
                # تجهيز الرسالة باسم العنصر المكتشف
                msg = String()
                msg.data = f"🚨 Alert: Found {class_name}!"
                
                # إرسال الرسالة في نظام ROS 2
                self.publisher_.publish(msg)
                
                # طباعة الرسالة على شاشة التيرمينال للتأكيد
                self.get_logger().info(msg.data)

            # تم إيقاف عرض الشاشة البصرية لتجنب خطأ الدوكر (Display Error)
            # annotated_frame = results[0].plot()
            # cv2.imshow("SiteSentry - ROS 2 Vision", annotated_frame)
            # cv2.waitKey(1)

def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # إغلاق نظيف عند الضغط على Ctrl+C
        pass
    finally:
        node.cap.release()
        # cv2.destroyAllWindows() # تم إيقافها لأننا ألغينا الشاشة
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()