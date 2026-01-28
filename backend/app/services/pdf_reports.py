"""
Futuristic & formal PDF report generation service using ReportLab Platypus

Design: White background, dark text, enterprise security report aesthetic
"""
import io
from typing import Literal, List, Tuple, Any
from collections import Counter
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
)

from sqlalchemy.orm import Session, joinedload

from app.models.scan import ScanJob
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.models.project import Project
from app.core.constants import CANON_FINDINGS_COUNT, CANON_SEV_BREAKDOWN, DEPRECATED_FINDINGS_BY_SEVERITY
import logging

logger = logging.getLogger(__name__)

ReportMode = Literal["full", "executive"]

# ---------- Color Palette ----------
COLOR_PAGE_BG = colors.white
COLOR_TEXT_PRIMARY = colors.HexColor("#0f172a")  # slate-900
COLOR_TEXT_MUTED = colors.HexColor("#475569")    # slate-600
COLOR_ACCENT = colors.HexColor("#4f46e5")        # indigo-600 (Thandev brand)
COLOR_HEADER_BG = colors.HexColor("#4f46e5")     # indigo-600
COLOR_LABEL_BG = colors.HexColor("#f1f5f9")      # slate-100
COLOR_ROW_ALT = colors.HexColor("#f8fafc")       # slate-50
COLOR_CARD_BG = colors.HexColor("#f8fafc")       # slate-50 for card backgrounds

# Severity colors with backgrounds for pills
SEVERITY_COLORS = {
    "critical": colors.HexColor("#dc2626"),  # red-600
    "high": colors.HexColor("#ea580c"),      # orange-600
    "medium": colors.HexColor("#ca8a04"),    # yellow-600
    "low": colors.HexColor("#16a34a"),       # green-600
    "info": colors.HexColor("#64748b"),      # slate-500
}

SEVERITY_BG_COLORS = {
    "critical": colors.HexColor("#dc2626"),   # red-600
    "high": colors.HexColor("#ea580c"),      # orange-600
    "medium": colors.HexColor("#fef3c7"),    # amber-100 (light)
    "low": colors.HexColor("#dcfce7"),       # green-100 (light)
    "info": colors.HexColor("#e2e8f0"),      # slate-200 (light)
}

SEVERITY_TEXT_COLORS = {
    "critical": colors.white,
    "high": colors.white,
    "medium": colors.HexColor("#78350f"),    # amber-900 (dark text on light)
    "low": colors.HexColor("#14532d"),       # green-900 (dark text on light)
    "info": colors.HexColor("#1e293b"),      # slate-800 (dark text on light)
}

# Status colors
STATUS_COLORS = {
    "completed": colors.HexColor("#16a34a"),  # green-600
    "failed": colors.HexColor("#dc2626"),     # red-600
    "error": colors.HexColor("#dc2626"),       # red-600
    "running": colors.HexColor("#ca8a04"),    # yellow-600
    "pending": colors.HexColor("#ca8a04"),    # yellow-600
    "queued": colors.HexColor("#ca8a04"),     # yellow-600
}


# ---------- Helper Functions ----------

def _safe_summary_value(summary: Any, key: str, default: Any = None) -> Any:
    if summary is None:
        return default
    if isinstance(summary, dict):
        return summary.get(key, default)
    return getattr(summary, key, default)


def _safe_stack_value(stack_info: Any, key: str, default: Any = None) -> Any:
    if stack_info is None:
        return default
    if isinstance(stack_info, dict):
        return stack_info.get(key, default)
    return getattr(stack_info, key, default)


def _severity_label(severity: Any) -> str:
    """Normalize severity to lowercase key."""
    if hasattr(severity, "value"):
        s = str(severity.value).lower()
    else:
        s = str(severity).lower() if severity else ""
    if s not in SEVERITY_COLORS:
        s = "info"
    return s


def _load_scan_and_findings(
    db: Session, scan_id: str, tenant: Tenant
) -> Tuple[ScanJob, List[Finding]]:
    """
    Load a ScanJob and its findings using tenant scoping.
    """
    q = (
        db.query(ScanJob)
        .options(
            joinedload(ScanJob.project),
            joinedload(ScanJob.findings),
        )
        .join(Project, ScanJob.project_id == Project.id)
        .filter(
            ScanJob.id == scan_id,
            Project.tenant_id == tenant.id,
        )
    )

    scan = q.first()
    if not scan:
        raise ValueError("Scan not found for this tenant")

    findings: List[Finding] = list(getattr(scan, "findings", []) or [])
    return scan, findings


def _build_styles():
    """Build paragraph styles for formal, enterprise report."""
    base = getSampleStyleSheet()
    
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=30,
            leading=34,
            textColor=COLOR_ACCENT,
            spaceAfter=6,
            alignment=1,  # Center
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["BodyText"],
            fontSize=12,
            leading=16,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=8,
            alignment=1,  # Center
        ),
        "tagline": ParagraphStyle(
            "tagline",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=12,
            alignment=1,  # Center
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Heading2"],
            fontSize=16,
            leading=20,
            textColor=COLOR_ACCENT,
            spaceBefore=16,
            spaceAfter=10,
            fontName="Helvetica-Bold",
        ),
        "subsection_title": ParagraphStyle(
            "subsection_title",
            parent=base["Heading3"],
            fontSize=12,
            leading=16,
            textColor=COLOR_TEXT_PRIMARY,
            spaceBefore=10,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=COLOR_TEXT_PRIMARY,
            spaceAfter=6,
        ),
        "small_muted": ParagraphStyle(
            "small_muted",
            parent=base["BodyText"],
            fontSize=8,
            leading=10,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=4,
        ),
        "finding_title": ParagraphStyle(
            "finding_title",
            parent=base["BodyText"],
            fontSize=11,
            leading=15,
            textColor=COLOR_TEXT_PRIMARY,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=COLOR_TEXT_PRIMARY,
            leftIndent=12,
            spaceAfter=4,
        ),
        "risk_score_large": ParagraphStyle(
            "risk_score_large",
            parent=base["BodyText"],
            fontSize=36,
            leading=42,
            textColor=COLOR_TEXT_PRIMARY,
            spaceAfter=4,
            fontName="Helvetica-Bold",
            alignment=0,  # Left
        ),
    }
    return styles


def _header_footer(canvas, doc):
    """Header and footer callback for PDF pages with branding."""
    canvas.saveState()
    
    # Header band with accent color
    header_band_y = A4[1] - 12 * mm
    canvas.setFillColor(COLOR_ACCENT)
    canvas.rect(doc.leftMargin, header_band_y, A4[0] - doc.leftMargin - doc.rightMargin, 3 * mm, fill=1, stroke=0)
    
    # Left: "Thandev" branding
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(colors.white)
    canvas.drawString(doc.leftMargin + 2 * mm, header_band_y + 0.5 * mm, "Thandev")
    
    # Right: "Security Scan Report"
    canvas.setFont("Helvetica", 9)
    report_text = "Security Scan Report"
    text_width = canvas.stringWidth(report_text, "Helvetica", 9)
    canvas.drawString(A4[0] - doc.rightMargin - text_width - 2 * mm, header_band_y + 0.5 * mm, report_text)
    
    # Footer: left text + page number right
    footer_y = 12 * mm
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(COLOR_TEXT_MUTED)
    canvas.drawString(doc.leftMargin, footer_y, "Thandev Security Scan Report")
    
    page_text = f"Page {doc.page}"
    text_width = canvas.stringWidth(page_text, "Helvetica", 8)
    canvas.drawString(A4[0] - doc.rightMargin - text_width, footer_y, page_text)
    
    canvas.restoreState()


def _build_status_pill(status: str) -> Table:
    """Build a status pill/badge table."""
    status_lower = status.lower()
    status_color = STATUS_COLORS.get(status_lower, COLOR_TEXT_MUTED)
    
    # Determine text color (white for dark backgrounds, dark for light)
    if status_lower in ["completed"]:
        text_color = colors.white
    elif status_lower in ["failed", "error"]:
        text_color = colors.white
    else:
        text_color = colors.HexColor("#78350f")  # amber-900 for yellow backgrounds
    
    pill_data = [[f"Status: {status.upper()}"]]
    pill_table = Table(
        pill_data,
        colWidths=[50 * mm],
        hAlign="CENTER",
    )
    pill_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), status_color),
            ("TEXTCOLOR", (0, 0), (-1, -1), text_color),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    return pill_table


def _compute_findings_metrics(findings: List[Finding]) -> tuple[int, dict, float]:
    """Compute findings count, severity breakdown, and risk score from actual findings."""
    import math
    
    findings_count = len(findings)
    severity_counts = Counter(_severity_label(getattr(f, "severity", "info")) for f in findings)
    breakdown = {sev: severity_counts.get(sev, 0) for sev in ["critical", "high", "medium", "low", "info"]}
    
    # Calculate risk score (0-10 scale)
    # Formula: max severity (Critical=10, High=8, Medium=5, Low=2, Info=0)
    #          + log factor for medium+ findings (min(3, log2(1+count_medium_high)))
    max_severity_scores = {
        "critical": 10,
        "high": 8,
        "medium": 5,
        "low": 2,
        "info": 0,
    }
    
    # Find max severity present
    max_severity_score = 0
    for severity, count in breakdown.items():
        if count > 0:
            max_severity_score = max(max_severity_score, max_severity_scores.get(severity, 0))
    
    # Count medium+ findings for log factor
    count_medium_high = breakdown["medium"] + breakdown["high"] + breakdown["critical"]
    log_factor = min(3.0, math.log2(1 + count_medium_high)) if count_medium_high > 0 else 0.0
    
    # Calculate base score
    base_score = max_severity_score + log_factor
    
    # Clamp to 0-10 and round to 1 decimal
    risk_score = max(0.0, min(10.0, base_score))
    risk_score = round(risk_score, 1)
    
    # Ensure > 0 if there's at least one Medium finding
    if breakdown["medium"] > 0 and risk_score == 0:
        risk_score = 0.1
    
    return findings_count, breakdown, risk_score


def _build_cover_page(scan: ScanJob, findings: List[Finding], styles: dict) -> List:
    """Build professional cover page with metadata."""
    story = []
    
    # Title
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("Thandev Security Scan Report", styles["title"]))
    
    # Subtitle
    project = getattr(scan, "project", None)
    target_url = ""
    if project:
        target_url = getattr(project, "target_url", "") or ""
    if not target_url:
        target_url = _safe_stack_value(getattr(scan, "stack_info", None), "target_url", "")
    
    subtitle_text = f"Automated security assessment for {target_url}" if target_url else "Automated security assessment"
    story.append(Paragraph(subtitle_text, styles["subtitle"]))
    
    # Status pill
    status = getattr(scan, "status", "")
    if hasattr(status, "value"):
        status = str(status.value)
    else:
        status = str(status) if status else "N/A"
    
    story.append(Spacer(1, 6))
    story.append(_build_status_pill(status))
    story.append(Spacer(1, 8))
    
    # Generated by tagline
    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    tagline_text = f"Generated by Thandev · {generated_time}"
    story.append(Paragraph(tagline_text, styles["tagline"]))
    story.append(Spacer(1, 16 * mm))
    
    # Metadata table (narrower, card-like)
    summary = getattr(scan, "summary", None)
    findings_count, severity_breakdown, risk_score = _compute_findings_metrics(findings)
    
    created_at = getattr(scan, "created_at", None)
    created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if created_at else "N/A"
    
    started_at = getattr(scan, "started_at", None)
    started_at_str = started_at.strftime("%Y-%m-%d %H:%M:%S UTC") if started_at else "N/A"
    
    completed_at = getattr(scan, "completed_at", None)
    completed_at_str = completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if completed_at else "N/A"
    
    scan_level = getattr(scan, "scan_level", "")
    if hasattr(scan_level, "value"):
        scan_level = str(scan_level.value).upper()
    else:
        scan_level = str(scan_level).upper() if scan_level else "N/A"
    
    meta_data = [
        ["Scan ID", str(getattr(scan, "id", ""))],
        ["Target URL", target_url or "N/A"],
        ["Scan Level", scan_level],
        ["Risk Score", str(risk_score)],
        ["Total Findings", str(findings_count)],
        ["Created At", created_at_str],
        ["Started At", started_at_str],
        ["Completed At", completed_at_str],
    ]
    
    # Narrower table with card-like styling
    meta_table = Table(
        meta_data,
        colWidths=[42 * mm, 108 * mm],
        hAlign="CENTER",
    )
    meta_table.setStyle(
        TableStyle(
            [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                # Label column - right aligned
                ("BACKGROUND", (0, 1), (0, -1), COLOR_LABEL_BG),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 1), (0, -1), COLOR_TEXT_PRIMARY),
                ("FONTSIZE", (0, 1), (0, -1), 9),
                ("ALIGN", (0, 1), (0, -1), "RIGHT"),
                # Value column - left aligned
                ("TEXTCOLOR", (1, 1), (1, -1), COLOR_TEXT_PRIMARY),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (1, 1), (1, -1), 9),
                ("ALIGN", (1, 1), (1, -1), "LEFT"),
                ("ROWBACKGROUNDS", (1, 1), (1, -1), [colors.white, COLOR_ROW_ALT]),
                # Grid with subtle colors
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 20 * mm))
    
    return story


def _build_executive_summary(scan: ScanJob, findings: List[Finding], styles: dict, mode: str = "full") -> List:
    """Build executive summary section with risk at a glance and severity breakdown."""
    story = []
    
    summary = getattr(scan, "summary", None)
    findings_count, severity_breakdown, risk_score = _compute_findings_metrics(findings)
    
    # Section 1: Risk at a glance
    story.append(Paragraph("Risk at a Glance", styles["section_title"]))
    
    max_severity = "INFO"
    for sev in ["critical", "high", "medium", "low", "info"]:
        if severity_breakdown.get(sev, 0) > 0:
            max_severity = sev.upper()
            break
    
    # Risk score and max severity in a table
    risk_data = [
        ["Risk Score", "Max Severity"],
        [str(risk_score), max_severity],
    ]
    
    risk_table = Table(
        risk_data,
        colWidths=[75 * mm, 75 * mm],
        hAlign="LEFT",
    )
    
    # Build max severity pill
    max_sev_lower = max_severity.lower()
    sev_bg = SEVERITY_BG_COLORS.get(max_sev_lower, COLOR_LABEL_BG)
    sev_text = SEVERITY_TEXT_COLORS.get(max_sev_lower, COLOR_TEXT_PRIMARY)
    
    risk_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), COLOR_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
            ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (0, 0), 9),
            ("BACKGROUND", (1, 0), (1, 0), COLOR_HEADER_BG),
            ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (1, 0), (1, 0), 9),
            # Risk score cell - large number
            ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (0, 1), 32),
            ("TEXTCOLOR", (0, 1), (0, 1), COLOR_TEXT_PRIMARY),
            ("ALIGN", (0, 1), (0, 1), "CENTER"),
            ("VALIGN", (0, 1), (0, 1), "MIDDLE"),
            # Max severity cell - colored pill
            ("BACKGROUND", (1, 1), (1, 1), sev_bg),
            ("TEXTCOLOR", (1, 1), (1, 1), sev_text),
            ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (1, 1), (1, 1), 12),
            ("ALIGN", (1, 1), (1, 1), "CENTER"),
            ("VALIGN", (1, 1), (1, 1), "MIDDLE"),
            ("BOTTOMPADDING", (1, 1), (1, 1), 6),
            ("TOPPADDING", (1, 1), (1, 1), 6),
            # Grid
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ])
    )
    story.append(risk_table)
    story.append(Spacer(1, 12))
    
    # Section 2: Executive Summary text
    story.append(Paragraph("Executive Summary", styles["section_title"]))
    
    exec_summary = _safe_summary_value(
        summary,
        "executive_summary",
        None,
    )
    
    if not exec_summary:
        # Generate enhanced executive summary
        from datetime import datetime
        target_url = getattr(scan, "project", None)
        target_str = getattr(target_url, "target_url", "target") if target_url else "target"
        scan_level = getattr(scan, "scan_level", "unknown")
        scan_date = getattr(scan, "created_at", datetime.now())
        date_str = scan_date.strftime("%d %B %Y") if hasattr(scan_date, "strftime") else str(scan_date)
        
        if findings_count == 0:
            exec_summary = (
                f"This security assessment was conducted on {target_str} using {scan_level} scan level on {date_str}. "
                "No security findings were detected. The target appears secure based on the scan configuration. "
                "Continue routine monitoring and periodic assessments."
            )
        else:
            critical_count = severity_breakdown.get("critical", 0)
            high_count = severity_breakdown.get("high", 0)
            medium_count = severity_breakdown.get("medium", 0)
            
            exec_summary = (
                f"This security assessment was conducted on {target_str} using {scan_level} scan level on {date_str}. "
            )
            
            if critical_count > 0:
                exec_summary += (
                    f"The scan identified {findings_count} finding(s) with {critical_count} critical, {high_count} high, "
                    f"and {medium_count} medium-severity issue(s). The overall risk score is {risk_score}/10. "
                    "Critical vulnerabilities require immediate attention."
                )
            elif high_count > 0:
                exec_summary += (
                    f"The scan identified {findings_count} finding(s) with {high_count} high and {medium_count} medium-severity issue(s). "
                    f"The overall risk score is {risk_score}/10. High-severity issues should be prioritized for remediation."
                )
            else:
                exec_summary += (
                    f"The scan identified {findings_count} finding(s) with an overall risk score of {risk_score}/10. "
                    "Focus on hardening and best practices to further improve security posture."
                )
    
    story.append(Paragraph(str(exec_summary), styles["body"]))
    story.append(Spacer(1, 10))
    
    # Section 2.5: Category-based findings summary (for executive mode)
    if mode == "executive" and findings_count > 0:
        import json
        from collections import defaultdict
        
        # Count findings by category
        category_counts = defaultdict(int)
        category_display = {
            "xss": "Cross-Site Scripting (XSS)",
            "sqli": "SQL Injection",
            "ssrf": "Server-Side Request Forgery (SSRF)",
            "ssti": "Server-Side Template Injection (SSTI)",
            "xxe": "XML External Entities (XXE)",
            "dir_traversal": "Directory Traversal / File Inclusion",
            "cors": "CORS Misconfiguration",
            "csrf": "Cross-Site Request Forgery (CSRF)",
            "cmdi": "Command Injection",
            "idor": "Insecure Direct Object Reference (IDOR)",
        }
        
        for f in findings:
            categories = []
            if f.raw_data:
                try:
                    raw_data_dict = json.loads(f.raw_data)
                    if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                        categories = raw_data_dict["categories"]
                        if not isinstance(categories, list):
                            categories = [categories] if categories else []
                except:
                    pass
            
            for cat in categories:
                if isinstance(cat, str):
                    cat_lower = cat.lower()
                    # Normalize
                    if cat_lower in ["directory_traversal", "dir_traversal"]:
                        cat_lower = "dir_traversal"
                    elif cat_lower in ["cors_misconfig", "cors"]:
                        cat_lower = "cors"
                    elif cat_lower in ["command_injection", "cmdi"]:
                        cat_lower = "cmdi"
                    
                    if cat_lower in category_display:
                        category_counts[cat_lower] += 1
        
        # Build category bullets
        category_bullets = []
        
        # Check each main category
        main_categories = ["xss", "sqli", "ssrf", "ssti", "xxe", "dir_traversal", "cors", "csrf", "cmdi", "idor"]
        
        for cat in main_categories:
            count = category_counts.get(cat, 0)
            if count > 0:
                display_name = category_display[cat]
                if cat == "xss":
                    category_bullets.append(
                        f"Reflected XSS was found on {count} URL(s); these issues allow an attacker to execute JavaScript in a victim's browser."
                    )
                elif cat == "sqli":
                    category_bullets.append(
                        f"SQL Injection was detected on {count} endpoint(s); this vulnerability may allow database compromise and data exfiltration."
                    )
                elif cat == "ssrf":
                    category_bullets.append(
                        f"Server-Side Request Forgery (SSRF) was identified on {count} endpoint(s); this may allow internal network access."
                    )
                elif cat == "ssti":
                    category_bullets.append(
                        f"Server-Side Template Injection (SSTI) was found on {count} endpoint(s); remote code execution may be possible."
                    )
                elif cat == "xxe":
                    category_bullets.append(
                        f"XML External Entities (XXE) was detected on {count} endpoint(s); file system access may be possible."
                    )
                elif cat == "dir_traversal":
                    category_bullets.append(
                        f"Directory traversal / file inclusion was found on {count} endpoint(s); sensitive files may be accessible."
                    )
                elif cat == "cors":
                    category_bullets.append(
                        f"CORS misconfiguration was identified on {count} endpoint(s); cross-origin data access may be possible."
                    )
                elif cat == "csrf":
                    category_bullets.append(
                        f"Cross-Site Request Forgery (CSRF) was detected on {count} endpoint(s); unauthorized actions may be performed on behalf of users."
                    )
                elif cat == "cmdi":
                    category_bullets.append(
                        f"Command injection was found on {count} endpoint(s); remote code execution may be possible."
                    )
                elif cat == "idor":
                    category_bullets.append(
                        f"Insecure Direct Object Reference (IDOR) was identified on {count} endpoint(s); unauthorized access to user data may be possible."
                    )
        
        # Add "not detected" messages for categories with 0 findings (limit to 2-6 total bullets)
        not_detected = []
        for cat in main_categories:
            if category_counts.get(cat, 0) == 0:
                display_name = category_display[cat]
                if cat == "sqli":
                    not_detected.append("No SQL Injection was detected on the tested endpoints.")
                elif cat == "ssrf":
                    not_detected.append("Server-Side Request Forgery (SSRF) was not observed during this assessment.")
                elif cat == "ssti":
                    not_detected.append("Server-Side Template Injection (SSTI) was not observed during this assessment.")
                elif cat == "xxe":
                    not_detected.append("XML External Entities (XXE) was not observed during this assessment.")
                elif cat == "dir_traversal":
                    not_detected.append("Directory traversal was not observed during this assessment.")
        
        # Combine and limit to 2-6 bullets
        all_bullets = category_bullets + not_detected[:max(0, 6 - len(category_bullets))]
        
        if all_bullets:
            story.append(Paragraph("Key Findings by Category", styles["subsection_title"]))
            for bullet in all_bullets[:6]:  # Limit to 6 bullets
                story.append(Paragraph(f"• {bullet}", styles["bullet"]))
            story.append(Spacer(1, 10))
    
    # Section 3: Severity Breakdown with colored pills
    story.append(Paragraph("Severity Breakdown", styles["subsection_title"]))
    
    # Build severity table with colored header pills
    severity_headers = []
    severity_counts_row = []
    
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = severity_breakdown.get(sev, 0)
        severity_headers.append(sev.capitalize())
        severity_counts_row.append(str(count))
    
    severity_data = [severity_headers, severity_counts_row]
    
    severity_table = Table(
        severity_data,
        colWidths=[30 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
        hAlign="LEFT",
    )
    
    table_style = [
        # Grid
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
    ]
    
    # Color-code header row cells as pills
    for i, sev in enumerate(["critical", "high", "medium", "low", "info"]):
        sev_bg = SEVERITY_BG_COLORS[sev]
        sev_text = SEVERITY_TEXT_COLORS[sev]
        table_style.append(("BACKGROUND", (i, 0), (i, 0), sev_bg))
        table_style.append(("TEXTCOLOR", (i, 0), (i, 0), sev_text))
        table_style.append(("FONTNAME", (i, 0), (i, 0), "Helvetica-Bold"))
        table_style.append(("FONTSIZE", (i, 0), (i, 0), 10))
        table_style.append(("BOTTOMPADDING", (i, 0), (i, 0), 8))
        table_style.append(("TOPPADDING", (i, 0), (i, 0), 8))
    
    severity_table.setStyle(TableStyle(table_style))
    story.append(severity_table)
    story.append(Spacer(1, 12))
    
    # Section 4: Remediation Overview / 30-day plan
    if mode == "executive" and findings_count > 0:
        story.append(Paragraph("30-Day Remediation Plan", styles["subsection_title"]))
        
        critical_count = severity_breakdown.get("critical", 0)
        high_count = severity_breakdown.get("high", 0)
        medium_count = severity_breakdown.get("medium", 0)
        
        # Immediate (24h)
        story.append(Paragraph("<b>Immediate (24 hours):</b>", styles["body"]))
        immediate_points = []
        if critical_count > 0:
            immediate_points.append(f"Address all {critical_count} critical vulnerabilities")
        # Check for authenticated bypass or RCE
        import json
        for f in findings:
            if _severity_label(getattr(f, "severity", "info")) == "critical":
                categories = []
                if f.raw_data:
                    try:
                        raw_data_dict = json.loads(f.raw_data)
                        if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                            categories = raw_data_dict["categories"] or []
                    except:
                        pass
                if "command_injection" in [c.lower() for c in categories if isinstance(c, str)]:
                    immediate_points.append("Remediate Remote Code Execution (RCE) vulnerabilities")
                    break
        if not immediate_points:
            immediate_points.append("Review and prioritize critical findings")
        for point in immediate_points:
            story.append(Paragraph(f"• {point}", styles["bullet"]))
        story.append(Spacer(1, 6))
        
        # Short term (7d)
        story.append(Paragraph("<b>Short Term (7 days):</b>", styles["body"]))
        short_term_points = []
        if high_count > 0:
            short_term_points.append(f"Remediate {high_count} high-severity vulnerabilities")
        if medium_count > 0:
            short_term_points.append(f"Address {medium_count} medium-severity issues in externally exposed endpoints")
        if not short_term_points:
            short_term_points.append("Review and address high and medium findings")
        for point in short_term_points:
            story.append(Paragraph(f"• {point}", styles["bullet"]))
        story.append(Spacer(1, 6))
        
        # Medium term (30d)
        story.append(Paragraph("<b>Medium Term (30 days):</b>", styles["body"]))
        medium_term_points = [
            "Implement HTTP security headers (CSP, HSTS, X-Frame-Options, etc.)",
            "Apply security best practices and hardening measures",
            "Conduct follow-up scan to verify remediation"
        ]
        for point in medium_term_points:
            story.append(Paragraph(f"• {point}", styles["bullet"]))
        story.append(Spacer(1, 8))
    else:
        rem_text = _safe_summary_value(summary, "remediation_overview")
        if rem_text:
            story.append(Paragraph("Suggested Next Steps", styles["subsection_title"]))
            story.append(Paragraph(str(rem_text), styles["body"]))
            story.append(Spacer(1, 8))
        elif findings_count > 0:
            story.append(Paragraph("Suggested Next Steps", styles["subsection_title"]))
            
            # Generate remediation points from findings
            nmap_findings = [f for f in findings if getattr(f, "tool_name", "").lower() == "nmap"]
            sslscan_findings = [f for f in findings if getattr(f, "tool_name", "").lower() == "sslscan"]
            nuclei_findings = [f for f in findings if getattr(f, "tool_name", "").lower() == "nuclei"]
            
            remediation_points = []
            
            if severity_breakdown.get("critical", 0) > 0 or severity_breakdown.get("high", 0) > 0:
                remediation_points.append("Prioritize remediation of High and Medium findings within 7–14 days.")
            
            if nmap_findings:
                remediation_points.append("Review exposed services on open ports and restrict where possible.")
            
            if sslscan_findings:
                remediation_points.append("Address TLS/SSL configuration issues to ensure secure communications.")
            
            if nuclei_findings:
                remediation_points.append("Patch identified vulnerabilities and apply security updates promptly.")
            
            if not remediation_points:
                remediation_points.append("Review all findings and implement appropriate security controls.")
            
            for point in remediation_points[:4]:  # Limit to 4 points
                story.append(Paragraph(f"• {point}", styles["bullet"]))
        else:
            story.append(Paragraph("Suggested Next Steps", styles["subsection_title"]))
            story.append(
                Paragraph(
                    "No immediate remediation actions required. Continue routine monitoring and periodic security assessments.",
                    styles["body"]
                )
            )
    
    story.append(Spacer(1, 12))
    
    return story


def _build_network_tls_section(scan: ScanJob, findings: List[Finding], styles: dict) -> List:
    """Build Network & TLS Surface section from findings with card styling."""
    story = []
    
    nmap_findings = [f for f in findings if getattr(f, "tool_name", "").lower() == "nmap"]
    sslscan_findings = [f for f in findings if getattr(f, "tool_name", "").lower() == "sslscan"]
    
    if not nmap_findings and not sslscan_findings:
        return story
    
    # Card-like container using table with background
    story.append(Spacer(1, 8))
    
    # Open Ports (Nmap)
    if nmap_findings:
        story.append(Paragraph("● Network & TLS Surface", styles["section_title"]))
        story.append(Paragraph("Open Ports", styles["subsection_title"]))
        story.append(
            Paragraph(
                f"This scan identified {len(nmap_findings)} open port(s). Review each port to ensure only necessary services are exposed.",
                styles["body"]
            )
        )
        
        port_data = [["Port/Service", "Status", "Finding"]]
        for f in nmap_findings[:10]:
            title = getattr(f, "title", "") or "Open port"
            url = getattr(f, "url", "") or ""
            port_data.append([url or title, "Open", title])
        
        if len(nmap_findings) > 10:
            port_data.append(["...", "...", f"{len(nmap_findings) - 10} more ports"])
        
        port_table = Table(
            port_data,
            colWidths=[50 * mm, 30 * mm, 75 * mm],
            hAlign="LEFT",
        )
        port_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(port_table)
        story.append(Spacer(1, 8))
    
    # TLS Issues (SSLScan)
    if sslscan_findings:
        story.append(Paragraph("TLS/SSL Issues", styles["subsection_title"]))
        story.append(
            Paragraph(
                f"This scan identified {len(sslscan_findings)} TLS/SSL configuration issue(s).",
                styles["body"]
            )
        )
        
        tls_data = [["Issue", "Severity"]]
        for f in sslscan_findings[:10]:
            title = getattr(f, "title", "") or "TLS issue"
            sev = _severity_label(getattr(f, "severity", "info"))
            tls_data.append([title, sev.capitalize()])
        
        if len(sslscan_findings) > 10:
            tls_data.append(["...", f"{len(sslscan_findings) - 10} more issues"])
        
        tls_table = Table(
            tls_data,
            colWidths=[100 * mm, 55 * mm],
            hAlign="LEFT",
        )
        tls_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tls_table)
        story.append(Spacer(1, 8))
    
    return story


def _build_stack_fingerprint(scan: ScanJob, styles: dict) -> List:
    """Build Stack Fingerprint section from stack_info with card styling."""
    story = []
    
    stack_info = getattr(scan, "stack_info", None)
    if not stack_info:
        return story
    
    story.append(Paragraph("● Stack Fingerprint", styles["section_title"]))
    
    fingerprint_data = []
    
    target_url = _safe_stack_value(stack_info, "target_url")
    if target_url:
        fingerprint_data.append(["Target URL", target_url])
    
    scan_level = _safe_stack_value(stack_info, "scan_level")
    if scan_level:
        fingerprint_data.append(["Scan Level", str(scan_level)])
    
    http_info = _safe_stack_value(stack_info, "http")
    if http_info and isinstance(http_info, dict):
        status_code = http_info.get("status_code")
        if status_code:
            fingerprint_data.append(["HTTP Status", str(status_code)])
        
        headers = http_info.get("headers")
        if headers and isinstance(headers, dict):
            server = headers.get("server")
            if server:
                fingerprint_data.append(["Server", str(server)])
            
            content_type = headers.get("content_type")
            if content_type:
                fingerprint_data.append(["Content-Type", str(content_type)])
            
            x_powered_by = headers.get("x_powered_by")
            if x_powered_by:
                fingerprint_data.append(["X-Powered-By", str(x_powered_by)])
    
    if not fingerprint_data:
        story.append(Paragraph("Stack fingerprint information not available for this scan.", styles["body"]))
        return story
    
    fingerprint_table = Table(
        fingerprint_data,
        colWidths=[45 * mm, 110 * mm],
        hAlign="LEFT",
    )
    fingerprint_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_LABEL_BG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_TEXT_PRIMARY),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(fingerprint_table)
    story.append(Spacer(1, 12))
    
    return story


def _build_category_breakdown(findings: List[Finding], styles: dict) -> List:
    """Build category breakdown table showing counts by category and severity."""
    story = []
    
    if not findings:
        return story
    
    import json
    from collections import defaultdict
    
    # Extract categories from findings
    category_severity_counts = defaultdict(lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0})
    
    for f in findings:
        categories = []
        if f.raw_data:
            try:
                raw_data_dict = json.loads(f.raw_data)
                if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                    categories = raw_data_dict["categories"]
                    if not isinstance(categories, list):
                        categories = [categories] if categories else []
            except:
                pass
        
        # If no categories, skip (or use "Other")
        if not categories:
            categories = ["Other"]
        
        sev = _severity_label(getattr(f, "severity", "info"))
        
        for cat in categories:
            if isinstance(cat, str):
                category_severity_counts[cat][sev] += 1
    
    if not category_severity_counts:
        return story
    
    story.append(Paragraph("Category Breakdown", styles["section_title"]))
    
    # Build table: Category | Critical | High | Medium | Low
    table_data = [["Category", "Critical", "High", "Medium", "Low"]]
    
    # Sort categories by total count (descending)
    sorted_categories = sorted(
        category_severity_counts.items(),
        key=lambda x: sum(x[1].values()),
        reverse=True
    )
    
    for category, counts in sorted_categories:
        row = [
            category,
            str(counts["critical"]),
            str(counts["high"]),
            str(counts["medium"]),
            str(counts["low"]),
        ]
        table_data.append(row)
    
    cat_table = Table(
        table_data,
        colWidths=[60 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm],
        hAlign="LEFT",
    )
    
    cat_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ])
    )
    
    story.append(cat_table)
    story.append(Spacer(1, 12))
    
    return story


def _build_web_attack_surface_overview(findings: List[Finding], styles: dict) -> List:
    """
    Build Web Attack Surface Overview section showing vulnerability classes.
    
    For each main category (xss, sqli, ssrf, etc.), shows:
    - Count of findings
    - Highest severity
    - Primary tools that found them
    """
    story = []
    
    if not findings:
        return story
    
    import json
    from collections import defaultdict
    
    # Main vulnerability categories to track
    main_categories = [
        "xss", "sqli", "ssrf", "ssti", "xxe", "dir_traversal",
        "cors", "csrf", "cmdi", "idor"
    ]
    
    # Extract category data from findings
    category_data = defaultdict(lambda: {
        "count": 0,
        "severities": [],
        "tools": set(),
    })
    
    for f in findings:
        categories = []
        if f.raw_data:
            try:
                raw_data_dict = json.loads(f.raw_data)
                if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                    categories = raw_data_dict["categories"]
                    if not isinstance(categories, list):
                        categories = [categories] if categories else []
            except:
                pass
        
        # Only track main categories
        for cat in categories:
            if isinstance(cat, str):
                cat_lower = cat.lower()
                # Normalize category names
                if cat_lower in ["directory_traversal", "dir_traversal"]:
                    cat_lower = "dir_traversal"
                elif cat_lower in ["cors_misconfig", "cors"]:
                    cat_lower = "cors"
                elif cat_lower in ["command_injection", "cmdi"]:
                    cat_lower = "cmdi"
                
                if cat_lower in main_categories:
                    category_data[cat_lower]["count"] += 1
                    sev = _severity_label(getattr(f, "severity", "info"))
                    category_data[cat_lower]["severities"].append(sev)
                    tool_name = getattr(f, "tool_name", "") or "unknown"
                    category_data[cat_lower]["tools"].add(tool_name)
    
    if not category_data:
        return story
    
    story.append(Paragraph("Web Attack Surface Overview", styles["section_title"]))
    story.append(Spacer(1, 8))
    
    # Build table: Category | Count | Highest Severity | Primary Tools
    table_data = [["Category", "Count", "Highest Severity", "Primary Tools"]]
    
    # Category display names
    category_display = {
        "xss": "Cross-Site Scripting (XSS)",
        "sqli": "SQL Injection",
        "ssrf": "Server-Side Request Forgery (SSRF)",
        "ssti": "Server-Side Template Injection (SSTI)",
        "xxe": "XML External Entities (XXE)",
        "dir_traversal": "Directory Traversal / File Inclusion",
        "cors": "CORS Misconfiguration",
        "csrf": "Cross-Site Request Forgery (CSRF)",
        "cmdi": "Command Injection",
        "idor": "Insecure Direct Object Reference (IDOR)",
    }
    
    # Sort categories by count (descending)
    sorted_categories = sorted(
        category_data.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    
    for category, data in sorted_categories:
        count = data["count"]
        if count == 0:
            continue
        
        # Find highest severity
        if data["severities"]:
            highest_sev = min(
                data["severities"],
                key=lambda s: severity_order.get(s, 4)
            )
            sev_color = SEVERITY_COLORS.get(highest_sev, COLOR_TEXT_PRIMARY)
        else:
            highest_sev = "N/A"
            sev_color = COLOR_TEXT_MUTED
        
        # Get primary tools (top 2)
        tools_list = sorted(list(data["tools"]))[:2]
        tools_str = ", ".join(tools_list) if tools_list else "N/A"
        
        display_name = category_display.get(category, category.title())
        
        row = [
            display_name,
            str(count),
            f'<font color="{sev_color.hexval()}">{highest_sev.upper()}</font>',
            tools_str,
        ]
        table_data.append(row)
    
    if len(table_data) == 1:  # Only header row
        return story
    
    # Build table
    surface_table = Table(
        table_data,
        colWidths=[80 * mm, 20 * mm, 30 * mm, 50 * mm],
        repeatRows=1,
    )
    
    surface_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_ROW_ALT, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_TEXT_MUTED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
    ]))
    
    story.append(surface_table)
    story.append(Spacer(1, 12))
    
    return story


def _build_top_exploitable_paths(findings: List[Finding], styles: dict) -> List:
    """Build Top 5 Exploitable Paths section with URL, category, severity, and impact."""
    story = []
    
    if not findings:
        return story
    
    import json
    
    # Filter to Critical/High/Medium findings and sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    exploitable = [
        f for f in findings
        if severity_order.get(_severity_label(getattr(f, "severity", "info")), 4) <= 2
    ]
    
    if not exploitable:
        return story
    
    # PR-4D: Sort by severity (critical > high > medium), then by CVSS score (descending)
    # Use negative severity_order so lower values (critical=0) come first
    sorted_exploitable = sorted(
        exploitable,
        key=lambda f: (
            -severity_order.get(_severity_label(getattr(f, "severity", "info")), 4),  # Negate so critical comes first
            -(getattr(f, "cvss_score", 0) or 0),  # Negate so higher CVSS comes first
        )
    )[:5]
    
    story.append(Paragraph("Top 5 Exploitable Paths", styles["section_title"]))
    
    for i, f in enumerate(sorted_exploitable, 1):
        sev = _severity_label(getattr(f, "severity", "info"))
        sev_color = SEVERITY_COLORS[sev]
        title = getattr(f, "title", "") or "(no title)"
        url = getattr(f, "url", "") or "N/A"
        
        # Extract category
        category = "Other"
        if f.raw_data:
            try:
                raw_data_dict = json.loads(f.raw_data)
                if isinstance(raw_data_dict, dict) and "categories" in raw_data_dict:
                    cats = raw_data_dict["categories"]
                    if isinstance(cats, list) and len(cats) > 0:
                        category = cats[0]
                    elif isinstance(cats, str):
                        category = cats
            except:
                pass
        
        # Generate impact statement based on category and severity
        impact_statements = {
            "xss": "Leak of session cookies may allow account takeover",
            "sqli": "Database compromise may expose sensitive data",
            "ssrf": "Internal network access may be possible",
            "ssti": "Remote code execution may be possible",
            "xxe": "File system access may be possible",
            "directory_traversal": "Sensitive files may be accessible",
            "command_injection": "Remote code execution may be possible",
            "idor": "Unauthorized access to user data may be possible",
            "csrf": "Unauthorized actions may be performed on behalf of users",
            "cors_misconfig": "Cross-origin data access may be possible",
        }
        impact = impact_statements.get(category.lower(), "Security risk identified")
        
        # Build entry
        entry_text = f'<b>{i}. {title}</b><br/>'
        entry_text += f'<font color="{COLOR_TEXT_MUTED.hexval()}">URL:</font> {url}<br/>'
        entry_text += f'<font color="{COLOR_TEXT_MUTED.hexval()}">Category:</font> {category} | '
        entry_text += f'<font color="{sev_color.hexval()}"><b>Severity: {sev.upper()}</b></font><br/>'
        entry_text += f'<font color="{COLOR_TEXT_MUTED.hexval()}">Impact:</font> {impact}'
        
        story.append(Paragraph(entry_text, styles["body"]))
        story.append(Spacer(1, 8))
    
    story.append(Spacer(1, 12))
    
    return story


def _build_findings_overview(findings: List[Finding], styles: dict, mode: str) -> List:
    """Build findings overview section (for executive mode, show top findings)."""
    story = []
    
    if not findings:
        return story
    
    if mode == "executive":
        story.append(Paragraph("Findings Overview", styles["section_title"]))
        
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_findings = sorted(
            findings,
            key=lambda f: severity_order.get(_severity_label(getattr(f, "severity", "info")), 4)
        )[:5]
        
        for f in sorted_findings:
            from xml.sax.saxutils import escape as xml_escape
            sev = _severity_label(getattr(f, "severity", "info"))
            sev_color = SEVERITY_COLORS[sev]
            title = getattr(f, "title", "") or "(no title)"
            tool = getattr(f, "tool_name", "") or ""
            
            text = f'<font color="{sev_color.hexval()}"><b>[{sev.upper()}]</b></font> <b>{xml_escape(title)}</b>'
            if tool:
                muted_hex = COLOR_TEXT_MUTED.hexval()
                text += f' <font color="{muted_hex}">({tool})</font>'
            
            story.append(Paragraph(text, styles["body"]))
            story.append(Spacer(1, 4))
    
    return story


def _build_findings_detail(findings: List[Finding], styles: dict) -> List:
    """Build detailed findings section (full mode only) with severity badges."""
    story = []
    
    if not findings:
        story.append(Paragraph("Findings Detail", styles["section_title"]))
        story.append(
            Paragraph(
                "No findings were detected in this scan. The target appears secure based on the scan configuration.",
                styles["body"]
            )
        )
        return story
    
    story.append(Paragraph("Findings Detail", styles["section_title"]))
    
    # Group by severity
    severity_order = ["critical", "high", "medium", "low", "info"]
    findings_by_sev: dict[str, List[Finding]] = {s: [] for s in severity_order}
    
    for f in findings:
        sev = _severity_label(getattr(f, "severity", "info"))
        findings_by_sev.setdefault(sev, []).append(f)
    
    # Render by severity
    for sev in severity_order:
        bucket = findings_by_sev.get(sev) or []
        if not bucket:
            continue
        
        sev_color = SEVERITY_COLORS[sev]
        sev_bg = SEVERITY_BG_COLORS[sev]
        sev_text_color = SEVERITY_TEXT_COLORS[sev]
        
        # Section heading with count and colored bar
        count = len(bucket)
        story.append(Spacer(1, 12))
        heading_text = f'<font color="{sev_color.hexval()}"><b>{sev.capitalize()} severity findings ({count})</b></font>'
        story.append(Paragraph(heading_text, styles["section_title"]))
        
        # Colored bar under heading (using a thin table)
        bar_table = Table(
            [[ "" ]],
            colWidths=[150 * mm],
            hAlign="LEFT",
        )
        bar_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), sev_color),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ])
        )
        story.append(bar_table)
        story.append(Spacer(1, 8))
        
        for f in bucket:
            title = getattr(f, "title", "") or "(no title)"
            description = getattr(f, "description", "") or ""
            recommendation = getattr(f, "recommendation", "") or ""
            url = getattr(f, "url", "") or ""
            path = getattr(f, "path", "") or ""
            line_number = getattr(f, "line_number")
            cve_id = getattr(f, "cve_id", "") or ""
            cwe_id = getattr(f, "cwe_id", "") or ""
            cvss_score = getattr(f, "cvss_score")
            tool = getattr(f, "tool_name", "") or ""
            status = getattr(f, "status", "open")
            if hasattr(status, "value"):
                status = str(status.value)
            
            # ZAP-specific metadata
            wasc_id = getattr(f, "wasc_id", None)
            plugin_id = getattr(f, "plugin_id", None)
            alert_ref = getattr(f, "alert_ref", None)
            zap_confidence = getattr(f, "zap_confidence", None)
            zap_riskcode = getattr(f, "zap_riskcode", None)
            
            # Title with severity badge (escape XML special characters)
            from xml.sax.saxutils import escape as xml_escape
            escaped_title = xml_escape(title)
            sev_badge_text = f'<font color="{sev_text_color.hexval()}"><b>{sev.upper()}</b></font>'
            title_text = f'[{sev_badge_text}] {escaped_title}'
            story.append(Paragraph(title_text, styles["finding_title"]))
            
            # Metadata line
            metadata_parts = []
            if tool:
                metadata_parts.append(f"Tool: {tool.upper()}")
            if cvss_score:
                metadata_parts.append(f"CVSS: {cvss_score}")
            if cve_id:
                metadata_parts.append(f"CVE: {cve_id}")
            if cwe_id:
                metadata_parts.append(f"CWE: {cwe_id}")
            if wasc_id:
                metadata_parts.append(f"WASC: {wasc_id}")
            if zap_confidence is not None:
                conf_labels = {0: "Low", 1: "Medium", 2: "High", 3: "Confirmed"}
                conf_label = conf_labels.get(zap_confidence, f"Unknown({zap_confidence})")
                metadata_parts.append(f"Confidence: {conf_label}")
            if status:
                metadata_parts.append(f"Status: {status.upper()}")
            
            if metadata_parts:
                story.append(
                    Paragraph(
                        f'<font color="{COLOR_TEXT_MUTED.hexval()}">{" · ".join(metadata_parts)}</font>',
                        styles["small_muted"]
                    )
                )
            
            # Description
            if description:
                story.append(Spacer(1, 4))
                story.append(Paragraph("<b>Description:</b>", styles["body"]))
                story.append(Paragraph(xml_escape(str(description)), styles["body"]))
            
            # Recommendation
            if recommendation:
                story.append(Spacer(1, 4))
                story.append(Paragraph("<b>Recommendation:</b>", styles["body"]))
                story.append(Paragraph(xml_escape(str(recommendation)), styles["body"]))
            
            # Location
            location_parts = []
            if url:
                location_parts.append(f"URL: {url}")
            if path:
                location_parts.append(f"Path: {path}")
            if line_number:
                location_parts.append(f"Line: {line_number}")
            
            if location_parts:
                story.append(Spacer(1, 4))
                story.append(
                    Paragraph(
                        f'<b>Location:</b> <font color="{COLOR_TEXT_MUTED.hexval()}">{" · ".join(location_parts)}</font>',
                        styles["small_muted"]
                    )
                )
            
            story.append(Spacer(1, 12))
    
    return story


def _build_enumeration_section(inventory: dict, styles: dict) -> List[Any]:
    """Build Asset Enumeration section from inventory data."""
    story = []
    
    if not inventory or not isinstance(inventory, dict):
        return story
    
    story.append(Spacer(1, 12))
    story.append(Paragraph("● Asset Enumeration", styles["section_title"]))
    
    discovery = inventory.get("discovery", {})
    merged = discovery.get("merged", {})
    
    # Discovery Summary
    if merged:
        story.append(Paragraph("Discovery Summary", styles["subsection_title"]))
        
        summary_data = []
        summary_data.append(["Metric", "Count"])
        
        all_urls_count = merged.get("all_urls_count", 0)
        unique_urls_count = merged.get("unique_urls_count", 0)
        param_urls_count = merged.get("param_urls_count", 0)
        
        summary_data.append(["Total URLs", str(all_urls_count)])
        summary_data.append(["Unique URLs", str(unique_urls_count)])
        summary_data.append(["Parameterized URLs", str(param_urls_count)])
        
        # Count total parameters from Arjun
        arjun_params = discovery.get("arjun", {}).get("params_by_url", {})
        total_params = 0
        if isinstance(arjun_params, dict):
            for params in arjun_params.values():
                if isinstance(params, list):
                    total_params += len(params)
                elif isinstance(params, dict):
                    total_params += len(params)
        
        summary_data.append(["Parameters Discovered", str(total_params)])
        
        summary_table = Table(
            summary_data,
            colWidths=[100 * mm, 50 * mm],
            hAlign="LEFT",
        )
        summary_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(summary_table)
        story.append(Spacer(1, 8))
    
    # Technologies Detected
    technologies = inventory.get("technologies", [])
    if technologies and isinstance(technologies, list):
        story.append(Paragraph("Technologies Detected", styles["subsection_title"]))
        tech_text = ", ".join(technologies[:20])  # Limit to 20 for PDF
        if len(technologies) > 20:
            tech_text += f" ... and {len(technologies) - 20} more"
        story.append(Paragraph(tech_text, styles["body"]))
        story.append(Spacer(1, 8))
    
    # Tool Breakdown
    tool_breakdown = []
    if discovery.get("httpx"):
        httpx_data = discovery["httpx"]
        tech_count = len(httpx_data.get("tech", [])) if isinstance(httpx_data.get("tech"), list) else 0
        tool_breakdown.append(["HTTPX (Tech Detection)", f"{tech_count} technologies"])
    
    if discovery.get("katana"):
        katana_data = discovery["katana"]
        urls_count = katana_data.get("urls_count", len(katana_data.get("urls", [])))
        tool_breakdown.append(["Katana (Live Crawl)", f"{urls_count} URLs"])
    
    if discovery.get("gau"):
        gau_data = discovery["gau"]
        urls_count = gau_data.get("urls_count", len(gau_data.get("urls", [])))
        tool_breakdown.append(["GAU (Historical URLs)", f"{urls_count} URLs"])
    
    if discovery.get("arjun"):
        arjun_data = discovery["arjun"]
        params_by_url = arjun_data.get("params_by_url", {})
        urls_with_params = len(params_by_url) if isinstance(params_by_url, dict) else 0
        tool_breakdown.append(["Arjun (Parameter Discovery)", f"{urls_with_params} URLs with params"])
    
    if tool_breakdown:
        story.append(Paragraph("Tool Breakdown", styles["subsection_title"]))
        tool_data = [["Tool", "Results"]]
        tool_data.extend(tool_breakdown)
        
        tool_table = Table(
            tool_data,
            colWidths=[100 * mm, 50 * mm],
            hAlign="LEFT",
        )
        tool_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(tool_table)
        story.append(Spacer(1, 8))
    
    # Parameterized URLs (sample)
    param_urls = merged.get("param_urls", [])
    if param_urls and isinstance(param_urls, list):
        story.append(Paragraph("Parameterized URLs (Sample)", styles["subsection_title"]))
        story.append(
            Paragraph(
                f"Found {len(param_urls)} parameterized URLs. Showing first 10:",
                styles["body"]
            )
        )
        for url in param_urls[:10]:
            story.append(Paragraph(f"• {url}", styles["bullet"]))
        if len(param_urls) > 10:
            story.append(Paragraph(f"... and {len(param_urls) - 10} more URLs", styles["body"]))
        story.append(Spacer(1, 8))
    
    return story


def _build_tech_dependencies_section(tech_stack: dict, styles: dict) -> List[Any]:
    """Build Tech & Dependencies section from tech stack data."""
    story = []
    
    if not tech_stack or not isinstance(tech_stack, dict):
        return story
    
    story.append(Spacer(1, 12))
    story.append(Paragraph("● Technology & Dependencies", styles["section_title"]))
    
    fingerprint = tech_stack.get("fingerprint", {})
    client_dependencies = tech_stack.get("client_dependencies", [])
    findings = tech_stack.get("findings", [])
    
    # Target Fingerprint
    if fingerprint:
        story.append(Paragraph("Target Fingerprint", styles["subsection_title"]))
        
        fp_data = []
        if fingerprint.get("status"):
            fp_data.append(["Status", str(fingerprint["status"])])
        if fingerprint.get("title"):
            fp_data.append(["Title", str(fingerprint["title"])])
        if fingerprint.get("server"):
            fp_data.append(["Server", str(fingerprint["server"])])
        if fingerprint.get("cdn"):
            fp_data.append(["CDN", str(fingerprint["cdn"])])
        
        if fp_data:
            # Add header row
            fp_data.insert(0, ["Field", "Value"])
            fp_table = Table(
                fp_data,
                colWidths=[50 * mm, 100 * mm],
                hAlign="LEFT",
            )
            fp_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            story.append(fp_table)
            story.append(Spacer(1, 8))
    
    # Technologies Detected
    technologies = fingerprint.get("technologies", [])
    if technologies and isinstance(technologies, list):
        story.append(Paragraph("Technologies Detected", styles["subsection_title"]))
        
        tech_data = [["Technology", "Version", "Confidence"]]
        for tech in technologies[:20]:  # Limit to 20
            name = tech.get("name", "Unknown")
            version = tech.get("version") or "N/A"
            confidence = tech.get("confidence", 0)
            confidence_pct = f"{int(confidence * 100)}%" if isinstance(confidence, (int, float)) else "N/A"
            tech_data.append([name, version, confidence_pct])
        
        if len(technologies) > 20:
            tech_data.append(["...", "...", f"{len(technologies) - 20} more"])
        
        tech_table = Table(
            tech_data,
            colWidths=[60 * mm, 40 * mm, 50 * mm],
            hAlign="LEFT",
        )
        tech_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(tech_table)
        story.append(Spacer(1, 8))
    
    # Client-Side Dependencies
    if client_dependencies and isinstance(client_dependencies, list):
        story.append(Paragraph("Client-Side Dependencies", styles["subsection_title"]))
        
        deps_data = [["Package", "Version", "Evidence"]]
        for dep in client_dependencies[:20]:  # Limit to 20
            name = dep.get("name", "Unknown")
            version = dep.get("version", "N/A")
            evidence = dep.get("evidence", "N/A")
            # Truncate evidence if too long
            if len(evidence) > 50:
                evidence = evidence[:47] + "..."
            deps_data.append([name, version, evidence])
        
        if len(client_dependencies) > 20:
            deps_data.append(["...", "...", f"{len(client_dependencies) - 20} more"])
        
        deps_table = Table(
            deps_data,
            colWidths=[50 * mm, 30 * mm, 70 * mm],
            hAlign="LEFT",
        )
        deps_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        story.append(deps_table)
        story.append(Spacer(1, 8))
    
    # Vulnerabilities in Dependencies
    if findings and isinstance(findings, list):
        vuln_findings = [f for f in findings if f.get("type") == "vulnerability"]
        if vuln_findings:
            story.append(Paragraph("Vulnerabilities in Dependencies", styles["subsection_title"]))
            
            vuln_data = [["Package", "Version", "Severity", "Evidence"]]
            for finding in vuln_findings[:15]:  # Limit to 15
                pkg = finding.get("package", "Unknown")
                version = finding.get("version", "N/A")
                severity = finding.get("severity", "unknown").upper()
                evidence = finding.get("evidence", "N/A")
                if len(evidence) > 40:
                    evidence = evidence[:37] + "..."
                vuln_data.append([pkg, version, severity, evidence])
            
            if len(vuln_findings) > 15:
                vuln_data.append(["...", "...", "...", f"{len(vuln_findings) - 15} more"])
            
            vuln_table = Table(
                vuln_data,
                colWidths=[35 * mm, 25 * mm, 25 * mm, 75 * mm],
                hAlign="LEFT",
            )
            vuln_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_ROW_ALT]),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            story.append(vuln_table)
            story.append(Spacer(1, 8))
    
    return story


def generate_scan_report_pdf(
    db: Session,
    scan_id: str,
    tenant: Tenant,
    mode: ReportMode = "full",
) -> bytes:
    """
    Generate a futuristic, formal PDF report for a scan.
    
    Args:
        db: Database session
        scan_id: Scan job ID
        tenant: Tenant for scoping
        mode: "full" (detailed findings) or "executive" (summary only)
    
    Returns:
        PDF bytes
    """
    scan, findings = _load_scan_and_findings(db, scan_id, tenant)
    styles = _build_styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=32 * mm,  # Increased for header band
        bottomMargin=22 * mm,  # Increased for footer
        title="Thandev Security Scan Report",
    )

    story: list = []

    # Page 1: Cover
    story.extend(_build_cover_page(scan, findings, styles))
    story.append(PageBreak())

    # Page 2: Executive Summary + Severity Breakdown + Remediation
    story.extend(_build_executive_summary(scan, findings, styles, mode))
    
    # Full mode only: Category Breakdown and Top Exploitable Paths
    if mode == "full":
        category_breakdown = _build_category_breakdown(findings, styles)
        if category_breakdown:
            story.extend(category_breakdown)
        
        top_paths = _build_top_exploitable_paths(findings, styles)
        if top_paths:
            story.extend(top_paths)
    
    # Network & TLS Surface (if applicable)
    network_tls = _build_network_tls_section(scan, findings, styles)
    if network_tls:
        story.extend(network_tls)
    
    # Stack Fingerprint (if available)
    stack_fp = _build_stack_fingerprint(scan, styles)
    if stack_fp:
        story.extend(stack_fp)

    # Full mode only: Enumeration and Tech & Dependencies sections
    if mode == "full":
        # Fetch inventory data
        from app.models.scan_artifact import ScanArtifact
        from sqlalchemy import and_
        
        inventory_artifact = db.query(ScanArtifact).filter(
            and_(
                ScanArtifact.scan_id == scan_id,
                ScanArtifact.type == "asset_inventory"
            )
        ).first()
        
        if inventory_artifact and inventory_artifact.payload:
            enumeration_section = _build_enumeration_section(inventory_artifact.payload, styles)
            if enumeration_section:
                story.append(PageBreak())
                story.extend(enumeration_section)
        
        # Fetch tech stack data
        tech_stack_artifact = db.query(ScanArtifact).filter(
            and_(
                ScanArtifact.scan_id == scan_id,
                ScanArtifact.type == "url_sca"
            )
        ).first()
        
        if tech_stack_artifact and tech_stack_artifact.payload:
            tech_deps_section = _build_tech_dependencies_section(tech_stack_artifact.payload, styles)
            if tech_deps_section:
                story.append(PageBreak())
                story.extend(tech_deps_section)

    # Findings overview (executive mode shows top findings)
    if mode == "executive":
        findings_overview = _build_findings_overview(findings, styles, mode)
        if findings_overview:
            story.extend(findings_overview)
    else:
        # Full mode: detailed findings on new page
        story.append(PageBreak())
        story.extend(_build_findings_detail(findings, styles))

    # Build PDF with header/footer
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
