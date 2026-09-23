"""Markdown → AST reader."""
import re
from pathlib import Path
from core.ast import (
    Document, Heading, Paragraph, BulletList,
    NumberedList, CodeBlock, BlockQuote, HorizontalRule, Table,
)


def _parse_table(lines, start):
    """Parse a GitHub-flavoured Markdown table starting at index 'start'."""
    headers = [c.strip() for c in lines[start].strip("|").split("|")]
    rows = []
    i = start + 2  # skip separator row
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip("|").split("|")]
        rows.append(cells)
        i += 1
    return Table(headers=headers, rows=rows), i


def read(path: str) -> Document:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    ast = Document()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block
        if line.strip().startswith("```"):
            lang = line.strip().strip("`").strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            ast.children.append(CodeBlock(code="\n".join(code_lines), language=lang))
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            ast.children.append(Heading(level=len(m.group(1)), text=m.group(2).strip()))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            ast.children.append(HorizontalRule())
            i += 1
            continue

        # Blockquote
        if line.strip().startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip("> ").strip())
                i += 1
            ast.children.append(BlockQuote(text=" ".join(quote)))
            continue

        # Bullet list
        if re.match(r"^\s*[-*+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip())
                i += 1
            ast.children.append(BulletList(items=items))
            continue

        # Numbered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip())
                i += 1
            ast.children.append(NumberedList(items=items))
            continue

        # Table
        if line.strip().startswith("|") and i + 1 < len(lines) and "---" in lines[i + 1]:
            table, i = _parse_table(lines, i)
            ast.children.append(table)
            continue

        # Blank line
        if not line.strip():
            i += 1
            continue

        # Paragraph (gather consecutive non-empty lines)
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|>|```|\s*[-*+]\s|\s*\d+\.\s|\|)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        ast.children.append(Paragraph(text=" ".join(para)))

    return ast
