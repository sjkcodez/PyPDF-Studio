"""XLSX / XLSM → AST reader.

Each worksheet becomes:
    Heading(level=1, "Sheet: <name>")
    Table(headers=..., rows=...)
"""
from pathlib import Path
from openpyxl import load_workbook
from core.ast import Document, Heading, Table


def _norm(v):
    return "" if v is None else str(v)


def read(path: str) -> Document:
    wb = load_workbook(path, data_only=True, read_only=True)
    ast = Document()
    ast.metadata["title"] = Path(path).stem

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            ast.children.append(Heading(level=1, text=f"Sheet: {sheet_name}"))

            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if not rows:
                continue

            # If the first row looks like a header, use it as such
            headers = [_norm(c) for c in rows[0]]
            body = [[_norm(c) for c in r] for r in rows[1:]]
            ast.children.append(Table(headers=headers, rows=body))
    finally:
        wb.close()

    return ast
