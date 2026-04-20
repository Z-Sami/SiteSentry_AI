"""
SLAM handler for SiteSentry.

Implements simplified 2D occupancy grid mapping using Bresenham line algorithm.
Combines LiDAR scan data with odometry for pose estimation.
"""

import logging
import numpy as np
import math
import time
import json
from pathlib import Path
from typing import Tuple, List, Optional
from dataclasses import dataclass
from threading import Lock

from sitesentry import config
from sitesentry.hardware.lidar_handler import ScanPoint

logger = logging.getLogger(__name__)


@dataclass
class Pose:
    """Robot pose in world frame."""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    theta: float = 0.0  # radians
    confidence: float = 1.0  # 0.0-1.0
    timestamp: float = 0.0


class SLAMHandler:
    """
    Simplified SLAM using occupancy grid.

    Uses Bresenham line algorithm to mark LiDAR scan rays on a 2D occupancy grid.
    Combines with odometry for pose tracking.
    Supports ArUco marker corrections for drift compensation.
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize SLAM handler.

        Args:
            simulate: If True, operate without LiDAR/hardware feedback.
        """
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        # Occupancy grid
        self.grid_resolution = config.OCCUPANCY_GRID_RESOLUTION  # meters per cell
        self.grid_size = config.OCCUPANCY_GRID_SIZE  # grid is NxN
        self.grid_meters = self.grid_size * self.grid_resolution  # total map size

        # Create occupancy grid (-1 = unknown, 0 = free, 100 = occupied)
        self.occupancy_grid = np.full(
            (self.grid_size, self.grid_size), -1, dtype=np.int8
        )

        # Pose tracking
        self.pose = Pose(timestamp=time.time())
        self.pose_lock = Lock()

        # Confidence tracking for localization
        self.confidence = 1.0
        self.integrated_error = 0.0

        self.logger.info(
            f"SLAM initialized: {self.grid_size}x{self.grid_size} "
            f"cells @ {self.grid_resolution}m resolution"
        )

    def update(self, scan_data: List[ScanPoint], odometry_pose: Tuple[float, float, float]) -> None:
        """
        Update SLAM with new LiDAR scan and odometry.

        Args:
            scan_data: List of LiDAR ScanPoint objects from latest 360° scan.
            odometry_pose: Tuple of (x, y, theta) from motor controller odometry.
        """
        try:
            with self.pose_lock:
                # Update pose from odometry
                self.pose.x = odometry_pose[0]
                self.pose.y = odometry_pose[1]
                self.pose.theta = odometry_pose[2]
                self.pose.timestamp = time.time()

                # Update occupancy grid from LiDAR scan
                if scan_data:
                    self._update_occupancy_grid(scan_data)

                    # Adjust confidence based on scan quality
                    self._update_confidence(scan_data)

        except Exception as e:
            self.logger.error(f"Error updating SLAM: {e}")

    def _update_occupancy_grid(self, scan_data: List[ScanPoint]) -> None:
        """
        Update occupancy grid using Bresenham line algorithm.

        For each LiDAR ray, mark the path as free and the endpoint as occupied.

        Args:
            scan_data: List of ScanPoint objects.
        """
        try:
            # Robot cell coordinates in grid
            robot_grid_x = self._world_to_grid_x(self.pose.x)
            robot_grid_y = self._world_to_grid_y(self.pose.y)

            for point in scan_data:
                if point.quality < 5:  # Skip low-quality points
                    continue

                # Convert LiDAR angle to world frame angle
                world_angle = self.pose.theta + math.radians(point.angle)

                # Compute world coordinates of scan endpoint
                endpoint_x = self.pose.x + point.distance * math.cos(world_angle)
                endpoint_y = self.pose.y + point.distance * math.sin(world_angle)

                # Convert to grid coordinates
                endpoint_grid_x = self._world_to_grid_x(endpoint_x)
                endpoint_grid_y = self._world_to_grid_y(endpoint_y)

                # Use Bresenham to mark ray path as free
                cells = self._bresenham_line(
                    robot_grid_x, robot_grid_y,
                    endpoint_grid_x, endpoint_grid_y
                )

                # Mark ray cells as free (but not endpoint)
                for i, (cx, cy) in enumerate(cells[:-1]):
                    if self._is_valid_grid_cell(cx, cy):
                        if self.occupancy_grid[cy, cx] != 100:
                            self.occupancy_grid[cy, cx] = max(0, self.occupancy_grid[cy, cx] - 10)

                # Mark endpoint as occupied
                if self._is_valid_grid_cell(endpoint_grid_x, endpoint_grid_y):
                    if point.distance < config.ULTRASONIC_MAX_DISTANCE:
                        self.occupancy_grid[endpoint_grid_y, endpoint_grid_x] = 100

        except Exception as e:
            self.logger.debug(f"Error updating grid: {e}")

    def _update_confidence(self, scan_data: List[ScanPoint]) -> None:
        """
        Update localization confidence based on scan consistency.

        Args:
            scan_data: List of ScanPoint objects.
        """
        # Count good quality points
        good_points = sum(1 for p in scan_data if p.quality > 10)

        # Confidence based on point count
        if good_points > 100:
            self.confidence = min(1.0, self.confidence + 0.05)
        else:
            self.confidence = max(0.5, self.confidence - 0.1)

    def get_current_pose(self) -> Pose:
        """
        Get current robot pose estimate.

        Returns:
            Pose object with (x, y, theta) and confidence.
        """
        with self.pose_lock:
            return Pose(
                x=self.pose.x,
                y=self.pose.y,
                theta=self.pose.theta,
                confidence=self.confidence,
                timestamp=self.pose.timestamp
            )

    def get_localization_confidence(self) -> float:
        """
        Get current localization confidence (0.0 to 1.0).

        Returns:
            Float between 0.0 (no confidence) and 1.0 (high confidence).
        """
        return self.confidence

    def reset_pose(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0) -> None:
        """
        Hard-reset pose (e.g., after ArUco marker detection).

        Args:
            x: New X position in meters.
            y: New Y position in meters.
            theta: New orientation in radians.
        """
        with self.pose_lock:
            self.pose.x = x
            self.pose.y = y
            self.pose.theta = theta
            self.pose.timestamp = time.time()
            self.confidence = 0.8  # Reduce confidence after reset
            self.logger.info(f"Pose reset to ({x:.2f}, {y:.2f}, {math.degrees(theta):.1f}°)")

    def save_map(self, filepath: str) -> bool:
        """
        Save occupancy grid to NPZ file.

        Args:
            filepath: Path where map should be saved.

        Returns:
            True if successful, False otherwise.
        """
        try:
            np.savez(
                filepath,
                grid=self.occupancy_grid,
                pose_x=self.pose.x,
                pose_y=self.pose.y,
                pose_theta=self.pose.theta,
                resolution=self.grid_resolution,
                timestamp=self.pose.timestamp
            )
            self.logger.info(f"Map saved to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save map: {e}")
            return False

    def load_map(self, filepath: str) -> bool:
        """
        Load occupancy grid from NPZ file.

        Args:
            filepath: Path to map file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            data = np.load(filepath)
            self.occupancy_grid = data["grid"]
            self.pose.x = float(data["pose_x"])
            self.pose.y = float(data["pose_y"])
            self.pose.theta = float(data["pose_theta"])
            self.pose.timestamp = float(data["timestamp"])
            self.logger.info(f"Map loaded from {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load map: {e}")
            return False

    def get_occupancy_grid(self) -> np.ndarray:
        """
        Get current occupancy grid for visualization.

        Returns:
            2D numpy array (-1=unknown, 0=free, 100=occupied).
        """
        return self.occupancy_grid.copy()

    @staticmethod
    def _bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """
        Bresenham line algorithm to get cells along a line.

        Args:
            x0, y0: Start cell coordinates.
            x1, y1: End cell coordinates.

        Returns:
            List of (x, y) cell coordinates along the line.
        """
        cells = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        while True:
            cells.append((x, y))
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

        return cells

    def _world_to_grid_x(self, world_x: float) -> int:
        """Convert world X coordinate to grid column index."""
        grid_x = int((world_x + self.grid_meters / 2) / self.grid_resolution)
        return max(0, min(self.grid_size - 1, grid_x))

    def _world_to_grid_y(self, world_y: float) -> int:
        """Convert world Y coordinate to grid row index."""
        grid_y = int((world_y + self.grid_meters / 2) / self.grid_resolution)
        return max(0, min(self.grid_size - 1, grid_y))

    def _is_valid_grid_cell(self, x: int, y: int) -> bool:
        """Check if grid cell coordinates are valid."""
        return 0 <= x < self.grid_size and 0 <= y < self.grid_size
