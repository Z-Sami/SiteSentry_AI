"""
LiDAR handler for RP LiDAR A1.

Manages 2D LiDAR scanning via serial USB connection.
Runs scan in background thread with thread-safe data buffer.
"""

import logging
import time
import threading
from typing import List, Tuple, Optional
from collections import deque
from dataclasses import dataclass
import math

try:
    from rplidar import RPLidar
except ImportError:
    RPLidar = None

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class ScanPoint:
    """Single LiDAR scan point."""
    angle: float  # degrees (0-360)
    distance: float  # meters
    quality: int  # 0-15 signal quality


class LidarHandler:
    """
    RP LiDAR A1 handler.

    Manages USB serial connection and 360° 2D scans.
    Runs scanning in background thread for non-blocking operation.
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize LiDAR handler.

        Args:
            simulate: If True, return synthetic scan data without USB access.
        """
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        self.lidar = None
        self.is_scanning = False
        self.scan_thread = None
        self.latest_scan = deque(maxlen=360)  # Store latest points
        self.scan_lock = threading.Lock()

        if self.simulate:
            self.logger.info("LiDAR in SIMULATE mode")
            return

        try:
            if RPLidar:
                self.lidar = RPLidar(port=config.LIDAR_SERIAL_PORT,
                                    baudrate=config.LIDAR_BAUDRATE,
                                    timeout=3)
                # Check if lidar is connected
                info = self.lidar.get_info()
                self.logger.info(f"LiDAR connected: {info}")
                self.logger.info("LiDAR handler initialized")
            else:
                raise ImportError("rplidar library not available")
        except Exception as e:
            self.logger.error(f"Failed to initialize LiDAR: {e}")
            self.simulate = True

    def start_scan(self) -> None:
        """Start continuous background scanning."""
        if self.simulate:
            self.logger.info("LiDAR scanning started (simulated)")
            self.is_scanning = True
            return

        if self.is_scanning:
            self.logger.warning("LiDAR already scanning")
            return

        try:
            if self.lidar:
                self.is_scanning = True
                self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
                self.scan_thread.start()
                self.logger.info("LiDAR scanning started")
        except Exception as e:
            self.logger.error(f"Failed to start scan: {e}")

    def stop_scan(self) -> None:
        """Stop background scanning."""
        self.is_scanning = False

        if self.scan_thread:
            self.scan_thread.join(timeout=2.0)

        if self.lidar:
            try:
                self.lidar.stop()
                self.lidar.disconnect()
            except Exception as e:
                self.logger.warning(f"Error stopping lidar: {e}")

        self.logger.info("LiDAR scanning stopped")

    def _scan_loop(self) -> None:
        """
        Background thread loop: continuously scan and buffer latest points.
        """
        try:
            iterator = self.lidar.iter_scans()
            for scan in iterator:
                if not self.is_scanning:
                    break

                with self.scan_lock:
                    self.latest_scan.clear()
                    for quality, angle, distance in scan:
                        point = ScanPoint(
                            angle=angle,
                            distance=distance / 1000.0,  # Convert to meters
                            quality=quality
                        )
                        self.latest_scan.append(point)

        except Exception as e:
            if self.is_scanning:
                self.logger.error(f"Error in scan loop: {e}")

    def get_scan_data(self) -> List[ScanPoint]:
        """
        Get latest complete 360° scan data.

        Returns:
            List of ScanPoint objects, or empty list if no data available.
        """
        if self.simulate:
            # Return synthetic scan data
            return self._generate_synthetic_scan()

        try:
            with self.scan_lock:
                return list(self.latest_scan)
        except Exception as e:
            self.logger.error(f"Error getting scan data: {e}")
            return []

    def get_nearest_wall_distance(self, angle_range: Tuple[float, float] = (0, 180)) -> Optional[float]:
        """
        Get nearest obstacle within specified angle range.

        Useful for finding closest wall in front of robot.

        Args:
            angle_range: (min_angle, max_angle) in degrees. Defaults to front hemisphere.

        Returns:
            Minimum distance in meters, or None if no points in range.
        """
        scan = self.get_scan_data()

        if not scan:
            return None

        # Filter points within angle range
        nearby_distances = []
        for point in scan:
            if angle_range[0] <= point.angle <= angle_range[1]:
                if 0 < point.distance < config.ULTRASONIC_MAX_DISTANCE:
                    nearby_distances.append(point.distance)

        if nearby_distances:
            return min(nearby_distances)

        return None

    def _generate_synthetic_scan(self) -> List[ScanPoint]:
        """Generate synthetic LiDAR scan data for testing."""
        import random
        scan = []
        for angle in range(0, 360, 10):
            distance = 1.0 + random.uniform(-0.1, 0.1)
            scan.append(ScanPoint(angle=angle, distance=distance, quality=15))
        return scan

    def cleanup(self) -> None:
        """Clean up LiDAR resources."""
        self.stop_scan()
        if self.lidar:
            try:
                self.lidar.disconnect()
                self.logger.info("LiDAR cleaned up")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
