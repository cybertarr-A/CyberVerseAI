import io
import logging
from typing import List, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger(__name__)


class ReportAgent:
    def __init__(self):
        self.name = "Report Agent"
        self.description = (
            "Synthesizes multi-agent research into premium PDF dashboards, "
            "Markdown docs, and structured JSON logs."
        )

    def generate_json_report(
        self, scan_data: Dict[str, Any], findings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "meta": {
                "scan_id": scan_data.get("id"),
                "status": scan_data.get("status"),
                "target": scan_data.get("target_value"),
                "risk_score": scan_data.get("risk_score"),
                "critical_count": scan_data.get("critical_count", 0),
                "high_count": scan_data.get("high_count", 0),
                "medium_count": scan_data.get("medium_count", 0),
                "low_count": scan_data.get("low_count", 0),
                "timestamp": str(scan_data.get("created_at")),
            },
            "findings": findings,
        }

    def generate_markdown_report(
        self, scan_data: Dict[str, Any], findings: List[Dict[str, Any]]
    ) -> str:
        md = []
        md.append("# CyberVerse AI — Intelligence Report")
        md.append(f"**Scan Target:** `{scan_data.get('target_value')}`")
        md.append(f"**Risk Score:** `{scan_data.get('risk_score')}/100`  ")
        md.append(
            f"**Critical:** `{scan_data.get('critical_count')}` | "
            f"**High:** `{scan_data.get('high_count')}` | "
            f"**Medium:** `{scan_data.get('medium_count')}` | "
            f"**Low:** `{scan_data.get('low_count')}`"
        )
        md.append("\n---\n")

        md.append("## Executive Summary")
        if scan_data.get("risk_score", 0) > 60:
            md.append(
                "⚠️ **CRITICAL ALERT:** The codebase contains highly exploitable "
                "security vectors. Lateral host compromise or token hijackings are "
                "highly likely if deployed to production. Urgent remediation is required."
            )
        else:
            md.append(
                "✅ **POSTURE REPORT:** The scanned components exhibit standard "
                "security bounds. Ensure code continues to adapt least-privilege "
                "structures and environment secret separation."
            )

        md.append("\n## Detailed Vulnerability Findings")

        for idx, f in enumerate(findings):
            md.append(f"### {idx+1}. {f['title']} [{f['severity'].upper()}]")
            md.append(f"- **File:** `{f.get('file_path')}:{f.get('line_number')}`")
            md.append(f"- **CWE:** `{f.get('cwe')}`")
            md.append(f"- **CVE:** `{f.get('cve')}`")
            md.append(f"- **MITRE ATT&CK:** `{f.get('mitre_attack')}`")
            md.append(f"- **OWASP:** `{f.get('owasp_category', 'N/A')}`")
            md.append(f"\n**Description:**\n{f['description']}")

            if f.get("code_snippet"):
                md.append(
                    f"\n**Vulnerable Code Snippet:**\n```\n{f['code_snippet']}\n```"
                )

            md.append(
                f"\n**Remediation Guidance:**\n{f.get('remediation_explanation', 'N/A')}"
            )
            if f.get("remediation_code"):
                md.append(
                    f"\n**Secure Implementation Example:**\n```\n{f['remediation_code']}\n```"
                )

            md.append("\n---\n")

        return "\n".join(md)

    def generate_pdf_report(
        self, scan_data: Dict[str, Any], findings: List[Dict[str, Any]]
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        # Premium color palette
        slate_gray = colors.HexColor("#1A202C")
        cyan_accent = colors.HexColor("#0D9488")
        light_bg = colors.HexColor("#F3F4F6")

        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=slate_gray,
            spaceAfter=15,
        )

        h2_style = ParagraphStyle(
            "H2Style",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=cyan_accent,
            spaceBefore=15,
            spaceAfter=8,
        )

        body_style = ParagraphStyle(
            "BodyStyle",
            parent=styles["BodyText"],
            fontSize=10,
            textColor=slate_gray,
            leading=14,
        )

        code_style = ParagraphStyle(
            "CodeStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#111827"),
            backColor=colors.HexColor("#F3F4F6"),
            borderColor=colors.HexColor("#E5E7EB"),
            borderWidth=1,
            borderPadding=8,
            spaceBefore=5,
            spaceAfter=8,
        )

        elements = []

        # 1. Header
        elements.append(
            Paragraph("CYBERVERSE AI — THREAT INTEL REPORT", title_style)
        )
        elements.append(
            Paragraph(
                f"<b>Scan Target:</b> {scan_data.get('target_value')}", body_style
            )
        )
        elements.append(Spacer(1, 10))

        # 2. Executive Metrics Table
        data = [
            ["Risk Level", "Score", "Critical", "High", "Medium", "Low"],
            [
                "HIGH ALERT"
                if scan_data.get("risk_score", 0) > 50
                else "SECURE POSTURE",
                f"{scan_data.get('risk_score')}/100",
                str(scan_data.get("critical_count", 0)),
                str(scan_data.get("high_count", 0)),
                str(scan_data.get("medium_count", 0)),
                str(scan_data.get("low_count", 0)),
            ],
        ]

        t = Table(data, colWidths=[150, 80, 70, 70, 70, 70])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), slate_gray),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, 1), light_bg),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 15))

        # 3. Findings list
        elements.append(
            Paragraph("Detailed Security Analysis Findings", h2_style)
        )

        for idx, f in enumerate(findings):
            elements.append(
                Paragraph(
                    f"<b>{idx+1}. {f['title']}</b> - "
                    f"<font color='red'><b>{f['severity'].upper()}</b></font>",
                    ParagraphStyle(
                        "FTitle", parent=body_style, fontSize=11, spaceBefore=8
                    ),
                )
            )

            # Metadata block
            meta_str = (
                f"<b>File:</b> {f.get('file_path')}:{f.get('line_number')} | "
                f"<b>CWE:</b> {f.get('cwe')} | "
                f"<b>CVE:</b> {f.get('cve')} | "
                f"<b>OWASP:</b> {f.get('owasp_category', 'N/A')}"
            )
            elements.append(
                Paragraph(
                    meta_str,
                    ParagraphStyle(
                        "FMeta",
                        parent=body_style,
                        fontSize=9,
                        textColor=colors.HexColor("#4B5563"),
                    ),
                )
            )

            # Description
            elements.append(Paragraph(f"{f['description']}", body_style))

            # Code snippet
            if f.get("code_snippet"):
                clean_snippet = (
                    f.get("code_snippet")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                elements.append(
                    Paragraph(f"<code>{clean_snippet}</code>", code_style)
                )

            # Remediation
            elements.append(
                Paragraph(
                    f"<b>Remediation Action:</b> {f.get('remediation_explanation', 'N/A')}",
                    body_style,
                )
            )

            if f.get("remediation_code"):
                clean_rem = (
                    f.get("remediation_code")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                elements.append(
                    Paragraph(f"<code>{clean_rem}</code>", code_style)
                )

            elements.append(Spacer(1, 10))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
