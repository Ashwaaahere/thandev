#!/usr/bin/env python3
"""
Generate comprehensive PDF documentation about Thandev platform
"""
import io
from datetime import datetime
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
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Color Palette
COLOR_PRIMARY = colors.HexColor("#4f46e5")  # Indigo-600
COLOR_TEXT = colors.HexColor("#0f172a")  # Slate-900
COLOR_TEXT_MUTED = colors.HexColor("#475569")  # Slate-600
COLOR_BG = colors.HexColor("#f8fafc")  # Slate-50
COLOR_ACCENT = colors.HexColor("#10b981")  # Green-600

def build_styles():
    """Build paragraph styles for the PDF"""
    base = getSampleStyleSheet()
    
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=36,
            leading=42,
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
            fontSize=24,
            leading=30,
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
            textColor=COLOR_PRIMARY,
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
            fontSize=11,
            leading=16,
            textColor=COLOR_TEXT,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontSize=11,
            leading=16,
            textColor=COLOR_TEXT,
            spaceAfter=6,
            leftIndent=10,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontSize=9,
            leading=14,
            textColor=COLOR_TEXT,
            spaceAfter=8,
            fontName="Courier",
            leftIndent=10,
            rightIndent=10,
            backColor=COLOR_BG,
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

def create_cover_page(styles):
    """Create the cover page"""
    story = []
    
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("Thandev", styles["title"]))
    story.append(Paragraph("Real-Time Security Intelligence Platform", styles["subtitle"]))
    story.append(Spacer(1, 20 * mm))
    
    # Version and date
    date_str = datetime.now().strftime("%B %Y")
    story.append(Paragraph(f"Complete Platform Documentation", styles["body"]))
    story.append(Paragraph(f"Version 2.0 · {date_str}", styles["body"]))
    
    story.append(Spacer(1, 40 * mm))
    
    # Key features box
    features_data = [
        ["🔒", "Security Scanning", "Multi-tier vulnerability detection"],
        ["⚡", "Performance Analysis", "Lighthouse-powered insights"],
        ["📰", "Security News", "Real-time threat intelligence"],
        ["💥", "Exploit Feed", "CVE tracking and monitoring"],
    ]
    
    feature_table = Table(features_data, colWidths=[15*mm, 60*mm, 100*mm])
    feature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_TEXT),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(feature_table)
    
    return story

def create_overview_section(styles):
    """Create overview section"""
    story = []
    
    story.append(Paragraph("Overview", styles["heading1"]))
    story.append(Paragraph(
        "Thandev is a comprehensive, modern security intelligence platform designed for security "
        "professionals, developers, and organizations. It combines multiple security tools and data "
        "sources into a unified, modern interface with real-time updates and comprehensive analysis capabilities.",
        styles["body"]
    ))
    
    story.append(Paragraph("What is Thandev?", styles["heading2"]))
    story.append(Paragraph(
        "Thandev is a full-stack DevSecOps security platform that automates vulnerability scanning, "
        "prioritization, and reporting for web applications. The platform combines network reconnaissance "
        "(Nmap), TLS analysis (SSLScan), and application scanning (Nuclei) into a unified workflow, "
        "providing enterprise-grade security assessment capabilities with AI-powered reporting and "
        "multi-tenant SaaS architecture.",
        styles["body"]
    ))
    
    story.append(Paragraph("Key Capabilities", styles["heading2"]))
    
    capabilities = [
        "Real-time security vulnerability scanning with multiple scan levels",
        "Performance analysis using Google Lighthouse technology",
        "Security news aggregation from certified sources",
        "CVE and exploit tracking with NVD integration",
        "Domain verification and ownership validation",
        "Multi-tenant architecture with user authentication",
        "Comprehensive PDF reporting with executive summaries",
        "Cloud Run integration for scalable scanning",
        "Modern, responsive web interface",
        "RESTful API for programmatic access",
    ]
    
    for cap in capabilities:
        story.append(Paragraph(f"• {cap}", styles["bullet"]))
    
    return story

def create_features_section(styles):
    """Create detailed features section"""
    story = []
    
    story.append(Paragraph("Platform Features", styles["heading1"]))
    
    # Security Scanning
    story.append(Paragraph("Security Scanning", styles["heading2"]))
    story.append(Paragraph(
        "Thandev provides comprehensive security scanning capabilities with three distinct scan levels, "
        "each optimized for different use cases and security requirements.",
        styles["body"]
    ))
    
    story.append(Paragraph("Multi-Tier Security Scans", styles["heading3"]))
    story.append(Paragraph(
        "The platform supports three scan levels that progressively increase in depth and coverage:",
        styles["body"]
    ))
    
    scan_levels = [
        ["Level 0 - Surface", "3-8 minutes", "Quick footprinting, tech stack detection, basic SSL/TLS analysis"],
        ["Level 1 - Discovery", "10-25 minutes", "Subdomain enumeration, directory discovery, medium-severity vulnerabilities"],
        ["Level 2 - Active", "20-45 minutes", "Comprehensive CVE scanning, advanced penetration testing, full port scanning"],
    ]
    
    scan_table = Table(scan_levels, colWidths=[50*mm, 30*mm, 95*mm])
    scan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), COLOR_BG),
        ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_TEXT),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(scan_table)
    story.append(Spacer(1, 8))
    
    story.append(Paragraph("Security Tools Integration", styles["heading3"]))
    tools = [
        "Nuclei: Vulnerability scanner with 1000+ templates, supports severity filtering and template tags",
        "Nmap: Network port scanner with version detection, service enumeration, and script scanning",
        "SSLScan: TLS/SSL configuration analysis with cipher suite detection and certificate validation",
        "OpenSSL Fallback: Automatic fallback to OpenSSL for basic SSL checks when SSLScan unavailable",
    ]
    
    for tool in tools:
        story.append(Paragraph(f"• {tool}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    # Performance Scanning
    story.append(Paragraph("Performance Scanning", styles["heading2"]))
    story.append(Paragraph(
        "Thandev integrates Google Lighthouse to provide comprehensive performance analysis similar to "
        "PageSpeed Insights, helping developers optimize their web applications.",
        styles["body"]
    ))
    
    story.append(Paragraph("Core Web Vitals", styles["heading3"]))
    vitals = [
        "Largest Contentful Paint (LCP): Measures loading performance",
        "First Input Delay (FID): Measures interactivity",
        "Cumulative Layout Shift (CLS): Measures visual stability",
        "First Contentful Paint (FCP): Initial rendering time",
        "Speed Index: Perceived load speed",
        "Time to Interactive (TTI): Time until page is fully interactive",
    ]
    
    for vital in vitals:
        story.append(Paragraph(f"• {vital}", styles["bullet"]))
    
    story.append(Paragraph("Performance Features", styles["heading3"]))
    perf_features = [
        "Desktop and mobile device emulation",
        "Optimization opportunities with actionable recommendations",
        "Technical diagnostics and best practices",
        "Cloud Run deployment for scalable scanning",
        "Comprehensive performance reports",
    ]
    
    for feat in perf_features:
        story.append(Paragraph(f"• {feat}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    # Security News
    story.append(Paragraph("Security News Aggregation", styles["heading2"]))
    story.append(Paragraph(
        "Thandev aggregates security news from certified, trusted sources, providing real-time updates "
        "on cybersecurity threats, vulnerabilities, and industry developments.",
        styles["body"]
    ))
    
    story.append(Paragraph("Certified News Sources", styles["heading3"]))
    sources = [
        "The Hacker News",
        "BleepingComputer",
        "Krebs on Security",
        "SANS Internet Storm Center",
        "Zero Day Initiative (ZDI)",
        "Dark Reading",
        "Ars Technica",
    ]
    
    for source in sources:
        story.append(Paragraph(f"• {source}", styles["bullet"]))
    
    story.append(Paragraph("News Features", styles["heading3"]))
    news_features = [
        "Real-time RSS feed updates",
        "Source and category filtering",
        "Full article content extraction",
        "News statistics and trending topics",
        "Search functionality",
    ]
    
    for feat in news_features:
        story.append(Paragraph(f"• {feat}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    # Exploit Feed
    story.append(Paragraph("Exploit Feed & CVE Tracking", styles["heading2"]))
    story.append(Paragraph(
        "Thandev provides comprehensive CVE tracking and exploit monitoring, integrating with the "
        "National Vulnerability Database (NVD) and other security data sources.",
        styles["body"]
    ))
    
    story.append(Paragraph("CVE Features", styles["heading3"]))
    cve_features = [
        "Real-time CVE data from NVD API v2.0",
        "CVSS v2/v3 scoring and severity classification",
        "EPSS (Exploit Prediction Scoring System) integration",
        "KEV (Known Exploited Vulnerabilities) tracking",
        "Advanced filtering by severity, CVE ID, date, and source",
        "Exploit availability and PoC tracking",
    ]
    
    for feat in cve_features:
        story.append(Paragraph(f"• {feat}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    # Domain Verification
    story.append(Paragraph("Domain Verification", styles["heading2"]))
    story.append(Paragraph(
        "Thandev includes a secure domain verification system that allows users to verify domain ownership "
        "via DNS TXT records, enabling advanced scanning features and domain-specific configurations.",
        styles["body"]
    ))
    
    story.append(Paragraph("Verification Features", styles["heading3"]))
    verify_features = [
        "DNS TXT record verification",
        "Cryptographically secure verification tokens",
        "Real-time verification status checking",
        "48-hour token validity with automatic expiration",
        "Rate limiting for verification requests",
    ]
    
    for feat in verify_features:
        story.append(Paragraph(f"• {feat}", styles["bullet"]))
    
    return story

def create_architecture_section(styles):
    """Create architecture section"""
    story = []
    
    story.append(Paragraph("System Architecture", styles["heading1"]))
    story.append(Paragraph(
        "Thandev is built with a modern, scalable architecture using industry-standard technologies "
        "and best practices for security, performance, and maintainability.",
        styles["body"]
    ))
    
    story.append(Paragraph("Tech Stack", styles["heading2"]))
    
    story.append(Paragraph("Frontend", styles["heading3"]))
    frontend_tech = [
        "Next.js 14 with App Router for server-side rendering and routing",
        "TypeScript for type-safe development",
        "Tailwind CSS 4 for modern utility-first styling",
        "Framer Motion for smooth animations and transitions",
        "NextAuth.js for authentication and session management",
        "Prisma for database ORM and type safety",
    ]
    
    for tech in frontend_tech:
        story.append(Paragraph(f"• {tech}", styles["bullet"]))
    
    story.append(Paragraph("Backend", styles["heading3"]))
    backend_tech = [
        "FastAPI for high-performance Python API framework",
        "SQLAlchemy 2.0 for modern Python ORM",
        "PostgreSQL (production) / SQLite (development) for data persistence",
        "Redis for caching and task queue",
        "Celery for distributed task processing",
        "Alembic for database migrations",
        "Pydantic for data validation and settings management",
    ]
    
    for tech in backend_tech:
        story.append(Paragraph(f"• {tech}", styles["bullet"]))
    
    story.append(Paragraph("Cloud Services", styles["heading3"]))
    cloud_tech = [
        "Google Cloud Run for serverless container platform (scanning services)",
        "Vercel for frontend deployment and hosting",
        "Fly.io for backend deployment and hosting",
        "Google Cloud Storage for artifact storage",
    ]
    
    for tech in cloud_tech:
        story.append(Paragraph(f"• {tech}", styles["bullet"]))
    
    story.append(Paragraph("Security Tools", styles["heading3"]))
    security_tools = [
        "Nuclei v3.4.10: Vulnerability scanner with 1000+ templates",
        "Nmap: Network port scanner and service detection",
        "SSLScan: SSL/TLS configuration analysis",
        "Lighthouse: Performance auditing tool",
        "Puppeteer: Headless Chrome automation",
    ]
    
    for tool in security_tools:
        story.append(Paragraph(f"• {tool}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Architecture Components", styles["heading2"]))
    story.append(Paragraph(
        "The platform consists of several key components working together to provide a seamless "
        "user experience:",
        styles["body"]
    ))
    
    components = [
        "Frontend (Next.js): User interface, authentication, dashboard, scan management",
        "Backend API (FastAPI): RESTful API, scan orchestration, data processing",
        "Database (PostgreSQL): Data persistence, user management, scan history",
        "Task Queue (Celery + Redis): Background job processing, scan execution",
        "Cloud Run Services: Scalable scanning services for security and performance scans",
        "Scheduler: Automated data ingestion from NVD, RSS feeds, and other sources",
    ]
    
    for comp in components:
        story.append(Paragraph(f"• {comp}", styles["bullet"]))
    
    return story

def create_workflow_section(styles):
    """Create workflow section"""
    story = []
    
    story.append(Paragraph("How It Works", styles["heading1"]))
    
    story.append(Paragraph("Security Scan Workflow", styles["heading2"]))
    story.append(Paragraph(
        "The security scanning process follows a well-defined workflow from scan initiation to "
        "report generation:",
        styles["body"]
    ))
    
    workflow_steps = [
        "1. User initiates scan via web interface or API, specifying target URL and scan level",
        "2. Backend creates ScanJob record with status PENDING",
        "3. Celery task is queued for asynchronous processing",
        "4. Celery worker picks up task and updates status to RUNNING",
        "5. Scan Orchestrator determines tools to run based on scan level (Tool Matrix)",
        "6. Tools execute sequentially: Nuclei, Nmap, SSLScan (based on level)",
        "7. Tool outputs are parsed by Findings Ingestor",
        "8. Findings are stored in database with severity, CVE IDs, and metadata",
        "9. AI Reporter generates executive summary and risk score",
        "10. Scan status updated to COMPLETED with summary data",
        "11. User can view results, download PDF reports, and track scan history",
    ]
    
    for step in workflow_steps:
        story.append(Paragraph(step, styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Performance Scan Workflow", styles["heading2"]))
    story.append(Paragraph(
        "Performance scans follow a similar workflow but use Lighthouse for analysis:",
        styles["body"]
    ))
    
    perf_steps = [
        "1. User initiates performance scan with target URL and device type",
        "2. Backend creates PerformanceScan record",
        "3. Lighthouse scan executes (locally or via Cloud Run)",
        "4. Performance metrics extracted: Core Web Vitals, scores, opportunities",
        "5. Results stored and displayed in interactive dashboard",
        "6. User can view detailed metrics, optimization opportunities, and diagnostics",
    ]
    
    for step in perf_steps:
        story.append(Paragraph(step, styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Tool Matrix System", styles["heading2"]))
    story.append(Paragraph(
        "Thandev uses a centralized Tool Matrix configuration that determines which tools run at "
        "each scan level. This provides flexibility and maintainability:",
        styles["body"]
    ))
    
    tool_matrix_info = [
        "Basic Level: Nuclei only (low/medium severity, CVE/vulnerability/exposure tags)",
        "Pro Level: Nuclei + Nmap (expanded severity and tags, top 1000 ports)",
        "Advanced Level: Nuclei + Nmap + SSLScan (full coverage, all ports, comprehensive analysis)",
    ]
    
    for info in tool_matrix_info:
        story.append(Paragraph(f"• {info}", styles["bullet"]))
    
    return story

def create_api_section(styles):
    """Create API documentation section"""
    story = []
    
    story.append(Paragraph("API Documentation", styles["heading1"]))
    story.append(Paragraph(
        "Thandev provides a comprehensive RESTful API for programmatic access to all platform features. "
        "The API follows REST conventions and uses JSON for data exchange.",
        styles["body"]
    ))
    
    story.append(Paragraph("Core Endpoints", styles["heading2"]))
    
    endpoints = [
        ["GET /health", "Health check with database status"],
        ["GET /api/exploits", "List exploits with pagination and filtering"],
        ["GET /api/exploits/stats", "Get exploit statistics"],
        ["POST /api/security-scan/", "Start a security scan"],
        ["GET /api/security-scan/{job_id}", "Get scan status and results"],
        ["POST /api/performance-scan/", "Start a performance scan"],
        ["GET /api/performance-scan/{job_id}", "Get performance scan results"],
        ["GET /news", "List security news articles"],
        ["POST /api/projects", "Create a new project"],
        ["GET /api/projects", "List all projects"],
    ]
    
    api_table = Table(endpoints, colWidths=[80*mm, 95*mm])
    api_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), COLOR_BG),
        ('TEXTCOLOR', (0, 0), (-1, -1), COLOR_TEXT),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Courier'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(api_table)
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Rate Limiting", styles["heading2"]))
    story.append(Paragraph(
        "The API implements rate limiting to ensure fair usage and prevent abuse:",
        styles["body"]
    ))
    
    rate_limits = [
        "Exploits endpoint: 100 requests/minute",
        "Exploit Stats: 30 requests/minute",
        "Security Scans: 10 requests/minute",
        "Performance Scans: 10 requests/minute",
    ]
    
    for limit in rate_limits:
        story.append(Paragraph(f"• {limit}", styles["bullet"]))
    
    return story

def create_user_benefits_section(styles):
    """Create user benefits section"""
    story = []
    
    story.append(Paragraph("What Thandev Offers Users", styles["heading1"]))
    
    story.append(Paragraph("For Security Professionals", styles["heading2"]))
    benefits_security = [
        "Comprehensive vulnerability scanning with multiple scan levels",
        "Real-time CVE tracking and exploit monitoring",
        "Security news aggregation from trusted sources",
        "Detailed PDF reports with executive summaries",
        "Multi-tenant support for managing multiple organizations",
        "API access for integration with existing security tools",
        "Historical scan tracking and trend analysis",
    ]
    
    for benefit in benefits_security:
        story.append(Paragraph(f"• {benefit}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("For Developers", styles["heading2"]))
    benefits_devs = [
        "Performance analysis with Core Web Vitals metrics",
        "Actionable optimization recommendations",
        "Desktop and mobile performance testing",
        "Integration with CI/CD pipelines",
        "RESTful API for automation",
        "Modern, intuitive web interface",
    ]
    
    for benefit in benefits_devs:
        story.append(Paragraph(f"• {benefit}", styles["bullet"]))
    
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("For Organizations", styles["heading2"]))
    benefits_orgs = [
        "Enterprise-grade security assessment capabilities",
        "Scalable architecture with Cloud Run integration",
        "Multi-tenant SaaS architecture",
        "Comprehensive reporting for compliance",
        "Real-time threat intelligence",
        "Cost-effective scanning infrastructure",
    ]
    
    for benefit in benefits_orgs:
        story.append(Paragraph(f"• {benefit}", styles["bullet"]))
    
    return story

def create_deployment_section(styles):
    """Create deployment section"""
    story = []
    
    story.append(Paragraph("Deployment & Infrastructure", styles["heading1"]))
    
    story.append(Paragraph("Deployment Options", styles["heading2"]))
    story.append(Paragraph(
        "Thandev supports multiple deployment options to suit different needs:",
        styles["body"]
    ))
    
    story.append(Paragraph("Frontend (Vercel)", styles["heading3"]))
    story.append(Paragraph(
        "The Next.js frontend is optimized for deployment on Vercel, providing automatic scaling, "
        "CDN distribution, and seamless CI/CD integration.",
        styles["body"]
    ))
    
    story.append(Paragraph("Backend (Fly.io)", styles["heading3"]))
    story.append(Paragraph(
        "The FastAPI backend can be deployed on Fly.io with PostgreSQL database, Redis for caching, "
        "and Celery workers for background processing.",
        styles["body"]
    ))
    
    story.append(Paragraph("Cloud Run Services", styles["heading3"]))
    story.append(Paragraph(
        "Security and performance scanning services are deployed as Google Cloud Run Jobs, providing "
        "serverless, scalable execution with automatic resource management.",
        styles["body"]
    ))
    
    story.append(Paragraph("Docker Support", styles["heading3"]))
    story.append(Paragraph(
        "Thandev includes Docker Compose configuration for local development and containerized "
        "deployment, making it easy to run the entire stack locally or in containerized environments.",
        styles["body"]
    ))
    
    return story

def create_footer(canvas, doc):
    """Create footer for each page"""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(COLOR_TEXT_MUTED)
    canvas.drawString(20*mm, 15*mm, f"Thandev Platform Documentation · Page {doc.page}")
    canvas.drawRightString(175*mm, 15*mm, datetime.now().strftime("%Y-%m-%d"))
    canvas.restoreState()

def generate_pdf(output_path):
    """Generate the comprehensive PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=25*mm,
        title="Thandev Platform Documentation",
    )
    
    styles = build_styles()
    story = []
    
    # Cover page
    story.extend(create_cover_page(styles))
    story.append(PageBreak())
    
    # Table of contents placeholder
    story.append(Paragraph("Table of Contents", styles["heading1"]))
    toc_items = [
        "Overview",
        "Platform Features",
        "System Architecture",
        "How It Works",
        "API Documentation",
        "What Thandev Offers Users",
        "Deployment & Infrastructure",
    ]
    for item in toc_items:
        story.append(Paragraph(f"• {item}", styles["bullet"]))
    story.append(PageBreak())
    
    # Main content
    story.extend(create_overview_section(styles))
    story.append(PageBreak())
    
    story.extend(create_features_section(styles))
    story.append(PageBreak())
    
    story.extend(create_architecture_section(styles))
    story.append(PageBreak())
    
    story.extend(create_workflow_section(styles))
    story.append(PageBreak())
    
    story.extend(create_api_section(styles))
    story.append(PageBreak())
    
    story.extend(create_user_benefits_section(styles))
    story.append(PageBreak())
    
    story.extend(create_deployment_section(styles))
    
    # Build PDF
    doc.build(story, onFirstPage=create_footer, onLaterPages=create_footer)
    
    # Write to file
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"PDF generated successfully: {output_path}")

if __name__ == "__main__":
    output_file = "/home/avi/Downloads/thandev-github-starter/thandev/THANDEV_COMPLETE_PLATFORM_DOCUMENTATION.pdf"
    generate_pdf(output_file)


