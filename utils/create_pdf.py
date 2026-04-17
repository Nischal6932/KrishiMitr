#!/usr/bin/env python3
"""
PDF Generator for IEEE Smart Farming Paper
Converts Markdown to PDF with professional formatting
"""

import os
import sys
from pathlib import Path

def create_pdf_with_reportlab():
    """Create PDF using ReportLab with professional formatting"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.lib.colors import black, navy
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # Try to register a better font
        try:
            # Try system fonts
            pdfmetrics.registerFont(TTFont('Helvetica', '/System/Library/Fonts/Helvetica.ttc'))
            font_name = 'Helvetica'
        except:
            font_name = 'Helvetica'
        
        # Create PDF document
        doc = SimpleDocTemplate("SupaDoc.pdf", pagesize=A4,
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=navy
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=black
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=8,
            spaceBefore=12,
            textColor=black
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=14
        )
        
        # Read the markdown file
        with open('IEEE_Smart_Farming_Paper_Working.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to basic HTML-like format for ReportLab
        story = []
        
        # Process content line by line
        lines = content.split('\n')
        current_section = []
        in_code_block = False
        code_content = []
        
        for line in lines:
            line = line.rstrip()
            
            # Handle code blocks
            if line.startswith('```'):
                if in_code_block:
                    # End code block
                    code_text = '\n'.join(code_content)
                    # Add code as preformatted text
                    story.append(Paragraph("<font name='Courier' size=8>" + code_text.replace('\n', '<br/>') + "</font>", body_style))
                    story.append(Spacer(1, 12))
                    code_content = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue
            
            if in_code_block:
                code_content.append(line)
                continue
            
            # Handle different markdown elements
            if line.startswith('# '):
                # Main title
                if current_section:
                    section_text = ' '.join(current_section)
                    story.append(Paragraph(section_text, body_style))
                    current_section = []
                story.append(Paragraph(line[2:], title_style))
                story.append(Spacer(1, 20))
                
            elif line.startswith('## '):
                # Main section
                if current_section:
                    section_text = ' '.join(current_section)
                    story.append(Paragraph(section_text, body_style))
                    current_section = []
                story.append(Paragraph(line[3:], heading_style))
                story.append(Spacer(1, 12))
                
            elif line.startswith('### '):
                # Subsection
                if current_section:
                    section_text = ' '.join(current_section)
                    story.append(Paragraph(section_text, body_style))
                    current_section = []
                story.append(Paragraph(line[4:], subheading_style))
                story.append(Spacer(1, 8))
                
            elif line.startswith('---'):
                # Horizontal rule - add page break or spacer
                if current_section:
                    section_text = ' '.join(current_section)
                    story.append(Paragraph(section_text, body_style))
                    current_section = []
                story.append(Spacer(1, 20))
                
            elif line.startswith('**') and line.endswith('**'):
                # Bold text
                text = line[2:-2]
                story.append(Paragraph(f"<b>{text}</b>", body_style))
                
            elif line.startswith('* ') or line.startswith('- '):
                # List item
                text = line[2:]
                story.append(Paragraph(f"• {text}", body_style))
                
            elif line.strip() == '':
                # Empty line
                if current_section:
                    section_text = ' '.join(current_section)
                    story.append(Paragraph(section_text, body_style))
                    current_section = []
                story.append(Spacer(1, 6))
                
            else:
                # Regular text
                current_section.append(line)
        
        # Add any remaining content
        if current_section:
            section_text = ' '.join(current_section)
            story.append(Paragraph(section_text, body_style))
        
        # Build PDF
        doc.build(story)
        print("PDF created successfully: SupaDoc.pdf")
        return True
        
    except ImportError:
        return False
    except Exception as e:
        print(f"Error creating PDF with ReportLab: {e}")
        return False

def create_pdf_with_fpdf():
    """Create PDF using FPDF2"""
    try:
        from fpdf import FPDF
        import re
        
        # Create PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Set font
        pdf.set_font("Helvetica", size=12)
        
        # Read the markdown file
        with open('IEEE_Smart_Farming_Paper_Working.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Process content
        lines = content.split('\n')
        
        for line in lines:
            line = line.rstrip()
            
            # Skip code blocks for now
            if line.startswith('```'):
                continue
            
            # Handle different markdown elements
            if line.startswith('# '):
                pdf.set_font_size(18)
                pdf.set_font(style='B')
                pdf.cell(0, 10, line[2:], ln=True, align='C')
                pdf.ln(5)
                pdf.set_font_size(12)
                pdf.set_font(style='')
                
            elif line.startswith('## '):
                pdf.set_font_size(16)
                pdf.set_font(style='B')
                pdf.cell(0, 10, line[3:], ln=True)
                pdf.ln(3)
                pdf.set_font_size(12)
                pdf.set_font(style='')
                
            elif line.startswith('### '):
                pdf.set_font_size(14)
                pdf.set_font(style='B')
                pdf.cell(0, 8, line[4:], ln=True)
                pdf.ln(2)
                pdf.set_font_size(12)
                pdf.set_font(style='')
                
            elif line.startswith('---'):
                pdf.ln(10)
                
            elif line.startswith('**') and line.endswith('**'):
                pdf.set_font(style='B')
                pdf.multi_cell(0, 5, line[2:-2])
                pdf.set_font(style='')
                
            elif line.strip() == '':
                pdf.ln(3)
                
            elif line.startswith('* ') or line.startswith('- '):
                pdf.cell(10, 5, "•", ln=0)
                pdf.multi_cell(0, 5, line[2:])
                
            else:
                # Regular text
                pdf.multi_cell(0, 5, line)
        
        # Save PDF
        pdf.output("SupaDoc.pdf")
        print("PDF created successfully: SupaDoc.pdf")
        return True
        
    except ImportError:
        return False
    except Exception as e:
        print(f"Error creating PDF with FPDF: {e}")
        return False

def create_simple_text_pdf():
    """Create a simple text-based PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        
        # Create PDF
        c = canvas.Canvas("SupaDoc.pdf", pagesize=A4)
        width, height = A4
        
        # Read the markdown file
        with open('IEEE_Smart_Farming_Paper_Working.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Set font
        c.setFont("Helvetica", 10)
        
        # Add content
        y_position = height - 50
        lines = content.split('\n')
        
        for line in lines:
            if y_position < 50:
                c.showPage()
                y_position = height - 50
                c.setFont("Helvetica", 10)
            
            # Handle different line types
            if line.startswith('# '):
                c.setFont("Helvetica-Bold", 16)
                c.drawCentredString(width/2, y_position, line[2:])
                y_position -= 30
                c.setFont("Helvetica", 10)
            elif line.startswith('## '):
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y_position, line[3:])
                y_position -= 20
                c.setFont("Helvetica", 10)
            elif line.startswith('### '):
                c.setFont("Helvetica-Bold", 12)
                c.drawString(70, y_position, line[4:])
                y_position -= 15
                c.setFont("Helvetica", 10)
            elif line.strip() == '':
                y_position -= 10
            else:
                # Wrap long lines
                if len(line) > 80:
                    words = line.split(' ')
                    current_line = ''
                    for word in words:
                        if len(current_line + word) < 80:
                            current_line += word + ' '
                        else:
                            c.drawString(50, y_position, current_line)
                            current_line = word + ' '
                            y_position -= 12
                            if y_position < 50:
                                c.showPage()
                                y_position = height - 50
                                c.setFont("Helvetica", 10)
                    if current_line:
                        c.drawString(50, y_position, current_line)
                        y_position -= 12
                else:
                    c.drawString(50, y_position, line)
                    y_position -= 12
        
        c.save()
        print("PDF created successfully: SupaDoc.pdf")
        return True
        
    except Exception as e:
        print(f"Error creating simple PDF: {e}")
        return False

def main():
    """Main function to create PDF"""
    print("Creating PDF: SupaDoc")
    
    # Try different PDF creation methods
    if create_pdf_with_reportlab():
        return
    elif create_pdf_with_fpdf():
        return
    elif create_simple_text_pdf():
        return
    else:
        print("Could not create PDF. Please install a PDF library:")
        print("pip install reportlab")
        print("or")
        print("pip install fpdf2")

if __name__ == "__main__":
    main()
