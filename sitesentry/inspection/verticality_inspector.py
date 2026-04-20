"""
Verticality inspector for wall tilt measurement.

Measures wall tilt angle using ultrasonic sensors and IMU.
Applies tilt formula and generates inspection reports.
"""

import logging
import time
import math
from typing import Dict, Optional
from dataclasses import dataclass

from sitesentry import config
from sitesentry.hardware import UltrasonicSensor, IMUSensor, MotorController

logger = logging.getLogger(__name__)


@dataclass
class WallTiltResult:
    """Wall tilt measurement result."""
    d1: float  # lower sensor distance (meters)
    d2: float  # upper sensor distance (meters)
    alpha: float  # floor tilt angle (degrees)
    theta_final: float  # computed wall tilt (degrees)
    is_critical: bool  # True if exceeds WALL_TILT_THRESHOLD
    timestamp: float


class VerticalityInspector:
    """
    Wall verticality and tilt inspector.

    Measures wall angle using two ultrasonic sensors mounted on robot's right side.
    Compensates for floor tilt using IMU measurements.
    """

    def __init__(self, lower_sensor: UltrasonicSensor, upper_sensor: UltrasonicSensor,
                 imu_sensor: IMUSensor, motor_controller: MotorController):
        """
        Initialize verticality inspector.

        Args:
            lower_sensor: UltrasonicSensor for lower wall measurement.
            upper_sensor: UltrasonicSensor for upper wall measurement.
            imu_sensor: IMUSensor for floor tilt measurement.
            motor_controller: MotorController for stop command during measurement.
        """
        self.lower_sensor = lower_sensor
        self.upper_sensor = upper_sensor
        self.imu_sensor = imu_sensor
        self.motor_controller = motor_controller

        self.logger = logging.getLogger(self.__class__.__name__)

    def measure_wall_tilt(self) -> Optional[WallTiltResult]:
        """
        Perform full wall tilt inspection.

        Procedure:
        1. Stop robot and wait 1 second for mechanical settle
        2. Measure d1 (lower sensor distance)
        3. Measure d2 (upper sensor distance)
        4. Measure α (floor tilt from IMU)
        5. Apply formula: θ_Final = atan((d1 - d2) / h) * (180/π) - α
        6. Return results with critical flag

        Returns:
            WallTiltResult object, or None if measurement fails.
        """
        try:
            self.logger.info("Starting wall tilt measurement...")

            # Step 1: Stop and settle
            self.motor_controller.stop()
            time.sleep(config.MOTOR_SETTLE_TIME)

            # Step 2: Measure lower sensor (d1)
            d1 = self.lower_sensor.get_distance()
            if d1 is None:
                self.logger.error("Failed to measure lower sensor")
                return None

            self.logger.debug(f"Lower sensor: {d1:.3f}m")

            # Step 3: Measure upper sensor (d2)
            d2 = self.upper_sensor.get_distance()
            if d2 is None:
                self.logger.error("Failed to measure upper sensor")
                return None

            self.logger.debug(f"Upper sensor: {d2:.3f}m")

            # Step 4: Measure floor tilt (α)
            alpha_deg = self.imu_sensor.get_tilt_angle()

            self.logger.debug(f"Floor tilt: {alpha_deg:.3f}°")

            # Step 5: Compute wall tilt angle
            # θ = atan((d1 - d2) / h) * (180/π) - α
            delta_d = d1 - d2
            h = config.SENSOR_VERTICAL_GAP

            if h == 0:
                self.logger.error("Sensor vertical gap is zero!")
                return None

            theta_rad = math.atan(delta_d / h)
            theta_deg = math.degrees(theta_rad)

            # Apply floor tilt compensation
            theta_final = theta_deg - alpha_deg

            # Step 6: Check if critical
            is_critical = abs(theta_final) > config.WALL_TILT_THRESHOLD

            result = WallTiltResult(
                d1=d1,
                d2=d2,
                alpha=alpha_deg,
                theta_final=theta_final,
                is_critical=is_critical,
                timestamp=time.time()
            )

            status = "CRITICAL" if is_critical else "OK"
            self.logger.info(
                f"Wall tilt: {theta_final:.2f}° [{status}] "
                f"(d1={d1:.3f}m, d2={d2:.3f}m, α={alpha_deg:.2f}°)"
            )

            return result

        except Exception as e:
            self.logger.error(f"Wall tilt measurement error: {e}")
            return None

    def get_tilt_summary(self, result: WallTiltResult) -> str:
        """
        Get human-readable summary of tilt measurement.

        Args:
            result: WallTiltResult from measurement.

        Returns:
            Formatted summary string.
        """
        status = "🔴 CRITICAL" if result.is_critical else "🟢 OK"

        summary = (
            f"{status}\n"
            f"Wall Tilt: {result.theta_final:.2f}°\n"
            f"Lower Distance: {result.d1:.3f}m\n"
            f"Upper Distance: {result.d2:.3f}m\n"
            f"Floor Tilt: {result.alpha:.2f}°"
        )

        return summary
