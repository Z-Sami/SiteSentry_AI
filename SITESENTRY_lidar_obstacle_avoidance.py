#!/usr/bin/env python3
"""
SITESENTRY - LIDAR OBSTACLE AVOIDANCE NODE
Complete integration with RPLidar A1 + Obstacle Detection
Works with existing Arduino code and web dashboard
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32
import numpy as np
import math
from collections import deque


class LidarObstacleAvoidanceNode(Node):
    """
    LIDAR-based obstacle avoidance system for SiteSentry robot
    
    Features:
    - Real-time obstacle detection from RPLidar
    - Automatic collision avoidance
    - Safe stop when obstacles too close
    - Integration with existing motor commands
    - Safety override capability
    """
    
    def __init__(self):
        super().__init__('lidar_obstacle_avoidance')
        
        # ============ PARAMETERS ============
        
        # Safety thresholds (meters)
        self.CRITICAL_DISTANCE = 0.15      # 15cm - STOP immediately!
        self.WARNING_DISTANCE = 0.30       # 30cm - Slow down
        self.SAFE_DISTANCE = 0.50          # 50cm - Normal speed
        
        # Detection zones (angles in degrees)
        self.FRONT_ZONE = 45               # ±45° front
        self.SIDE_ZONE = 90                # ±90° side
        self.REAR_ZONE = 180               # Rear detection
        
        # Motion parameters
        self.MAX_LINEAR_SPEED = 0.5        # m/s
        self.MAX_ANGULAR_SPEED = 2.0       # rad/s
        self.SAFETY_MARGIN = 0.05          # 5cm extra margin
        
        # Filtering
        self.SCAN_BUFFER_SIZE = 5          # Average last 5 scans
        self.scan_buffer = deque(maxlen=self.SCAN_BUFFER_SIZE)
        
        # ============ ROS 2 SETUP ============
        
        # Create QoS profile for LiDAR (high frequency)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )
        
        # SUBSCRIBERS
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',  # RPLidar publishes to /scan
            self.lidar_callback,
            qos_profile
        )
        
        # Subscribe to incoming motor commands
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        # PUBLISHERS
        self.safe_cmd_vel_pub = self.create_publisher(
            Twist,
            'cmd_vel_safe',  # Safe version of cmd_vel
            10
        )
        
        self.obstacle_pub = self.create_publisher(
            Bool,
            'lidar/obstacle_detected',
            10
        )
        
        self.min_distance_pub = self.create_publisher(
            Float32,
            'lidar/min_distance',
            10
        )
        
        self.danger_zone_pub = self.create_publisher(
            Float32,
            'lidar/danger_distance',
            10
        )
        
        # ============ STATE VARIABLES ============
        
        self.last_cmd_vel = Twist()
        self.last_cmd_time = self.get_clock().now()
        self.obstacle_detected = False
        self.min_distance = float('inf')
        self.danger_distance = self.SAFE_DISTANCE
        
        # Statistics
        self.lidar_frames = 0
        self.obstacles_avoided = 0
        
        self.get_logger().info("🤖 LiDAR Obstacle Avoidance Node INITIALIZED!")
        self.get_logger().info(f"   Critical Distance: {self.CRITICAL_DISTANCE}m")
        self.get_logger().info(f"   Warning Distance: {self.WARNING_DISTANCE}m")
        self.get_logger().info(f"   Safe Distance: {self.SAFE_DISTANCE}m")
    
    def lidar_callback(self, msg: LaserScan):
        """
        Process LiDAR scan and detect obstacles
        
        Scan angles:
        - 0° = front right
        - 90° = left
        - 180° = back
        - 270° = right
        """
        
        if msg.ranges is None or len(msg.ranges) == 0:
            return
        
        self.lidar_frames += 1
        
        # Convert to numpy array for easier processing
        ranges = np.array(msg.ranges)
        
        # Filter out invalid readings (0 or inf)
        valid_ranges = ranges[(ranges > msg.range_min) & (ranges < msg.range_max)]
        
        if len(valid_ranges) == 0:
            self.get_logger().warn("No valid LiDAR readings!")
            return
        
        # Store scan for filtering
        self.scan_buffer.append(valid_ranges)
        
        # Average over last N scans (smoothing)
        if len(self.scan_buffer) == self.SCAN_BUFFER_SIZE:
            filtered_ranges = np.mean(list(self.scan_buffer), axis=0)
        else:
            filtered_ranges = valid_ranges
        
        # Analyze obstacles
        self.analyze_obstacles(msg, filtered_ranges)
        
        # Modify motor commands based on obstacles
        self.apply_safety_override(msg)
    
    def analyze_obstacles(self, msg: LaserScan, filtered_ranges):
        """
        Analyze LiDAR scan for obstacles
        Detect obstacles in different zones
        """
        
        # Number of measurements
        num_measurements = len(msg.ranges)
        angle_increment = msg.angle_increment  # radians per measurement
        
        # Initialize zone distances
        front_distance = float('inf')
        left_distance = float('inf')
        right_distance = float('inf')
        rear_distance = float('inf')
        
        # Analyze each measurement
        for i, distance in enumerate(filtered_ranges):
            if distance <= 0 or math.isinf(distance):
                continue
            
            # Calculate angle for this measurement
            angle = msg.angle_min + (i * angle_increment)
            angle_degrees = math.degrees(angle)
            
            # Normalize angle to 0-360
            if angle_degrees < 0:
                angle_degrees += 360
            
            # Categorize by zone
            if -self.FRONT_ZONE <= angle_degrees <= self.FRONT_ZONE:
                # Front zone
                front_distance = min(front_distance, distance)
            
            elif self.FRONT_ZONE < angle_degrees <= (90 + self.SIDE_ZONE/2):
                # Left zone
                left_distance = min(left_distance, distance)
            
            elif (90 + self.SIDE_ZONE/2) < angle_degrees <= (180 - self.SIDE_ZONE/2):
                # Back-left zone
                rear_distance = min(rear_distance, distance)
            
            elif (180 - self.SIDE_ZONE/2) < angle_degrees < (180 + self.SIDE_ZONE/2):
                # Back zone
                rear_distance = min(rear_distance, distance)
            
            elif (180 + self.SIDE_ZONE/2) <= angle_degrees < (270 - self.SIDE_ZONE/2):
                # Back-right zone
                rear_distance = min(rear_distance, distance)
            
            elif (270 - self.SIDE_ZONE/2) <= angle_degrees <= 360:
                # Right zone
                right_distance = min(right_distance, distance)
            
            elif angle_degrees <= -self.FRONT_ZONE:
                # Front right zone
                front_distance = min(front_distance, distance)
        
        # Find overall minimum distance
        self.min_distance = min(front_distance, left_distance, right_distance, rear_distance)
        
        # Check for obstacles
        if self.min_distance <= self.CRITICAL_DISTANCE:
            self.obstacle_detected = True
            self.danger_distance = self.CRITICAL_DISTANCE
            
            if self.lidar_frames % 10 == 0:  # Log every 10 frames
                self.get_logger().warn(
                    f"🚨 CRITICAL OBSTACLE: {self.min_distance:.2f}m - STOPPING!"
                )
            
            self.obstacles_avoided += 1
        
        elif self.min_distance <= self.WARNING_DISTANCE:
            self.obstacle_detected = True
            self.danger_distance = self.WARNING_DISTANCE
            
            if self.lidar_frames % 20 == 0:
                self.get_logger().info(
                    f"⚠️ WARNING: Obstacle at {self.min_distance:.2f}m - Slowing down"
                )
        
        else:
            self.obstacle_detected = False
            self.danger_distance = self.SAFE_DISTANCE
        
        # Detailed zone analysis (for debugging)
        if self.lidar_frames % 50 == 0:
            self.get_logger().debug(
                f"Zones - Front: {front_distance:.2f}m, "
                f"Left: {left_distance:.2f}m, "
                f"Right: {right_distance:.2f}m, "
                f"Rear: {rear_distance:.2f}m"
            )
        
        # Publish sensor data
        self.publish_obstacle_status()
    
    def cmd_vel_callback(self, msg: Twist):
        """
        Receive motor commands and store for safety override
        """
        self.last_cmd_vel = msg
        self.last_cmd_time = self.get_clock().now()
    
    def apply_safety_override(self, scan_msg: LaserScan):
        """
        Modify motor commands based on obstacle detection
        
        Three levels of response:
        1. SAFE DISTANCE (>50cm) - Allow full speed
        2. WARNING DISTANCE (30-50cm) - Reduce speed by 50%
        3. CRITICAL DISTANCE (<15cm) - STOP immediately
        """
        
        # Create modified command
        safe_cmd = Twist()
        
        if self.min_distance <= self.CRITICAL_DISTANCE:
            # ========== CRITICAL: STOP IMMEDIATELY ==========
            safe_cmd.linear.x = 0.0
            safe_cmd.angular.z = 0.0
            
            # Allow turning in place if requested
            # (to help robot escape)
            if abs(self.last_cmd_vel.angular.z) > 0.1:
                safe_cmd.angular.z = self.last_cmd_vel.angular.z * 0.3
        
        elif self.min_distance <= self.WARNING_DISTANCE:
            # ========== WARNING: REDUCE SPEED ==========
            speed_reduction = (self.min_distance - self.CRITICAL_DISTANCE) / \
                            (self.WARNING_DISTANCE - self.CRITICAL_DISTANCE)
            
            safe_cmd.linear.x = self.last_cmd_vel.linear.x * speed_reduction * 0.7
            safe_cmd.angular.z = self.last_cmd_vel.angular.z * 0.8
            
            self.get_logger().info(
                f"Reducing speed to {speed_reduction*70:.0f}% - "
                f"Obstacle at {self.min_distance:.2f}m"
            )
        
        else:
            # ========== SAFE: ALLOW FULL SPEED ==========
            safe_cmd = self.last_cmd_vel
        
        # Enforce speed limits
        safe_cmd.linear.x = max(-self.MAX_LINEAR_SPEED, 
                               min(self.MAX_LINEAR_SPEED, safe_cmd.linear.x))
        safe_cmd.angular.z = max(-self.MAX_ANGULAR_SPEED, 
                                min(self.MAX_ANGULAR_SPEED, safe_cmd.angular.z))
        
        # Publish safe command
        self.safe_cmd_vel_pub.publish(safe_cmd)
    
    def publish_obstacle_status(self):
        """Publish obstacle detection status"""
        
        # Obstacle detected message
        obstacle_msg = Bool()
        obstacle_msg.data = self.obstacle_detected
        self.obstacle_pub.publish(obstacle_msg)
        
        # Minimum distance
        min_dist_msg = Float32()
        min_dist_msg.data = self.min_distance
        self.min_distance_pub.publish(min_dist_msg)
        
        # Danger zone distance
        danger_msg = Float32()
        danger_msg.data = self.danger_distance
        self.danger_zone_pub.publish(danger_msg)


def main(args=None):
    rclpy.init(args=args)
    
    node = LidarObstacleAvoidanceNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info(
            f"Shutting down... Avoided {node.obstacles_avoided} obstacles!"
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()