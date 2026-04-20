"""
Camera handler for Raspberry Pi Camera v2.

Captures images with automatic LED array control based on ambient light.
"""

import logging
import time
from pathlib import Path
from typing import Optional
import numpy as np

try:
    from picamera2 import Picamera2
    import libcamera
except (ImportError, RuntimeError):
    Picamera2 = None
    libcamera = None

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    GPIO = None

from sitesentry import config

logger = logging.getLogger(__name__)


class CameraHandler:
    """
    Raspberry Pi Camera v2 with LED array control.

    Auto-activates LED array when ambient light is below threshold (100 lux).
    Captures images in BGR format compatible with OpenCV.
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize camera handler.

        Args:
            simulate: If True, return synthetic images without camera access.
        """
        self.simulate = simulate or config.SIMULATE_HARDWARE
        self.logger = logging.getLogger(self.__class__.__name__)

        self.camera = None
        self.led_pin = config.CAMERA_PINS.led_array
        self.led_enabled = False

        if self.simulate:
            self.logger.info("Camera in SIMULATE mode")
            return

        try:
            # Setup LED pin
            if GPIO:
                GPIO.setup(self.led_pin, GPIO.OUT)
                GPIO.output(self.led_pin, GPIO.LOW)

            # Initialize camera
            if Picamera2:
                self.camera = Picamera2()

                # Configure camera
                config_dict = self.camera.create_preview_configuration(
                    main={"format": "RGB888", "size": config.CAMERA_RESOLUTION},
                    lores={"format": "YUV420", "size": (640, 480)}
                )
                self.camera.configure(config_dict)
                self.camera.start()
                time.sleep(1.0)  # Allow camera to stabilize

                self.logger.info("Camera initialized")
            else:
                raise ImportError("picamera2 library not available")

        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {e}")
            self.simulate = True

    def _check_light_level(self) -> bool:
        """
        Check ambient light level and auto-control LED.

        Uses camera metadata to estimate lux. If below threshold, enables LED.

        Returns:
            True if LED is enabled, False otherwise.
        """
        if self.simulate or not self.camera:
            return False

        try:
            # Try to estimate light level from camera metadata
            # This is a simplified approach - in production, use an external light sensor
            metadata = self.camera.capture_metadata()

            # Rough lux estimation from exposure time and ISO
            if metadata:
                exposure_time = metadata.get("ExposureTime", 1000)  # microseconds
                iso_sensitivity = metadata.get("IsoSensitivity", 100)
                estimated_lux = (100000.0 / (exposure_time * iso_sensitivity * 0.01))

                if estimated_lux < config.CAMERA_LIGHT_THRESHOLD:
                    if not self.led_enabled:
                        self._set_led(True)
                    return True
                else:
                    if self.led_enabled:
                        self._set_led(False)
                    return False

        except Exception as e:
            self.logger.debug(f"Error checking light level: {e}")

        return self.led_enabled

    def _set_led(self, enable: bool) -> None:
        """
        Control LED array.

        Args:
            enable: True to turn on, False to turn off.
        """
        try:
            if GPIO:
                GPIO.output(self.led_pin, GPIO.HIGH if enable else GPIO.LOW)
                self.led_enabled = enable
                self.logger.debug(f"LED array {'enabled' if enable else 'disabled'}")
        except Exception as e:
            self.logger.error(f"Error controlling LED: {e}")

    def capture_image(self) -> Optional[np.ndarray]:
        """
        Capture a single image.

        Automatically controls LED array based on ambient light.

        Returns:
            Image as numpy array (BGR format, uint8), or None if capture fails.
        """
        if self.simulate:
            # Return synthetic image: 480x640 BGR
            return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        try:
            if not self.camera:
                return None

            # Check light and adjust LED
            self._check_light_level()

            # Capture image
            request = self.camera.capture_request()
            array = request.make_array("main")

            # Convert RGB to BGR for OpenCV compatibility
            image_bgr = array[..., ::-1]

            request.release()

            self.logger.debug("Image captured")
            return image_bgr

        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
            return None

    def capture_and_save(self, filepath: str) -> bool:
        """
        Capture image and save to disk.

        Args:
            filepath: Path where image should be saved.

        Returns:
            True if successful, False otherwise.
        """
        try:
            image = self.capture_image()

            if image is None:
                self.logger.error("Failed to capture image")
                return False

            # Convert BGR to RGB for saving
            import cv2
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            cv2.imwrite(filepath, image_rgb)

            self.logger.info(f"Image saved to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up camera and GPIO resources."""
        if self.camera:
            try:
                self.camera.stop()
                self.camera.close()
                self.logger.info("Camera cleaned up")
            except Exception as e:
                self.logger.error(f"Error closing camera: {e}")

        if GPIO:
            try:
                GPIO.cleanup([self.led_pin])
                self.logger.info("Camera GPIO cleaned up")
            except Exception as e:
                self.logger.error(f"Error cleaning GPIO: {e}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
