"""
Sync manager for cloud data synchronization.

Periodically checks connectivity and syncs pending data to cloud (via Telegram).
Handles offline buffering gracefully.
"""

import logging
import time
import threading
import socket
from typing import Optional

from sitesentry import config
from sitesentry.data import DatabaseHandler
from sitesentry.communication.telegram_handler import TelegramHandler

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Background sync manager for cloud data.

    Periodically checks internet connectivity and uploads pending records via Telegram.
    Handles network failures gracefully without crashing.
    """

    def __init__(self, db_handler: DatabaseHandler, telegram_handler: TelegramHandler):
        """
        Initialize sync manager.

        Args:
            db_handler: DatabaseHandler instance.
            telegram_handler: TelegramHandler instance.
        """
        self.db_handler = db_handler
        self.telegram_handler = telegram_handler
        self.logger = logging.getLogger(self.__class__.__name__)

        self.is_running = False
        self.sync_thread = None
        self.last_sync_time = 0

    def start(self) -> None:
        """Start background sync thread."""
        if self.is_running:
            self.logger.warning("Sync manager already running")
            return

        self.is_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        self.logger.info("Sync manager started")

    def stop(self) -> None:
        """Stop background sync thread."""
        self.is_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5.0)
        self.logger.info("Sync manager stopped")

    def _sync_loop(self) -> None:
        """Background thread loop: periodically check and sync data."""
        while self.is_running:
            try:
                # Check if it's time to sync
                current_time = time.time()
                if current_time - self.last_sync_time >= config.SYNC_INTERVAL:
                    self.sync_pending_data()
                    self.last_sync_time = current_time

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                self.logger.error(f"Error in sync loop: {e}")
                time.sleep(10)

    def check_connectivity(self) -> bool:
        """
        Check internet connectivity.

        Attempts to ping a public DNS server.

        Returns:
            True if connected, False otherwise.
        """
        try:
            socket.create_connection((config.CONNECTIVITY_CHECK_IP, 53), timeout=config.CONNECTIVITY_CHECK_TIMEOUT)
            self.logger.debug("Connectivity check: online")
            return True
        except Exception:
            self.logger.debug("Connectivity check: offline")
            return False

    def sync_pending_data(self) -> bool:
        """
        Check for pending data and sync to cloud.

        Gets unsynced records from database, attempts to send via Telegram,
        and marks as synced if successful.

        Returns:
            True if sync completed (even if no records), False if sync failed.
        """
        try:
            # Check connectivity
            if not self.check_connectivity():
                self.logger.debug("Offline - buffering data locally")
                return True  # Not an error, just offline

            # Get unsynced records
            unsynced_records = self.db_handler.get_unsynced_records()

            if not unsynced_records:
                self.logger.debug("No pending data to sync")
                return True

            self.logger.info(f"Syncing {len(unsynced_records)} pending records...")

            # Format and send summary
            wall_count = sum(1 for r in unsynced_records if r.get("table_name") == "wall_scans")
            socket_count = sum(1 for r in unsynced_records if r.get("table_name") == "socket_scans")

            message = (
                f"📊 *SiteSentry Cloud Sync*\n"
                f"Wall scans: {wall_count}\n"
                f"Socket detections: {socket_count}\n"
                f"Status: ✅ Synced to cloud"
            )

            # Send notification (non-blocking)
            success = self.telegram_handler.send_alert(message, async_mode=True)

            if success:
                # Mark records as synced
                queue_ids = [r["queue_id"] for r in unsynced_records]
                self.db_handler.mark_synced(queue_ids)
                self.logger.info(f"Successfully synced {len(unsynced_records)} records")
                return True
            else:
                self.logger.warning("Failed to send sync notification")
                return False

        except Exception as e:
            self.logger.error(f"Error during sync: {e}")
            return False

    def force_sync(self) -> bool:
        """
        Manually trigger sync immediately.

        Returns:
            True if sync completed, False otherwise.
        """
        self.last_sync_time = 0  # Force sync on next check
        time.sleep(0.5)
        return self.sync_pending_data()
