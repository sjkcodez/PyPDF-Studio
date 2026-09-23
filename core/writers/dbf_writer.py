"""AST → DBF (dBASE) writer.

Requires the AST to contain exactly one Table node (from DBF reader or
from any format that produced a Table).
"""
from core.ast import Document, Table


def _infer_field_type(values):
    """Return 'C' (character) or 'N' (numeric) based on column values."""
    for v in values:
        if v == "" or v is None:
            continue
        try:
            float(v)
        except (TypeError, ValueError):
            return "C"
    return "N"


def write(ast: Document, output_path: str):
    import dbf

    table_node = None
    for node in ast.children:
        if isinstance(node, Table):
            table_node = node
            break

    if table_node is None:
        raise ValueError("DBF writer requires a Table node in the AST.")

    headers = table_node.headers
    rows = table_node.rows

    # Compute max length per column
    col_widths = []
    for i, h in enumerate(headers):
        max_len = len(h)
        for row in rows:
            if i < len(row):
                max_len = max(max_len, len(str(row[i])))
        col_widths.append(max(max_len, 1))

    # Build field specs
    fields = []
    for i, h in enumerate(headers):
        col_values = [str(r[i]) if i < len(r) else "" for r in rows]
        ftype = _infer_field_type(col_values)
        safe_name = h.replace(" ", "_")[:10] or f"FIELD{i}"
        if ftype == "N":
            fields.append(f"{safe_name} N 18.2")
        else:
            fields.append(f"{safe_name} C {col_widths[i]}")

    # Create the table
    table = dbf.Table(output_path, "; ".join(fields))
    table.open(dbf.READ_WRITE)

    for row in rows:
        record = []
        for i, v in enumerate(row):
            if i >= len(fields):
                break
            ftype = fields[i].split()[1]
            if ftype == "N":
                try:
                    record.append(float(v) if v != "" else 0.0)
                except (TypeError, ValueError):
                    record.append(0.0)
            else:
                record.append(str(v))
        while len(record) < len(fields):
            record.append("")
        table.append(tuple(record))

    table.close()
