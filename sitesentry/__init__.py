"""
SiteSentry - Autonomous Construction QA Robot

A modular Python codebase for an autonomous construction QA robot that inspects
building sites, measures wall verticality, detects electrical sockets, and
generates detailed inspection reports.

Main Components:
- Hardware: Motors, sensors, cameras, LiDAR
- Navigation: SLAM, ArUco markers, waypoint planning
- Inspection: Wall tilt measurement, socket detection (YOLO)
- Data: SQLite3 persistence with cloud sync
- Communication: Telegram notifications
- Reporting: As-built maps and PDF reports
"""

__version__ = "1.0.0"
__author__ = "SiteSentry Team"

# Import main modules for convenience
from sitesentry import config
