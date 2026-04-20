#!/usr/bin/env python3
"""
SiteSentry Main Orchestrator

Entry point for autonomous construction QA robot inspection missions.
Coordinates all hardware, navigation, inspection, and reporting modules.
"""

import logging
import argparse
import signal
import sys
import time
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

# Import all modules
from sitesentry import config
from sitesentry.hardware import (
    ArduinoHandler, MotorController, IMUSensor, UltrasonicSensor,
    LidarHandler, CameraHandler
)
from sitesentry.navigation import SLAMHandler, ArucoHandler, PathPlanner
from sitesentry.inspection import VerticalityInspector, SocketInspector
from sitesentry.data import DatabaseHandler
from sitesentry.communication import TelegramHandler, SyncManager
from sitesentry.reporting import MapGenerator, PDFReporter

# Setup logging
def setup_logging(log_dir: Path = config.LOGS_DIR) -> logging.Logger:
    """Setup logging to file and console."""
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"sitesentry_{timestamp}.log"

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger("SiteSentry")
    logger.info(f"SiteSentry started - Log: {log_file}")
    return logger


class SiteSentryMission:
    """
    Main mission orchestrator for SiteSentry robot.

    Manages hardware initialization, mission planning, inspection execution,
    and result reporting.
    """

    def __init__(self, args, logger: logging.Logger):
        """
        Initialize mission orchestrator.

        Args:
            args: Parsed command-line arguments.
            logger: Logger instance.
        """
        self.args = args
        self.logger = logger
        self.running = True

        # Hardware modules
        self.arduino_handler = None  # Initialize Arduino first
        self.motor_controller = None
        self.imu_sensor = None
        self.ultrasonic_lower = None
        self.ultrasonic_upper = None
        self.lidar_handler = None
        self.camera_handler = None

        # Navigation modules
        self.slam_handler = None
        self.aruco_handler = None
        self.path_planner = None

        # Inspection modules
        self.verticality_inspector = None
        self.socket_inspector = None

        # Data & communication modules
        self.db_handler = None
        self.telegram_handler = None
        self.sync_manager = None

        # Reporting modules
        self.map_generator = None
        self.pdf_reporter = None

        # Mission state
        self.session_id = None
        self.mission_start_time = None

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame) -> None:
        """Handle interrupt signals gracefully."""
        self.logger.warning(f"Received signal {sig}, shutting down...")
        self.running = False

    def initialize_hardware(self) -> bool:
        """
        Initialize all hardware modules.

        Returns:
            True if all hardware initialized successfully, False otherwise.
        """
        try:
            self.logger.info("Initializing hardware...")

            simulate = self.args.simulate or config.SIMULATE_HARDWARE

            # Arduino handler FIRST (all other sensors depend on it)
            self.arduino_handler = ArduinoHandler(simulate=simulate)

            # Motor controller (uses Arduino encoders)
            self.motor_controller = MotorController(
                self.arduino_handler,
                simulate=simulate
            )

            # IMU sensor (reads from Arduino via MPU6050)
            self.imu_sensor = IMUSensor(
                self.arduino_handler,
                simulate=simulate
            )

            # Ultrasonic sensors (read from Arduino)
            self.ultrasonic_lower = UltrasonicSensor(
                self.arduino_handler,
                sensor_type="lower",
                simulate=simulate
            )
            self.ultrasonic_upper = UltrasonicSensor(
                self.arduino_handler,
                sensor_type="upper",
                simulate=simulate
            )

            # LiDAR
            self.lidar_handler = LidarHandler(simulate=simulate)
            self.lidar_handler.start_scan()

            # Camera
            self.camera_handler = CameraHandler(simulate=simulate)

            self.logger.info("Hardware initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"Hardware initialization failed: {e}")
            return False

    def initialize_software(self) -> bool:
        """
        Initialize all software modules.

        Returns:
            True if all modules initialized successfully, False otherwise.
        """
        try:
            self.logger.info("Initializing software modules...")

            # SLAM
            self.slam_handler = SLAMHandler(simulate=self.args.simulate)

            # ArUco
            self.aruco_handler = ArucoHandler(simulate=self.args.simulate)

            # Path planner
            self.path_planner = PathPlanner(waypoints_path=self.args.waypoints)

            # Inspection modules
            self.verticality_inspector = VerticalityInspector(
                self.ultrasonic_lower,
                self.ultrasonic_upper,
                self.imu_sensor,
                self.motor_controller
            )

            self.socket_inspector = SocketInspector(
                self.camera_handler,
                simulate=self.args.simulate
            )

            # Database
            self.db_handler = DatabaseHandler()

            # Communication
            self.telegram_handler = TelegramHandler()
            self.sync_manager = SyncManager(self.db_handler, self.telegram_handler)
            if self.telegram_handler.is_enabled():
                self.sync_manager.start()

            # Reporting
            self.map_generator = MapGenerator(self.db_handler, self.slam_handler)
            self.pdf_reporter = PDFReporter(self.db_handler)

            self.logger.info("Software initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"Software initialization failed: {e}")
            return False

    def execute_mission(self) -> bool:
        """
        Execute main inspection mission.

        Returns:
            True if mission completed successfully, False if interrupted or failed.
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("Starting SiteSentry inspection mission")
            self.logger.info("=" * 60)

            self.mission_start_time = time.time()

            # Create scan session
            self.session_id = self.db_handler.create_scan_session(
                room_id="Main Area"
            )
            self.logger.info(f"Session {self.session_id} created")

            # Get first waypoint
            waypoint = self.path_planner.get_next_waypoint()
            iteration = 0

            while waypoint and self.running:
                iteration += 1
                self.logger.info(f"\n--- Waypoint {iteration}: {waypoint.room_id} ({waypoint.action}) ---")

                # Navigate to waypoint
                odom = self.motor_controller.get_odometry()
                current_pose = (odom.x, odom.y, odom.theta)

                success = self.path_planner.navigate_to(
                    waypoint.x, waypoint.y, current_pose, self.motor_controller
                )

                if not success:
                    self.logger.warning(f"Failed to navigate to waypoint {waypoint.index}")
                    waypoint = self.path_planner.get_next_waypoint()
                    continue

                # Check for ArUco markers
                frame = self.camera_handler.capture_image()
                if frame is not None:
                    markers = self.aruco_handler.detect_markers(frame)
                    if markers:
                        for marker in markers:
                            self.logger.info(f"ArUco marker detected: ID {marker.marker_id}")
                            correction_pose = self.aruco_handler.get_correction_pose(
                                marker.marker_id, current_pose
                            )
                            if correction_pose:
                                self.slam_handler.reset_pose(*correction_pose)

                # Execute action
                if waypoint.action == "scan_wall":
                    self.logger.info("Executing wall tilt scan...")
                    result = self.verticality_inspector.measure_wall_tilt()

                    if result:
                        # Save to database
                        from sitesentry.data import WallScanRecord
                        record = WallScanRecord(
                            session_id=self.session_id,
                            room_id=waypoint.room_id,
                            x=waypoint.x,
                            y=waypoint.y,
                            d1=result.d1,
                            d2=result.d2,
                            alpha=result.alpha,
                            theta_final=result.theta_final,
                            is_critical=result.is_critical,
                            timestamp=result.timestamp
                        )
                        self.db_handler.save_wall_scan(record)

                        # Send alert if critical
                        if result.is_critical:
                            alert = f"🔴 CRITICAL WALL TILT in {waypoint.room_id}: {result.theta_final:.2f}°"
                            self.telegram_handler.send_alert(alert)
                            self.logger.warning(alert)

                        self.logger.info(f"Wall tilt: {result.theta_final:.2f}°")

                elif waypoint.action == "scan_socket":
                    self.logger.info("Executing socket scan...")
                    frame = self.camera_handler.capture_image()

                    if frame is not None:
                        detections = self.socket_inspector.detect_sockets(frame)
                        current_pose = self.slam_handler.get_current_pose()

                        verifications = self.socket_inspector.verify_against_blueprint(
                            detections,
                            (current_pose.x, current_pose.y, current_pose.theta),
                            waypoint.room_id
                        )

                        # Save socket results
                        from sitesentry.data import SocketScanRecord
                        for verification in verifications:
                            # Save detected frame
                            frame_path = config.OUTPUTS_DIR / f"socket_{self.session_id}_{verification.socket_id}.jpg"
                            if not config.OUTPUTS_DIR.exists():
                                config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

                            import cv2
                            cv2.imwrite(str(frame_path), frame)

                            record = SocketScanRecord(
                                session_id=self.session_id,
                                room_id=waypoint.room_id,
                                socket_id=verification.socket_id,
                                status=verification.status,
                                detected_x=verification.detected_world_x,
                                detected_y=verification.detected_world_y,
                                cad_x=verification.cad_x,
                                cad_y=verification.cad_y,
                                confidence=verification.confidence,
                                image_path=str(frame_path),
                                timestamp=time.time()
                            )
                            self.db_handler.save_socket_scan(record)

                        self.logger.info(f"Socket scan: {len(verifications)} results")

                # Update SLAM with latest LiDAR and odometry
                scan_data = self.lidar_handler.get_scan_data()
                odom = self.motor_controller.get_odometry()
                self.slam_handler.update(scan_data, (odom.x, odom.y, odom.theta))

                # Get next waypoint
                waypoint = self.path_planner.get_next_waypoint()
                time.sleep(0.5)  # Brief pause between waypoints

            # Mission complete
            self.logger.info("\n" + "=" * 60)
            self.logger.info("Mission execution complete")
            self.logger.info("=" * 60)

            # Generate reports
            return self._generate_reports()

        except Exception as e:
            self.logger.error(f"Mission execution error: {e}")
            return False

    def _generate_reports(self) -> bool:
        """
        Generate as-built map and PDF report.

        Returns:
            True if reports generated successfully.
        """
        try:
            self.logger.info("\nGenerating reports...")

            # Save SLAM map
            map_path = config.OUTPUTS_DIR / f"slam_map_{self.session_id}.npz"
            self.slam_handler.save_map(str(map_path))

            # Generate as-built map image
            map_image_path = self.map_generator.generate_as_built_map(self.session_id)

            # Generate PDF report
            pdf_path = self.pdf_reporter.generate_report(
                self.session_id,
                map_image_path=map_image_path
            )

            if pdf_path:
                # Send PDF via Telegram
                if self.telegram_handler.is_enabled():
                    caption = f"🤖 SiteSentry Inspection Report - Session {self.session_id}"
                    self.telegram_handler.send_pdf(pdf_path, caption=caption)

                self.logger.info(f"Report saved: {pdf_path}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Report generation error: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up all resources."""
        self.logger.info("Cleaning up resources...")

        try:
            if self.sync_manager:
                self.sync_manager.stop()

            if self.lidar_handler:
                self.lidar_handler.cleanup()

            if self.motor_controller:
                self.motor_controller.cleanup()

            if self.camera_handler:
                self.camera_handler.cleanup()

            if self.arduino_handler:
                self.arduino_handler.stop()

            if self.db_handler:
                self.db_handler.cleanup()

            self.logger.info("Cleanup complete")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def run(self) -> int:
        """
        Main mission entry point.

        Returns:
            Exit code (0 = success, 1 = failure).
        """
        try:
            # Initialize
            if not self.initialize_hardware():
                return 1

            if not self.initialize_software():
                return 1

            # Dry run mode
            if self.args.dry_run:
                self.logger.info("DRY RUN MODE - No actual movement or data collection")
                self.logger.info(f"Waypoints: {self.path_planner.get_total_waypoints()}")
                return 0

            # Execute mission
            if not self.execute_mission():
                return 1

            return 0

        except Exception as e:
            self.logger.error(f"Mission failed: {e}")
            return 1

        finally:
            self.cleanup()


def main():
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="SiteSentry Autonomous Construction QA Robot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --dry-run
  python main.py --waypoints data/waypoints.json --simulate
  python main.py --session-name "Building A - Floor 1"
        """
    )

    parser.add_argument(
        "--session-name",
        type=str,
        default="SiteSentry Session",
        help="Name/description for this inspection session"
    )

    parser.add_argument(
        "--waypoints",
        type=str,
        default=str(config.WAYPOINTS_PATH),
        help="Path to waypoints JSON file"
    )

    parser.add_argument(
        "--blueprint",
        type=str,
        default=str(config.BLUEPRINT_PATH),
        help="Path to CAD blueprint JSON file"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no movement, no data collection)"
    )

    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulation mode (all hardware returns synthetic data)"
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()

    # Log configuration
    logger.debug("Configuration: " + json.dumps(config.get_config_dict(), indent=2, default=str))

    # Run mission
    mission = SiteSentryMission(args, logger)
    exit_code = mission.run()

    logger.info(f"SiteSentry terminated with exit code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
