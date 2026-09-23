"""CSV / TSV → AST reader."""
import csv
from pathlib import Path
from core.ast import Document, Table


def read(path: str) -> Document:
    p = Path(path)
    delimiter = "\t" if p.suffix.lower() == ".tsv" else ","

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=delimiter))

    ast = Document()
    ast.metadata["title"] = p.stem

    if rows:
        ast.children.append(Table(headers=rows[0], rows=rows[1:]))

    return ast
