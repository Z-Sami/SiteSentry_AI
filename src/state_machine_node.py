#!/usr/bin/env python3
import rospy
import socket
import json
import actionlib
import os
from dotenv import load_dotenv
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Twist

class SiteSentryStateMachine:
    def __init__(self):
        rospy.init_node('state_machine_node', anonymous=True)
        
        # تحميل إعدادات البيئة (التعديل الجديد)
        load_dotenv()
        
        # إعدادات استقبال الأوامر من سامي (يستمع على 5005)
        self.udp_ip = os.getenv("ROS_IP", "127.0.0.1")
        self.udp_port = int(os.getenv("ROS_PORT", 5005))
        
        # إعدادات إرسال الإحداثيات لسامي (يرسل إلى 5006)
        self.brain_ip = os.getenv("BRAIN_IP", "127.0.0.1")
        self.brain_port = int(os.getenv("BRAIN_PORT", 5006))
        
        # إعداد الاتصال
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.5) # كي لا يتجمد الكود وهو ينتظر
        
        # ناشر أوامر الحركة (للمحاذاة)
        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # عميل الملاحة (move_base)
        self.nav_client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        
        self.state = "IDLE"
        self.current_waypoint_index = 0
        self.mission_data = []

    def load_mission(self):
        try:
            with open('mission.json', 'r') as f:
                self.mission_data = json.load(f)
            rospy.loginfo("Mission loaded successfully.")
        except Exception as e:
            rospy.logerr(f"Error loading mission.json: {e}")

    def run(self):
        rate = rospy.Rate(10) # 10 مرات في الثانية
        
        while not rospy.is_shutdown():
            # 1. حالة الانتظار (Idle State)
            if self.state == "IDLE":
                try:
                    data, addr = self.sock.recvfrom(1024)
                    msg = data.decode('utf-8')
                    if msg == "START_MISSION":
                        rospy.loginfo("START_MISSION received from Telegram!")
                        self.load_mission()
                        self.state = "NAVIGATION"
                except socket.timeout:
                    pass

            # 2. حالة الملاحة (Navigation State)
            elif self.state == "NAVIGATION":
                if self.current_waypoint_index < len(self.mission_data):
                    target = self.mission_data[self.current_waypoint_index]
                    rospy.loginfo(f"Navigating to Target {self.current_waypoint_index + 1}: X={target['x']}, Y={target['y']}")
                    # هنا يتم إرسال الهدف لـ move_base (محاكاة حالياً)
                    # rospy.sleep(2)
                    self.state = "ALIGNMENT"
                else:
                    rospy.loginfo("Mission Complete! Returning to IDLE.")
                    self.state = "IDLE"

            # 3. حالة المحاذاة (Alignment State)
            elif self.state == "ALIGNMENT":
                rospy.loginfo("Aligning with the wall...")
                align_msg = Twist()
                align_msg.angular.z = 0.1
                self.cmd_pub.publish(align_msg)
                rospy.sleep(1)
                
                self.cmd_pub.publish(Twist()) # إيقاف الروبوت
                self.state = "HANDOVER"

            # 4. حالة تسليم القيادة (Handover State)
            elif self.state == "HANDOVER":
                target = self.mission_data[self.current_waypoint_index]
                handover_msg = f"TARGET_REACHED, {target['x']}, {target['y']}"
                
                # التعديل هنا: استخدام متغيرات الإرسال الجديدة
                self.sock.sendto(handover_msg.encode('utf-8'), (self.brain_ip, self.brain_port)) 
                
                rospy.loginfo(f"Handed over to Sami ({self.brain_ip}:{self.brain_port}). Sleeping...")
                self.state = "RESUME"

            # 5. حالة الاستئناف (Resume State)
            elif self.state == "RESUME":
                try:
                    data, addr = self.sock.recvfrom(1024)
                    msg = data.decode('utf-8')
                    if msg == "INSPECTION_DONE":
                        rospy.loginfo("Inspection Done. Proceeding to next target.")
                        self.current_waypoint_index += 1
                        self.state = "NAVIGATION"
                except socket.timeout:
                    pass

            rate.sleep()

if __name__ == '__main__':
    sm = SiteSentryStateMachine()
    sm.run()
