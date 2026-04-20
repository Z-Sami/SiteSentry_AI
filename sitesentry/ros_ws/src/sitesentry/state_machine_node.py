#!/usr/bin/env python3
"""
SiteSentry State Machine Node
=============================
ROS1 Noetic node implementing the mission execution state machine.

States:
  IDLE       - Wait for UDP "START_MISSION" signal from Telegram bot
  NAVIGATING - Use move_base to navigate robot to target waypoint
  ALIGNING   - Rotate to wall alignment; trigger Arduino ALIGN_MODE
  WAITING    - Send "TARGET_REACHED" to robot_brain; wait for "INSPECTION_DONE"
  DONE       - All targets completed; send "MISSION_COMPLETE"

Communication:
  - ROS topics: /cmd_vel, /move_base
  - UDP port 5005: Receive START_MISSION, send INSPECTION_DONE
  - UDP port 5006: Send TARGET_REACHED, receive INSPECTION_DONE
  - Serial: Arduino motor control
"""

import rospy
import json
import socket
import serial
import time
import os
import sys
from pathlib import Path
from enum import Enum
from threading import Thread, Lock

# ROS Messages
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Twist, Quaternion
from tf.transformations import quaternion_from_euler
import tf

# ===== CONFIGURATION =====
CONFIG = {
    "mission_file": os.path.join(os.path.dirname(__file__), "../../mission.json"),
    "serial_port": "/dev/ttyUSB0",
    "serial_baudrate": 57600,
    "udp_listen_port": 5005,      # Receive START_MISSION
    "udp_robot_brain_port": 5006, # Send/receive to robot_brain
    "udp_robot_brain_host": "127.0.0.1",
    "udp_timeout": 0.1,           # Non-blocking UDP timeout
    "move_base_timeout": 60.0,    # seconds to reach waypoint
    "align_rotation_speed": 0.1,  # rad/s
    "align_duration": 2.0,        # seconds
}

# State enum
class State(Enum):
    IDLE = 0
    NAVIGATING = 1
    ALIGNING = 2
    WAITING = 3
    DONE = 4

class StateMachineNode:
    def __init__(self):
        """Initialize ROS node and state machine"""
        rospy.init_node("sitesentry_state_machine", anonymous=False)
        
        # Load configuration from ROS params
        self.config = CONFIG.copy()
        self.config["mission_file"] = rospy.get_param("~mission_file", CONFIG["mission_file"])
        self.config["serial_port"] = rospy.get_param("~serial_port", CONFIG["serial_port"])
        self.config["udp_listen_port"] = rospy.get_param("~udp_listen_port", CONFIG["udp_listen_port"])
        
        # State machine
        self.state = State.IDLE
        self.state_lock = Lock()
        self.mission_data = None
        self.current_target_idx = 0
        
        # ROS clients and publishers
        self.move_base_client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.cmd_vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        
        # Communication
        self.serial_conn = None
        self.udp_sock = None
        self.udp_robot_brain_sock = None
        
        # Thread flags
        self.mission_active = False
        self.keep_running = True
        
        rospy.loginfo("State Machine Node initialized")
    
    def setup_connections(self):
        """Initialize serial and UDP connections"""
        # Serial to Arduino
        try:
            self.serial_conn = serial.Serial(
                self.config["serial_port"],
                self.config["serial_baudrate"],
                timeout=1
            )
            rospy.loginfo(f"✓ Serial connected: {self.config['serial_port']}")
        except Exception as e:
            rospy.logwarn(f"Serial connection failed: {e}")
            rospy.logwarn("Continuing without Arduino... (simulated mode)")
        
        # UDP socket for listening (START_MISSION)
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.bind(("0.0.0.0", self.config["udp_listen_port"]))
            self.udp_sock.settimeout(self.config["udp_timeout"])
            rospy.loginfo(f"✓ UDP listen socket: 0.0.0.0:{self.config['udp_listen_port']}")
        except Exception as e:
            rospy.logerr(f"UDP listen socket failed: {e}")
            sys.exit(1)
        
        # UDP socket for sending to robot_brain
        try:
            self.udp_robot_brain_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_robot_brain_sock.settimeout(self.config["udp_timeout"])
            rospy.loginfo(f"✓ UDP robot_brain socket: {self.config['udp_robot_brain_host']}:{self.config['udp_robot_brain_port']}")
        except Exception as e:
            rospy.logerr(f"UDP robot_brain socket failed: {e}")
    
    def load_mission(self):
        """Load mission.json from disk"""
        mission_path = Path(self.config["mission_file"])
        
        if not mission_path.exists():
            rospy.logerr(f"mission.json not found: {mission_path}")
            rospy.logerr("Please run: python3 cad_to_json.py <site_plan.dxf>")
            return False
        
        try:
            with open(mission_path, 'r') as f:
                self.mission_data = json.load(f)
            
            targets = self.mission_data.get("targets", [])
            rospy.loginfo(f"✓ Loaded mission with {len(targets)} targets")
            return True
        except Exception as e:
            rospy.logerr(f"Failed to load mission: {e}")
            return False
    
    def send_udp(self, host, port, message):
        """Send UDP message to robot_brain or Telegram"""
        try:
            if self.udp_robot_brain_sock:
                self.udp_robot_brain_sock.sendto(message.encode(), (host, port))
                rospy.loginfo(f"UDP sent: {message} → {host}:{port}")
            return True
        except Exception as e:
            rospy.logwarn(f"UDP send failed: {e}")
            return False
    
    def recv_udp_timeout(self, timeout=None):
        """Receive UDP message with timeout (non-blocking)"""
        if not self.udp_sock:
            return None
        
        old_timeout = self.udp_sock.gettimeout()
        if timeout:
            self.udp_sock.settimeout(timeout)
        
        try:
            data, addr = self.udp_sock.recvfrom(1024)
            self.udp_sock.settimeout(old_timeout)
            return data.decode().strip()
        except socket.timeout:
            self.udp_sock.settimeout(old_timeout)
            return None
        except Exception as e:
            rospy.logwarn(f"UDP receive error: {e}")
            self.udp_sock.settimeout(old_timeout)
            return None
    
    def listen_for_mission_start(self):
        """Block until START_MISSION is received on UDP 5005"""
        rospy.loginfo("Waiting for START_MISSION...")
        
        while self.keep_running and self.state == State.IDLE:
            msg = self.recv_udp_timeout(timeout=1.0)
            if msg and "START_MISSION" in msg:
                rospy.loginfo("✓ START_MISSION received!")
                with self.state_lock:
                    self.state = State.NAVIGATING
                    self.current_target_idx = 0
                    self.mission_active = True
                return True
            rospy.sleep(0.1)
        
        return False
    
    def wait_for_move_base(self, timeout=None):
        """Wait for move_base server to be available"""
        if timeout is None:
            timeout = self.config["move_base_timeout"]
        
        if not self.move_base_client.wait_for_server(rospy.Duration(timeout)):
            rospy.logerr("move_base action server not available!")
            return False
        
        return True
    
    def send_navigation_goal(self, target):
        """Send a goal to move_base"""
        rospy.loginfo(f"Navigating to target {target['id']}: ({target['x']}, {target['y']})")
        
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        
        # Position
        goal.target_pose.pose.position.x = target["x"]
        goal.target_pose.pose.position.y = target["y"]
        goal.target_pose.pose.position.z = 0.0
        
        # Orientation (facing the target label direction)
        goal.target_pose.pose.orientation = Quaternion(*quaternion_from_euler(0, 0, 0))
        
        self.move_base_client.send_goal(goal)
        
        # Wait for result
        finished = self.move_base_client.wait_for_result(
            rospy.Duration(self.config["move_base_timeout"])
        )
        
        if finished:
            state = self.move_base_client.get_state()
            if state == actionlib.GoalStatus.SUCCEEDED:
                rospy.loginfo(f"✓ Reached target {target['id']}")
                return True
            else:
                rospy.logwarn(f"move_base failed with state: {state}")
                return False
        else:
            rospy.logwarn(f"move_base timeout for target {target['id']}")
            self.move_base_client.cancel_goal()
            return False
    
    def align_to_wall(self, target):
        """Execute wall alignment"""
        rospy.loginfo(f"Aligning to wall for target {target['id']}...")
        
        with self.state_lock:
            self.state = State.ALIGNING
        
        # Send ALIGN_MODE command to Arduino
        if self.serial_conn:
            try:
                self.serial_conn.write(b"ALIGN_MODE\n")
                rospy.loginfo("Sent ALIGN_MODE to Arduino")
            except Exception as e:
                rospy.logwarn(f"Failed to send ALIGN_MODE: {e}")
        
        # Publish slow rotation on /cmd_vel
        rotate_cmd = Twist()
        rotate_cmd.angular.z = self.config["align_rotation_speed"]
        
        start_time = time.time()
        while time.time() - start_time < self.config["align_duration"]:
            self.cmd_vel_pub.publish(rotate_cmd)
            rospy.sleep(0.05)
        
        # Stop rotation
        stop_cmd = Twist()
        self.cmd_vel_pub.publish(stop_cmd)
        rospy.loginfo("✓ Alignment complete")
        
        with self.state_lock:
            self.state = State.WAITING
    
    def wait_for_inspection(self, target):
        """Wait for robot_brain to complete inspection"""
        rospy.loginfo(f"Waiting for inspection of target {target['id']}...")
        
        # Send TARGET_REACHED message to robot_brain
        target_msg = f"TARGET_REACHED,{target['id']},{target['x']},{target['y']}"
        self.send_udp(
            self.config["udp_robot_brain_host"],
            self.config["udp_robot_brain_port"],
            target_msg
        )
        
        with self.state_lock:
            self.state = State.WAITING
        
        # Wait for INSPECTION_DONE on UDP 5005
        timeout_start = time.time()
        inspection_timeout = 120.0  # 2 minutes max
        
        while time.time() - timeout_start < inspection_timeout:
            msg = self.recv_udp_timeout(timeout=1.0)
            if msg and "INSPECTION_DONE" in msg:
                rospy.loginfo("✓ INSPECTION_DONE received")
                return True
            rospy.sleep(0.1)
        
        rospy.logwarn(f"Inspection timeout for target {target['id']}")
        return False
    
    def mission_loop(self):
        """Main mission execution loop"""
        if not self.load_mission():
            return
        
        targets = self.mission_data.get("targets", [])
        
        if not targets:
            rospy.logwarn("No targets in mission!")
            with self.state_lock:
                self.state = State.IDLE
            return
        
        rospy.loginfo(f"Starting mission with {len(targets)} targets")
        
        # Wait for move_base
        if not self.wait_for_move_base(timeout=30.0):
            rospy.logerr("move_base not available; aborting")
            with self.state_lock:
                self.state = State.IDLE
            return
        
        # Process each target
        for idx, target in enumerate(targets):
            if not self.keep_running:
                break
            
            self.current_target_idx = idx
            rospy.loginfo(f"\n=== Target {idx + 1}/{len(targets)} ===")
            
            with self.state_lock:
                self.state = State.NAVIGATING
            
            # Navigate to target
            if not self.send_navigation_goal(target):
                rospy.logwarn(f"Failed to navigate to target {target['id']}, skipping...")
                continue
            
            # Align to wall
            self.align_to_wall(target)
            
            # Wait for inspection
            if not self.wait_for_inspection(target):
                rospy.logwarn(f"Inspection timeout for target {target['id']}")
        
        # Mission complete
        rospy.loginfo("\n=== MISSION COMPLETE ===")
        self.send_udp(
            self.config["udp_robot_brain_host"],
            self.config["udp_robot_brain_port"],
            "MISSION_COMPLETE"
        )
        
        with self.state_lock:
            self.state = State.DONE
            self.mission_active = False
    
    def run(self):
        """Main node loop"""
        self.setup_connections()
        
        rospy.loginfo("State Machine Node running...")
        
        try:
            while self.keep_running:
                if self.state == State.IDLE:
                    # Wait for mission start signal
                    self.listen_for_mission_start()
                
                elif self.state == State.NAVIGATING:
                    # Mission loop handles all transitions
                    self.mission_loop()
                
                else:
                    rospy.sleep(0.5)
        
        except rospy.ROSInterruptException:
            rospy.loginfo("Shutting down...")
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        self.keep_running = False
        
        # Stop motors
        self.cmd_vel_pub.publish(Twist())
        
        # Close connections
        if self.serial_conn:
            self.serial_conn.close()
        if self.udp_sock:
            self.udp_sock.close()
        if self.udp_robot_brain_sock:
            self.udp_robot_brain_sock.close()
        
        rospy.loginfo("State Machine Node shutdown complete")

def main():
    try:
        node = StateMachineNode()
        node.run()
    except Exception as e:
        rospy.logerr(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
