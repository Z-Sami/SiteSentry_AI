"""
Telegram bot handler for notifications and reporting.

Sends alerts, images, and PDF reports via Telegram Bot API.
Supports both sync and async message sending.
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
import threading

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    Bot = None
    TelegramError = None

from sitesentry import config

logger = logging.getLogger(__name__)


class TelegramHandler:
    """
    Telegram bot notification handler.

    Sends text alerts, images, and documents (PDF reports) to Telegram.
    Handles connectivity issues gracefully without crashing.
    """

    def __init__(self, token: str = None, chat_id: str = None):
        """
        Initialize Telegram handler.

        Args:
            token: Telegram bot token. Defaults to config.TELEGRAM_BOT_TOKEN.
            chat_id: Telegram chat ID. Defaults to config.TELEGRAM_CHAT_ID.
        """
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.logger = logging.getLogger(self.__class__.__name__)

        self.bot = None
        self.enabled = False

        if not self.token or not self.chat_id:
            self.logger.warning("Telegram credentials not configured")
            return

        try:
            if Bot:
                self.bot = Bot(token=self.token)
                self.enabled = True
                self.logger.info("Telegram handler initialized")
            else:
                self.logger.warning("python-telegram-bot not installed")
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram: {e}")

    def send_alert(self, message_text: str, async_mode: bool = True) -> bool:
        """
        Send text alert message.

        Args:
            message_text: Alert message text.
            async_mode: If True, send asynchronously in background thread.

        Returns:
            True if message queued/sent, False if failed.
        """
        if not self.enabled:
            self.logger.debug("Telegram disabled, skipping alert")
            return False

        if async_mode:
            thread = threading.Thread(target=self._send_alert_sync, args=(message_text,), daemon=True)
            thread.start()
            return True
        else:
            return self._send_alert_sync(message_text)

    def _send_alert_sync(self, message_text: str) -> bool:
        """Synchronously send alert message."""
        try:
            if not self.bot:
                return False

            # Use asyncio to send message
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.bot.send_message(chat_id=self.chat_id, text=message_text)
            )
            loop.close()

            self.logger.debug("Alert sent via Telegram")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
            return False

    def send_image(self, image_path: str, caption: str = "", async_mode: bool = True) -> bool:
        """
        Send image file via Telegram.

        Args:
            image_path: Path to image file.
            caption: Optional caption text.
            async_mode: If True, send asynchronously in background thread.

        Returns:
            True if message queued/sent, False if failed.
        """
        if not self.enabled:
            self.logger.debug("Telegram disabled, skipping image")
            return False

        if not Path(image_path).exists():
            self.logger.error(f"Image file not found: {image_path}")
            return False

        if async_mode:
            thread = threading.Thread(
                target=self._send_image_sync,
                args=(image_path, caption),
                daemon=True
            )
            thread.start()
            return True
        else:
            return self._send_image_sync(image_path, caption)

    def _send_image_sync(self, image_path: str, caption: str) -> bool:
        """Synchronously send image."""
        try:
            if not self.bot:
                return False

            with open(image_path, 'rb') as f:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.bot.send_photo(chat_id=self.chat_id, photo=f, caption=caption)
                )
                loop.close()

            self.logger.debug(f"Image sent: {image_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send image: {e}")
            return False

    def send_pdf(self, pdf_path: str, caption: str = "", async_mode: bool = True) -> bool:
        """
        Send PDF document via Telegram.

        Args:
            pdf_path: Path to PDF file.
            caption: Optional caption text.
            async_mode: If True, send asynchronously in background thread.

        Returns:
            True if message queued/sent, False if failed.
        """
        if not self.enabled:
            self.logger.debug("Telegram disabled, skipping PDF")
            return False

        if not Path(pdf_path).exists():
            self.logger.error(f"PDF file not found: {pdf_path}")
            return False

        if async_mode:
            thread = threading.Thread(
                target=self._send_pdf_sync,
                args=(pdf_path, caption),
                daemon=True
            )
            thread.start()
            return True
        else:
            return self._send_pdf_sync(pdf_path, caption)

    def _send_pdf_sync(self, pdf_path: str, caption: str) -> bool:
        """Synchronously send PDF."""
        try:
            if not self.bot:
                return False

            with open(pdf_path, 'rb') as f:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.bot.send_document(chat_id=self.chat_id, document=f, caption=caption)
                )
                loop.close()

            self.logger.debug(f"PDF sent: {pdf_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send PDF: {e}")
            return False

    def send_room_summary(self, room_id: str, wall_results: List[Dict], socket_results: List[Dict],
                         async_mode: bool = True) -> bool:
        """
        Send formatted room inspection summary.

        Args:
            room_id: Room identifier.
            wall_results: List of wall scan result dictionaries.
            socket_results: List of socket scan result dictionaries.
            async_mode: If True, send asynchronously in background thread.

        Returns:
            True if message queued/sent, False if failed.
        """
        try:
            # Format summary message
            critical_walls = sum(1 for w in wall_results if w.get("is_critical", False))
            matched_sockets = sum(1 for s in socket_results if s.get("status") == "MATCH")
            missing_sockets = sum(1 for s in socket_results if s.get("status") == "MISSING")
            extra_sockets = sum(1 for s in socket_results if s.get("status") == "EXTRA")

            message = (
                f"🏗️ *Room {room_id} Inspection Complete*\n\n"
                f"*Wall Status:*\n"
                f"  Total walls: {len(wall_results)}\n"
                f"  Critical: {critical_walls}\n\n"
                f"*Socket Status:*\n"
                f"  Matched: {matched_sockets}\n"
                f"  Missing: {missing_sockets}\n"
                f"  Extra: {extra_sockets}\n"
            )

            if critical_walls > 0:
                message += f"\n⚠️ *ALERT: {critical_walls} critical wall tilt(s) detected!*"

            return self.send_alert(message, async_mode=async_mode)

        except Exception as e:
            self.logger.error(f"Error sending room summary: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if Telegram is properly configured and enabled."""
        return self.enabled
