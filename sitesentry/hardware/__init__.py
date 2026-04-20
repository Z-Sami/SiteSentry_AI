"""
Hardware module for SiteSentry.

Provides drivers for all robot hardware components:
- Arduino interface (sensors hub)
- Motor controller with odometry
- IMU sensor (MPU6050) via Arduino
- Ultrasonic sensors via Arduino
- LiDAR scanner
- Camera system
"""

from .arduino_handler import ArduinoHandler
from .motor_controller import MotorController
from .imu_sensor import IMUSensor
from .ultrasonic_sensor import UltrasonicSensor
from .lidar_handler import LidarHandler
from .camera_handler import CameraHandler

__all__ = [
    "ArduinoHandler",
    "MotorController",
    "IMUSensor",
    "UltrasonicSensor",
    "LidarHandler",
    "CameraHandler",
]
