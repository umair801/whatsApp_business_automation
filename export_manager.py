"""
Export Manager
Generates CSV and PDF reports from analytics data
"""

import csv
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

NAVY   = colors.HexColor("#0f1f3d")
BLUE   = colors.HexColor("#2563eb")
GREEN  = colors.HexColor("#10b981")
RED    = colors.HexColor("#ef4444")
AMBER  = colors.HexColor("#f59e0b")
LIGHT  = colors.HexColor("#f5f7fa")
BORDER = colors.HexColor("#e4e9f0")
WHITE  = colors.white
MUTED  = colors.HexColor("#64748b")


class ExportManager:
    """Handles CSV and PDF generation from analytics data"""

    def __init__(self, analytics_engine):
        self.analytics = analytics_engine

    def export_overview_csv(self) -> io.StringIO:
        data = self.analytics.get_overview()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TechZone WhatsApp Automation - Overview Report"])
        writer.writerow(["Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")])
        writer.writerow([])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Unique Customers", data.get("unique_customers", 0)])
        writer.writerow(["Total Messages", data.get("total_messages", 0)])
        writer.writerow(["Messages Today", data.get("messages_today", 0)])
        writer.writerow(["Total Orders", data.get("total_orders", 0)])
        writer.writerow(["Pending Orders", data.get("pending_orders", 0)])
        writer.writerow(["Total Revenue (Rs.)", data.get("total_revenue", 0)])
        writer.writerow(["Total Escalations", data.get("total_escalations", 0)])
        writer.writerow(["Open Escalations", data.get("open_escalations", 0)])
        output.seek(0)
        return output

    def export_orders_csv(self) -> io.StringIO:
        data = self.analytics.get_order_metrics()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TechZone WhatsApp Automation - Orders Report"])
        writer.writerow(["Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")])
        writer.writerow([])
        writer.writerow(["Order Number", "Product", "Amount (Rs.)", "Status", "Date"])
        for order in data.get("recent_orders", []):
            writer.writerow([
                order.get("order_number", ""), order.get("product_name", ""),
                order.get("total_amount", 0), order.get("status", ""),
                str(order.get("created_at", ""))[:10],
            ])
        output.seek(0)
        return output

    def export_escalations_csv(self) -> io.StringIO:
        data = self.analytics.get_escalation_metrics()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TechZone WhatsApp Automation - Escalations Report"])
        writer.writerow(["Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")])
        writer.writerow([])
        writer.writerow(["Case ID", "Sentiment Score", "Label", "Reason", "Status", "Timestamp"])
        for esc in data.get("recent_escalations", []):
            writer.writerow([
                esc.get("case_id", ""), esc.get("sentiment_score", ""),
                esc.get("sentiment_label", ""), esc.get("escalation_reason", ""),
                esc.get("status", ""), str(esc.get("timestamp", ""))[:16].replace("T", " "),
            ])
        output.seek(0)
        return output

    def export_trends_csv(self) -> io.StringIO:
        data = self.analytics.get_conversation_trends()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TechZone WhatsApp Automation - Conversation Trends"])
        writer.writerow(["Generated:", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")])
        writer.writerow([])
        writer.writerow(["Date", "Messages"])
        for row in data:
            writer.writerow([row["date"], row["messages"]])
        output.seek(0)
        return output

    def export_full_pdf(self) -> io.BytesIO:
        dashboard_data = self.analytics.get_dashboard_data()
        overview    = dashboard_data.get("overview", {})
        trends      = dashboard_data.get("conversation_trends", [])
        langs       = dashboard_data.get("language_breakdown", [])
        orders      = dashboard_data.get("order_metrics", {})
        escalations = dashboard_data.get("escalation_metrics", {})

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
            title="TechZone Business Intelligence Report")

        story = []
        title_style    = ParagraphStyle("RT", fontSize=22, fontName="Helvetica-Bold", textColor=NAVY, alignment=TA_LEFT, spaceAfter=4)
        subtitle_style = ParagraphStyle("ST", fontSize=10, fontName="Helvetica", textColor=MUTED, alignment=TA_LEFT, spaceAfter=20)
        section_style  = ParagraphStyle("SEC", fontSize=12, fontName="Helvetica-Bold", textColor=NAVY, spaceBefore=16, spaceAfter=8)

        story.append(Paragraph("TechZone Intelligence Report", title_style))
        story.append(Paragraph(
            f"WhatsApp Business Automation · Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}",
            subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=16))

        story.append(Paragraph("Executive Summary", section_style))
        kpi_data = [["Metric", "Value"],
            ["Unique Customers",  str(overview.get("unique_customers", 0))],
            ["Total Messages",    str(overview.get("total_messages", 0))],
            ["Messages Today",    str(overview.get("messages_today", 0))],
            ["Total Orders",      str(overview.get("total_orders", 0))],
            ["Pending Orders",    str(overview.get("pending_orders", 0))],
            ["Total Revenue",     f"Rs. {overview.get('total_revenue', 0):,}"],
            ["Total Escalations", str(overview.get("total_escalations", 0))],
            ["Open Escalations",  str(overview.get("open_escalations", 0))]]
        kpi_table = Table(kpi_data, colWidths=[9*cm, 8*cm])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,0), NAVY), ("TEXTCOLOR",(0,0),(-1,0), WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,0),10),
            ("ALIGN",(0,0),(-1,0),"LEFT"), ("PADDING",(0,0),(-1,0),10),
            ("FONTNAME",(0,1),(-1,-1),"Helvetica"), ("FONTSIZE",(0,1),(-1,-1),9),
            ("PADDING",(0,1),(-1,-1),8), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
            ("GRID",(0,0),(-1,-1),0.5,BORDER)]))
        story.append(kpi_table)
        story.append(Spacer(1, 16))

        if langs:
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))
            story.append(Paragraph("Language Distribution", section_style))
            total_msgs = sum(l.get("count", 0) for l in langs)
            lang_data = [["Language", "Messages", "Share %"]]
            for l in langs:
                cnt = l.get("count", 0)
                pct = f"{(cnt / total_msgs * 100):.1f}%" if total_msgs else "0%"
                lang_data.append([l.get("language", ""), str(cnt), pct])
            lang_table = Table(lang_data, colWidths=[7*cm, 5*cm, 5*cm])
            lang_table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),BLUE), ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
                ("PADDING",(0,0),(-1,-1),8), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("GRID",(0,0),(-1,-1),0.5,BORDER)]))
            story.append(lang_table)
            story.append(Spacer(1, 16))

        if trends:
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))
            story.append(Paragraph("Conversation Trends (Last 7 Days)", section_style))
            trend_data = [["Date", "Messages"]] + [[t.get("date",""), str(t.get("messages",0))] for t in trends]
            trend_table = Table(trend_data, colWidths=[9*cm, 8*cm])
            trend_table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),BLUE), ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9),
                ("PADDING",(0,0),(-1,-1),8), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("GRID",(0,0),(-1,-1),0.5,BORDER)]))
            story.append(trend_table)
            story.append(Spacer(1, 16))

        recent_orders = orders.get("recent_orders", [])
        if recent_orders:
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))
            story.append(Paragraph("Recent Orders", section_style))
            order_data = [["Order #", "Product", "Amount (Rs.)", "Status", "Date"]]
            for o in recent_orders:
                order_data.append([o.get("order_number",""), o.get("product_name",""),
                    f"{o.get('total_amount',0):,}", o.get("status","").upper(), str(o.get("created_at",""))[:10]])
            order_table = Table(order_data, colWidths=[4.5*cm, 4.5*cm, 3*cm, 2.5*cm, 2.5*cm])
            order_table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
                ("PADDING",(0,0),(-1,-1),7), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("GRID",(0,0),(-1,-1),0.5,BORDER), ("TEXTCOLOR",(3,1),(3,-1),GREEN),
                ("FONTNAME",(3,1),(3,-1),"Helvetica-Bold")]))
            story.append(order_table)
            story.append(Spacer(1, 16))

        recent_escs = escalations.get("recent_escalations", [])
        if recent_escs:
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=12))
            story.append(Paragraph("Escalation Events", section_style))
            esc_data = [["Case ID", "Score", "Label", "Reason", "Status"]]
            for e in recent_escs:
                reason = e.get("escalation_reason", "")
                esc_data.append([e.get("case_id",""), str(e.get("sentiment_score","")),
                    e.get("sentiment_label","").upper(), reason[:40]+("..." if len(reason)>40 else ""),
                    e.get("status","").upper()])
            esc_table = Table(esc_data, colWidths=[5*cm, 2*cm, 2.5*cm, 5*cm, 2.5*cm])
            esc_table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),RED), ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
                ("PADDING",(0,0),(-1,-1),7), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
                ("GRID",(0,0),(-1,-1),0.5,BORDER)]))
            story.append(esc_table)

        story.append(Spacer(1, 24))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "TechZone WhatsApp Intelligence · Enterprise Agentic AI Portfolio · Project 1/50 · Confidential",
            ParagraphStyle("Footer", fontSize=7, fontName="Helvetica", textColor=MUTED, alignment=TA_CENTER)))

        doc.build(story)
        buffer.seek(0)
        return buffer
