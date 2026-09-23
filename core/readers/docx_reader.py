"""DOCX → AST reader.

Extracts:
  • Heading levels from Word's paragraph styles (Heading 1, Heading 2, …)
  • Fallback heading detection by font size when styles aren't applied
  • Inline bold / italic from paragraph runs
  • Bullet and numbered lists grouped into single List nodes
  • Tables
"""
from collections import Counter
from docx import Document as DocxDocument
from core.ast import (
    Document, Heading, Paragraph, BulletList, NumberedList, Table, Run,
)


# ============================================================
# Style helpers
# ============================================================
def _style_level(style_name: str):
    """Return heading level from a Word style name, else None."""
    s = (style_name or "").lower()
    if s.startswith("heading"):
        digits = "".join(ch for ch in s if ch.isdigit())
        return int(digits) if digits else 1
    if s == "title":
        return 1
    if s == "subtitle":
        return 2
    return None


def _run_is_bold(run) -> bool:
    # run.bold can be True / False / None (inherit from style)
    if run.bold is not None:
        return bool(run.bold)
    # Fall back to the style's bold setting
    try:
        if run._parent and run._parent.style and run._parent.style.font.bold:
            return True
    except Exception:
        pass
    return False


def _run_is_italic(run) -> bool:
    if run.italic is not None:
        return bool(run.italic)
    try:
        if run._parent and run._parent.style and run._parent.style.font.italic:
            return True
    except Exception:
        pass
    return False


def _run_size(run):
    if run.font and run.font.size:
        return run.font.size.pt
    return None


def _para_default_size(para):
    try:
        style = para.style
        if style and style.font and style.font.size:
            return style.font.size.pt
    except Exception:
        pass
    return None


def _effective_run_size(run, para):
    s = _run_size(run)
    if s is not None:
        return s
    return _para_default_size(para)


def _para_max_size(para) -> float:
    default = _para_default_size(para)
    max_s = 0.0
    for r in para.runs:
        s = _run_size(r) or default
        if s and s > max_s:
            max_s = s
    return max_s


# ============================================================
# Body-size detection + heading size map
# ============================================================
def _detect_body_size(doc) -> float:
    """Most common font size in the document (this is body text)."""
    sizes = []
    for para in doc.paragraphs:
        default = _para_default_size(para)
        for r in para.runs:
            s = _run_size(r) or default
            if s:
                sizes.append(round(s, 1))
    if not sizes:
        return 11.0  # Word default
    return Counter(sizes).most_common(1)[0][0]


def _compute_size_level_map(doc, body_size: float) -> dict:
    """Map each heading-sized font to a Markdown heading level.

    Any size noticeably larger than the body text becomes a heading level.
    The largest size gets level 1, the next gets level 2, and so on.
    """
    sizes = set()
    for para in doc.paragraphs:
        s = _para_max_size(para)
        if s > 0:
            sizes.add(round(s, 1))

    # Only sizes meaningfully larger than the body text count as headings
    heading_sizes = sorted(
        [s for s in sizes if s > body_size * 1.05],
        reverse=True,
    )
    return {s: min(i + 1, 6) for i, s in enumerate(heading_sizes)}


# ============================================================
# Run extraction
# ============================================================
def _extract_runs(paragraph) -> list:
    runs = []
    for r in paragraph.runs:
        text = r.text
        if not text:
            continue
        runs.append(Run(
            text=text,
            bold=_run_is_bold(r),
            italic=_run_is_italic(r),
        ))
    return runs


# ============================================================
# Main reader
# ============================================================
def read(path: str) -> Document:
    doc = DocxDocument(path)
    ast = Document()
    ast.metadata["title"] = doc.core_properties.title or ""

    body_size = _detect_body_size(doc)
    size_level_map = _compute_size_level_map(doc, body_size)

    bullets = []
    numbers = []

    def flush_lists():
        if bullets:
            ast.children.append(BulletList(items=bullets[:]))
            bullets.clear()
        if numbers:
            ast.children.append(NumberedList(items=numbers[:]))
            numbers.clear()

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        runs = _extract_runs(para)
        style_name = (para.style.name if para.style else "") or ""

        # ---------- 1. Style-based heading ----------
        level = _style_level(style_name)

        # ---------- 2. Size-based heading fallback ----------
        if level is None:
            max_size = round(_para_max_size(para), 1)
            level = size_level_map.get(max_size)

        if level is not None:
            flush_lists()
            ast.children.append(Heading(
                level=min(level, 6),
                text=text,
                runs=runs,
            ))
            continue

        # ---------- 3. Lists ----------
        lower = style_name.lower()
        if "list bullet" in lower or "list paragraph" in lower and para._element.pPr is not None and para._element.pPr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"
        ) is None:
            bullets.append(text)
            continue
        if "list number" in lower:
            numbers.append(text)
            continue

        # ---------- 4. Regular paragraph ----------
        flush_lists()
        ast.children.append(Paragraph(text=text, runs=runs))

    flush_lists()

    # ---------- Tables ----------
    for tbl in doc.tables:
        if not tbl.rows:
            continue
        headers = [c.text.strip() for c in tbl.rows[0].cells]
        rows = [[c.text.strip() for c in r.cells] for r in tbl.rows[1:]]
        ast.children.append(Table(headers=headers, rows=rows))

    return ast
