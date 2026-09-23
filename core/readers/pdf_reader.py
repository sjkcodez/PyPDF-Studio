"""PDF → AST reader with heading and style detection.

Uses PyMuPDF's dict output, which exposes per-span font name and size.
Headings are detected from font size relative to the body text size.
Bold / italic are detected from font names (Arial-Bold, Arial-Italic, etc.).
"""
from collections import Counter
from pathlib import Path
from core.ast import Document, Heading, Paragraph, Run


def _open_pdf(path):
    try:
        import pymupdf as fitz
        return fitz.open(str(path))
    except ImportError:
        import fitz
        return fitz.open(str(path))


# ============================================================
# Font / style detection
# ============================================================
def _is_bold_font(font_name: str) -> bool:
    if not font_name:
        return False
    n = font_name.lower()
    return "bold" in n or "heavy" in n or "black" in n


def _is_italic_font(font_name: str) -> bool:
    if not font_name:
        return False
    n = font_name.lower()
    return "italic" in n or "oblique" in n


# ============================================================
# Span collection
# ============================================================
def _collect_span_sizes(pages_data) -> list:
    """Return every span size in the document (for body-size detection)."""
    sizes = []
    for data in pages_data:
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    s = span.get("size", 0.0) or 0.0
                    if s > 0:
                        sizes.append(round(s, 1))
    return sizes


def _body_size(sizes) -> float:
    if not sizes:
        return 11.0
    return Counter(sizes).most_common(1)[0][0]


def _size_level_map(sizes, body_size: float) -> dict:
    unique = sorted(set(sizes), reverse=True)
    heading_sizes = [s for s in unique if s > body_size * 1.05]
    return {s: min(i + 1, 6) for i, s in enumerate(heading_sizes)}


# ============================================================
# Main reader
# ============================================================
def read(path: str) -> Document:
    doc = _open_pdf(path)
    ast = Document()
    ast.metadata["title"] = Path(path).stem

    # -------- Pass 1: collect all pages' data --------
    pages_data = []
    for page in doc:
        try:
            pages_data.append(page.get_text("dict"))
        except Exception:
            pages_data.append({"blocks": []})

    # -------- Compute body size + heading map --------
    all_sizes = _collect_span_sizes(pages_data)
    body_size = _body_size(all_sizes)
    if body_size < 4:
        body_size = 11.0
    level_map = _size_level_map(all_sizes, body_size)

    # -------- Pass 2: build AST --------
    for data in pages_data:
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue

            runs = []
            max_size = 0.0

            for line_idx, line in enumerate(block.get("lines", [])):
                # Add a space between lines (PDF lines don't include them)
                if line_idx > 0 and runs:
                    last = runs[-1]
                    if last.text and not last.text.endswith((" ", "\t", "\n")):
                        runs.append(Run(text=" ", bold=last.bold, italic=last.italic))

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    font = span.get("font", "") or ""
                    size = float(span.get("size", 0.0) or 0.0)
                    if size > max_size:
                        max_size = size

                    runs.append(Run(
                        text=text,
                        bold=_is_bold_font(font),
                        italic=_is_italic_font(font),
                    ))

            if not runs:
                continue

            full_text = "".join(r.text for r in runs).strip()
            if not full_text:
                continue

            # Heading detection
            rounded = round(max_size, 1)
            level = level_map.get(rounded)

            if level is not None and len(full_text) <= 200:
                ast.children.append(Heading(
                    level=level,
                    text=full_text,
                    runs=runs,
                ))
            else:
                ast.children.append(Paragraph(
                    text=full_text,
                    runs=runs,
                ))

    doc.close()
    return ast
