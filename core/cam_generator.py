"""
CAM Generator - Pillar 3
==========================
Generates professional Credit Appraisal Memo (CAM) documents
in both PDF and Word format.
"""

import os
import json
import logging
from datetime import datetime
from io import BytesIO

from config import Config

logger = logging.getLogger(__name__)


class CAMGenerator:
    """Generate Credit Appraisal Memo documents."""

    def __init__(self, company_data: dict):
        self.data = company_data
        self.company_name = company_data.get("company_name", "Unknown Company")
        self.generated_at = datetime.now()

    def generate_word(self, output_path: str = None) -> str:
        """Generate CAM as Word document."""
        from docx import Document
        from docx.shared import Inches, Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT

        doc = Document()

        # ── Styles ──
        style = doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

        # ── Title Page ──
        doc.add_paragraph("")
        doc.add_paragraph("")
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("CREDIT APPRAISAL MEMORANDUM")
        run.font.size = Pt(28)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 51, 102)

        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(f"\n{self.company_name}")
        run.font.size = Pt(22)
        run.font.color.rgb = RGBColor(0, 102, 153)

        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = date_para.add_run(f"\nDate: {self.generated_at.strftime('%d %B %Y')}")
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(102, 102, 102)

        confidential = doc.add_paragraph()
        confidential.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = confidential.add_run("\n\n- CONFIDENTIAL -")
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = RGBColor(204, 0, 0)

        doc.add_paragraph("\n\nPrepared by: Intelli-Credit AI Engine")
        doc.add_page_break()

        # ── Table of Contents ──
        doc.add_heading("Table of Contents", level=1)
        toc_items = [
            "1. Executive Summary",
            "2. Company Overview",
            "3. Promoter Background",
            "4. Financial Analysis",
            "5. Five Cs Assessment",
            "6. Cross-Verification Results",
            "7. Secondary Research Findings",
            "8. Primary Due Diligence Notes",
            "9. Risk Assessment Matrix",
            "10. Recommendation",
            "Appendices",
        ]
        for item in toc_items:
            doc.add_paragraph(item, style="List Number")
        doc.add_page_break()

        # ── 1. Executive Summary ──
        doc.add_heading("1. Executive Summary", level=1)
        narrative = self.data.get("narrative", {})
        exec_summary = narrative.get("executive_summary",
                                     self._default_executive_summary())
        doc.add_paragraph(exec_summary)
        doc.add_paragraph("")

        # Quick scorecard table
        scoring = self.data.get("scoring", {})
        overall = scoring.get("overall_score", 0)
        risk_grade = scoring.get("risk_grade", "N/A")
        rec = scoring.get("recommendation", {})

        table = doc.add_table(rows=5, cols=2)
        table.style = "Light Grid Accent 1"
        cells = [
            ("Overall Credit Score", f"{overall}/100"),
            ("Risk Grade", risk_grade),
            ("Recommendation", rec.get("decision", "N/A")),
            ("Suggested Interest Rate", f"{rec.get('interest_rate_pct', 'N/A')}%"),
            ("Risk Premium", f"{rec.get('risk_premium_bps', 'N/A')} bps"),
        ]
        for i, (label, value) in enumerate(cells):
            table.rows[i].cells[0].text = label
            table.rows[i].cells[1].text = str(value)
            for cell in table.rows[i].cells:
                for paragraph in cell.paragraphs:
                    paragraph.style.font.size = Pt(11)

        doc.add_page_break()

        # ── 2. Company Overview ──
        doc.add_heading("2. Company Overview", level=1)
        doc.add_paragraph(narrative.get("company_overview",
                                        "Company overview data extracted from uploaded documents."))

        # ── 3. Promoter Background ──
        doc.add_heading("3. Promoter Background", level=1)
        doc.add_paragraph(narrative.get("promoter_background",
                                        "Promoter background information as extracted from research."))

        # ── 4. Financial Analysis ──
        doc.add_heading("4. Financial Analysis", level=1)
        doc.add_paragraph(narrative.get("financial_analysis_narrative",
                                        "Financial analysis based on uploaded documents."))

        # Financial metrics table
        metrics = self.data.get("financial_metrics", {})
        if metrics and not metrics.get("error"):
            doc.add_heading("Key Financial Metrics", level=2)
            metric_items = [
                ("Revenue", metrics.get("revenue", {})),
                ("EBITDA", metrics.get("ebitda", {})),
                ("PAT", metrics.get("pat", {})),
                ("Total Debt", metrics.get("total_debt", {})),
                ("Net Worth", metrics.get("net_worth", {})),
                ("D/E Ratio", metrics.get("debt_equity_ratio", "N/A")),
                ("Current Ratio", metrics.get("current_ratio", "N/A")),
                ("DSCR", metrics.get("dscr", "N/A")),
                ("ICR", metrics.get("interest_coverage_ratio", "N/A")),
            ]
            table = doc.add_table(rows=len(metric_items) + 1, cols=3)
            table.style = "Light Grid Accent 1"
            headers = table.rows[0].cells
            headers[0].text = "Metric"
            headers[1].text = "Value"
            headers[2].text = "Unit/Details"

            for i, (name, val) in enumerate(metric_items, 1):
                table.rows[i].cells[0].text = name
                if isinstance(val, dict):
                    table.rows[i].cells[1].text = str(val.get("value", "N/A"))
                    details = []
                    if val.get("unit"):
                        details.append(f"₹ {val['unit']}")
                    if val.get("margin_pct"):
                        details.append(f"Margin: {val['margin_pct']}%")
                    if val.get("growth_pct"):
                        details.append(f"Growth: {val['growth_pct']}%")
                    table.rows[i].cells[2].text = ", ".join(details) if details else ""
                else:
                    table.rows[i].cells[1].text = str(val) if val else "N/A"
                    table.rows[i].cells[2].text = ""

        doc.add_page_break()

        # ── 5. Five Cs Assessment ──
        doc.add_heading("5. Five Cs Assessment", level=1)
        five_cs_narrative = narrative.get("five_cs_narrative", {})
        scores = scoring.get("scores", {})
        details = scoring.get("details", {})

        for c_name in ["character", "capacity", "capital", "collateral", "conditions"]:
            doc.add_heading(f"5.{list(scores.keys()).index(c_name) + 1 if c_name in scores else ''}. "
                            f"{c_name.title()}", level=2)

            c_score = scores.get(c_name, 0)
            c_detail = details.get(c_name, {})

            # Score indicator
            score_para = doc.add_paragraph()
            run = score_para.add_run(f"Score: {c_score}/100")
            run.font.bold = True
            run.font.size = Pt(13)
            if c_score >= 70:
                run.font.color.rgb = RGBColor(0, 128, 0)
            elif c_score >= 50:
                run.font.color.rgb = RGBColor(204, 153, 0)
            else:
                run.font.color.rgb = RGBColor(204, 0, 0)

            # Narrative
            doc.add_paragraph(five_cs_narrative.get(c_name, f"{c_name.title()} assessment."))

            # Scoring factors
            factors = c_detail.get("factors", [])
            if factors:
                doc.add_paragraph("Scoring Factors:", style="List Bullet")
                for factor in factors:
                    doc.add_paragraph(factor, style="List Bullet 2")

        doc.add_page_break()

        # ── 6. Cross-Verification Results ──
        doc.add_heading("6. Cross-Verification Results", level=1)
        cv = self.data.get("cross_verification", {})
        cv_score = cv.get("reconciliation_score", 100)

        score_para = doc.add_paragraph()
        run = score_para.add_run(f"Reconciliation Score: {cv_score}/100")
        run.font.bold = True
        run.font.size = Pt(13)

        doc.add_paragraph(cv.get("summary", "Cross-verification analysis completed."))

        checks = cv.get("checks_performed", [])
        for check in checks:
            doc.add_heading(check.get("check_name", "Check"), level=3)
            doc.add_paragraph(check.get("detail", ""))

        doc.add_page_break()

        # ── 7. Secondary Research ──
        doc.add_heading("7. Secondary Research Findings", level=1)
        research = self.data.get("research_analysis", {})

        news_sent = research.get("news_sentiment", {})
        doc.add_heading("News Sentiment", level=2)
        doc.add_paragraph(
            f"Overall Sentiment: {news_sent.get('overall_label', 'N/A')} "
            f"(Score: {news_sent.get('overall_score', 'N/A')})"
        )
        doc.add_paragraph(
            f"Articles Analyzed: {news_sent.get('article_count', 0)} "
            f"(Positive: {news_sent.get('positive_count', 0)}, "
            f"Negative: {news_sent.get('negative_count', 0)})"
        )

        risk_signals = research.get("risk_signals", {})
        doc.add_heading("Risk Signals", level=2)
        doc.add_paragraph(f"Risk Level: {risk_signals.get('risk_level', 'N/A')}")
        for signal in risk_signals.get("signals", []):
            doc.add_paragraph(
                f"• [{signal['severity']}] {signal['category']}: "
                f"{', '.join(signal.get('keywords_found', []))}",
            )

        # ── 8. Primary Due Diligence ──
        doc.add_heading("8. Primary Due Diligence Notes", level=1)
        qual = self.data.get("qualitative_data", {})
        if qual:
            doc.add_paragraph(qual.get("combined_notes", "No qualitative inputs provided."))
            if qual.get("ai_analysis"):
                analysis = qual["ai_analysis"]
                doc.add_heading("AI Analysis of Due Diligence", level=2)
                doc.add_paragraph(analysis.get("adjustment_rationale", ""))
        else:
            doc.add_paragraph("No primary due diligence notes provided for this assessment.")

        doc.add_page_break()

        # ── 9. Risk Assessment Matrix ──
        doc.add_heading("9. Risk Assessment Matrix", level=1)
        risks = self.data.get("risk_matrix", self._default_risk_matrix())
        table = doc.add_table(rows=len(risks) + 1, cols=4)
        table.style = "Light Grid Accent 1"
        headers = table.rows[0].cells
        headers[0].text = "Risk Category"
        headers[1].text = "Level"
        headers[2].text = "Impact"
        headers[3].text = "Mitigation"
        for i, risk in enumerate(risks, 1):
            table.rows[i].cells[0].text = risk.get("category", "")
            table.rows[i].cells[1].text = risk.get("level", "")
            table.rows[i].cells[2].text = risk.get("impact", "")
            table.rows[i].cells[3].text = risk.get("mitigation", "")

        doc.add_page_break()

        # ── 10. Recommendation ──
        doc.add_heading("10. Final Recommendation", level=1)
        decision = rec.get("decision", "REFER")

        # Decision box
        dec_para = doc.add_paragraph()
        run = dec_para.add_run(f"\n  DECISION: {decision}  \n")
        run.font.size = Pt(20)
        run.font.bold = True
        if decision == "APPROVE":
            run.font.color.rgb = RGBColor(0, 128, 0)
        elif decision == "REJECT":
            run.font.color.rgb = RGBColor(204, 0, 0)
        else:
            run.font.color.rgb = RGBColor(204, 153, 0)

        doc.add_paragraph(narrative.get("recommendation_rationale",
                                        "Recommendation based on comprehensive analysis."))

        if decision in ("APPROVE", "REFER"):
            doc.add_heading("Proposed Terms", level=2)
            terms_table = doc.add_table(rows=4, cols=2)
            terms_table.style = "Light Grid Accent 1"
            terms = [
                ("Interest Rate", f"{rec.get('interest_rate_pct', 'N/A')}% p.a."),
                ("Risk Premium", f"{rec.get('risk_premium_bps', 'N/A')} basis points"),
                ("Key Conditions", ", ".join(rec.get("conditions", ["Standard terms"]))),
                ("Loan Multiplier", f"Up to {rec.get('max_loan_multiplier', 'N/A')}x Net Worth"),
            ]
            for i, (label, value) in enumerate(terms):
                terms_table.rows[i].cells[0].text = label
                terms_table.rows[i].cells[1].text = value

        if rec.get("key_reasons"):
            doc.add_heading("Key Decision Factors", level=2)
            for reason in rec["key_reasons"]:
                doc.add_paragraph(reason, style="List Bullet")

        # ── Footer ──
        doc.add_paragraph("")
        footer = doc.add_paragraph()
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run(
            f"\n\nGenerated by Intelli-Credit AI Engine\n"
            f"{self.generated_at.strftime('%d %B %Y, %H:%M IST')}\n"
            f"This document is computer-generated and should be reviewed by a credit committee."
        )
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(153, 153, 153)

        # Save
        if not output_path:
            output_path = os.path.join(
                Config.OUTPUT_FOLDER,
                f"CAM_{self.company_name.replace(' ', '_')}_{self.generated_at.strftime('%Y%m%d_%H%M')}.docx"
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        logger.info(f"CAM Word document saved: {output_path}")
        return output_path

    def generate_pdf(self, output_path: str = None) -> str:
        """Generate CAM as PDF document."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, HRFlowable
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        if not output_path:
            output_path = os.path.join(
                Config.OUTPUT_FOLDER,
                f"CAM_{self.company_name.replace(' ', '_')}_{self.generated_at.strftime('%Y%m%d_%H%M')}.pdf"
            )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                topMargin=2 * cm, bottomMargin=2 * cm)

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="CamTitle", fontSize=28, alignment=TA_CENTER,
            textColor=HexColor("#003366"), spaceAfter=12, fontName="Helvetica-Bold", leading=32
        ))
        styles.add(ParagraphStyle(
            name="CamSubtitle", fontSize=18, alignment=TA_CENTER,
            textColor=HexColor("#006699"), spaceAfter=24
        ))
        styles.add(ParagraphStyle(
            name="SectionHead", fontSize=16, textColor=HexColor("#003366"),
            spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"
        ))
        styles.add(ParagraphStyle(
            name="SubSection", fontSize=13, textColor=HexColor("#004d80"),
            spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"
        ))
        styles.add(ParagraphStyle(
            name="BodyText2", fontSize=11, spaceAfter=6,
            leading=15, fontName="Helvetica"
        ))

        elements = []

        # Title page
        elements.append(Spacer(1, 4 * cm))
        elements.append(Paragraph("CREDIT APPRAISAL MEMORANDUM", styles["CamTitle"]))
        elements.append(Paragraph(self.company_name, styles["CamSubtitle"]))
        elements.append(Spacer(1, 1 * cm))
        elements.append(Paragraph(
            f"Date: {self.generated_at.strftime('%d %B %Y')}",
            styles["BodyText2"]
        ))
        elements.append(Paragraph("- CONFIDENTIAL -", styles["CamSubtitle"]))
        elements.append(Spacer(1, 2 * cm))
        elements.append(Paragraph(
            "Prepared by: Intelli-Credit AI Engine", styles["BodyText2"]
        ))
        elements.append(PageBreak())

        # Executive Summary
        scoring = self.data.get("scoring", {})
        rec = scoring.get("recommendation", {})
        narrative = self.data.get("narrative", {})

        elements.append(Paragraph("1. Executive Summary", styles["SectionHead"]))
        elements.append(HRFlowable(width="100%", color=HexColor("#003366")))
        elements.append(Paragraph(
            narrative.get("executive_summary", self._default_executive_summary()),
            styles["BodyText2"]
        ))

        # Scorecard
        scorecard_data = [
            ["Metric", "Value"],
            ["Overall Score", f"{scoring.get('overall_score', 0)}/100"],
            ["Risk Grade", scoring.get("risk_grade", "N/A")],
            ["Decision", rec.get("decision", "N/A")],
            ["Interest Rate", f"{rec.get('interest_rate_pct', 'N/A')}%"],
        ]
        t = Table(scorecard_data, colWidths=[8 * cm, 8 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(t)
        elements.append(PageBreak())

        # Five Cs section
        elements.append(Paragraph("2. Five Cs Assessment", styles["SectionHead"]))
        elements.append(HRFlowable(width="100%", color=HexColor("#003366")))

        scores = scoring.get("scores", {})
        five_cs_data = [["Category", "Score", "Weight", "Weighted"]]
        weights = scoring.get("weights", {})
        for c_name in ["character", "capacity", "capital", "collateral", "conditions"]:
            s = scores.get(c_name, 0)
            w = weights.get(c_name, 0)
            five_cs_data.append([c_name.title(), f"{s:.0f}/100", f"{w*100:.0f}%", f"{s*w:.1f}"])

        five_cs_data.append(["OVERALL", f"{scoring.get('overall_score', 0):.1f}/100", "100%", ""])

        t = Table(five_cs_data, colWidths=[5 * cm, 4 * cm, 3.5 * cm, 4 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), HexColor("#E6EEF5")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(t)
        elements.append(PageBreak())

        # Recommendation
        elements.append(Paragraph("3. Final Recommendation", styles["SectionHead"]))
        elements.append(HRFlowable(width="100%", color=HexColor("#003366")))

        decision = rec.get("decision", "REFER")
        color = "#008000" if decision == "APPROVE" else "#CC0000" if decision == "REJECT" else "#CC9900"
        elements.append(Paragraph(
            f'<b><font size="20" color="{color}">DECISION: {decision}</font></b>',
            styles["BodyText2"]
        ))
        elements.append(Paragraph(
            narrative.get("recommendation_rationale", "Based on comprehensive analysis."),
            styles["BodyText2"]
        ))

        if rec.get("key_reasons"):
            elements.append(Paragraph("Key Factors:", styles["SubSection"]))
            for reason in rec["key_reasons"]:
                elements.append(Paragraph(f"• {reason}", styles["BodyText2"]))

        # Footer
        elements.append(Spacer(1, 2 * cm))
        elements.append(HRFlowable(width="100%", color=HexColor("#CCCCCC")))
        elements.append(Paragraph(
            f"Generated by Intelli-Credit AI Engine | "
            f"{self.generated_at.strftime('%d %B %Y, %H:%M IST')} | CONFIDENTIAL",
            ParagraphStyle(name="Footer", fontSize=8, textColor=HexColor("#999999"),
                           alignment=TA_CENTER)
        ))

        doc.build(elements)
        logger.info(f"CAM PDF saved: {output_path}")
        return output_path

    def _default_executive_summary(self) -> str:
        scoring = self.data.get("scoring", {})
        rec = scoring.get("recommendation", {})
        return (
            f"This Credit Appraisal Memo presents a comprehensive analysis of {self.company_name} "
            f"based on financial documents, secondary research, and AI-powered risk assessment. "
            f"The overall credit score is {scoring.get('overall_score', 'N/A')}/100 "
            f"({scoring.get('risk_grade', 'N/A')}). "
            f"Recommendation: {rec.get('decision', 'REFER')} with an interest rate of "
            f"{rec.get('interest_rate_pct', 'N/A')}% p.a. including a risk premium of "
            f"{rec.get('risk_premium_bps', 'N/A')} basis points."
        )

    def _default_risk_matrix(self) -> list:
        return [
            {"category": "Credit Risk", "level": "Assessed per scoring", "impact": "Direct",
             "mitigation": "Collateral, covenants, monitoring"},
            {"category": "Market Risk", "level": "Sector-dependent", "impact": "Indirect",
             "mitigation": "Diversification, sector limits"},
            {"category": "Operational Risk", "level": "Based on due diligence", "impact": "Moderate",
             "mitigation": "Insurance, process controls"},
            {"category": "Compliance Risk", "level": "Regulatory scan", "impact": "High",
             "mitigation": "Regular compliance monitoring"},
            {"category": "Fraud Risk", "level": "Cross-verification based", "impact": "Critical",
             "mitigation": "Enhanced due diligence, forensic triggers"},
        ]
