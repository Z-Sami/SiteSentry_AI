import json
import os
from fpdf import FPDF

class SiteSentryReport(FPDF):
    def header(self):
        self.set_fill_color(44, 62, 80) # Dark Professional Blue
        self.rect(0, 0, 210, 35, 'F')
        self.set_font('Arial', 'B', 18)
        self.set_text_color(255, 255, 255)
        self.cell(0, 15, 'SITESENTRY | INSPECTION REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Final Audit - Electrical & Structural Integrity', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'SiteSentry Autonomous Systems | Page {self.page_no()}', 0, 0, 'C')

def clean_ai_text(text):
    """
    Summarizes the long AI text into short, clean bullet points.
    """
    # Simple logic to pick key sentences or split by double stars
    summary = []
    lines = text.replace("**", "").split('\n')
    for line in lines:
        if ":" in line or "Found" in line or "Defect" in line:
            clean_line = line.strip("- ").strip()
            if clean_line: summary.append(f"- {clean_line}")
    
    # Join the first 3 important points to keep it concise
    return "\n".join(summary[:3]) if summary else "- Analysis provided in logs"

def generate_pdf_report(json_file):
    if not os.path.exists(json_file): return

    with open(json_file, 'r') as f:
        data = json.load(f)

    pdf = SiteSentryReport()
    pdf.add_page()
    
    # 1. Summary Header
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, f"PROJECT SUMMARY", "B", 1)
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Date: {data['summary']['timestamp']}  |  Processed: {data['summary']['completed']}/{data['summary']['total_targets']}", 0, 1)
    pdf.ln(5)

    # 2. Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(230, 233, 237) 
    pdf.cell(25, 10, "Target ID", 1, 0, 'C', True)
    pdf.cell(30, 10, "Status", 1, 0, 'C', True)
    pdf.cell(20, 10, "Tilt", 1, 0, 'C', True)
    pdf.cell(115, 10, "Key Observations (AI Summary)", 1, 1, 'C', True)

    # 3. Data Rows
    pdf.set_font("Arial", size=9)
    for item in data['details']:
        # Format the AI text to be bulleted and short
        short_analysis = clean_ai_text(item['ai_report'])
        
        # Calculate height based on the summary length
        row_height = 15 
        
        pdf.cell(25, row_height, item['id'], 1, 0, 'C')
        
        # Status color
        if "Issue" in item['status']:
            pdf.set_text_color(200, 0, 0)
        else:
            pdf.set_text_color(0, 128, 0)
        pdf.cell(30, row_height, item['status'], 1, 0, 'C')
        
        pdf.set_text_color(0, 0, 0)
        pdf.cell(20, row_height, f"{item['tilt_degrees']} deg", 1, 0, 'C')
        
        # Multi-cell for the summary
        curr_x = pdf.get_x()
        curr_y = pdf.get_y()
        pdf.multi_cell(115, 5, short_analysis, 1, 'L')
        pdf.set_xy(curr_x + 115, curr_y) # Move to end of row
        pdf.ln(row_height)

    pdf.output("SiteSentry_Concise_Report.pdf")
    print("Clean PDF generated: SiteSentry_Concise_Report.pdf")

if __name__ == "__main__":
    generate_pdf_report("final_site_report.json")