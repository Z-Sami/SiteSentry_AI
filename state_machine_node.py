#!/usr/bin/env python3
import rospy
import socket
import json
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Twist

class SiteSentryStateMachine:
    def __init__(self):
        rospy.init_node('state_machine_node', anonymous=True)
        
        # إعداد اتصال UDP مع سامي
        self.udp_ip = "127.0.0.1" # (يتغير لاحقاً لـ IP جهاز سامي)
        self.udp_port = 5005
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.5) # كي لا يتجمد الكود وهو ينتظر
        
        # ناشر أوامر الحركة (للمحاذاة)
        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        # عميل الملاحة (move_base بدلاً من Nav2)
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
                    pass # لا يوجد رسالة، ابقَ في حالة الانتظار

            # 2. حالة الملاحة (Navigation State)
            elif self.state == "NAVIGATION":
                if self.current_waypoint_index < len(self.mission_data):
                    target = self.mission_data[self.current_waypoint_index]
                    rospy.loginfo(f"Navigating to Target {self.current_waypoint_index + 1}: X={target['x']}, Y={target['y']}")
                    
                    # هنا يتم إرسال الهدف لـ move_base (محاكاة للعملية حالياً)
                    # ropsy.sleep(2) # محاكاة وقت المشي
                    
                    # نفترض أنه وصل للهدف
                    self.state = "ALIGNMENT"
                else:
                    rospy.loginfo("Mission Complete! Returning to IDLE.")
                    self.state = "IDLE"

            # 3. حالة المحاذاة (Alignment State)
            elif self.state == "ALIGNMENT":
                rospy.loginfo("Aligning with the wall...")
                # هنا كود الدوران البطيء يميناً ويساراً (سنربطه بحساسات بتول لاحقاً)
                align_msg = Twist()
                align_msg.angular.z = 0.1 # دوران بطيء
                self.cmd_pub.publish(align_msg)
                rospy.sleep(1) # محاكاة وقت المحاذاة
                
                # إيقاف الروبوت
                self.cmd_pub.publish(Twist())
                self.state = "HANDOVER"

            # 4. حالة تسليم القيادة (Handover State)
            elif self.state == "HANDOVER":
                target = self.mission_data[self.current_waypoint_index]
                handover_msg = f"TARGET_REACHED, {target['x']}, {target['y']}"
                # إرسال الرسالة لكود سامي
                self.sock.sendto(handover_msg.encode('utf-8'), (self.udp_ip, 5006)) # افتراض بورت استقبال سامي
                rospy.loginfo("Handed over to Sami for inspection. Sleeping...")
                self.state = "RESUME" # ننتقل لحالة انتظار الرد

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
