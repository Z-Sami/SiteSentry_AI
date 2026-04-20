"""
PDF report generator for SiteSentry inspection results.

Creates professional PDF reports with executive summary, room-by-room data, and maps.
"""

import logging
from typing import Optional
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import pytz

from sitesentry import config
from sitesentry.data import DatabaseHandler

logger = logging.getLogger(__name__)


class PDFReporter:
    """
    PDF inspection report generator.

    Creates multi-page PDF reports with:
    - Cover page (session info)
    - Executive summary (statistics)
    - Room-by-room breakdown table
    - As-built map
    """

    def __init__(self, db_handler: DatabaseHandler):
        """
        Initialize PDF reporter.

        Args:
            db_handler: DatabaseHandler for reading scan results.
        """
        self.db_handler = db_handler
        self.logger = logging.getLogger(self.__class__.__name__)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        # Modify existing Title style instead of adding a new one
        if 'Title' in self.styles:
            self.styles['Title'].fontSize = 24
            self.styles['Title'].textColor = colors.HexColor('#1f4788')
            self.styles['Title'].spaceAfter = 30
            self.styles['Title'].alignment = TA_CENTER
        else:
            self.styles.add(ParagraphStyle(
                name='Title',
                parent=self.styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1f4788'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            ))

        # Add or modify Subtitle
        try:
            self.styles.add(ParagraphStyle(
                name='Subtitle',
                parent=self.styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#333333'),
                spaceAfter=12,
                alignment=TA_CENTER
            ))
        except ValueError:
            # Style already exists, modify it
            self.styles['Subtitle'].fontSize = 14
            self.styles['Subtitle'].textColor = colors.HexColor('#333333')

        # Add or modify SectionHeader
        try:
            self.styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#1f4788'),
                spaceAfter=12,
                spaceBefore=12,
                fontName='Helvetica-Bold'
            ))
        except ValueError:
            # Style already exists, modify it
            self.styles['SectionHeader'].fontSize = 14
            self.styles['SectionHeader'].textColor = colors.HexColor('#1f4788')

    def generate_report(self, session_id: int, map_image_path: Optional[str] = None,
                        output_path: Optional[str] = None) -> Optional[str]:
        """
        Generate complete inspection report PDF.

        Args:
            session_id: Scan session ID.
            map_image_path: Path to as-built map image. If None, skips map page.
            output_path: Path to save PDF. Defaults to outputs/report_{session_id}.pdf

        Returns:
            Path to generated PDF, or None if generation failed.
        """
        try:
            output_path = output_path or str(config.OUTPUTS_DIR / f"report_{session_id}.pdf")

            # Get session data
            session_summary = self.db_handler.get_session_summary(session_id)
            if not session_summary:
                self.logger.error(f"Session {session_id} not found")
                return None

            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=letter,
                                   rightMargin=0.5*inch, leftMargin=0.5*inch,
                                   topMargin=0.5*inch, bottomMargin=0.5*inch)

            # Build content
            story = []

            # Page 1: Cover
            story.extend(self._create_cover_page(session_summary))
            story.append(PageBreak())

            # Page 2: Executive Summary
            story.extend(self._create_summary_page(session_summary, session_id))
            story.append(PageBreak())

            # Pages 3+: Room breakdown
            story.extend(self._create_room_breakdown(session_id))
            story.append(PageBreak())

            # Last page: Map (if available)
            if map_image_path and Path(map_image_path).exists():
                story.extend(self._create_map_page(map_image_path))

            # Build PDF
            doc.build(story)

            self.logger.info(f"Report saved to {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            return None

    def _create_cover_page(self, session_summary: dict) -> list:
        """Create PDF cover page."""
        story = []

        # Logo/title
        story.append(Spacer(1, 1.5*inch))

        title = Paragraph("🤖 SiteSentry", self.styles['Title'])
        story.append(title)

        subtitle = Paragraph("Autonomous Construction QA Robot<br/>Inspection Report", self.styles['Subtitle'])
        story.append(subtitle)

        story.append(Spacer(1, 0.5*inch))

        # Session info
        info_style = ParagraphStyle(
            'Info',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=8
        )

        session_id = session_summary.get('session_id', 'N/A')
        timestamp = session_summary.get('timestamp', 0)
        date_str = datetime.fromtimestamp(timestamp, tz=pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        room_id = session_summary.get('room_id', 'N/A')
        total_area = session_summary.get('total_area', 'N/A')

        story.append(Paragraph(f"<b>Session ID:</b> {session_id}", info_style))
        story.append(Paragraph(f"<b>Date:</b> {date_str}", info_style))
        story.append(Paragraph(f"<b>Room:</b> {room_id}", info_style))

        if isinstance(total_area, (int, float)):
            story.append(Paragraph(f"<b>Area Scanned:</b> {total_area:.1f} m²", info_style))

        return story

    def _create_summary_page(self, session_summary: dict, session_id: int) -> list:
        """Create executive summary page."""
        story = []

        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))

        # Summary statistics
        wall_total = session_summary.get('wall_scans_total', 0)
        wall_critical = session_summary.get('wall_scans_critical', 0)
        socket_stats = session_summary.get('socket_stats', {})

        matched = socket_stats.get('MATCH', 0)
        missing = socket_stats.get('MISSING', 0)
        extra = socket_stats.get('EXTRA', 0)
        total_sockets = matched + missing + extra

        # Create summary table
        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Walls Scanned', str(wall_total), '✓'],
            ['Critical Tilts', str(wall_critical), '🔴' if wall_critical > 0 else '✓'],
            ['Total Sockets (CAD)', str(matched + missing), ''],
            ['Sockets Matched', str(matched), '✓'],
            ['Sockets Missing', str(missing), '⚠' if missing > 0 else '✓'],
            ['Extra Detections', str(extra), ''],
        ]

        summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 0.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        # Findings
        findings_style = ParagraphStyle(
            'Finding',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )

        story.append(Paragraph("<b>Key Findings:</b>", self.styles['SectionHeader']))

        if wall_critical > 0:
            story.append(Paragraph(
                f"⚠️ <b>{wall_critical} wall(s) with critical tilt detected.</b> "
                f"See room breakdown for details.",
                findings_style
            ))

        if missing > 0:
            story.append(Paragraph(
                f"📌 <b>{missing} socket(s) not detected.</b> "
                f"May require manual verification.",
                findings_style
            ))

        if extra > 0:
            story.append(Paragraph(
                f"❓ <b>{extra} extra detection(s) not in CAD.</b> "
                f"Possible additional outlets or false positives.",
                findings_style
            ))

        if wall_critical == 0 and missing == 0 and extra == 0:
            story.append(Paragraph(
                "✅ <b>All checks passed.</b> No critical issues detected.",
                findings_style
            ))

        return story

    def _create_room_breakdown(self, session_id: int) -> list:
        """Create room-by-room breakdown table."""
        story = []

        story.append(Paragraph("Room-by-Room Breakdown", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))

        try:
            cursor = self.db_handler.cursor

            # Get wall scans
            cursor.execute("""
                SELECT room_id, id, x, y, theta_final, is_critical FROM wall_scans WHERE session_id = ?
                ORDER BY room_id, id
            """, (session_id,))

            wall_scans = cursor.fetchall()

            if not wall_scans:
                story.append(Paragraph("No wall scans recorded.", self.styles['Normal']))
                return story

            # Create wall breakdown table
            wall_data = [['Room', 'Scan ID', 'Position', 'Tilt Angle', 'Status']]

            for room_id, scan_id, x, y, tilt_angle, is_critical in wall_scans:
                status = '🔴 CRITICAL' if is_critical else '🟢 OK'
                position = f"({x:.2f}, {y:.2f})"
                wall_data.append([
                    str(room_id),
                    str(scan_id),
                    position,
                    f"{tilt_angle:.2f}°",
                    status
                ])

            wall_table = Table(wall_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1*inch, 1.2*inch])
            wall_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))

            story.append(wall_table)

        except Exception as e:
            self.logger.warning(f"Error creating room breakdown: {e}")

        return story

    def _create_map_page(self, map_image_path: str) -> list:
        """Create map page with as-built image."""
        story = []

        story.append(Paragraph("As-Built Map", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))

        try:
            img = Image(map_image_path, width=6.5*inch, height=6.5*inch)
            story.append(img)
        except Exception as e:
            self.logger.warning(f"Error adding map image: {e}")
            story.append(Paragraph(f"[Map image unavailable: {e}]", self.styles['Normal']))

        return story
