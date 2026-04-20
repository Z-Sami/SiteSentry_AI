"""
IMU sensor driver for MPU6050.

Reads floor tilt angle from Arduino via serial connection.
Arduino handles the MPU6050 hardware directly via I2C.
"""

import logging
from typing import Optional

from sitesentry import config

logger = logging.getLogger(__name__)


class IMUSensor:
    """
    MPU6050 IMU sensor driver.

    Reads tilt angle from Arduino which runs MPU6050 on I2C.
    Measures floor incline to detect wall tilt during inspection.
    """

    def __init__(self, arduino_handler, simulate: bool = False):
        """
        Initialize IMU sensor.

        Args:
            arduino_handler: Reference to ArduinoHandler instance.
            simulate: If True, return synthetic data.
        """
        self.arduino = arduino_handler
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        if self.simulate:
            self.logger.info("IMU sensor in SIMULATE mode")
        else:
            self.logger.info("IMU sensor (MPU6050) connected via Arduino")

    def get_tilt_angle(self) -> float:
        """
        Get current floor tilt angle from Arduino.

        Returns:
            Tilt angle in degrees (positive = tilted up, negative = tilted down).
        """
        if self.simulate:
            # Return small random variation for testing
            import random
            return random.uniform(-0.5, 0.5)

        try:
            sensor_data = self.arduino.get_sensor_data()
            
            # Arduino sends robotAngle in degrees
            angle = sensor_data.robot_angle
            
            # Validate reading
            if abs(angle) > 90.0:  # Unreasonable tilt
                self.logger.warning(f"IMU angle out of range: {angle}°")
                return 0.0
            
            self.logger.debug(f"IMU tilt angle: {angle:.2f}°")
            return angle

        except Exception as e:
            self.logger.error(f"Error reading tilt angle: {e}")
            return 0.0
