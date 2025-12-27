#!/usr/bin/env python3
"""
Generate comprehensive PDF documentation from markdown
Converts COMPLETE_REPOSITORY_DOCUMENTATION.md to PDF
"""
import io
import re
from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    Preformatted,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfgen import canvas

# Color Palette
COLOR_PRIMARY = colors.HexColor("#4f46e5")  # Indigo-600
COLOR_SECONDARY = colors.HexColor("#7c3aed")  # Purple-600
COLOR_TEXT = colors.HexColor("#0f172a")  # Slate-900
COLOR_TEXT_MUTED = colors.HexColor("#475569")  # Slate-600
COLOR_BG = colors.HexColor("#f8fafc")  # Slate-50
COLOR_ACCENT = colors.HexColor("#10b981")  # Green-600
COLOR_CODE_BG = colors.HexColor("#f1f5f9")  # Slate-100

def build_styles():
    """Build paragraph styles for the PDF"""
    base = getSampleStyleSheet()
    
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=32,
            leading=38,
            textColor=COLOR_PRIMARY,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["BodyText"],
            fontSize=14,
            leading=18,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=20,
            alignment=TA_CENTER,
        ),
        "heading1": ParagraphStyle(
            "heading1",
            parent=base["Heading1"],
            fontSize=22,
            leading=28,
            textColor=COLOR_PRIMARY,
            spaceBefore=20,
            spaceAfter=12,
            fontName="Helvetica-Bold",
        ),
        "heading2": ParagraphStyle(
            "heading2",
            parent=base["Heading2"],
            fontSize=18,
            leading=24,
            textColor=COLOR_SECONDARY,
            spaceBefore=16,
            spaceAfter=10,
            fontName="Helvetica-Bold",
        ),
        "heading3": ParagraphStyle(
            "heading3",
            parent=base["Heading3"],
            fontSize=14,
            leading=20,
            textColor=COLOR_TEXT,
            spaceBefore=12,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=COLOR_TEXT,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=COLOR_TEXT,
            spaceAfter=4,
            leftIndent=10,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontSize=8,
            leading=12,
            textColor=COLOR_TEXT,
            spaceAfter=8,
            fontName="Courier",
            leftIndent=15,
            rightIndent=15,
            backColor=COLOR_CODE_BG,
            borderPadding=5,
        ),
        "code_inline": ParagraphStyle(
            "code_inline",
            parent=base["BodyText"],
            fontSize=9,
            leading=14,
            textColor=COLOR_SECONDARY,
            fontName="Courier",
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=COLOR_TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }
    return styles

def parse_markdown(markdown_text):
    """Parse markdown and return structured content"""
    lines = markdown_text.split('\n')
    content = []
    current_code_block = []
    in_code_block = False
    code_language = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Code blocks
        if line.startswith('```'):
            if in_code_block:
                # End code block
                if current_code_block:
                    content.append(('code', '\n'.join(current_code_block), code_language))
                    current_code_block = []
                in_code_block = False
                code_language = None
            else:
                # Start code block
                in_code_block = True
                code_language = line[3:].strip() if len(line) > 3 else None
            i += 1
            continue
        
        if in_code_block:
            current_code_block.append(line)
            i += 1
            continue
        
        # Headers
        if line.startswith('# '):
            content.append(('h1', line[2:].strip()))
        elif line.startswith('## '):
            content.append(('h2', line[3:].strip()))
        elif line.startswith('### '):
            content.append(('h3', line[4:].strip()))
        elif line.startswith('#### '):
            content.append(('h3', line[5:].strip()))  # Treat h4 as h3
        # Horizontal rule
        elif line.strip() == '---':
            content.append(('hr', None))
        # Bullet points
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            content.append(('bullet', line.strip()[2:].strip()))
        # Numbered list
        elif re.match(r'^\d+\.\s', line.strip()):
            content.append(('bullet', line.strip()))
        # Empty line
        elif not line.strip():
            content.append(('spacer', None))
        # Regular text
        else:
            # Check for inline code
            text = line
            if '`' in text:
                # Simple inline code handling
                text = text.replace('`', '<font name="Courier" color="' + str(COLOR_SECONDARY) + '">')
                # This is simplified - proper markdown parsing would be better
            content.append(('text', text))
        
        i += 1
    
    # Handle any remaining code block
    if current_code_block:
        content.append(('code', '\n'.join(current_code_block), code_language))
    
    return content

def escape_html(text):
    """Escape HTML special characters for ReportLab"""
    if not text:
        return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

def create_cover_page(styles):
    """Create the cover page"""
    story = []
    
    story.append(Spacer(1, 80 * mm))
    story.append(Paragraph("Thandev Platform", styles["title"]))
    story.append(Paragraph("Complete Repository Documentation", styles["subtitle"]))
    story.append(Spacer(1, 10 * mm))
    
    # Version and date
    date_str = datetime.now().strftime("%B %Y")
    story.append(Paragraph("From A to Z: Every Concept, Implementation, and Code Explanation", styles["body"]))
    story.append(Paragraph(f"Version 2.0 · {date_str}", styles["body"]))
    
    story.append(Spacer(1, 50 * mm))
    
    # Key features box
    features_data = [
        ["🔒", "Security Scanning", "Multi-tier vulnerability detection"],
        ["🧠", "RAG-Powered Planning", "AI-enhanced scan planning"],
        ["⚡", "Performance Analysis", "Lighthouse-powered insights"],
        ["📰", "Security News", "Real-time threat intelligence"],
        ["💥", "Exploit Feed", "CVE tracking and monitoring"],
        ["🏗️", "Microservices", "Scalable cloud-native architecture"],
    ]
    
    feature_table = Table(features_data, colWidths=[15*mm, 50*mm, 100*mm])
    feature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_TEXT),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(feature_table)
    
    return story

def create_footer(canvas_obj, doc):
    """Create footer for each page"""
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(COLOR_TEXT_MUTED)
    canvas_obj.drawString(20*mm, 15*mm, f"Thandev Platform Documentation · Page {doc.page}")
    canvas_obj.drawRightString(175*mm, 15*mm, datetime.now().strftime("%Y-%m-%d"))
    canvas_obj.restoreState()

def convert_markdown_to_pdf(markdown_path, output_path):
    """Convert markdown file to PDF"""
    # Read markdown file
    with open(markdown_path, 'r', encoding='utf-8') as f:
        markdown_text = f.read()
    
    # Parse markdown
    content = parse_markdown(markdown_text)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=25*mm,
        title="Thandev Platform - Complete Documentation",
    )
    
    styles = build_styles()
    story = []
    
    # Cover page
    story.extend(create_cover_page(styles))
    story.append(PageBreak())
    
    # Process content
    for item_type, *args in content:
        if item_type == 'h1':
            story.append(Paragraph(escape_html(args[0]), styles["heading1"]))
        elif item_type == 'h2':
            story.append(Paragraph(escape_html(args[0]), styles["heading2"]))
        elif item_type == 'h3':
            story.append(Paragraph(escape_html(args[0]), styles["heading3"]))
        elif item_type == 'text':
            text = escape_html(args[0])
            if text.strip():
                story.append(Paragraph(text, styles["body"]))
        elif item_type == 'bullet':
            text = escape_html(args[0])
            # Remove leading number if present
            text = re.sub(r'^\d+\.\s*', '• ', text)
            if not text.startswith('•'):
                text = '• ' + text
            story.append(Paragraph(text, styles["bullet"]))
        elif item_type == 'code':
            code_text = escape_html(args[0])
            story.append(Preformatted(code_text, styles["code"]))
        elif item_type == 'spacer':
            story.append(Spacer(1, 6))
        elif item_type == 'hr':
            story.append(Spacer(1, 12))
            # Could add a line here
            story.append(Spacer(1, 12))
    
    # Build PDF
    doc.build(story, onFirstPage=create_footer, onLaterPages=create_footer)
    
    # Write to file
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"PDF generated successfully: {output_path}")
    print(f"Total pages: {len(story)}")

if __name__ == "__main__":
    # Paths
    repo_root = Path(__file__).parent
    markdown_file = repo_root / "COMPLETE_REPOSITORY_DOCUMENTATION.md"
    output_file = repo_root / "THANDEV_COMPLETE_REPOSITORY_DOCUMENTATION.pdf"
    
    if not markdown_file.exists():
        print(f"Error: Markdown file not found: {markdown_file}")
        exit(1)
    
    print(f"Reading markdown from: {markdown_file}")
    print(f"Generating PDF to: {output_file}")
    
    convert_markdown_to_pdf(markdown_file, output_file)



