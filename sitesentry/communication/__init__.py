"""
Communication module for SiteSentry.

Handles Telegram notifications and cloud synchronization.
"""

from .telegram_handler import TelegramHandler
from .sync_manager import SyncManager

__all__ = [
    "TelegramHandler",
    "SyncManager",
]
