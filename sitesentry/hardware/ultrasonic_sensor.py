"""
Ultrasonic sensor driver for HC-SR04.

Reads distance measurements from Arduino via serial connection.
Arduino handles the sensor hardware directly.
"""

import logging
from typing import Optional

from sitesentry import config

logger = logging.getLogger(__name__)


class UltrasonicSensor:
    """
    Ultrasonic distance sensor driver.

    Reads HC-SR04 measurements from Arduino.
    Two sensors: lower (bottom/trigger) and upper (top/echo).
    """

    def __init__(self, arduino_handler, sensor_type: str = "lower", simulate: bool = False):
        """
        Initialize ultrasonic sensor.

        Args:
            arduino_handler: Reference to ArduinoHandler instance.
            sensor_type: "lower" or "upper" sensor.
            simulate: If True, return synthetic data.
        """
        self.arduino = arduino_handler
        self.sensor_type = sensor_type  # "lower" or "upper"
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(f"{self.__class__.__name__}({sensor_type})")

        if self.simulate:
            self.logger.info(f"Ultrasonic sensor {sensor_type} in SIMULATE mode")
        else:
            self.logger.info(f"Ultrasonic sensor {sensor_type} connected via Arduino")

    def get_distance(self) -> Optional[float]:
        """
        Get distance measurement from Arduino.

        Returns:
            Distance in meters, or None if measurement fails.
        """
        if self.simulate:
            # Return synthetic distance with small variation
            import random
            return 0.45 + random.uniform(-0.05, 0.05)

        try:
            sensor_data = self.arduino.get_sensor_data()
            
            if self.sensor_type == "lower":
                distance = sensor_data.dist_bottom
            else:  # "upper"
                distance = sensor_data.dist_top
            
            # Validate reading
            if distance > 4.0:  # Ultrasonic max range ~4m
                self.logger.warning(f"Distance reading out of range: {distance}m")
                return None
            
            if distance < 0.02:  # Min range ~2cm
                self.logger.warning(f"Distance reading too close: {distance}m")
                return None
            
            self.logger.debug(f"Ultrasonic {self.sensor_type}: {distance:.3f}m")
            return distance

        except Exception as e:
            self.logger.error(f"Error getting distance: {e}")
            return None
