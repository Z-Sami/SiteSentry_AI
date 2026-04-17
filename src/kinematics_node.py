#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32

class SiteSentryKinematics:
    def __init__(self):
        rospy.init_node('kinematics_node', anonymous=True)
        self.track_width = 0.5 
        self.pub_right = rospy.Publisher('/right_wheel_speed', Float32, queue_size=10)
        self.pub_left = rospy.Publisher('/left_wheel_speed', Float32, queue_size=10)
        rospy.Subscriber('/cmd_vel', Twist, self.cmd_vel_callback)
        rospy.loginfo("SiteSentry Kinematics Node Started. Ready to move!")

    def cmd_vel_callback(self, msg):
        v_x = msg.linear.x    
        w_z = msg.angular.z   
        v_right = v_x + (w_z * self.track_width / 2.0)
        v_left = v_x - (w_z * self.track_width / 2.0)
        self.pub_right.publish(v_right)
        self.pub_left.publish(v_left)

if __name__ == '__main__':
    try:
        node = SiteSentryKinematics()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
