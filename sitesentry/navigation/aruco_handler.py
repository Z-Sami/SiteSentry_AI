"""
ArUco marker handler for localization correction.

Detects ArUco markers in camera images and applies pose corrections to SLAM.
"""

import logging
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class MarkerDetection:
    """Detected ArUco marker information."""
    marker_id: int
    corners: np.ndarray  # 4x2 array of corner points
    distance: float  # estimated distance to marker in meters
    angle: float  # bearing angle in degrees


class ArucoHandler:
    """
    ArUco marker detection and pose correction.

    Detects 4x4 ArUco markers placed at known locations.
    When detected, corrects SLAM pose to marker's known world position.
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize ArUco handler.

        Args:
            simulate: If True, return synthetic detections without OpenCV.
        """
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        self.aruco_dict = None
        self.parameters = None
        self.known_positions = {}  # marker_id -> (x, y, theta)

        self._load_known_positions()

        if self.simulate:
            self.logger.info("ArUco handler in SIMULATE mode")
            return

        try:
            if cv2:
                # Use ArUco dictionary and detector
                self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
                self.parameters = cv2.aruco.DetectorParameters()
                self.logger.info("ArUco handler initialized")
            else:
                raise ImportError("opencv-contrib-python not available")
        except Exception as e:
            self.logger.error(f"Failed to initialize ArUco handler: {e}")
            self.simulate = True

    def _load_known_positions(self) -> None:
        """
        Load known marker positions from JSON file.

        Expected format:
        {
            "markers": [
                {"id": 0, "x": 1.0, "y": 2.5, "theta": 0.0},
                ...
            ]
        }
        """
        try:
            aruco_map_path = config.ARUCO_MAP_PATH

            if aruco_map_path.exists():
                with open(aruco_map_path, "r") as f:
                    data = json.load(f)
                    for marker in data.get("markers", []):
                        marker_id = marker["id"]
                        self.known_positions[marker_id] = (
                            marker["x"],
                            marker["y"],
                            math.radians(marker.get("theta", 0.0))
                        )

                self.logger.info(f"Loaded {len(self.known_positions)} marker positions")
            else:
                self.logger.warning(f"ArUco map file not found: {aruco_map_path}")

        except Exception as e:
            self.logger.error(f"Failed to load known marker positions: {e}")

    def detect_markers(self, frame: np.ndarray) -> List[MarkerDetection]:
        """
        Detect ArUco markers in image frame.

        Args:
            frame: Image frame as numpy array (BGR or RGB).

        Returns:
            List of MarkerDetection objects.
        """
        if self.simulate:
            # Return synthetic detection
            return self._generate_synthetic_detection()

        if not cv2 or frame is None:
            return []

        try:
            # Convert BGR to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Detect markers
            detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
            corners, ids, rejected = detector.detectMarkers(gray)

            detections = []

            if ids is not None:
                for marker_idx, marker_id in enumerate(ids.flatten()):
                    corner = corners[marker_idx][0]  # 4x2 array

                    # Estimate distance from marker size
                    distance = self._estimate_distance(corner)

                    # Estimate bearing angle
                    center = np.mean(corner, axis=0)
                    angle = self._estimate_bearing(center, frame.shape[1])

                    detection = MarkerDetection(
                        marker_id=int(marker_id),
                        corners=corner,
                        distance=distance,
                        angle=angle
                    )
                    detections.append(detection)

            if detections:
                self.logger.debug(f"Detected {len(detections)} ArUco markers")

            return detections

        except Exception as e:
            self.logger.error(f"Error detecting markers: {e}")
            return []

    def get_correction_pose(self, marker_id: int, current_pose: Tuple[float, float, float]
                           ) -> Optional[Tuple[float, float, float]]:
        """
        Get corrected pose based on detected marker.

        Args:
            marker_id: ID of detected marker.
            current_pose: Current robot pose (x, y, theta).

        Returns:
            Corrected pose (x, y, theta), or None if marker unknown.
        """
        if marker_id not in self.known_positions:
            self.logger.warning(f"Marker {marker_id} not in known positions")
            return None

        # Get known marker position
        known_x, known_y, known_theta = self.known_positions[marker_id]

        # Simple approach: reset to marker's known position
        # In production, use more sophisticated pose graph optimization
        return (known_x, known_y, known_theta)

    def _estimate_distance(self, corner: np.ndarray) -> float:
        """
        Estimate distance to ArUco marker from corner positions.

        Marker size assumed to be 10cm (config.ARUCO_MARKER_SIZE).

        Args:
            corner: 4x2 array of marker corner pixel coordinates.

        Returns:
            Estimated distance in meters.
        """
        try:
            # Use marker size in pixels to estimate distance
            marker_size_pixels = np.linalg.norm(corner[0] - corner[1])

            # Focal length (approximate for typical camera)
            focal_length = 800  # pixels

            # Distance = (marker_real_size * focal_length) / marker_size_pixels
            distance = (config.ARUCO_MARKER_SIZE * focal_length) / marker_size_pixels

            return max(0.1, min(5.0, distance))  # Clamp to reasonable range

        except Exception:
            return 1.0  # Default distance

    def _estimate_bearing(self, center: Tuple[float, float], image_width: int) -> float:
        """
        Estimate bearing angle to marker center in image.

        Args:
            center: (x, y) pixel coordinates of marker center.
            image_width: Width of image in pixels.

        Returns:
            Bearing angle in degrees (-90 to 90, where 0 is center).
        """
        # Convert pixel X to angle: left edge = -90°, center = 0°, right edge = 90°
        angle_deg = ((center[0] - image_width / 2) / image_width) * 90

        return angle_deg

    def _generate_synthetic_detection(self) -> List[MarkerDetection]:
        """Generate synthetic marker detections for testing."""
        import random

        if random.random() > 0.3:  # 30% chance to detect
            marker_id = list(self.known_positions.keys())[0] if self.known_positions else 0
            return [
                MarkerDetection(
                    marker_id=marker_id,
                    corners=np.array([[0, 0], [100, 0], [100, 100], [0, 100]]),
                    distance=1.0 + random.uniform(-0.1, 0.1),
                    angle=random.uniform(-30, 30)
                )
            ]
        return []

    def __del__(self):
        """Cleanup."""
        pass
