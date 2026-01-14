import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem

# Add backend directory to path to import local modules if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def create_pdf(markdown_path, output_path):
    print(f"Generating PDF from {markdown_path} to {output_path}")
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Title'],
        fontSize=24,
        leading=30,
        spaceAfter=20,
        textColor=colors.HexColor("#4f46e5")
    ))
    styles.add(ParagraphStyle(
        name='CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor("#1e1b4b")
    ))
    styles.add(ParagraphStyle(
        name='CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor("#4338ca")
    ))
    styles.add(ParagraphStyle(
        name='CustomHeading3',
        parent=styles['Heading3'],
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#4f46e5")
    ))
    styles.add(ParagraphStyle(
        name='BodyTextCustom',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='BulletPoint',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=4
    ))

    story = []
    
    # Manual Cover Page
    story.append(Spacer(1, 60*mm))
    story.append(Paragraph("Thandev Backend", styles['MainTitle']))
    story.append(Paragraph("Comprehensive System Documentation", styles['Heading1']))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Generated automatically from system codebase", styles['BodyTextCustom']))
    story.append(PageBreak())

    # Read Markdown
    try:
        with open(markdown_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Could not find markdown file at {markdown_path}")
        return

    current_list_items = []

    def flush_list():
        nonlocal current_list_items
        if current_list_items:
            # Create a ListFlowable
            tlist = ListFlowable(
                [ListItem(Paragraph(text, styles['BulletPoint'])) for text in current_list_items],
                bulletType='bullet',
                start='circle',
                leftIndent=10
            )
            story.append(tlist)
            story.append(Spacer(1, 6))
            current_list_items = []

    for line in lines:
        line = line.strip()
        if not line:
            flush_list()
            continue

        if line.startswith('# '):
            flush_list()
            story.append(Paragraph(line[2:], styles['MainTitle']))
        elif line.startswith('## '):
            flush_list()
            story.append(Paragraph(line[3:], styles['CustomHeading1']))
        elif line.startswith('### '):
            flush_list()
            story.append(Paragraph(line[4:], styles['CustomHeading2']))
        elif line.startswith('#### '):
            flush_list()
            story.append(Paragraph(line[5:], styles['CustomHeading3']))
        elif line.startswith('- ') or line.startswith('* '):
            text = line[2:]
            # Bold handling (simple **bold**)
            text = text.replace('**', '<b>', 1).replace('**', '</b>', 1)
            text = text.replace('`', '<font face="Courier">', 1).replace('`', '</font>', 1)
            current_list_items.append(text)
        else:
            flush_list()
            text = line
            # Simple markdown bold/code support
            while '**' in text:
                text = text.replace('**', '<b>', 1).replace('**', '</b>', 1)
            while '`' in text:
                text = text.replace('`', '<font face="Courier" color="black">', 1).replace('`', '</font>', 1)
            
            story.append(Paragraph(text, styles['BodyTextCustom']))

    flush_list()
    doc.build(story)
    print(f"Success! PDF generated at: {output_path}")

if __name__ == "__main__":
    # Use absolute paths
    base_dir = "/home/ashwath/thandev/backend/docs"
    md_file = os.path.join(base_dir, "backend_documentation.md")
    pdf_file = os.path.join(base_dir, "backend_documentation.pdf")
    create_pdf(md_file, pdf_file)
