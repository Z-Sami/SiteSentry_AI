#!/usr/bin/env python3
"""
SITESENTRY - Vision System for Socket Detection & ArUco Markers
Detects electrical sockets using YOLO and resets SLAM drift with ArUco markers
"""

import cv2
import numpy as np
from ultralytics import YOLO
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import json
from datetime import datetime

class SitesentryVisionNode(Node):
    def __init__(self):
        super().__init__('sitesentry_vision')
        
        self.bridge = CvBridge()
        
        # Load YOLO model (for socket detection)
        self.get_logger().info("Loading YOLOv8 model...")
        self.yolo_model = YOLO('yolov8n.pt')  # Or your custom model
        
        # ArUco marker setup
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        
        # Subscribers
        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)
        
        # Publishers
        self.detections_pub = self.create_publisher(
            String, 'sitesentry/socket_detections', 10)
        self.aruco_pub = self.create_publisher(
            String, 'sitesentry/aruco_marker', 10)
        self.annotated_image_pub = self.create_publisher(
            Image, 'sitesentry/detections_image', 10)
        
        # Socket database (CAD coordinates)
        self.cad_sockets = self.load_cad_database()
        
        # SLAM reset threshold
        self.aruco_reset_threshold = 0.5  # meters
        
        self.get_logger().info("SiteSentry Vision Node initialized!")
    
    def load_cad_database(self):
        """Load CAD blueprint socket coordinates"""
        # Example format: {room_id: [(x, y), (x, y), ...]}
        return {
            "room_104": [
                (1.5, 0.5),  # Socket 1
                (1.5, 2.0),  # Socket 2
                (3.0, 0.5),  # Socket 3
                (3.0, 2.0),  # Socket 4
                (4.5, 1.0),  # Socket 5 (missing in this example)
            ]
        }
    
    def image_callback(self, msg):
        """Process incoming camera frames"""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            
            # Detect ArUco markers (SLAM drift correction)
            self.detect_aruco_markers(cv_image)
            
            # Detect sockets using YOLO
            detections = self.detect_sockets(cv_image)
            
            # Publish results
            self.publish_detections(detections)
            
            # Create annotated image for visualization
            annotated = self.draw_detections(cv_image, detections)
            self.publish_annotated_image(annotated)
            
        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")
    
    def detect_aruco_markers(self, image):
        """
        Detect ArUco markers for SLAM drift reset
        When a marker is detected, publish reset command to SLAM node
        """
        corners, ids, rejected = self.detector.detectMarkers(image)
        
        if ids is not None and len(ids) > 0:
            # Found ArUco marker - trigger SLAM reset
            marker_id = ids[0][0]
            marker_data = {
                'timestamp': datetime.now().isoformat(),
                'marker_id': int(marker_id),
                'action': 'SLAM_RESET',
                'message': f'ArUco marker {marker_id} detected - Resetting SLAM coordinates'
            }
            
            # Publish reset command
            msg = String()
            msg.data = json.dumps(marker_data)
            self.aruco_pub.publish(msg)
            
            self.get_logger().info(f"ArUco Marker {marker_id} detected - SLAM reset triggered!")
            
            # Draw markers on image
            cv2.aruco.drawDetectedMarkers(image, corners, ids)
    
    def detect_sockets(self, image):
        """
        Detect electrical sockets using YOLOv8
        Returns: List of detections with bounding boxes and confidence
        """
        # Run YOLO inference
        results = self.yolo_model(image)
        
        detections = []
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # Filter for socket class (adjust based on your YOLO training)
                    if confidence > 0.5:  # Confidence threshold
                        # Calculate center point
                        center_x = (x1 + x2) / 2.0
                        center_y = (y1 + y2) / 2.0
                        
                        # Project image coordinates to world coordinates
                        # (This requires camera calibration - simplified version)
                        world_x, world_y = self.pixel_to_world(center_x, center_y, image)
                        
                        detection = {
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'center': [float(center_x), float(center_y)],
                            'world_coord': [world_x, world_y],
                            'confidence': confidence,
                            'class': int(class_id),
                            'match_status': 'UNKNOWN'  # Will be updated by matching logic
                        }
                        
                        detections.append(detection)
        
        # Match detections with CAD blueprint
        detections = self.match_with_cad(detections)
        
        return detections
    
    def pixel_to_world(self, px, py, image):
        """
        Convert pixel coordinates to world coordinates
        Simplified version - requires camera calibration matrix in production
        """
        # In production, use proper camera calibration (K matrix, distortion coeffs)
        # For now, simple linear mapping
        h, w = image.shape[:2]
        
        # Assume camera viewing from height 0.5m, looking down at 45 degrees
        world_x = (px / w) * 5.0  # 5 meters width
        world_y = (py / h) * 3.0  # 3 meters depth
        
        return world_x, world_y
    
    def match_with_cad(self, detections):
        """
        Match detected sockets with CAD blueprint
        Uses adaptive tolerance (5-15cm radius)
        """
        current_room = "room_104"  # In production, determine from SLAM/navigation
        cad_coords = self.cad_sockets.get(current_room, [])
        
        # Matching tolerance (5-15cm based on SLAM confidence)
        tolerance = 0.10  # 10cm default (adjust based on SLAM covariance)
        
        matched_indices = set()
        
        for detection in detections:
            detected_x, detected_y = detection['world_coord']
            best_distance = float('inf')
            best_cad_idx = -1
            
            # Find closest CAD socket
            for i, (cad_x, cad_y) in enumerate(cad_coords):
                if i not in matched_indices:
                    distance = np.sqrt((detected_x - cad_x)**2 + (detected_y - cad_y)**2)
                    
                    if distance < best_distance:
                        best_distance = distance
                        best_cad_idx = i
            
            # Update match status
            if best_distance <= tolerance:
                detection['match_status'] = 'MATCH'
                detection['cad_index'] = best_cad_idx
                detection['distance_to_cad'] = best_distance
                matched_indices.add(best_cad_idx)
            else:
                detection['match_status'] = 'EXTRA'  # Unregistered socket
        
        # Check for missing sockets
        missing_sockets = []
        for i in range(len(cad_coords)):
            if i not in matched_indices:
                missing_sockets.append({
                    'cad_index': i,
                    'cad_coord': cad_coords[i],
                    'status': 'MISSING'
                })
        
        return detections, missing_sockets
    
    def publish_detections(self, result):
        """Publish detection results to ROS 2"""
        detections, missing_sockets = result
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_detected': len(detections),
            'matches': sum(1 for d in detections if d['match_status'] == 'MATCH'),
            'extra': sum(1 for d in detections if d['match_status'] == 'EXTRA'),
            'missing': len(missing_sockets),
            'detections': detections,
            'missing_sockets': missing_sockets
        }
        
        msg = String()
        msg.data = json.dumps(output, default=str)
        self.detections_pub.publish(msg)
        
        # Also log to console
        self.get_logger().info(
            f"Sockets: {output['matches']} Match, "
            f"{output['extra']} Extra, "
            f"{output['missing']} Missing"
        )
    
    def draw_detections(self, image, result):
        """Draw detected sockets and CAD overlays on image"""
        detections, missing_sockets = result
        annotated = image.copy()
        
        # Draw detections
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Color based on match status
            if detection['match_status'] == 'MATCH':
                color = (0, 255, 0)  # Green
                label = 'MATCH'
            elif detection['match_status'] == 'EXTRA':
                color = (0, 165, 255)  # Orange
                label = 'EXTRA'
            else:
                color = (0, 0, 255)  # Red
                label = 'UNKNOWN'
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            cv2.putText(annotated, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw world coordinates
            text = f"({detection['world_coord'][0]:.2f}, {detection['world_coord'][1]:.2f})"
            cv2.putText(annotated, text, (x1, y2+15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Draw statistics
        stats_text = f"Detected: {len(detections)} | Missing: {len(missing_sockets)}"
        cv2.putText(annotated, stats_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return annotated
    
    def publish_annotated_image(self, image):
        """Publish annotated image for visualization"""
        try:
            msg = self.bridge.cv2_to_imgmsg(image, "bgr8")
            self.annotated_image_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing annotated image: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = SitesentryVisionNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
