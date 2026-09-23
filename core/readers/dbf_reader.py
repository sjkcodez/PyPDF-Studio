"""DBF (dBASE) → AST reader."""
from pathlib import Path
from core.ast import Document, Table


def read(path: str) -> Document:
    from dbfread import DBF

    table = DBF(path, load=True, ignore_missing_memofile=True)
    headers = list(table.field_names)
    rows = []
    for record in table:
        rows.append(["" if record.get(f) is None else str(record.get(f, "")) for f in headers])

    ast = Document()
    ast.metadata["title"] = Path(path).stem
    ast.children.append(Table(headers=headers, rows=rows))
    return ast
