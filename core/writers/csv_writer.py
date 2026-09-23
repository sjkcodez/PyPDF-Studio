"""AST → CSV / TSV writer.

Handles three cases:
  1. AST contains a Table node           → writes the table
  2. AST contains multiple Table nodes   → concatenates them
  3. AST has no tables (text-only doc)   → writes each paragraph as one row
"""
import csv

from core.ast import Document, Table, Heading, Paragraph, BulletList, NumberedList


def write(ast: Document, output_path: str):
    delimiter = "\t" if output_path.lower().endswith(".tsv") else ","

    # ---- 1. Collect all tables in the AST ----
    tables = [n for n in ast.children if isinstance(n, Table)]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)

        if tables:
            for idx, table in enumerate(tables):
                if idx > 0:
                    w.writerow([])  # blank row between tables
                if table.headers:
                    w.writerow(table.headers)
                for row in table.rows:
                    w.writerow(row)
            return

        # ---- 2. No tables: use text as single-column rows ----
        wrote_anything = False
        for node in ast.children:
            if isinstance(node, Heading):
                w.writerow([node.text])
                wrote_anything = True
            elif isinstance(node, Paragraph):
                w.writerow([node.text])
                wrote_anything = True
            elif isinstance(node, BulletList):
                for item in node.items:
                    w.writerow([f"• {item}"])
                wrote_anything = True
            elif isinstance(node, NumberedList):
                for i, item in enumerate(node.items, 1):
                    w.writerow([f"{i}. {item}"])
                wrote_anything = True

        if not wrote_anything:
            w.writerow(["[No extractable content]"])
