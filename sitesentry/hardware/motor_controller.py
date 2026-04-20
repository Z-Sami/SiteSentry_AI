"""
Motor controller for differential drive robot.

Manages motor control via Arduino and reads encoder odometry from Arduino.
Arduino handles PWM motor control (L298N) directly.
"""

import logging
import time
import math
from typing import Tuple
from dataclasses import dataclass
from threading import Lock

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    GPIO = None

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class OdometryData:
    """Odometry position and orientation."""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    timestamp: float = 0.0


class MotorController:
    """
    Manages motor control for 4WD differential drive robot.

    Communicates with Arduino which handles:
    - PWM control of motors (L298N driver)
    - Reading wheel encoders (4 wheels)
    - Computing tilt angle from MPU6050
    
    Uses differential drive kinematics for odometry.
    """

    def __init__(self, arduino_handler, simulate: bool = False):
        """
        Initialize motor controller.

        Args:
            arduino_handler: Reference to ArduinoHandler instance.
            simulate: If True, return synthetic data without Arduino.
        """
        self.arduino = arduino_handler
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        # Odometry tracking
        self.prev_encoder_fr = 0  # Front-right encoder
        self.prev_encoder_fl = 0  # Front-left encoder
        self.odom = OdometryData(timestamp=time.time())
        self.odom_lock = Lock()

        if self.simulate:
            self.logger.info("Motor controller in SIMULATE mode")
        else:
            self.logger.info("Motor controller connected via Arduino")

    def move_forward(self, speed: int = None) -> None:
        """
        Move forward at given speed (0-100).

        Args:
            speed: Motor speed percentage (0-100). Defaults to config.MOTOR_SPEED_STRAIGHT.
        """
        if speed is None:
            speed = config.MOTOR_SPEED_STRAIGHT
        self.set_motor_speeds(speed, speed)

    def move_backward(self, speed: int = None) -> None:
        """
        Move backward at given speed (0-100).

        Args:
            speed: Motor speed percentage (0-100). Defaults to config.MOTOR_SPEED_STRAIGHT.
        """
        if speed is None:
            speed = config.MOTOR_SPEED_STRAIGHT
        self.set_motor_speeds(-speed, -speed)

    def turn_left(self, speed: int = None) -> None:
        """
        Turn left (rotate counter-clockwise).

        Args:
            speed: Motor speed percentage (0-100).
        """
        if speed is None:
            speed = config.MOTOR_SPEED_STRAIGHT
        self.set_motor_speeds(-speed, speed)

    def turn_right(self, speed: int = None) -> None:
        """
        Turn right (rotate clockwise).

        Args:
            speed: Motor speed percentage (0-100).
        """
        if speed is None:
            speed = config.MOTOR_SPEED_STRAIGHT
        self.set_motor_speeds(speed, -speed)

    def set_motor_speeds(self, left_speed: int, right_speed: int) -> None:
        """
        Set individual left and right motor speeds via Arduino.

        Args:
            left_speed: Left motor speed (-100 to 100). Positive = forward, negative = backward.
            right_speed: Right motor speed (-100 to 100).
        """
        if self.simulate:
            self.logger.debug(f"[SIMULATE] Motors: L={left_speed}, R={right_speed}")
            return

        try:
            left_speed = max(-100, min(100, left_speed))
            right_speed = max(-100, min(100, right_speed))
            
            # Send motor command to Arduino
            # Format: "M,left_speed,right_speed" (e.g., "M,150,150" for forward)
            command = f"M,{left_speed},{right_speed}"
            self.arduino.send_command(command)
            
            self.logger.debug(f"Motor command: {command}")

        except Exception as e:
            self.logger.error(f"Error setting motor speeds: {e}")

    def stop(self) -> None:
        """Stop all motors immediately."""
        self.set_motor_speeds(0, 0)

    def get_odometry(self) -> OdometryData:
        """
        Get current odometry (position and orientation).

        Reads encoder counts from Arduino and uses differential drive kinematics:
            - Δx = (Δs_left + Δs_right) / 2 * cos(θ)
            - Δy = (Δs_left + Δs_right) / 2 * sin(θ)
            - Δθ = (Δs_right - Δs_left) / wheelbase

        Returns:
            OdometryData: Current (x, y, theta) and timestamp.
        """
        if self.simulate:
            # Return dummy odometry for simulation
            with self.odom_lock:
                self.odom.timestamp = time.time()
                return OdometryData(
                    x=self.odom.x,
                    y=self.odom.y,
                    theta=self.odom.theta,
                    timestamp=self.odom.timestamp
                )

        try:
            sensor_data = self.arduino.get_sensor_data()
            
            with self.odom_lock:
                # Get current encoder counts
                curr_encoder_fr = sensor_data.encoder_fr
                curr_encoder_fl = sensor_data.encoder_fl
                
                # Calculate delta ticks
                delta_fr_ticks = curr_encoder_fr - self.prev_encoder_fr
                delta_fl_ticks = curr_encoder_fl - self.prev_encoder_fl
                
                # Update previous values
                self.prev_encoder_fr = curr_encoder_fr
                self.prev_encoder_fl = curr_encoder_fl
                
                # Convert ticks to distance (meters)
                meters_per_tick = (math.pi * config.WHEEL_DIAMETER) / config.COUNTS_PER_REVOLUTION
                delta_fr_distance = delta_fr_ticks * meters_per_tick
                delta_fl_distance = delta_fl_ticks * meters_per_tick
                
                # Use average of front wheels for differential drive
                delta_distance = (delta_fr_distance + delta_fl_distance) / 2.0
                delta_theta = (delta_fr_distance - delta_fl_distance) / config.WHEEL_BASE
                
                # Update position
                self.odom.x += delta_distance * math.cos(self.odom.theta)
                self.odom.y += delta_distance * math.sin(self.odom.theta)
                self.odom.theta += delta_theta
                self.odom.timestamp = time.time()
                
                return OdometryData(
                    x=self.odom.x,
                    y=self.odom.y,
                    theta=self.odom.theta,
                    timestamp=self.odom.timestamp
                )
                
        except Exception as e:
            self.logger.error(f"Error getting odometry: {e}")
            return OdometryData(timestamp=time.time())

    def reset_odometry(self) -> None:
        """Reset odometry to origin (0, 0, 0)."""
        with self.odom_lock:
            self.odom = OdometryData(timestamp=time.time())
            self.prev_encoder_fr = 0
            self.prev_encoder_fl = 0
            self.logger.info("Odometry reset to origin")

    def cleanup(self) -> None:
        """Clean up motor controller resources."""
        try:
            self.stop()
            self.logger.info("Motor controller cleaned up")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
