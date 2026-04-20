"""
As-built map generator for visual inspection reports.

Creates annotated map images showing room layout, socket locations, and wall tilt.
"""

import logging
from typing import Optional, List, Dict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import matplotlib.patches as mpatches

from sitesentry import config
from sitesentry.data import DatabaseHandler
from sitesentry.navigation import SLAMHandler

logger = logging.getLogger(__name__)


class MapGenerator:
    """
    As-built map visualization generator.

    Creates annotated PNG images showing:
    - SLAM occupancy grid (room layout)
    - Verified sockets (green), missing (red), extra (orange)
    - Critical walls (red), normal walls (green)
    - ArUco correction points marked with ⊕
    - Robot path overlay
    """

    def __init__(self, db_handler: DatabaseHandler, slam_handler: SLAMHandler):
        """
        Initialize map generator.

        Args:
            db_handler: DatabaseHandler for reading scan results.
            slam_handler: SLAMHandler for occupancy grid data.
        """
        self.db_handler = db_handler
        self.slam_handler = slam_handler
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_as_built_map(self, session_id: int, output_path: Optional[str] = None) -> Optional[str]:
        """
        Generate as-built map image for a scan session.

        Args:
            session_id: Scan session ID from database.
            output_path: Path to save map image. Defaults to outputs/map_{session_id}.png

        Returns:
            Path to generated map image, or None if generation failed.
        """
        try:
            output_path = output_path or str(config.OUTPUTS_DIR / f"map_{session_id}.png")

            # Get session data
            session_summary = self.db_handler.get_session_summary(session_id)
            if not session_summary:
                self.logger.error(f"Session {session_id} not found")
                return None

            # Get occupancy grid
            grid = self.slam_handler.get_occupancy_grid()

            # Create figure
            fig, ax = plt.subplots(figsize=(12, 10))

            # Plot occupancy grid
            self._plot_occupancy_grid(ax, grid)

            # Plot wall scans with tilt indicators
            self._plot_wall_scans(ax, session_id)

            # Plot socket scans
            self._plot_socket_scans(ax, session_id)

            # Add legend
            self._add_legend(ax)

            # Add title and labels
            room_id = session_summary.get("room_id", "Unknown")
            title = f"SiteSentry As-Built Map - Session {session_id}"
            if room_id:
                title += f" - {room_id}"

            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel("X (meters)", fontsize=11)
            ax.set_ylabel("Y (meters)", fontsize=11)
            ax.grid(True, alpha=0.3)

            # Save figure
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()

            self.logger.info(f"Map saved to {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Error generating map: {e}")
            return None

    def _plot_occupancy_grid(self, ax, grid: np.ndarray) -> None:
        """
        Plot occupancy grid as background.

        Args:
            ax: Matplotlib axes.
            grid: 2D occupancy grid.
        """
        try:
            # Convert grid to image format (0=free/white, 100=occupied/black, -1=unknown/gray)
            image = np.zeros((grid.shape[0], grid.shape[1], 3), dtype=np.uint8)

            # Unknown cells: light gray
            image[grid == -1] = [200, 200, 200]
            # Free cells: white
            image[grid == 0] = [255, 255, 255]
            # Occupied cells: black
            image[grid == 100] = [0, 0, 0]

            # Flip Y axis for display
            image = np.flipud(image)

            # Display image
            grid_resolution = self.slam_handler.grid_resolution
            grid_size = self.slam_handler.grid_size
            extent = [-grid_size * grid_resolution / 2, grid_size * grid_resolution / 2,
                      -grid_size * grid_resolution / 2, grid_size * grid_resolution / 2]

            ax.imshow(image, extent=extent, origin='upper', alpha=0.7)

        except Exception as e:
            self.logger.warning(f"Error plotting occupancy grid: {e}")

    def _plot_wall_scans(self, ax, session_id: int) -> None:
        """
        Plot wall scans with color coding for tilt status.

        Args:
            ax: Matplotlib axes.
            session_id: Session ID.
        """
        try:
            cursor = self.db_handler.cursor
            cursor.execute("""
                SELECT x, y, theta_final, is_critical FROM wall_scans WHERE session_id = ?
            """, (session_id,))

            for row in cursor.fetchall():
                x, y, theta_final, is_critical = row

                # Color based on criticality
                color = 'red' if is_critical else 'green'
                alpha = 0.8 if is_critical else 0.5

                # Plot as line indicating tilt direction
                length = 0.2
                dx = length * np.cos(np.radians(theta_final))
                dy = length * np.sin(np.radians(theta_final))

                ax.arrow(x, y, dx, dy, head_width=0.05, head_length=0.03,
                        fc=color, ec=color, alpha=alpha, linewidth=2)

        except Exception as e:
            self.logger.warning(f"Error plotting wall scans: {e}")

    def _plot_socket_scans(self, ax, session_id: int) -> None:
        """
        Plot socket detection results with status indicators.

        Args:
            ax: Matplotlib axes.
            session_id: Session ID.
        """
        try:
            cursor = self.db_handler.cursor
            cursor.execute("""
                SELECT detected_x, detected_y, status FROM socket_scans WHERE session_id = ?
            """, (session_id,))

            for row in cursor.fetchall():
                detected_x, detected_y, status = row

                # Color based on status
                if status == "MATCH":
                    color = 'green'
                    marker = 'o'
                elif status == "MISSING":
                    color = 'red'
                    marker = 'x'
                else:  # EXTRA
                    color = 'orange'
                    marker = 's'

                ax.plot(detected_x, detected_y, marker=marker, color=color, markersize=8, alpha=0.7)

        except Exception as e:
            self.logger.warning(f"Error plotting socket scans: {e}")

    def _add_legend(self, ax) -> None:
        """Add legend to map."""
        try:
            legend_elements = [
                mpatches.Patch(color='green', label='OK (Normal Wall/Matched Socket)', alpha=0.7),
                mpatches.Patch(color='red', label='Critical/Missing', alpha=0.7),
                mpatches.Patch(color='orange', label='Extra Detection', alpha=0.7),
                mpatches.Patch(color='black', label='Occupied Space', alpha=0.7),
                mpatches.Patch(color='white', label='Free Space', alpha=0.7),
            ]

            ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

        except Exception as e:
            self.logger.warning(f"Error adding legend: {e}")
