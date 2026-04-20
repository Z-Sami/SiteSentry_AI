"""
Configuration module for SiteSentry autonomous construction QA robot.

Centralizes all hardware pin numbers, constants, thresholds, and paths.
Loads sensitive data from environment variables via python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Dict, Any

# ============================================================================
# BASE PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent

# Load environment variables from .env file
# Try both sitesentry/.env and parent/.env locations
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)
DATA_DIR = PROJECT_ROOT / "sitesentry" / "data"
MODELS_DIR = PROJECT_ROOT / "sitesentry" / "models"
OUTPUTS_DIR = PROJECT_ROOT / "sitesentry" / "outputs"
LOGS_DIR = PROJECT_ROOT / "sitesentry" / "logs"

# Create directories if they don't exist
for directory in [DATA_DIR, MODELS_DIR, OUTPUTS_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# GPIO PIN CONFIGURATION (Raspberry Pi 4)
# ============================================================================
@dataclass
class MotorPins:
    """Motor driver (L298N) GPIO pin assignments."""
    # Left motor
    left_forward: int = 17
    left_backward: int = 27
    left_enable: int = 22  # PWM pin for speed control

    # Right motor
    right_forward: int = 23
    right_backward: int = 24
    right_enable: int = 25  # PWM pin for speed control


@dataclass
class EncoderPins:
    """Wheel encoder GPIO pin assignments."""
    left_encoder: int = 5
    right_encoder: int = 6


@dataclass
class UltrasonicPins:
    """Ultrasonic sensor GPIO pin assignments."""
    # Lower sensor (d1) - measures base wall distance
    lower_trig: int = 12
    lower_echo: int = 13

    # Upper sensor (d2) - measures top wall distance
    upper_trig: int = 16
    upper_echo: int = 19


@dataclass
class CameraPins:
    """Camera system GPIO pin assignments."""
    led_array: int = 26  # Auto-activates below 100 lux


@dataclass
class IMUConfig:
    """IMU (MPU6050) configuration."""
    i2c_bus: int = 1
    i2c_address: int = 0x68
    calibration_samples: int = 50


# ============================================================================
# HARDWARE INSTANTIATION
# ============================================================================
MOTOR_PINS = MotorPins()
ENCODER_PINS = EncoderPins()
ULTRASONIC_PINS = UltrasonicPins()
CAMERA_PINS = CameraPins()
IMU_CONFIG = IMUConfig()

# ============================================================================
# INSPECTION THRESHOLDS & CONSTANTS
# ============================================================================
# Vertical gap between upper and lower ultrasonic sensors (meters)
SENSOR_VERTICAL_GAP = 0.5

# Wall tilt angle threshold (degrees) - exceeding this triggers critical alert
WALL_TILT_THRESHOLD = 0.5

# Socket detection tolerance range (meters)
SOCKET_TOLERANCE_MIN = 0.05  # 5cm - used when confidence > 0.85
SOCKET_TOLERANCE_MAX = 0.15  # 15cm - used for lower confidence detections

# SLAM/localization confidence threshold
SLAM_CONFIDENCE_THRESHOLD = 0.8

# Ultrasonic sensor configuration
ULTRASONIC_MAX_DISTANCE = 4.0  # meters - max reliable distance
ULTRASONIC_TIMEOUT = 0.04  # seconds - max wait for echo
ULTRASONIC_READINGS_PER_SCAN = 5  # number of readings to average
ULTRASONIC_OUTLIER_STDDEV = 2.0  # discard readings > 2 sigma

# IMU/tilt measurement configuration
IMU_READINGS_PER_SCAN = 10  # number of readings to average for stability

# Motor control
PWM_FREQUENCY = 50  # Hz
MAX_MOTOR_SPEED = 100  # 0-100 percentage
MOTOR_SPEED_STRAIGHT = 50  # default speed for forward motion
MOTOR_SETTLE_TIME = 1.0  # seconds - wait after stop before scanning

# Navigation
POSITION_TOLERANCE = 0.03  # 3cm - acceptable distance to waypoint
HEADING_TOLERANCE = 5  # degrees
PID_KP = 0.5  # proportional gain
PID_KI = 0.1  # integral gain
PID_KD = 0.2  # derivative gain
MAX_LINEAR_SPEED = 0.5  # m/s
MAX_ANGULAR_SPEED = 0.5  # rad/s

# Encoder odometry
WHEEL_DIAMETER = 0.1  # meters
WHEEL_BASE = 0.25  # distance between left and right wheels (meters)
COUNTS_PER_REVOLUTION = 20  # encoder ticks per motor revolution

# Arduino (sensors interface via serial)
ARDUINO_SERIAL_PORT = "/dev/ttyACM0"  # Serial port for Arduino (USB on RPi)
ARDUINO_BAUDRATE = 9600  # Baud rate for Arduino (matches Arduino code: Serial.begin(9600))
ARDUINO_TIMEOUT = 1.0  # seconds - timeout for serial reads

# Camera
CAMERA_LIGHT_THRESHOLD = 100  # lux - below this, LED array activates
CAMERA_RESOLUTION = (1920, 1080)
CAMERA_FRAMERATE = 30

# LiDAR (RP LiDAR A1)
LIDAR_SERIAL_PORT = "/dev/ttyUSB0"
LIDAR_BAUDRATE = 115200
LIDAR_MOTOR_PWM = 50  # 0-100

# SLAM/Mapping
OCCUPANCY_GRID_RESOLUTION = 0.05  # 5cm per cell
OCCUPANCY_GRID_SIZE = 100  # 100x100 grid = 5m x 5m
ARUCO_MARKER_SIZE = 0.1  # 10cm markers

# ============================================================================
# FILE PATHS
# ============================================================================
BLUEPRINT_PATH = DATA_DIR / "blueprint.json"
WAYPOINTS_PATH = DATA_DIR / "waypoints.json"
ARUCO_MAP_PATH = DATA_DIR / "aruco_map.json"
DATABASE_PATH = DATA_DIR / "sitesentry.db"
YOLO_MODEL_PATH = MODELS_DIR / "socket_detector.pt"

# ============================================================================
# COMMUNICATION & EXTERNAL SERVICES
# ============================================================================
# Telegram Bot Configuration (loaded from environment variables)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Groq Llama 4 AI Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Connectivity check
CONNECTIVITY_CHECK_IP = "8.8.8.8"
CONNECTIVITY_CHECK_TIMEOUT = 5  # seconds
SYNC_INTERVAL = 30  # seconds - check for pending data to sync

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# SIMULATION MODE
# ============================================================================
# If True, hardware modules return synthetic data (useful for testing)
SIMULATE_HARDWARE = False

# ============================================================================
# UTILITY FUNCTION: Get all config as dict
# ============================================================================
def get_config_dict() -> Dict[str, Any]:
    """
    Return all configuration as a dictionary for logging/debugging.

    Returns:
        Dict containing all public config variables.
    """
    config = {
        # Paths
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "models_dir": str(MODELS_DIR),
        "outputs_dir": str(OUTPUTS_DIR),
        "logs_dir": str(LOGS_DIR),
        # Motors
        "motor_pins": MOTOR_PINS.__dict__,
        "encoder_pins": ENCODER_PINS.__dict__,
        "ultrasonic_pins": ULTRASONIC_PINS.__dict__,
        "camera_pins": CAMERA_PINS.__dict__,
        "imu_config": IMU_CONFIG.__dict__,
        # Thresholds
        "sensor_vertical_gap": SENSOR_VERTICAL_GAP,
        "wall_tilt_threshold": WALL_TILT_THRESHOLD,
        "socket_tolerance_min": SOCKET_TOLERANCE_MIN,
        "socket_tolerance_max": SOCKET_TOLERANCE_MAX,
        "slam_confidence_threshold": SLAM_CONFIDENCE_THRESHOLD,
        # Motor config
        "pwm_frequency": PWM_FREQUENCY,
        "max_motor_speed": MAX_MOTOR_SPEED,
        "motor_speed_straight": MOTOR_SPEED_STRAIGHT,
        "motor_settle_time": MOTOR_SETTLE_TIME,
        # Navigation
        "position_tolerance": POSITION_TOLERANCE,
        "heading_tolerance": HEADING_TOLERANCE,
        "pid_gains": {"kp": PID_KP, "ki": PID_KI, "kd": PID_KD},
        # File paths
        "blueprint_path": str(BLUEPRINT_PATH),
        "waypoints_path": str(WAYPOINTS_PATH),
        "aruco_map_path": str(ARUCO_MAP_PATH),
        "database_path": str(DATABASE_PATH),
        "yolo_model_path": str(YOLO_MODEL_PATH),
        # Communication
        "telegram_token_set": bool(TELEGRAM_BOT_TOKEN),
        "sync_interval": SYNC_INTERVAL,
        # Hardware simulation
        "simulate_hardware": SIMULATE_HARDWARE,
    }
    return config
