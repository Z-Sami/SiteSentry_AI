"""
Arduino serial communication handler.

Manages serial communication with Arduino for:
- Ultrasonic sensor readings (top and bottom)
- MPU6050 IMU tilt angle data
- Motor encoder counts (4 wheels)

Expected Arduino output (CSV format, every 500ms):
distTop,distBottom,wallTilt,countFR,countFL,robotAngle
Example: 0.45,0.42,0.03,1234,1200,2.5
"""

import logging
import time
import threading
from typing import Optional
from collections import deque
from dataclasses import dataclass

try:
    import serial
except ImportError:
    serial = None

from sitesentry import config

logger = logging.getLogger(__name__)


@dataclass
class ArduinoSensorData:
    """Container for Arduino sensor readings (CSV format)."""
    dist_top: float = 0.0  # meters (ultrasonic top/upper sensor)
    dist_bottom: float = 0.0  # meters (ultrasonic bottom/lower sensor)
    wall_tilt: float = 0.0  # meters (dist_top - dist_bottom)
    encoder_fr: int = 0  # ticks (front-right)
    encoder_fl: int = 0  # ticks (front-left)
    robot_angle: float = 0.0  # degrees (IMU tilt angle)
    timestamp: float = 0.0  # seconds


class ArduinoHandler:
    """
    Handles serial communication with Arduino.
    
    Receives CSV-formatted sensor data every 500ms:
    distTop,distBottom,wallTilt,countFR,countFL,robotAngle
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize Arduino handler.

        Args:
            simulate: If True, generates simulated sensor data.
        """
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.serial_port = None
        self.running = False
        self.receive_thread = None
        self.data_buffer = deque(maxlen=100)
        self.latest_data = ArduinoSensorData()
        self.lock = threading.Lock()

        if not self.simulate:
            self._initialize_serial()

    def _initialize_serial(self) -> bool:
        """
        Initialize serial connection to Arduino.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            if serial is None:
                logger.warning("pyserial not installed, falling back to simulation")
                self.simulate = True
                return False

            self.serial_port = serial.Serial(
                port=config.ARDUINO_SERIAL_PORT,
                baudrate=config.ARDUINO_BAUDRATE,
                timeout=config.ARDUINO_TIMEOUT
            )
            logger.info(f"Arduino connected on {config.ARDUINO_SERIAL_PORT} @ {config.ARDUINO_BAUDRATE} baud")
            
            # Give Arduino time to reset and start
            time.sleep(3)
            
            # Start receive thread
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            logger.info("Arduino receive thread started")
            
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Arduino: {e}. Using simulation mode.")
            self.simulate = True
            return False

    def _receive_loop(self) -> None:
        """Background thread: receive and parse Arduino CSV data."""
        buffer = ""
        
        while self.running:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # Look for complete lines (ending with \n)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self._parse_csv_data(line.strip())
                        
            except Exception as e:
                logger.debug(f"Serial read error: {e}")
                time.sleep(0.1)

    def _parse_csv_data(self, line: str) -> None:
        """
        Parse CSV sensor data from Arduino.
        Format: distTop,distBottom,wallTilt,countFR,countFL,robotAngle

        Args:
            line: CSV line from Arduino.
        """
        try:
            if not line or ',' not in line:
                return
            
            parts = line.split(',')
            if len(parts) < 6:
                logger.debug(f"Incomplete data: {line}")
                return
            
            with self.lock:
                self.latest_data = ArduinoSensorData(
                    dist_top=float(parts[0]),  # distTop
                    dist_bottom=float(parts[1]),  # distBottom
                    wall_tilt=float(parts[2]),  # wallTilt
                    encoder_fr=int(float(parts[3])),  # countFR
                    encoder_fl=int(float(parts[4])),  # countFL
                    robot_angle=float(parts[5]),  # robotAngle (degrees)
                    timestamp=time.time()
                )
                self.data_buffer.append(self.latest_data)
                
        except (ValueError, IndexError) as e:
            logger.debug(f"Parse error: {e} - line: {line}")
        except Exception as e:
            logger.debug(f"Unexpected parse error: {e}")

    def _generate_simulated_data(self) -> ArduinoSensorData:
        """Generate simulated sensor data for testing."""
        import random
        
        # Simulate realistic sensor data
        return ArduinoSensorData(
            dist_top=0.45 + random.gauss(0, 0.02),  # ~45cm ± 2cm
            dist_bottom=0.42 + random.gauss(0, 0.02),  # ~42cm ± 2cm
            wall_tilt=random.gauss(0.03, 0.01),  # ~3cm difference
            encoder_fr=random.randint(100, 5000),
            encoder_fl=random.randint(100, 5000),
            robot_angle=random.gauss(0, 1),  # ±1° tilt
            timestamp=time.time()
        )

    def get_sensor_data(self) -> ArduinoSensorData:
        """
        Get latest sensor data from Arduino.

        Returns:
            Latest ArduinoSensorData.
        """
        if self.simulate:
            return self._generate_simulated_data()
        
        with self.lock:
            return self.latest_data

    def send_command(self, command: str) -> bool:
        """
        Send command to Arduino (future extensibility).

        Args:
            command: Command string to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if self.simulate or not self.serial_port:
            return True
        
        try:
            self.serial_port.write(f"{command}\n".encode())
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False

    def stop(self) -> None:
        """Stop serial communication."""
        self.running = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        logger.info("Arduino handler stopped")
