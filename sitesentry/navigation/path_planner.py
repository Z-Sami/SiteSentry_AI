"""
Path planner for waypoint-based navigation.

Loads pre-defined waypoints from JSON and provides navigation to each.
Implements PID-based heading control for accurate positioning.
"""

import logging
import json
import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Navigation waypoint."""
    room_id: str
    x: float
    y: float
    action: str  # "move", "scan_wall", "scan_socket", "aruco_check"
    index: int = 0


class PathPlanner:
    """
    Waypoint-based path planner.

    Loads pre-planned waypoints from JSON file and provides navigation commands.
    Implements PID controller for heading correction during navigation.
    """

    def __init__(self, waypoints_path: str = None):
        """
        Initialize path planner.

        Args:
            waypoints_path: Path to waypoints JSON file. Defaults to config.WAYPOINTS_PATH.
        """
        self.waypoints_path = waypoints_path or str(config.WAYPOINTS_PATH)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.waypoints: List[Waypoint] = []
        self.current_index = 0

        # PID controller state for heading control
        self.pid_previous_error = 0.0
        self.pid_integral = 0.0

        self._load_waypoints()

    def _load_waypoints(self) -> None:
        """Load waypoints from JSON file."""
        try:
            waypoints_file = Path(self.waypoints_path)

            if not waypoints_file.exists():
                self.logger.warning(f"Waypoints file not found: {self.waypoints_path}")
                return

            with open(waypoints_file, "r") as f:
                data = json.load(f)

            self.waypoints = []
            for idx, wp_dict in enumerate(data.get("waypoints", [])):
                waypoint = Waypoint(
                    room_id=wp_dict["room_id"],
                    x=wp_dict["x"],
                    y=wp_dict["y"],
                    action=wp_dict.get("action", "move"),
                    index=idx
                )
                self.waypoints.append(waypoint)

            self.logger.info(f"Loaded {len(self.waypoints)} waypoints")

        except Exception as e:
            self.logger.error(f"Failed to load waypoints: {e}")

    def get_next_waypoint(self) -> Optional[Waypoint]:
        """
        Get next waypoint in sequence.

        Returns:
            Waypoint object, or None if all waypoints exhausted.
        """
        if self.current_index >= len(self.waypoints):
            return None

        waypoint = self.waypoints[self.current_index]
        self.current_index += 1

        return waypoint

    def peek_next_waypoint(self) -> Optional[Waypoint]:
        """
        Peek at next waypoint without advancing.

        Returns:
            Waypoint object, or None if all waypoints exhausted.
        """
        if self.current_index < len(self.waypoints):
            return self.waypoints[self.current_index]
        return None

    def reset(self) -> None:
        """Reset waypoint index to beginning."""
        self.current_index = 0
        self.pid_previous_error = 0.0
        self.pid_integral = 0.0
        self.logger.info("Path planner reset to start")

    def navigate_to(self, target_x: float, target_y: float, current_pose: Tuple[float, float, float],
                    motor_controller, max_iterations: int = 100) -> bool:
        """
        Navigate to target position using PID-based heading control.

        Algorithm:
        1. Compute distance to target
        2. If distance < tolerance, stop and return True
        3. Compute desired heading to target
        4. Apply PID control to correct current heading
        5. Move forward/turn as needed
        6. Repeat until target reached or max iterations exceeded

        Args:
            target_x: Target X coordinate in meters.
            target_y: Target Y coordinate in meters.
            current_pose: Tuple of (x, y, theta) from SLAM/odometry.
            motor_controller: MotorController instance for movement commands.
            max_iterations: Maximum navigation iterations to prevent infinite loops.

        Returns:
            True if target reached, False if navigation failed or exceeded iterations.
        """
        try:
            self.pid_previous_error = 0.0
            self.pid_integral = 0.0

            for iteration in range(max_iterations):
                current_x, current_y, current_theta = current_pose

                # Compute distance to target
                dx = target_x - current_x
                dy = target_y - current_y
                distance = math.sqrt(dx ** 2 + dy ** 2)

                # Check if target reached
                if distance < config.POSITION_TOLERANCE:
                    motor_controller.stop()
                    self.logger.info(f"Target reached in {iteration} iterations")
                    return True

                # Compute desired heading
                desired_heading = math.atan2(dy, dx)

                # Compute heading error (normalized to -π to π)
                heading_error = desired_heading - current_theta
                while heading_error > math.pi:
                    heading_error -= 2 * math.pi
                while heading_error < -math.pi:
                    heading_error += 2 * math.pi

                # PID control for heading
                control_output = self._pid_controller(heading_error)

                # Determine motor commands
                if abs(heading_error) > math.radians(config.HEADING_TOLERANCE):
                    # Need to turn
                    if control_output > 0:
                        motor_controller.turn_left(50)
                    else:
                        motor_controller.turn_right(50)
                else:
                    # Heading corrected, move forward
                    motor_controller.move_forward(config.MOTOR_SPEED_STRAIGHT)

                # Small sleep to allow odometry update
                time.sleep(0.1)

            self.logger.warning(f"Navigation failed: max iterations ({max_iterations}) exceeded")
            motor_controller.stop()
            return False

        except Exception as e:
            self.logger.error(f"Navigation error: {e}")
            motor_controller.stop()
            return False

    def _pid_controller(self, error: float) -> float:
        """
        Compute PID control output for heading correction.

        Args:
            error: Heading error in radians.

        Returns:
            Control output (positive = turn left, negative = turn right).
        """
        # Proportional term
        p_term = config.PID_KP * error

        # Integral term
        self.pid_integral += error
        self.pid_integral = max(-1.0, min(1.0, self.pid_integral))  # Clamp
        i_term = config.PID_KI * self.pid_integral

        # Derivative term
        d_term = config.PID_KD * (error - self.pid_previous_error)
        self.pid_previous_error = error

        # Total output
        output = p_term + i_term + d_term

        # Clamp output
        return max(-1.0, min(1.0, output))

    def get_remaining_waypoints(self) -> int:
        """Get number of remaining waypoints."""
        return max(0, len(self.waypoints) - self.current_index)

    def get_total_waypoints(self) -> int:
        """Get total number of waypoints."""
        return len(self.waypoints)

    def get_progress(self) -> float:
        """
        Get navigation progress as percentage.

        Returns:
            Float between 0.0 and 1.0.
        """
        if len(self.waypoints) == 0:
            return 0.0
        return self.current_index / len(self.waypoints)
