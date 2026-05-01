#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import requests
import os

# التوكن والـ Chat ID الخاصين فيك
TOKEN = "8287352191:AAEax7cHSI_rMA2poLYac-pt1uzraLHSq68"
CHAT_ID = "5887708500"

class TelegramBotNode(Node):
    def __init__(self):
        super().__init__('telegram_bot')
        
        # هاي العقدة رح تتنصت على قناة اسمها /site_alerts
        self.subscription = self.create_subscription(
            String,
            '/site_alerts',
            self.alert_callback,
            10)
            
        self.get_logger().info('Telegram Bot is Online and waiting for YOLO alerts...')
        
        # إرسال رسالة ترحيبية أول ما يشتغل الكود
        self.send_telegram_msg("🤖 SiteSentry System Activated! I am watching the site.")

    def alert_callback(self, msg):
        self.get_logger().warn(f'Sending Alert to Telegram: {msg.data}')
        self.send_telegram_msg(f"🚨 ALERT: {msg.data}")
        
        # إذا في صورة التقطها YOLO، بنبعثها كمان
        if os.path.exists("latest_alert.jpg"):
            self.send_telegram_photo("latest_alert.jpg")

    def send_telegram_msg(self, text):
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            self.get_logger().error(f'Failed to send message: {e}')

    def send_telegram_photo(self, photo_path):
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo:
                payload = {"chat_id": CHAT_ID}
                files = {"photo": photo}
                requests.post(url, data=payload, files=files)
        except Exception as e:
            self.get_logger().error(f'Failed to send photo: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = TelegramBotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()