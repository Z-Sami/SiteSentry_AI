"""
Socket inspector for electrical outlet detection.

Uses YOLOv8 for object detection and cross-references with CAD blueprint.
"""

import logging
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

import numpy as np

from sitesentry import config
from sitesentry.hardware import CameraHandler

logger = logging.getLogger(__name__)


@dataclass
class SocketDetection:
    """Detected socket in image."""
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    pixel_center: Tuple[int, int]


@dataclass
class SocketVerification:
    """Socket verification result."""
    socket_id: str
    detected_world_x: float
    detected_world_y: float
    cad_x: float
    cad_y: float
    distance_error: float
    status: str  # "MATCH", "MISSING", "EXTRA"
    confidence: float


class SocketInspector:
    """
    Electrical socket detector and verifier.

    Detects sockets in camera images using YOLOv8.
    Converts pixel coordinates to world frame.
    Verifies against CAD blueprint with adaptive tolerance.
    """

    def __init__(self, camera_handler: CameraHandler, model_path: str = None, simulate: bool = False):
        """
        Initialize socket inspector.

        Args:
            camera_handler: CameraHandler instance for image capture.
            model_path: Path to YOLOv8 model file. Defaults to config.YOLO_MODEL_PATH.
            simulate: If True, return synthetic detections without YOLO.
        """
        self.camera_handler = camera_handler
        self.model_path = model_path or str(config.YOLO_MODEL_PATH)
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        self.model = None
        self.blueprint_sockets = {}

        self._load_blueprint()
        self._load_model()

    def _load_model(self) -> None:
        """Load YOLOv8 model for socket detection."""
        if self.simulate:
            self.logger.info("Socket inspector in SIMULATE mode")
            return

        try:
            if YOLO and Path(self.model_path).exists():
                self.model = YOLO(self.model_path)
                self.logger.info(f"Loaded YOLO model from {self.model_path}")
            else:
                self.logger.warning(f"YOLO model not found at {self.model_path}")
                self.simulate = True
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            self.simulate = True

    def _load_blueprint(self) -> None:
        """
        Load CAD blueprint with socket locations.

        Expected format:
        {
            "sockets": [
                {"id": "S1", "x": 2.1, "y": 0.8, "room": "R1"},
                ...
            ]
        }
        """
        try:
            blueprint_path = config.BLUEPRINT_PATH

            if blueprint_path.exists():
                with open(blueprint_path, "r") as f:
                    blueprint = json.load(f)
                    for socket in blueprint.get("sockets", []):
                        self.blueprint_sockets[socket["id"]] = {
                            "x": socket["x"],
                            "y": socket["y"],
                            "room": socket.get("room", "")
                        }

                self.logger.info(f"Loaded {len(self.blueprint_sockets)} blueprint sockets")
            else:
                self.logger.warning(f"Blueprint file not found: {blueprint_path}")

        except Exception as e:
            self.logger.error(f"Failed to load blueprint: {e}")

    def detect_sockets(self, frame: np.ndarray) -> List[SocketDetection]:
        """
        Detect sockets in image frame using YOLO.

        Args:
            frame: Image frame as numpy array (BGR).

        Returns:
            List of SocketDetection objects.
        """
        if self.simulate:
            return self._generate_synthetic_detections()

        if not self.model or frame is None:
            return []

        try:
            # Run inference
            results = self.model(frame, verbose=False)

            detections = []
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    confidence = float(box.conf[0])

                    # Create bounding box (x, y, w, h)
                    w = x2 - x1
                    h = y2 - y1
                    bbox = (x1, y1, w, h)

                    # Pixel center
                    pixel_center = ((x1 + x2) // 2, (y1 + y2) // 2)

                    detection = SocketDetection(
                        bbox=bbox,
                        confidence=confidence,
                        pixel_center=pixel_center
                    )
                    detections.append(detection)

            if detections:
                self.logger.debug(f"Detected {len(detections)} sockets")

            return detections

        except Exception as e:
            self.logger.error(f"Error detecting sockets: {e}")
            return []

    def pixel_to_world(self, pixel_center: Tuple[int, int], current_pose: Tuple[float, float, float],
                       camera_matrix: Optional[np.ndarray] = None) -> Tuple[float, float]:
        """
        Convert pixel coordinates to world coordinates.

        Uses pinhole camera model with assumed camera parameters.

        Args:
            pixel_center: (x, y) pixel coordinates in image.
            current_pose: Robot pose (x, y, theta).
            camera_matrix: Camera calibration matrix. If None, uses default.

        Returns:
            World coordinates (x, y) in meters.
        """
        try:
            if camera_matrix is None:
                # Assume camera parameters (typical for Raspberry Pi Camera v2)
                focal_length = 1640  # pixels
                sensor_width_mm = 3.68
                sensor_height_mm = 2.76
                image_width = config.CAMERA_RESOLUTION[0]
                image_height = config.CAMERA_RESOLUTION[1]

                camera_matrix = np.array([
                    [focal_length, 0, image_width / 2],
                    [0, focal_length, image_height / 2],
                    [0, 0, 1]
                ], dtype=float)

            # Approximate: assume socket is at 1 meter distance from camera
            # In production, use depth from stereo or ToF sensor
            estimated_distance = 1.0

            # Pixel to normalized image coordinates
            pixel_x, pixel_y = pixel_center
            norm_x = (pixel_x - camera_matrix[0, 2]) / camera_matrix[0, 0]
            norm_y = (pixel_y - camera_matrix[1, 2]) / camera_matrix[1, 1]

            # Camera-frame coordinates
            cam_x = estimated_distance * norm_x
            cam_y = estimated_distance * norm_y
            cam_z = estimated_distance

            # Assume camera points forward along robot's X axis
            # Transform camera frame to world frame
            robot_x, robot_y, robot_theta = current_pose

            world_x = robot_x + cam_z * math.cos(robot_theta) - cam_x * math.sin(robot_theta)
            world_y = robot_y + cam_z * math.sin(robot_theta) + cam_x * math.cos(robot_theta)

            return (world_x, world_y)

        except Exception as e:
            self.logger.error(f"Error converting pixel to world: {e}")
            return (0.0, 0.0)

    def verify_against_blueprint(self, detections: List[SocketDetection],
                                current_pose: Tuple[float, float, float],
                                room_id: str) -> List[SocketVerification]:
        """
        Verify detected sockets against CAD blueprint.

        Algorithm:
        1. Convert pixel coordinates to world coordinates
        2. Match each detection to nearest blueprint socket
        3. Check distance against tolerance (adaptive based on confidence)
        4. Tag as "MATCH", "EXTRA", or report "MISSING" sockets

        Args:
            detections: List of SocketDetection from YOLO.
            current_pose: Robot pose (x, y, theta).
            room_id: Room identifier for filtering blueprint sockets.

        Returns:
            List of SocketVerification results.
        """
        try:
            verifications = []
            matched_blueprint_ids = set()

            # Process detections
            for detection in detections:
                world_x, world_y = self.pixel_to_world(detection.pixel_center, current_pose)

                # Find nearest blueprint socket
                best_match = None
                best_distance = float('inf')

                for socket_id, socket_info in self.blueprint_sockets.items():
                    if socket_info["room"] != room_id:
                        continue

                    cad_x, cad_y = socket_info["x"], socket_info["y"]
                    distance = math.sqrt((world_x - cad_x) ** 2 + (world_y - cad_y) ** 2)

                    if distance < best_distance:
                        best_distance = distance
                        best_match = (socket_id, cad_x, cad_y)

                # Adaptive tolerance based on confidence
                if detection.confidence > 0.85:
                    tolerance = config.SOCKET_TOLERANCE_MIN
                else:
                    tolerance = config.SOCKET_TOLERANCE_MAX

                if best_match and best_distance <= tolerance:
                    socket_id, cad_x, cad_y = best_match
                    verification = SocketVerification(
                        socket_id=socket_id,
                        detected_world_x=world_x,
                        detected_world_y=world_y,
                        cad_x=cad_x,
                        cad_y=cad_y,
                        distance_error=best_distance,
                        status="MATCH",
                        confidence=detection.confidence
                    )
                    verifications.append(verification)
                    matched_blueprint_ids.add(best_match[0])
                else:
                    # Extra detection (no matching blueprint socket)
                    verification = SocketVerification(
                        socket_id=f"EXTRA_{len(verifications)}",
                        detected_world_x=world_x,
                        detected_world_y=world_y,
                        cad_x=0.0,
                        cad_y=0.0,
                        distance_error=best_distance if best_match else float('inf'),
                        status="EXTRA",
                        confidence=detection.confidence
                    )
                    verifications.append(verification)

            # Check for missing sockets
            for socket_id, socket_info in self.blueprint_sockets.items():
                if socket_info["room"] == room_id and socket_id not in matched_blueprint_ids:
                    verification = SocketVerification(
                        socket_id=socket_id,
                        detected_world_x=0.0,
                        detected_world_y=0.0,
                        cad_x=socket_info["x"],
                        cad_y=socket_info["y"],
                        distance_error=float('inf'),
                        status="MISSING",
                        confidence=0.0
                    )
                    verifications.append(verification)

            self.logger.info(
                f"Socket verification: {len([v for v in verifications if v.status == 'MATCH'])} "
                f"matches, {len([v for v in verifications if v.status == 'EXTRA'])} extra, "
                f"{len([v for v in verifications if v.status == 'MISSING'])} missing"
            )

            return verifications

        except Exception as e:
            self.logger.error(f"Error verifying sockets: {e}")
            return []

    def _generate_synthetic_detections(self) -> List[SocketDetection]:
        """Generate synthetic socket detections for testing."""
        import random

        detections = []
        for _ in range(random.randint(1, 3)):
            detections.append(SocketDetection(
                bbox=(random.randint(100, 1000), random.randint(100, 900), 100, 100),
                confidence=random.uniform(0.7, 0.95),
                pixel_center=(random.randint(150, 1950), random.randint(150, 1050))
            ))

        return detections
