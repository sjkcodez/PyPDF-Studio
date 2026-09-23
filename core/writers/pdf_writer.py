"""AST → PDF writer (via reportlab)."""
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph as RLParagraph, Spacer,
    ListFlowable, ListItem, Preformatted, Table as RLTable, TableStyle,
)
from reportlab.lib import colors
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList,
    CodeBlock, BlockQuote, HorizontalRule, Table,
)


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def write(ast: Document, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=LETTER,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    flow = []

    if ast.metadata.get("title"):
        flow.append(RLParagraph(_escape(ast.metadata["title"]), styles["Title"]))
        flow.append(Spacer(1, 12))

    for node in ast.children:
        if isinstance(node, Heading):
            style_name = f"Heading{min(node.level, 4)}" if node.level <= 4 else "Heading4"
            flow.append(RLParagraph(_escape(node.text), styles[style_name]))
            flow.append(Spacer(1, 6))
        elif isinstance(node, Paragraph):
            flow.append(RLParagraph(_escape(node.text), styles["BodyText"]))
            flow.append(Spacer(1, 6))
        elif isinstance(node, BulletList):
            items = [ListItem(RLParagraph(_escape(i), styles["BodyText"])) for i in node.items]
            flow.append(ListFlowable(items, bulletType="bullet"))
            flow.append(Spacer(1, 6))
        elif isinstance(node, NumberedList):
            items = [ListItem(RLParagraph(_escape(i), styles["BodyText"])) for i in node.items]
            flow.append(ListFlowable(items, bulletType="1"))
            flow.append(Spacer(1, 6))
        elif isinstance(node, CodeBlock):
            flow.append(Preformatted(node.code, styles["Code"]))
            flow.append(Spacer(1, 6))
        elif isinstance(node, BlockQuote):
            flow.append(RLParagraph(f"<i>{_escape(node.text)}</i>", styles["BodyText"]))
            flow.append(Spacer(1, 6))
        elif isinstance(node, HorizontalRule):
            flow.append(Spacer(1, 12))
        elif isinstance(node, Table):
            data = [node.headers] + node.rows
            t = RLTable(data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            flow.append(t)
            flow.append(Spacer(1, 12))

    doc.build(flow)
