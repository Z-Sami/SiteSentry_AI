#!/usr/bin/env python3
"""
SiteSentry Report Generator
===========================
Generates professional PDF and annotated DXF reports from inspection results.

Output formats:
  - SiteSentry_Concise_Report.pdf    (reportlab)
  - Final_Inspection_Report.dxf      (ezdxf with colored marks)

Usage:
  python3 report_generator.py <final_site_report.json> [-o output_dir]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
except ImportError:
    print("ERROR: reportlab not installed. Run: pip install reportlab")
    sys.exit(1)

try:
    import ezdxf
except ImportError:
    print("ERROR: ezdxf not installed. Run: pip install ezdxf")
    sys.exit(1)

# ===== CONFIGURATION =====
CONFIG = {
    "pdf_filename": "SiteSentry_Concise_Report.pdf",
    "dxf_filename": "Final_Inspection_Report.dxf",
    "template_dxf": None,  # Will look for site_plan.dxf
    "output_dir": "./results",
    "max_image_width": 300,  # pixels
    "max_image_height": 200,
}

# Color mapping for status
STATUS_COLORS = {
    "PASS": colors.HexColor("#22c55e"),    # Green
    "FAIL": colors.HexColor("#ef4444"),    # Red
    "WARNING": colors.HexColor("#eab308"),  # Yellow
    "UNKNOWN": colors.HexColor("#6b7280"),  # Gray
}

# DXF color mapping
DXF_STATUS_COLORS = {
    "PASS": 3,      # Green
    "FAIL": 1,      # Red
    "WARNING": 2,   # Yellow
    "UNKNOWN": 8,   # Gray
}

class ReportGenerator:
    def __init__(self, report_json_path, output_dir=None):
        """Initialize report generator"""
        self.report_path = Path(report_json_path)
        self.output_dir = Path(output_dir or CONFIG["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load report
        self.report = self._load_report()
        self.captures_dir = self.report_path.parent / "captures"
        
        print(f"✓ Loaded report: {self.report_path}")
        print(f"  Targets: {len(self.report.get('details', []))}")
    
    def _load_report(self):
        """Load final_site_report.json"""
        try:
            with open(self.report_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"ERROR: Failed to load report: {e}")
            raise
    
    def generate_pdf(self):
        """Generate professional PDF report"""
        pdf_path = self.output_dir / CONFIG["pdf_filename"]
        
        print(f"\nGenerating PDF: {pdf_path}")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        # Collect elements
        elements = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor("#374151"),
            spaceAfter=10,
        )
        
        # Cover Page
        elements.append(Paragraph("🏗️ SiteSentry", title_style))
        elements.append(Paragraph("Construction Inspection Report", styles['Heading3']))
        elements.append(Spacer(1, 0.3*inch))
        
        summary = self.report.get("summary", {})
        cover_data = [
            ["Project Name:", summary.get("project_name", "N/A")],
            ["Report Date:", summary.get("start_time", "N/A")],
            ["Total Targets:", str(summary.get("total_targets", 0))],
            ["Completed:", str(summary.get("completed", 0))],
        ]
        
        cover_table = Table(cover_data, colWidths=[2*inch, 3*inch])
        cover_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        elements.append(cover_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Summary Statistics
        elements.append(Paragraph("Summary", heading_style))
        
        stats_data = [
            ["Status", "Count", "Percentage"],
            ["✅ Passed", str(summary.get("passed", 0)), 
             f"{100 * summary.get('passed', 0) / max(summary.get('completed', 1), 1):.1f}%"],
            ["❌ Failed", str(summary.get("failed", 0)),
             f"{100 * summary.get('failed', 0) / max(summary.get('completed', 1), 1):.1f}%"],
            ["⚠️ Warnings", str(summary.get("warnings", 0)),
             f"{100 * summary.get('warnings', 0) / max(summary.get('completed', 1), 1):.1f}%"],
        ]
        
        stats_table = Table(stats_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Add page break before details
        elements.append(PageBreak())
        
        # Target Details
        details = self.report.get("details", [])
        
        for i, target in enumerate(details):
            if i > 0:
                elements.append(PageBreak())
            
            # Target heading
            target_id = target.get("id", "Unknown")
            elements.append(Paragraph(f"Target {i+1}: {target_id}", heading_style))
            
            # Status badge
            status = target.get("inspection_status", "UNKNOWN")
            status_color = STATUS_COLORS.get(status, STATUS_COLORS["UNKNOWN"])
            
            badge_data = [[
                f"Status: {status}",
                f"Severity: {target.get('severity', 'N/A')}",
                f"Confidence: {target.get('confidence', 0):.1%}"
            ]]
            
            badge_table = Table(badge_data, colWidths=[2*inch, 2*inch, 1.5*inch])
            badge_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), status_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 12),
            ]))
            
            elements.append(badge_table)
            elements.append(Spacer(1, 0.2*inch))
            
            # Coordinates
            coords = target.get("coordinates", {})
            coord_text = f"Location: ({coords.get('x', 0):.2f}, {coords.get('y', 0):.2f})"
            elements.append(Paragraph(coord_text, styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            # Image (if available)
            image_file = target.get("image_file", "")
            if image_file:
                image_path = self.report_path.parent / image_file
                if image_path.exists():
                    try:
                        img = Image(str(image_path), width=3*inch, height=2*inch)
                        elements.append(img)
                        elements.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        print(f"Warning: Failed to add image {image_path}: {e}")
            
            # Defects
            defects = target.get("defects_found", [])
            if defects:
                elements.append(Paragraph("<b>Defects Found:</b>", styles['Normal']))
                for defect in defects:
                    elements.append(Paragraph(f"• {defect}", styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
            
            # Recommendation
            recommendation = target.get("ai_recommendation", "")
            if recommendation:
                elements.append(Paragraph("<b>Recommendation:</b>", styles['Normal']))
                elements.append(Paragraph(recommendation, styles['Normal']))
            
            elements.append(Spacer(1, 0.2*inch))
        
        # Build PDF
        try:
            doc.build(elements)
            print(f"✓ PDF saved: {pdf_path}")
            return pdf_path
        except Exception as e:
            print(f"ERROR: PDF generation failed: {e}")
            return None
    
    def generate_annotated_dxf(self):
        """Generate annotated DXF map with inspection results"""
        dxf_path = self.output_dir / CONFIG["dxf_filename"]
        
        print(f"\nGenerating annotated DXF: {dxf_path}")
        
        # Find template DXF (look for site_plan.dxf or mission.json reference)
        template_path = self._find_template_dxf()
        
        if not template_path:
            print("WARNING: Could not find template DXF file, creating new one")
            dwg = ezdxf.new('R2000')
        else:
            try:
                dwg = ezdxf.readfile(str(template_path))
                print(f"  Using template: {template_path}")
            except Exception as e:
                print(f"WARNING: Failed to load template DXF: {e}, creating new one")
                dwg = ezdxf.new('R2000')
        
        # Add inspection results layer
        if 'INSPECTION_RESULTS' not in dwg.layers:
            dwg.layers.new(name='INSPECTION_RESULTS', dxfattribs={'color': 7})
        
        mspace = dwg.modelspace()
        
        # Add result markers
        details = self.report.get("details", [])
        
        for target in details:
            status = target.get("inspection_status", "UNKNOWN")
            coords = target.get("coordinates", {})
            x = coords.get("x", 0)
            y = coords.get("y", 0)
            target_id = str(target.get("id", ""))
            
            # Draw colored circle
            color_idx = DXF_STATUS_COLORS.get(status, 8)
            
            mspace.add_circle(
                (x, y),
                radius=0.2,
                dxfattribs={
                    'layer': 'INSPECTION_RESULTS',
                    'color': color_idx,
                    'lineweight': 35,
                }
            )
            
            # Add text label with severity
            severity = target.get("severity", "UNKNOWN")
            label = f"{status}:{severity}"
            
            mspace.add_text(
                label,
                dxfattribs={
                    'layer': 'INSPECTION_RESULTS',
                    'height': 0.15,
                    'color': color_idx,
                }
            ).set_pos((x + 0.3, y + 0.3))
        
        # Save DXF
        try:
            dwg.saveas(str(dxf_path))
            print(f"✓ DXF saved: {dxf_path}")
            return dxf_path
        except Exception as e:
            print(f"ERROR: DXF generation failed: {e}")
            return None
    
    def _find_template_dxf(self):
        """Search for template DXF file"""
        search_paths = [
            self.report_path.parent.parent / "site_plan.dxf",
            self.report_path.parent.parent / "site_map.dxf",
            Path.cwd() / "site_plan.dxf",
            Path.cwd() / "site_map.dxf",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return None
    
    def generate_all(self):
        """Generate all reports"""
        print("\n" + "="*50)
        print("SiteSentry Report Generator")
        print("="*50)
        
        pdf_path = self.generate_pdf()
        dxf_path = self.generate_annotated_dxf()
        
        print("\n" + "="*50)
        print("✅ Report generation complete!")
        print("="*50)
        
        return {"pdf": pdf_path, "dxf": dxf_path}

def main():
    parser = argparse.ArgumentParser(
        description="SiteSentry Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 report_generator.py final_site_report.json
  python3 report_generator.py results/final_site_report.json -o ./reports
        """
    )
    
    parser.add_argument("report_json", help="Path to final_site_report.json")
    parser.add_argument("-o", "--output-dir", default=CONFIG["output_dir"],
                        help=f"Output directory (default: {CONFIG['output_dir']})")
    
    args = parser.parse_args()
    
    try:
        generator = ReportGenerator(args.report_json, args.output_dir)
        results = generator.generate_all()
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
