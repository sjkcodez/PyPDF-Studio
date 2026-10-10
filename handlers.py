"""Non-interactive tool handlers for the web GUI — v6.9.

Changes in this version:
- PDF → XLSX now preserves cell background colors and text colors by
  sampling pixels from the rendered PDF page and inspecting text spans.
- Falls back to the previous CSV-based approach if no tables are detected
  or if color extraction fails for any reason.
- Everything else unchanged from v6.8.
- FIX: shutil.move() replaces Path.replace() so files can cross Docker
  bind-mount boundaries (uploads/ and output/ are separate mounts).
"""
import io
import os
import re
import csv
import json as _json
import uuid
import zipfile
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.utils import OUTPUT_DIR


# ============================================================
# Tunables
# ============================================================
SMALL_PDF_PAGE_LIMIT = 30

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".jif",
    ".png",
    ".webp",
    ".gif",
    ".tif", ".tiff",
    ".bmp",
    ".ico",
    ".tga",
    ".pcx",
    ".dds",
    ".ppm", ".pgm", ".pbm", ".pnm",
    ".heic", ".heif",
    ".avif",
    ".cr2", ".cr3", ".crw",
    ".nef", ".nrw",
    ".arw", ".srf", ".sr2",
    ".dng",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
    ".x3f",
    ".kdc", ".dcr", ".mrw",
    ".3fr", ".fff", ".iiq", ".rwl",
}

RAW_EXTS = {
    ".cr2", ".cr3", ".crw",
    ".nef", ".nrw",
    ".arw", ".srf", ".sr2",
    ".dng",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
    ".x3f",
    ".kdc", ".dcr", ".mrw",
    ".3fr", ".fff", ".iiq", ".rwl",
}

IMAGE_OUTPUT_EXTS = {
    "jpg", "jpeg", "jpe", "jfif", "jif",
    "png", "webp", "gif",
    "tif", "tiff",
    "bmp",
    "heic", "heif",
    "ico",
}


# ============================================================
# Output path helpers
# ============================================================
_SAFE_RE = re.compile(r'[^\w.\-]', flags=re.UNICODE)


def _sanitize(name: str) -> str:
    safe = _SAFE_RE.sub("_", name)
    safe = safe.strip("._-")
    return safe or "file"


def _out(stem: str, ext: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_stem = _sanitize(stem)
    safe_ext = ext.lstrip(".")
    name = f"{safe_stem}_converted_{ts}.{safe_ext}"
    path = OUTPUT_DIR / name
    counter = 1
    while path.exists():
        name = f"{safe_stem}_converted_{ts}_{counter}.{safe_ext}"
        path = OUTPUT_DIR / name
        counter += 1
    return path


# ============================================================
# Misc helpers
# ============================================================
def _parse_pages(spec: str, total: int):
    spec = (spec or "").strip()
    if not spec or spec.lower() == "all":
        return list(range(total))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, int(b)))
        else:
            out.append(int(part) - 1)
    return [i for i in out if 0 <= i < total]


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def _fitz():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz


def _safe_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pdf_page_count(pdf_path: Path) -> int:
    try:
        fitz = _fitz()
        doc = fitz.open(str(pdf_path))
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


def _require_tesseract():
    import shutil as _sh
    if _sh.which("tesseract") is None:
        raise RuntimeError(
            "Tesseract OCR is not installed.\n"
            "Install it from:\n"
            "  • Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  • Linux:   sudo apt install tesseract-ocr\n"
            "  • macOS:   brew install tesseract"
        )


# ============================================================
# XML ↔ JSON
# ============================================================
def _xml_to_json(xml_path: Path, out_path: Path):
    try:
        import xmltodict
    except ImportError:
        raise RuntimeError(
            "XML → JSON requires the 'xmltodict' package.\n"
            "Install it:\n"
            "  pip install xmltodict"
        )
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        data = xmltodict.parse(content)
    except Exception as e:
        raise RuntimeError(f"Could not parse XML: {e}")
    with open(out_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, indent=2, ensure_ascii=False)


def _json_to_xml(json_path: Path, out_path: Path):
    try:
        import xmltodict
    except ImportError:
        raise RuntimeError(
            "JSON → XML requires the 'xmltodict' package.\n"
            "Install it:\n"
            "  pip install xmltodict"
        )
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = _json.load(f)
        except Exception as e:
            raise RuntimeError(f"Could not parse JSON: {e}")

    if not isinstance(data, dict) or len(data) != 1:
        data = {"root": data}

    try:
        xml_str = xmltodict.unparse(data, pretty=True, full_document=True)
    except Exception as e:
        raise RuntimeError(f"Could not produce XML: {e}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_str)


# ============================================================
# Image loading / saving
# ============================================================
def _register_heif_support() -> bool:
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        return True
    except ImportError:
        return False


def _load_raw_image(img_path: Path):
    try:
        import rawpy
    except ImportError:
        raise RuntimeError(
            "RAW image support requires the 'rawpy' package.\n"
            "Install it:\n"
            "  pip install rawpy\n"
            "On Linux you may also need:\n"
            "  sudo apt install -y libraw-dev"
        )
    try:
        from PIL import Image
        with rawpy.imread(str(img_path)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
        return Image.fromarray(rgb)
    except Exception as e:
        raise RuntimeError(f"Could not decode RAW file '{img_path.name}': {e}")


def _load_any_image(img_path: Path):
    from PIL import Image

    ext = img_path.suffix.lower()
    _register_heif_support()

    if ext in RAW_EXTS:
        img = _load_raw_image(img_path)
    else:
        try:
            img = Image.open(str(img_path))
            try:
                img.seek(0)
            except Exception:
                pass
            img.load()
        except Exception as e:
            if ext in (".heic", ".heif", ".avif"):
                raise RuntimeError(
                    f"Could not open '{img_path.name}' ({ext}).\n"
                    "For HEIF/HEIC support, install:\n"
                    "  pip install pillow-heif\n"
                    "On Linux you may also need:\n"
                    "  sudo apt install -y libheif-dev\n"
                    f"Underlying error: {e}"
                )
            raise RuntimeError(f"Could not open image '{img_path.name}': {e}")

    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    return img


def _load_image_for_imaging(img_path: Path):
    from PIL import Image

    ext = img_path.suffix.lower()
    _register_heif_support()

    if ext in RAW_EXTS:
        img = _load_raw_image(img_path)
    else:
        try:
            img = Image.open(str(img_path))
            try:
                img.seek(0)
            except Exception:
                pass
            img.load()
        except Exception as e:
            if ext in (".heic", ".heif", ".avif"):
                raise RuntimeError(
                    f"Could not open '{img_path.name}' ({ext}).\n"
                    "For HEIF/HEIC support, install:\n"
                    "  pip install pillow-heif\n"
                    f"Underlying error: {e}"
                )
            raise RuntimeError(f"Could not open image '{img_path.name}': {e}")

    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode == "LA":
        img = img.convert("RGBA")
    elif img.mode == "1":
        img = img.convert("L")

    return img


def _save_image_as(img, target_ext: str, out_path: Path):
    from PIL import Image

    ext = target_ext.lower().lstrip(".")
    path_str = str(out_path)

    if ext in ("jpg", "jpeg", "jpe", "jfif", "jif"):
        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(path_str, format="JPEG", quality=92, optimize=True)
        return

    if ext == "png":
        if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            img = img.convert("RGBA")
        img.save(path_str, format="PNG", optimize=True)
        return

    if ext == "webp":
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
        img.save(path_str, format="WEBP", quality=92, method=6)
        return

    if ext == "gif":
        if img.mode != "P":
            img_p = img.convert("P", palette=Image.ADAPTIVE, colors=256)
        else:
            img_p = img
        img_p.save(path_str, format="GIF", optimize=True)
        return

    if ext in ("tif", "tiff"):
        img.save(path_str, format="TIFF", compression="tiff_lzw")
        return

    if ext == "bmp":
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(path_str, format="BMP")
        return

    if ext in ("heic", "heif"):
        if not _register_heif_support():
            raise RuntimeError(
                "HEIC output requires 'pillow-heif'.\n"
                "Install it:\n"
                "  pip install pillow-heif"
            )
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.save(path_str, format="HEIF", quality=90)
        return

    if ext == "ico":
        thumb = img.copy()
        thumb.thumbnail((256, 256))
        if thumb.mode not in ("RGB", "RGBA"):
            thumb = thumb.convert("RGBA")
        thumb.save(path_str, format="ICO", sizes=[(256, 256)])
        return

    raise ValueError(
        f"Unsupported image output format: .{ext}\n"
        f"Supported image outputs: jpg, jpeg, jfif, png, webp, gif, "
        f"tiff, tif, bmp, heic, heif, ico"
    )


def _image_to_pdf(img_path: Path, out_path: Path, resolution: float = 150.0):
    img = _load_any_image(img_path)
    img.save(str(out_path), "PDF", resolution=resolution)


# ============================================================
# OCR helpers
# ============================================================
def _ocr_image_to_searchable_pdf(img_path: Path, out_path: Path, lang: str = "eng"):
    _require_tesseract()
    import pytesseract
    img = _load_any_image(img_path)
    try:
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension="pdf", lang=lang)
    except pytesseract.TesseractError as e:
        raise RuntimeError(f"Tesseract failed: {e}")
    Path(out_path).write_bytes(pdf_bytes)


def _ocr_image_to_text(img_path: Path, out_path: Path, lang: str = "eng"):
    _require_tesseract()
    import pytesseract
    img = _load_any_image(img_path)
    try:
        text = pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractError as e:
        raise RuntimeError(f"Tesseract failed: {e}")
    Path(out_path).write_text(text, encoding="utf-8")


def _ocr_pdf_to_searchable_pdf(pdf_path: Path, out_path: Path, lang: str = "eng"):
    _require_tesseract()
    import pytesseract
    from PIL import Image
    fitz = _fitz()

    doc = fitz.open(str(pdf_path))
    out_doc = fitz.open()
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    img, extension="pdf", lang=lang
                )
            except pytesseract.TesseractError as e:
                raise RuntimeError(f"Tesseract failed: {e}")
            out_doc.insert_pdf(fitz.open("pdf", pdf_bytes))
        out_doc.save(str(out_path))
    finally:
        try:
            out_doc.close()
        except Exception:
            pass
        try:
            doc.close()
        except Exception:
            pass


def _ocr_pdf_to_text(pdf_path: Path, out_path: Path, lang: str = "eng"):
    _require_tesseract()
    import pytesseract
    from PIL import Image
    fitz = _fitz()

    doc = fitz.open(str(pdf_path))
    pages_text = []
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                pages_text.append(pytesseract.image_to_string(img, lang=lang))
            except pytesseract.TesseractError as e:
                raise RuntimeError(f"Tesseract failed: {e}")
    finally:
        try:
            doc.close()
        except Exception:
            pass

    Path(out_path).write_text("\n\n".join(pages_text), encoding="utf-8")


# ============================================================
# PDF table extraction (text only — used by CSV / TSV)
# ============================================================
def _pdf_extract_tables(pdf_path: Path):
    fitz = _fitz()
    doc = fitz.open(str(pdf_path))

    headers = None
    all_rows = []

    for page in doc:
        try:
            finder = page.find_tables()
        except Exception:
            finder = None
        if finder is None:
            continue
        try:
            for tbl in finder.tables:
                data = tbl.extract()
                if not data:
                    continue
                if headers is None:
                    headers = [str(c) if c is not None else "" for c in data[0]]
                    for r in data[1:]:
                        all_rows.append([str(c) if c is not None else "" for c in r])
                else:
                    for r in data:
                        all_rows.append([str(c) if c is not None else "" for c in r])
        except Exception:
            continue

    if headers is None:
        headers = ["Text"]
        for page in doc:
            for line in page.get_text().splitlines():
                stripped = line.rstrip()
                if stripped:
                    all_rows.append([stripped])

    doc.close()
    return headers, all_rows


def _pdf_to_tabular(pdf_path: Path, out_path: Path, delimiter: str = ","):
    headers, rows = _pdf_extract_tables(pdf_path)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)


# ============================================================
# Cell value coercion
# ============================================================
def _coerce_cell_value(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v

    s = str(v).strip()
    if not s:
        return ""

    if any(ch in s for ch in (",", "$", "€", "£", "%", "(", ")")):
        return s

    if len(s) > 1 and s[0] == "0" and s[1].isdigit() and "." not in s:
        return s

    if s.lstrip("-").isdigit():
        try:
            return int(s)
        except Exception:
            return s

    try:
        f = float(s)
        if f != f or f in (float("inf"), float("-inf")):
            return s
        return f
    except Exception:
        return s


# ============================================================
# CSV → XLSX (used as a fallback)
# ============================================================
def _csv_to_xlsx(csv_path: Path, out_path: Path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r_idx, row in enumerate(reader, 1):
            for c_idx, val in enumerate(row, 1):
                ws.cell(row=r_idx, column=c_idx, value=_coerce_cell_value(val))

    wb.save(str(out_path))


# ============================================================
# PDF → XLSX with color preservation
# ============================================================
def _sample_cell_background(pix, page_rect, bbox, scale, offset=4):
    """Sample a cell's background color from the rendered page image.

    Samples the four corners a few pixels inward — this avoids both the
    border line at the edge and the text in the middle of the cell.
    Returns an uppercase RRGGBB hex string, or None if the color is white.
    """
    try:
        x0, y0, x1, y1 = bbox
    except Exception:
        return None

    # Convert PDF points → pixel coordinates
    px0 = int((x0 - page_rect.x0) * scale)
    py0 = int((y0 - page_rect.y0) * scale)
    px1 = int((x1 - page_rect.x0) * scale)
    py1 = int((y1 - page_rect.y0) * scale)

    # Guard against tiny cells
    if px1 - px0 < 2 * offset + 1 or py1 - py0 < 2 * offset + 1:
        offset = max(1, offset // 2)

    corners = [
        (px0 + offset, py0 + offset),
        (px1 - offset, py0 + offset),
        (px0 + offset, py1 - offset),
        (px1 - offset, py1 - offset),
    ]

    samples = []
    for x, y in corners:
        if 0 <= x < pix.width and 0 <= y < pix.height:
            try:
                rgb = pix.pixel(x, y)
                samples.append(tuple(rgb[:3]))
            except Exception:
                continue

    if not samples:
        return None

    rgb, _ = Counter(samples).most_common(1)[0]

    # Skip white / near-white (default background — no need to style)
    if all(c >= 250 for c in rgb):
        return None

    return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _find_text_color(page, cell_bbox):
    """Find the dominant non-black, non-white text color in a cell."""
    try:
        fitz = _fitz()
        clip = fitz.Rect(cell_bbox)
        text_dict = page.get_text("dict", clip=clip)
    except Exception:
        return None

    colors = []
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                color_int = span.get("color", 0)
                if not isinstance(color_int, int):
                    continue
                r = (color_int >> 16) & 0xFF
                g = (color_int >> 8) & 0xFF
                b = color_int & 0xFF
                # Skip black (default)
                if r < 30 and g < 30 and b < 30:
                    continue
                # Skip white (probably not visible text)
                if r > 240 and g > 240 and b > 240:
                    continue
                colors.append(f"{r:02X}{g:02X}{b:02X}")

    if not colors:
        return None
    return Counter(colors).most_common(1)[0][0]


def _get_cell_bboxes(table):
    """Return a 2D list of cell bboxes for a PyMuPDF Table object."""
    # Modern API: table.rows[i].cells[j]
    try:
        result = []
        for row in table.rows:
            row_boxes = []
            for cell in row.cells:
                if hasattr(cell, "bbox"):
                    row_boxes.append(cell.bbox)
                else:
                    row_boxes.append(cell)
            result.append(row_boxes)
        if result and any(any(r) for r in result):
            return result
    except Exception:
        pass

    # Older API: flat .cells + row_count / col_count
    try:
        flat = list(table.cells)
        rows = getattr(table, "row_count", None)
        cols = getattr(table, "col_count", None)
        if rows and cols:
            result = []
            idx = 0
            for _ in range(rows):
                row_boxes = []
                for _ in range(cols):
                    row_boxes.append(flat[idx] if idx < len(flat) else None)
                    idx += 1
                result.append(row_boxes)
            return result
    except Exception:
        pass

    return []


def _pdf_to_xlsx_with_colors(pdf_path: Path, out_path: Path) -> bool:
    """PDF → XLSX with cell colors preserved.

    Returns True if at least one table was found and written.
    """
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font

    fitz = _fitz()
    doc = fitz.open(str(pdf_path))
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    current_row = 1
    table_found = False
    first_table = True

    for page in doc:
        try:
            finder = page.find_tables()
        except Exception:
            finder = None
        if finder is None:
            continue

        # Render the page once for pixel sampling
        try:
            pix = page.get_pixmap(dpi=150)
            page_rect = page.rect
            scale = pix.width / page_rect.width if page_rect.width else 1.0
        except Exception:
            pix = None
            page_rect = None
            scale = 1.0

        for tbl in finder.tables:
            try:
                data = tbl.extract()
            except Exception:
                continue
            if not data:
                continue

            table_found = True
            cell_bboxes = _get_cell_bboxes(tbl)

            if not first_table:
                current_row += 1  # blank separator row between tables

            for r_idx, row_data in enumerate(data):
                for c_idx, val in enumerate(row_data):
                    cell = ws.cell(row=current_row + r_idx, column=c_idx + 1)
                    cell.value = _coerce_cell_value(val)

                    bg_color = None
                    text_color = None

                    if (cell_bboxes
                            and r_idx < len(cell_bboxes)
                            and c_idx < len(cell_bboxes[r_idx])):
                        bbox = cell_bboxes[r_idx][c_idx]
                        if bbox is not None and pix is not None and page_rect is not None:
                            try:
                                bg_color = _sample_cell_background(
                                    pix, page_rect, bbox, scale
                                )
                            except Exception:
                                bg_color = None
                            try:
                                text_color = _find_text_color(page, bbox)
                            except Exception:
                                text_color = None

                    if bg_color:
                        cell.fill = PatternFill(
                            start_color=bg_color,
                            end_color=bg_color,
                            fill_type="solid",
                        )

                    is_header = (r_idx == 0)
                    if is_header or text_color:
                        cell.font = Font(bold=is_header, color=text_color)

            current_row += len(data)
            first_table = False

    doc.close()

    if not table_found:
        return False

    wb.save(str(out_path))
    return True


def _pdf_to_xlsx(pdf_path: Path, out_path: Path):
    """PDF → XLSX.

    Tries color-preserving table extraction first. If no tables are
    detected (or color extraction fails), falls back to the previous
    CSV → XLSX workflow.
    """
    try:
        if _pdf_to_xlsx_with_colors(pdf_path, out_path):
            return
    except Exception:
        pass

    # Fallback: CSV → XLSX
    with tempfile.TemporaryDirectory() as td:
        tmp_csv = Path(td) / "temp.csv"
        _pdf_to_tabular(pdf_path, tmp_csv, delimiter=",")
        _csv_to_xlsx(tmp_csv, out_path)


# ============================================================
# Validation
# ============================================================
def _is_docx_readable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 100:
        return False
    try:
        from docx import Document
        d = Document(str(path))
        _ = len(d.paragraphs)
        _ = len(d.tables)
        return True
    except Exception:
        return False


# ============================================================
# PDF → DOCX — validation-first pipeline
# ============================================================
def _iter_all_paragraphs(doc):
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn

    seen = set()

    def _yield(p):
        pid = id(p._element)
        if pid in seen:
            return None
        seen.add(pid)
        return p

    for p in doc.paragraphs:
        r = _yield(p)
        if r is not None:
            yield r

    def walk_tables(container):
        for table in container.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        r = _yield(p)
                        if r is not None:
                            yield r
                    yield from walk_tables(cell)

    yield from walk_tables(doc)

    try:
        for txbx in doc.element.body.iter(qn("w:txbxContent")):
            for p_elem in txbx.findall(qn("w:p")):
                r = _yield(Paragraph(p_elem, doc))
                if r is not None:
                    yield r
    except Exception:
        pass


def _strip_all_layout_constraints(docx_path: Path) -> int:
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from copy import deepcopy
    except ImportError:
        return 0

    try:
        doc = Document(str(docx_path))
    except Exception:
        return 0

    body = doc.element.body
    changes = 0

    for frame in list(body.iter(qn("w:framePr"))):
        parent = frame.getparent()
        if parent is not None:
            parent.remove(frame)
            changes += 1

    for ind in list(body.iter(qn("w:ind"))):
        parent = ind.getparent()
        if parent is not None:
            parent.remove(ind)
            changes += 1

    for tbl in list(body.iter(qn("w:tbl"))):
        rows = tbl.findall(qn("w:tr"))
        is_layout = False
        if len(rows) == 1:
            cells = rows[0].findall(qn("w:tc"))
            if len(cells) == 1:
                is_layout = True

        if not is_layout:
            continue

        for tblw in tbl.findall(qn("w:tblW")):
            tblw.set(qn("w:type"), "auto")
            tblw.set(qn("w:w"), "0")
            changes += 1

    for _ in range(6):
        found_any = False

        for txbx in list(body.iter(qn("w:txbxContent"))):
            outer_p = None
            anc = txbx
            while anc is not None:
                if anc.tag == qn("w:p"):
                    outer_p = anc
                    break
                anc = anc.getparent()
            if outer_p is None:
                continue

            inner_paras = list(txbx.findall(qn("w:p")))
            if not inner_paras:
                continue

            unsafe = False
            for p in inner_paras:
                for el in p.iter():
                    if (el.get(qn("r:id")) is not None or
                            el.tag in (qn("w:hyperlink"),
                                       qn("w:bookmarkStart"),
                                       qn("w:drawing"),
                                       qn("w:object"))):
                        unsafe = True
                        break
                if unsafe:
                    break
            if unsafe:
                continue

            for ip in inner_paras:
                outer_p.addprevious(deepcopy(ip))

            has_text = any(
                t.text and t.text.strip() for t in outer_p.iter(qn("w:t"))
            )
            if not has_text:
                outer_p.getparent().remove(outer_p)
            else:
                for r in list(outer_p.findall(qn("w:r"))):
                    if (r.find(".//" + qn("w:drawing")) is not None or
                            r.find(".//" + qn("w:pict")) is not None):
                        outer_p.remove(r)

            changes += 1
            found_any = True

        for tbl in list(body.iter(qn("w:tbl"))):
            rows = tbl.findall(qn("w:tr"))
            if len(rows) != 1:
                continue
            cells = rows[0].findall(qn("w:tc"))
            if len(cells) != 1:
                continue
            cell = cells[0]
            if cell.find(qn("w:tbl")) is not None:
                continue

            unsafe = False
            for el in cell.iter():
                if (el.get(qn("r:id")) is not None or
                        el.tag in (qn("w:hyperlink"),
                                   qn("w:bookmarkStart"),
                                   qn("w:drawing"),
                                   qn("w:object"))):
                    unsafe = True
                    break
            if unsafe:
                continue

            moved = 0
            for child in list(cell):
                if child.tag == qn("w:tcPr"):
                    continue
                tbl.addprevious(deepcopy(child))
                moved += 1
            if moved == 0:
                continue

            tbl.getparent().remove(tbl)
            changes += 1
            found_any = True

        if not found_any:
            break

    if changes:
        doc.save(str(docx_path))

    return changes


def _is_wrapped_fragment(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 3 or " " in t:
        return False
    return t.isalnum()


def _postprocess_docx_merge_wrapped_words(docx_path: Path) -> int:
    try:
        from docx import Document
    except ImportError:
        return 0

    try:
        doc = Document(str(docx_path))
    except Exception:
        return 0

    all_paras = list(_iter_all_paragraphs(doc))
    non_empty = [p for p in all_paras if p.text and p.text.strip()]
    if len(non_empty) < 2:
        return 0

    merges = 0
    i = 0
    while i < len(non_empty) - 1:
        p = non_empty[i]
        q = non_empty[i + 1]

        if p._element is None or p._element.getparent() is None:
            i += 1
            continue
        if q._element is None or q._element.getparent() is None:
            i += 1
            continue

        tp = (p.text or "").rstrip()
        tq = (q.text or "").strip()

        if not _is_wrapped_fragment(tq):
            i += 1
            continue

        if len(tq) > 1 and tp and tp[-1] in ".,;:!?)]}\u2014\u2013-":
            i += 1
            continue

        try:
            if p.runs:
                p.runs[-1].text = p.runs[-1].text.rstrip() + tq
            else:
                p.add_run(tq)
            q._element.getparent().remove(q._element)
            merges += 1
        except Exception:
            i += 1

    if merges:
        try:
            doc.save(str(docx_path))
        except Exception:
            pass

    return merges


def _try_pdf2docx_plain(pdf_path: Path, out_path: Path) -> bool:
    try:
        from pdf2docx import Converter
        cv = Converter(str(pdf_path))
        try:
            cv.convert(str(out_path))
        finally:
            cv.close()
        return _is_docx_readable(out_path)
    except Exception:
        return False


def _try_pdf2docx_with_cleanup(pdf_path: Path, out_path: Path) -> bool:
    if not _try_pdf2docx_plain(pdf_path, out_path):
        return False

    tmp_clean = out_path.with_name(out_path.stem + "_cleanup_tmp.docx")
    try:
        shutil.copy2(out_path, tmp_clean)

        try:
            _strip_all_layout_constraints(tmp_clean)
        except Exception:
            pass

        try:
            _postprocess_docx_merge_wrapped_words(tmp_clean)
        except Exception:
            pass

        if _is_docx_readable(tmp_clean):
            # Cross-device safe move: shutil.move falls back to copy+delete
            # when os.rename fails with EXDEV (Docker bind mounts).
            shutil.move(str(tmp_clean), str(out_path))
            return True
        return True
    finally:
        try:
            tmp_clean.unlink()
        except Exception:
            pass


def _try_libreoffice_pdf_to_docx(pdf_path: Path, out_path: Path) -> bool:
    try:
        from core import libreoffice
        if not libreoffice.is_available():
            return False

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            converted = libreoffice.convert(pdf_path, "docx", tdp)
            shutil.move(str(converted), str(out_path))

        return _is_docx_readable(out_path)
    except Exception:
        return False


def _plain_text_docx(pdf_path: Path, out_path: Path) -> bool:
    try:
        from docx import Document
        fitz = _fitz()
        doc = fitz.open(str(pdf_path))
        out = Document()
        out.add_heading(pdf_path.stem, level=0)

        for pno, page in enumerate(doc, 1):
            out.add_heading(f"Page {pno}", level=2)
            for line in page.get_text().splitlines():
                if line.strip():
                    out.add_paragraph(line.rstrip())

        doc.close()
        out.save(str(out_path))
        return _is_docx_readable(out_path)
    except Exception:
        return False


def _pdf_to_docx(pdf_path: Path, out_path: Path):
    page_count = _pdf_page_count(pdf_path)
    force_lo = os.environ.get("PDF_FORCE_LIBREOFFICE") == "1"

    if not force_lo and 0 < page_count <= SMALL_PDF_PAGE_LIMIT:
        if _try_pdf2docx_with_cleanup(pdf_path, out_path):
            if _is_docx_readable(out_path):
                return

    if _try_libreoffice_pdf_to_docx(pdf_path, out_path):
        if _is_docx_readable(out_path):
            return

    if _try_pdf2docx_plain(pdf_path, out_path):
        if _is_docx_readable(out_path):
            return

    if _plain_text_docx(pdf_path, out_path):
        return

    raise RuntimeError(
        "All PDF → DOCX strategies failed. "
        "Try installing LibreOffice, or install a newer pdf2docx:\n"
        "  pip install --upgrade pdf2docx"
    )


# ============================================================
# PDF → PPTX helper
# ============================================================
def _pdf_to_pptx(pdf_path: Path, out_path: Path):
    from pptx import Presentation
    from pptx.util import Inches

    fitz = _fitz()
    doc = fitz.open(str(pdf_path))
    if len(doc) == 0:
        doc.close()
        raise ValueError("The PDF has no pages.")

    prs = Presentation()
    r = doc[0].rect
    aspect = (r.height / r.width) if r.width else 1.414
    width_in = 10.0
    height_in = width_in * aspect
    prs.slide_width  = Inches(width_in)
    prs.slide_height = Inches(height_in)

    blank_layout = prs.slide_layouts[6]

    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        slide = prs.slides.add_slide(blank_layout)
        slide.shapes.add_picture(
            io.BytesIO(img_bytes),
            0, 0,
            width=prs.slide_width,
            height=prs.slide_height,
        )

    doc.close()
    prs.save(str(out_path))


# ============================================================
# Organize
# ============================================================
def handle_merge(files, options, work):
    from pypdf import PdfWriter
    if len(files) < 2:
        raise ValueError("Merge needs at least 2 PDF files.")
    w = PdfWriter()
    for f in files:
        if not _is_pdf(f):
            raise ValueError(f"'{f.name}' is not a PDF.")
        w.append(str(f))
    out = _out("merged", "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_split(files, options, work):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(files[0]))
    total = len(reader.pages)

    points_str = (options.get("split_points") or "").strip()
    pages_str  = (options.get("pages") or "").strip()

    ranges = []
    if points_str:
        points = sorted({int(p) for p in points_str.split(",") if p.strip().isdigit()})
        points = [p for p in points if 0 < p < total]
        prev = 0
        for p in points:
            ranges.append((prev, p - 1))
            prev = p
        ranges.append((prev, total - 1))
    elif pages_str:
        ranges = [(i, i) for i in _parse_pages(pages_str, total)]
    else:
        ranges = [(i, i) for i in range(total)]

    if not ranges:
        raise ValueError("Nothing to split.")

    if len(ranges) == 1:
        a, b = ranges[0]
        w = PdfWriter()
        for i in range(a, b + 1):
            w.add_page(reader.pages[i])
        out = _out(files[0].stem, "pdf")
        with open(out, "wb") as fh:
            w.write(fh)
        return out

    out = _out(files[0].stem, "zip")
    with zipfile.ZipFile(out, "w") as zf:
        for idx, (a, b) in enumerate(ranges, 1):
            w = PdfWriter()
            for i in range(a, b + 1):
                w.add_page(reader.pages[i])
            name = f"part_{idx:02d}_pages_{a+1}-{b+1}.pdf"
            tmp = work / name
            with open(tmp, "wb") as fh:
                w.write(fh)
            zf.write(tmp, name)
            tmp.unlink(missing_ok=True)
    return out


def handle_extract_pages(files, options, work):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(files[0]))
    idx = _parse_pages(options.get("pages", ""), len(reader.pages))
    if not idx:
        raise ValueError("No valid pages specified.")
    w = PdfWriter()
    for i in idx:
        w.add_page(reader.pages[i])
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_remove_pages(files, options, work):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(files[0]))
    remove = set(_parse_pages(options.get("pages", ""), len(reader.pages)))
    if not remove:
        raise ValueError("No valid pages specified to remove.")
    w = PdfWriter()
    for i, p in enumerate(reader.pages):
        if i not in remove:
            w.add_page(p)
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_rearrange(files, options, work):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(files[0]))
    total = len(reader.pages)
    order = [int(x.strip()) - 1 for x in options.get("order", "").split(",") if x.strip()]
    order = [i for i in order if 0 <= i < total]
    if not order:
        raise ValueError("Provide a valid new order like '3,1,2'.")
    w = PdfWriter()
    for i in order:
        w.add_page(reader.pages[i])
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


# ============================================================
# Optimize
# ============================================================
def handle_compress(files, options, work):
    fitz = _fitz()
    doc = fitz.open(files[0])
    out = _out(files[0].stem, "pdf")
    doc.save(out, garbage=4, deflate=True, clean=True)
    doc.close()
    return out


# ============================================================
# Convert to PDF
# ============================================================
def handle_images_to_pdf(files, options, work):
    if not files:
        raise ValueError("Upload at least one image.")

    pages = []
    for f in files:
        if not _is_image(f):
            raise ValueError(f"'{f.name}' is not a supported image.")
        pages.append(_load_any_image(f))

    stem = files[0].stem if files else "images"
    out = _out(stem, "pdf")

    if len(pages) == 1:
        pages[0].save(str(out), "PDF", resolution=150.0)
    else:
        pages[0].save(
            str(out),
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=pages[1:],
        )
    return out


def _html_to_pdf_weasy(url_or_html, out_path):
    from weasyprint import HTML
    if url_or_html.startswith(("http://", "https://")):
        HTML(url_or_html).write_pdf(str(out_path))
    else:
        HTML(string=url_or_html).write_pdf(str(out_path))


def _html_to_pdf_xhtml(url_or_html, out_path):
    from xhtml2pdf import pisa
    import urllib.request

    if url_or_html.startswith(("http://", "https://")):
        req = urllib.request.Request(
            url_or_html,
            headers={"User-Agent": "Mozilla/5.0 (PyPDF Studio)"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
    else:
        html = url_or_html

    with open(out_path, "wb") as fh:
        pisa.CreatePDF(html, dest=fh, encoding="utf-8")


def handle_webpage_to_pdf(files, options, work):
    url = (options.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Enter a valid URL starting with http:// or https://")

    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace(".", "_") or "webpage"
    except Exception:
        domain = "webpage"

    out = _out(domain, "pdf")
    try:
        _html_to_pdf_weasy(url, out)
        return out
    except Exception as e1:
        try:
            _html_to_pdf_xhtml(url, out)
            return out
        except Exception as e2:
            raise RuntimeError(
                f"Both PDF engines failed.\n"
                f"WeasyPrint: {e1}\n"
                f"xhtml2pdf: {e2}"
            )


# ============================================================
# Convert from PDF
# ============================================================
def handle_pdf_to_images(files, options, work):
    fitz = _fitz()
    fmt = (options.get("format") or "png").lower()
    ext = "jpg" if fmt == "jpg" else "png"

    doc = fitz.open(files[0])
    page_count = len(doc)

    if page_count == 1:
        pix = doc[0].get_pixmap(dpi=150)
        out = _out(files[0].stem, ext)
        pix.save(str(out))
        doc.close()
        return out

    out = _out(files[0].stem, "zip")
    with zipfile.ZipFile(out, "w") as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            tmp = work / f"page_{i+1}.{ext}"
            pix.save(tmp)
            zf.write(tmp, f"page_{i+1}.{ext}")
            tmp.unlink(missing_ok=True)
    doc.close()
    return out


def handle_extract_images(files, options, work):
    fitz = _fitz()
    doc = fitz.open(files[0])

    collected = []
    for pno in range(len(doc)):
        for idx, img in enumerate(doc.get_page_images(pno, full=True)):
            try:
                base = doc.extract_image(img[0])
                name = f"p{pno+1}_img{idx+1}.{base['ext']}"
                collected.append((name, base["image"]))
            except Exception:
                continue
    doc.close()

    if not collected:
        raise ValueError("No embedded images found in this PDF.")

    if len(collected) == 1:
        name, data = collected[0]
        emb_ext = Path(name).suffix.lstrip(".") or "png"
        out = _out(files[0].stem, emb_ext)
        out.write_bytes(data)
        return out

    out = _out(files[0].stem, "zip")
    with zipfile.ZipFile(out, "w") as zf:
        for name, data in collected:
            zf.writestr(name, data)
    return out


def handle_pdf_to_text(files, options, work):
    fitz = _fitz()
    doc = fitz.open(files[0])
    text = "\n\n".join(p.get_text() for p in doc)
    doc.close()
    out = _out(files[0].stem, "txt")
    out.write_text(text, encoding="utf-8")
    return out


def handle_pdf_to_word(files, options, work):
    out = _out(files[0].stem, "docx")
    _pdf_to_docx(files[0], out)
    return out


# ============================================================
# Edit
# ============================================================
def handle_rotate(files, options, work):
    fitz = _fitz()
    doc = fitz.open(files[0])

    rotations_str = (options.get("rotations") or "").strip()
    if rotations_str:
        for part in rotations_str.split(","):
            if ":" not in part:
                continue
            pnum, deg = part.split(":", 1)
            try:
                idx = int(pnum.strip()) - 1
                d   = int(deg.strip())
            except ValueError:
                continue
            if 0 <= idx < len(doc):
                page = doc[idx]
                page.set_rotation((page.rotation + d) % 360)
    else:
        angle = int(_safe_float(options.get("angle"), 90))
        if angle not in (90, 180, 270):
            raise ValueError("Angle must be 90, 180, or 270.")
        spec = options.get("pages") or "all"
        for i in _parse_pages(spec, len(doc)):
            page = doc[i]
            page.set_rotation((page.rotation + angle) % 360)

    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


def handle_crop(files, options, work):
    fitz = _fitz()
    L = _safe_float(options.get("left"), 0)
    R = _safe_float(options.get("right"), 0)
    T = _safe_float(options.get("top"), 0)
    B = _safe_float(options.get("bottom"), 0)
    if L < 0 or R < 0 or T < 0 or B < 0:
        raise ValueError("Margins must be zero or positive.")
    doc = fitz.open(files[0])
    for page in doc:
        r = page.rect
        new_rect = fitz.Rect(r.x0 + L, r.y0 + T, r.x1 - R, r.y1 - B)
        if new_rect.is_empty or new_rect.width <= 0 or new_rect.height <= 0:
            doc.close()
            raise ValueError("Crop margins are too large for this page size.")
        page.set_cropbox(new_rect)
    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


def handle_overlay(files, options, work):
    from pypdf import PdfReader, PdfWriter
    if len(files) < 2:
        raise ValueError("Overlay needs 2 PDFs (background first, overlay second).")
    if not _is_pdf(files[0]) or not _is_pdf(files[1]):
        raise ValueError("Both files must be PDFs.")
    br, fr = PdfReader(str(files[0])), PdfReader(str(files[1]))
    w = PdfWriter()
    n = max(len(br.pages), len(fr.pages))
    for i in range(n):
        base = br.pages[i % len(br.pages)]
        top = fr.pages[i % len(fr.pages)]
        base.merge_page(top)
        w.add_page(base)
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_page_numbers(files, options, work):
    fitz = _fitz()
    pos = options.get("position") or "bottom-center"
    doc = fitz.open(files[0])
    for i, page in enumerate(doc, start=1):
        r = page.rect
        if pos == "top-right":
            pt = fitz.Point(r.x1 - 60, 30)
        elif pos == "bottom-right":
            pt = fitz.Point(r.x1 - 60, r.y1 - 20)
        else:
            pt = fitz.Point(r.x0 + r.width / 2 - 10, r.y1 - 20)
        page.insert_text(pt, str(i), fontsize=10)
    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


# ============================================================
# Security
# ============================================================
def handle_sign(files, options, work):
    fitz = _fitz()
    if len(files) < 2:
        raise ValueError("Upload 2 files: the PDF first, then the signature image.")
    if not _is_pdf(files[0]):
        raise ValueError("The first file must be a PDF.")
    if not _is_image(files[1]):
        raise ValueError("The second file must be a signature image.")

    fx = max(0.0, min(1.0, _safe_float(options.get("signature_x"), 0.60)))
    fy = max(0.0, min(1.0, _safe_float(options.get("signature_y"), 0.75)))
    fw = max(0.05, min(1.0, _safe_float(options.get("signature_w"), 0.22)))

    doc = fitz.open(files[0])
    total = len(doc)

    spec = (options.get("signature_pages") or "last").strip().lower()
    if spec == "all":
        target_pages = list(range(total))
    elif spec == "last" or spec == "":
        target_pages = [total - 1]
    else:
        target_pages = _parse_pages(spec, total)

    if not target_pages:
        doc.close()
        raise ValueError("No valid pages selected for signing.")

    sig_img = _load_any_image(files[1])
    aspect = (sig_img.height / sig_img.width) if sig_img.width else 0.35

    tmp_sig = work / "_signature_normalised.png"
    sig_img.save(str(tmp_sig), "PNG")

    for pno in target_pages:
        page = doc[pno]
        r = page.rect
        w = r.width * fw
        h = w * aspect
        x0 = r.x0 + r.width * fx
        y0 = r.y0 + r.height * fy
        rect = fitz.Rect(x0, y0, x0 + w, y0 + h)
        rect = rect & r
        if rect.is_empty or rect.width <= 0 or rect.height <= 0:
            continue
        page.insert_image(rect, filename=str(tmp_sig))

    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


def handle_unlock(files, options, work):
    from pypdf import PdfReader, PdfWriter
    pw = options.get("password") or ""
    reader = PdfReader(str(files[0]))
    if reader.is_encrypted:
        result = reader.decrypt(pw)
        if not result:
            raise ValueError("Incorrect password.")
    w = PdfWriter()
    for p in reader.pages:
        w.add_page(p)
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_protect(files, options, work):
    from pypdf import PdfReader, PdfWriter
    pw = (options.get("password") or "").strip()
    if not pw:
        raise ValueError("Password is required.")
    reader = PdfReader(str(files[0]))
    w = PdfWriter()
    for p in reader.pages:
        w.add_page(p)
    w.encrypt(user_password=pw, owner_password=pw)
    out = _out(files[0].stem, "pdf")
    with open(out, "wb") as fh:
        w.write(fh)
    return out


def handle_flatten(files, options, work):
    fitz = _fitz()
    doc = fitz.open(files[0])
    for page in doc:
        annots = list(page.annots()) if page.annots() else []
        for a in annots:
            page.add_redact_annot(a.rect)
        page.apply_redactions()
    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


# ============================================================
# Watermark
# ============================================================
def handle_watermark_text(files, options, work):
    fitz = _fitz()
    text = (options.get("text") or "CONFIDENTIAL").strip()
    if not text:
        raise ValueError("Watermark text cannot be empty.")

    rotation = _safe_float(options.get("rotation"), 45.0)
    opacity  = max(0.02, min(0.5, _safe_float(options.get("opacity"), 0.15)))

    doc = fitz.open(files[0])
    for page in doc:
        r = page.rect
        fontsize = min(r.width, r.height) * 0.15
        font = fitz.Font("helv")
        text_width = font.text_length(text, fontsize=fontsize)

        tw = fitz.TextWriter(page.rect)
        x0 = r.width / 2 - text_width / 2
        y0 = r.height / 2 + fontsize / 3
        tw.append(fitz.Point(x0, y0), text, font=font, fontsize=fontsize)

        pivot = fitz.Point(r.width / 2, r.height / 2)
        mat = fitz.Matrix(1, 1).prerotate(rotation)
        tw.write_text(
            page,
            color=(0.5, 0.5, 0.5),
            opacity=opacity,
            overlay=False,
            morph=(pivot, mat),
        )

    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


def handle_watermark_image(files, options, work):
    fitz = _fitz()
    if len(files) < 2:
        raise ValueError("Upload 2 files: the PDF first, then the watermark image.")
    if not _is_pdf(files[0]):
        raise ValueError("The first file must be a PDF.")
    if not _is_image(files[1]):
        raise ValueError("The second file must be an image.")

    rotation = _safe_float(options.get("rotation"), 45.0)
    opacity  = max(0.02, min(0.5, _safe_float(options.get("opacity"), 0.15)))
    scale    = max(0.1,  min(1.0, _safe_float(options.get("scale"), 0.5)))

    from PIL import Image
    pil = _load_any_image(files[1]).convert("RGBA")
    if abs(rotation) > 0.01:
        rotated = pil.rotate(rotation, expand=True, resample=Image.BICUBIC,
                             fillcolor=(0, 0, 0, 0))
    else:
        rotated = pil
    tmp_png = work / "_wm_rotated.png"
    rotated.save(tmp_png)
    aspect = rotated.height / rotated.width if rotated.width else 1.0

    doc = fitz.open(files[0])
    for page in doc:
        r = page.rect
        w = r.width * scale
        h = w * aspect
        if h > r.height * scale:
            h = r.height * scale
            w = h / aspect
        x0 = r.x0 + (r.width - w) / 2
        y0 = r.y0 + (r.height - h) / 2
        rect = fitz.Rect(x0, y0, x0 + w, y0 + h)
        page.insert_image(
            rect,
            filename=str(tmp_png),
            overlay=False,
            alpha=opacity,
        )

    out = _out(files[0].stem, "pdf")
    doc.save(out)
    doc.close()
    return out


# ============================================================
# OCR (dedicated tool)
# ============================================================
def handle_ocr(files, options, work):
    lang = options.get("lang") or "eng"
    out = _out(files[0].stem, "pdf")
    _ocr_pdf_to_searchable_pdf(files[0], out, lang=lang)
    return out


# ============================================================
# Compare
# ============================================================
def handle_compare(files, options, work):
    fitz = _fitz()
    if len(files) < 2:
        raise ValueError("Compare needs 2 PDFs.")
    if not _is_pdf(files[0]) or not _is_pdf(files[1]):
        raise ValueError("Both files must be PDFs.")
    da, db = fitz.open(files[0]), fitz.open(files[1])
    lines = [f"A: {files[0].name}", f"B: {files[1].name}", "",
             f"Pages: A={len(da)}  B={len(db)}"]
    n = max(len(da), len(db))
    diffs = 0
    for i in range(n):
        ta = da[i].get_text() if i < len(da) else ""
        tb = db[i].get_text() if i < len(db) else ""
        if ta != tb:
            diffs += 1
            lines.append(f"\n--- Page {i+1} differs ---")
            sa, sb = set(ta.split()), set(tb.split())
            oa, ob = sorted(sa - sb)[:50], sorted(sb - sa)[:50]
            if oa:
                lines.append("Only in A: " + ", ".join(oa))
            if ob:
                lines.append("Only in B: " + ", ".join(ob))
    lines.append(f"\nTotal pages with differences: {diffs}")
    da.close()
    db.close()
    out = _out(f"compare_{files[0].stem}_vs_{files[1].stem}", "txt")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ============================================================
# Universal converter
# ============================================================
def handle_universal(files, options, work):
    from core.readers import get_reader
    from core.writers import get_writer
    from core import libreoffice

    target = (options.get("format") or "").lower().lstrip(".")
    if not target:
        raise ValueError("Select an output format.")

    src = files[0]
    src_ext = src.suffix.lower()

    OFFICE_EXTS = {
        ".docx", ".doc", ".dot", ".dotx", ".dotm", ".docm",
        ".rtf", ".odt", ".ott", ".fodt", ".pub",
        ".txt", ".html", ".htm", ".xhtml",
        ".xlsx", ".xls", ".xlsm", ".xlt", ".xltx", ".xltm",
        ".ods", ".ots", ".fods", ".csv", ".tsv",
        ".pptx", ".ppt", ".pot", ".potx", ".potm", ".pptm",
        ".odp", ".otp", ".fodp",
    }

    TARGET_EXT = {
        "pdf":  "pdf",
        "docx": "docx", "doc": "doc", "rtf": "rtf",
        "odt":  "odt",  "pub": "pub",
        "html": "html", "htm": "html",
        "txt":  "txt",  "text": "txt",
        "xlsx": "xlsx", "xls": "xls", "ods": "ods",
        "csv":  "csv",  "tsv": "tsv",
        "pptx": "pptx", "ppt": "ppt", "odp": "odp",
    }

    ocr_lang = (options.get("ocr_lang") or "eng").strip() or "eng"

    # Image → Image
    if src_ext in IMAGE_EXTS and target in IMAGE_OUTPUT_EXTS:
        out = _out(src.stem, target)
        img = _load_image_for_imaging(src)
        _save_image_as(img, target, out)
        return out

    # Image → OCR PDF
    if src_ext in IMAGE_EXTS and target in ("ocr", "ocr-pdf"):
        out = _out(src.stem, "pdf")
        _ocr_image_to_searchable_pdf(src, out, lang=ocr_lang)
        return out

    # Image → OCR text
    if src_ext in IMAGE_EXTS and target in ("ocr-txt", "ocr-text"):
        out = _out(src.stem, "txt")
        _ocr_image_to_text(src, out, lang=ocr_lang)
        return out

    # Image → PDF
    if src_ext in IMAGE_EXTS and target == "pdf":
        out = _out(src.stem, "pdf")
        _image_to_pdf(src, out)
        return out

    # XML ↔ JSON
    if src_ext == ".xml" and target == "json":
        out = _out(src.stem, "json")
        _xml_to_json(src, out)
        return out

    if src_ext == ".json" and target == "xml":
        out = _out(src.stem, "xml")
        _json_to_xml(src, out)
        return out

    # Office → Office / PDF
    if src_ext in OFFICE_EXTS and target in TARGET_EXT and src_ext != ".pdf":
        target_ext = TARGET_EXT[target]
        if not libreoffice.is_available():
            raise RuntimeError(
                "LibreOffice is required for Office/ODF conversions.\n"
                "Install it:\n"
                "  Ubuntu/Debian: sudo apt install -y libreoffice\n"
                "  Fedora:        sudo dnf install -y libreoffice\n"
                "  macOS:         brew install --cask libreoffice\n"
                "  Windows:       https://www.libreoffice.org/download/"
            )
        out = _out(src.stem, target_ext)
        converted = libreoffice.convert(src, target_ext, work)
        # Cross-device safe move
        shutil.move(str(converted), str(out))
        return out

    # PDF → various
    if src_ext == ".pdf":
        if target == "pdf":
            out = _out(src.stem, "pdf")
            shutil.copy2(src, out)
            return out

        if target in ("ocr", "ocr-pdf"):
            out = _out(src.stem, "pdf")
            _ocr_pdf_to_searchable_pdf(src, out, lang=ocr_lang)
            return out

        if target in ("ocr-txt", "ocr-text"):
            out = _out(src.stem, "txt")
            _ocr_pdf_to_text(src, out, lang=ocr_lang)
            return out

        if target == "docx":
            out = _out(src.stem, "docx")
            _pdf_to_docx(src, out)
            return out

        if target in ("doc", "rtf", "odt"):
            with tempfile.TemporaryDirectory() as td:
                tdp = Path(td)
                tmp_docx = tdp / "out.docx"
                _pdf_to_docx(src, tmp_docx)
                if not libreoffice.is_available():
                    raise RuntimeError(
                        "LibreOffice is required to produce .doc/.rtf/.odt "
                        "from a PDF. Install it first."
                    )
                out = _out(src.stem, target)
                converted = libreoffice.convert(tmp_docx, target, tdp)
                # Cross-device safe move
                shutil.move(str(converted), str(out))
                return out

        if target in ("pptx", "ppt", "odp"):
            with tempfile.TemporaryDirectory() as td:
                tdp = Path(td)
                tmp_pptx = tdp / "out.pptx"
                _pdf_to_pptx(src, tmp_pptx)
                if target == "pptx":
                    out = _out(src.stem, "pptx")
                    shutil.move(str(tmp_pptx), str(out))
                    return out
                if not libreoffice.is_available():
                    raise RuntimeError(
                        "LibreOffice is required to produce .ppt/.odp "
                        "from a PDF. Install it first."
                    )
                out = _out(src.stem, target)
                converted = libreoffice.convert(tmp_pptx, target, tdp)
                # Cross-device safe move
                shutil.move(str(converted), str(out))
                return out

        if target in ("xlsx", "xls", "ods"):
            with tempfile.TemporaryDirectory() as td:
                tdp = Path(td)
                tmp_xlsx = tdp / "out.xlsx"
                _pdf_to_xlsx(src, tmp_xlsx)
                if target == "xlsx":
                    out = _out(src.stem, "xlsx")
                    shutil.move(str(tmp_xlsx), str(out))
                    return out
                if not libreoffice.is_available():
                    raise RuntimeError(
                        "LibreOffice is required to produce .xls/.ods "
                        "from a PDF. Install it first."
                    )
                out = _out(src.stem, target)
                converted = libreoffice.convert(tmp_xlsx, target, tdp)
                # Cross-device safe move
                shutil.move(str(converted), str(out))
                return out

        if target in ("csv", "tsv"):
            delim = "\t" if target == "tsv" else ","
            out = _out(src.stem, target)
            _pdf_to_tabular(src, out, delimiter=delim)
            return out

    # AST pipeline
    reader = get_reader(src_ext)
    if reader is None:
        raise ValueError(
            f"No reader available for '{src_ext}'.\n"
            f"Supported inputs include images, Office formats, "
            f"XML, JSON, Markdown, HTML, and PDF."
        )

    writer = get_writer(target)
    if writer is None:
        raise ValueError(
            f"No writer available for '{target}'.\n"
            f"Supported outputs include: pdf, docx, xlsx, pptx, "
            f"html, md, txt, xml, json, csv, tsv, odt, ods, odp, rtf, "
            f"jpg, png, webp, gif, tiff, bmp, heic, ico, ocr, ocr-txt, "
            f"dbf, dxf."
        )

    ast = reader(str(src))
    out = _out(src.stem, target)
    writer(ast, str(out))
    return out


HANDLERS = {
    "merge": handle_merge,
    "split": handle_split,
    "extract_pages": handle_extract_pages,
    "remove_pages": handle_remove_pages,
    "rearrange": handle_rearrange,
    "compress": handle_compress,
    "images_to_pdf": handle_images_to_pdf,
    "webpage_to_pdf": handle_webpage_to_pdf,
    "pdf_to_images": handle_pdf_to_images,
    "extract_images": handle_extract_images,
    "pdf_to_text": handle_pdf_to_text,
    "pdf_to_word": handle_pdf_to_word,
    "rotate": handle_rotate,
    "crop": handle_crop,
    "overlay": handle_overlay,
    "page_numbers": handle_page_numbers,
    "protect": handle_protect,
    "unlock": handle_unlock,
    "sign": handle_sign,
    "flatten": handle_flatten,
    "watermark_text": handle_watermark_text,
    "watermark_image": handle_watermark_image,
    "ocr": handle_ocr,
    "compare": handle_compare,
    "universal": handle_universal,
}


# ============================================================
# Tool catalog
# ============================================================
TOOLS = [
    {"id": "merge", "name": "Merge PDF", "desc": "Combine multiple PDFs into one",
     "category": "Organize", "accept": ".pdf", "multiple": True,
     "hint": "Select 2 or more PDF files."},

    {"id": "split", "name": "Split PDF",
     "desc": "Break a PDF into separate pages (ZIP)",
     "category": "Organize", "accept": ".pdf", "multiple": False,
     "preview": "scissors",
     "hint": "Click the ✂ icon between pages to split there. No scissors = split every page.",
     "options": [{"name": "pages", "label": "Pages (optional fallback)",
                  "type": "text", "placeholder": "1-3,5,7"}]},

    {"id": "extract_pages", "name": "Extract Pages",
     "desc": "Pull selected pages into a new PDF",
     "category": "Organize", "accept": ".pdf", "multiple": False,
     "preview": "toggle-extract",
     "hint": "Click pages to include them in the extracted PDF.",
     "options": [{"name": "pages", "label": "Pages (fallback)",
                  "type": "text", "placeholder": "1-3,7"}]},

    {"id": "remove_pages", "name": "Remove Pages",
     "desc": "Delete selected pages",
     "category": "Organize", "accept": ".pdf", "multiple": False,
     "preview": "toggle-remove",
     "hint": "Click pages to mark them for removal.",
     "options": [{"name": "pages", "label": "Pages (fallback)",
                  "type": "text", "placeholder": "2,4-5"}]},

    {"id": "rearrange", "name": "Rearrange Pages",
     "desc": "Reorder pages in a custom sequence",
     "category": "Organize", "accept": ".pdf", "multiple": False,
     "preview": "reorder",
     "hint": "Click a page, then click another to swap them.",
     "options": [{"name": "order", "label": "New order (fallback)",
                  "type": "text", "placeholder": "3,1,2"}]},

    {"id": "compress", "name": "Compress PDF", "desc": "Shrink a PDF's file size",
     "category": "Optimize", "accept": ".pdf", "multiple": False},

    {"id": "images_to_pdf", "name": "Images to PDF",
     "desc": "Combine any image files into a single PDF",
     "category": "Convert to PDF",
     "accept": (
         ".jpg,.jpeg,.jpe,.jfif,.jif,.png,.webp,.gif,.tif,.tiff,.bmp,"
         ".ico,.tga,.pcx,.dds,.ppm,.pgm,.pbm,.pnm,"
         ".heic,.heif,.avif,"
         ".cr2,.cr3,.crw,.nef,.nrw,.arw,.srf,.sr2,.dng,.raf,.orf,"
         ".rw2,.pef,.srw,.x3f,.kdc,.dcr,.mrw,.3fr,.fff,.iiq,.rwl"
     ),
     "multiple": True,
     "hint": "Select 1 or more images (JPEG/JFIF, PNG, WebP, GIF, TIFF, BMP, "
             "ICO, TGA, PCX, DDS, Netpbm, HEIC, or RAW). "
             "Each becomes one PDF page."},

    {"id": "webpage_to_pdf", "name": "Webpage to PDF", "desc": "Save any URL as a PDF",
     "category": "Convert to PDF", "accept": None, "multiple": False, "url_only": True,
     "options": [{"name": "url", "label": "URL", "type": "text", "placeholder": "https://example.com"}]},

    {"id": "pdf_to_images", "name": "PDF to Images",
     "desc": "Each page → PNG or JPG (single file or ZIP)",
     "category": "Convert from PDF", "accept": ".pdf", "multiple": False,
     "options": [{"name": "format", "label": "Image format",
                  "type": "select", "choices": ["png", "jpg"]}]},

    {"id": "extract_images", "name": "Extract Images",
     "desc": "All embedded images (single file or ZIP)",
     "category": "Convert from PDF", "accept": ".pdf", "multiple": False},

    {"id": "pdf_to_text", "name": "PDF to Text", "desc": "Extract text into a .txt file",
     "category": "Convert from PDF", "accept": ".pdf", "multiple": False},

    {"id": "pdf_to_word", "name": "PDF to Word", "desc": "Convert a PDF to editable .docx",
     "category": "Convert from PDF", "accept": ".pdf", "multiple": False},

    {"id": "rotate", "name": "Rotate Pages",
     "desc": "Rotate by 90°, 180° or 270°",
     "category": "Edit", "accept": ".pdf", "multiple": False,
     "preview": "rotate",
     "hint": "Click each page to rotate it 90° clockwise.",
     "options": [
         {"name": "angle", "label": "Angle (fallback)", "type": "select",
          "choices": ["90", "180", "270"]},
         {"name": "pages", "label": "Pages (fallback)", "type": "text",
          "placeholder": "all"},
     ]},

    {"id": "crop", "name": "Crop PDF", "desc": "Trim margins (in points)",
     "category": "Edit", "accept": ".pdf", "multiple": False,
     "options": [
         {"name": "left", "label": "Left", "type": "number", "placeholder": "0"},
         {"name": "right", "label": "Right", "type": "number", "placeholder": "0"},
         {"name": "top", "label": "Top", "type": "number", "placeholder": "0"},
         {"name": "bottom", "label": "Bottom", "type": "number", "placeholder": "0"},
     ]},

    {"id": "overlay", "name": "Overlay PDFs", "desc": "Merge two PDFs on top of each other",
     "category": "Edit", "accept": ".pdf", "multiple": True,
     "hint": "Select 2 PDFs: background first, overlay second."},

    {"id": "page_numbers", "name": "Add Page Numbers", "desc": "Insert page numbers",
     "category": "Edit", "accept": ".pdf", "multiple": False,
     "options": [{"name": "position", "label": "Position", "type": "select",
                  "choices": ["bottom-center", "bottom-right", "top-right"]}]},

    {"id": "protect", "name": "Protect PDF", "desc": "Add password protection",
     "category": "Security", "accept": ".pdf", "multiple": False,
     "options": [{"name": "password", "label": "Password", "type": "password"}]},

    {"id": "unlock", "name": "Unlock PDF", "desc": "Remove password protection",
     "category": "Security", "accept": ".pdf", "multiple": False,
     "options": [{"name": "password", "label": "Password (if required)", "type": "password"}]},

    {"id": "sign", "name": "Sign PDF",
     "desc": "Place a signature image anywhere on the document",
     "category": "Security",
     "accept": ".pdf,.png,.jpg,.jpeg,.jpe,.jfif,.heic,.heif,.webp,.tif,.tiff",
     "multiple": True,
     "preview": "sign",
     "hint": "Upload the PDF first, then the signature image. "
             "Use the arrow pad to move your signature, then click "
             "any page to place it there.",
     "options": [
         {"name": "signature_pages", "label": "Pages (fallback: last | all | 1,3,5)",
          "type": "text", "placeholder": "last"},
     ]},

    {"id": "flatten", "name": "Flatten PDF", "desc": "Bake annotations into the page",
     "category": "Security", "accept": ".pdf", "multiple": False},

    {"id": "watermark_text", "name": "Text Watermark",
     "desc": "Pale, behind-content watermark (like Word)",
     "category": "Watermark", "accept": ".pdf", "multiple": False,
     "preview": "watermark-text",
     "hint": "Type the watermark text and rotate it with the slider.",
     "options": [
         {"name": "text", "label": "Watermark text", "type": "text",
          "placeholder": "CONFIDENTIAL"},
         {"name": "rotation", "label": "Rotation (degrees)", "type": "text",
          "placeholder": "45"},
         {"name": "opacity", "label": "Opacity (0.02–0.5)", "type": "text",
          "placeholder": "0.15"},
     ]},

    {"id": "watermark_image", "name": "Image Watermark",
     "desc": "Pale, behind-content image watermark (logo)",
     "category": "Watermark",
     "accept": ".pdf,.png,.jpg,.jpeg,.jpe,.jfif,.heic,.heif,.webp,.tif,.tiff",
     "multiple": True,
     "preview": "watermark-image",
     "hint": "Upload the PDF first, then the watermark image. "
             "Rotate it with the slider.",
     "options": [
         {"name": "rotation", "label": "Rotation (degrees)", "type": "text",
          "placeholder": "45"},
         {"name": "opacity", "label": "Opacity (0.02–0.5)", "type": "text",
          "placeholder": "0.15"},
         {"name": "scale", "label": "Scale (0.1–1.0)", "type": "text",
          "placeholder": "0.5"},
     ]},

    {"id": "ocr", "name": "PDF OCR", "desc": "Make a scanned PDF searchable",
     "category": "OCR", "accept": ".pdf", "multiple": False,
     "options": [{"name": "lang", "label": "Language", "type": "select",
                  "choices": ["eng", "swa", "fra", "deu", "spa", "ita"]}]},

    {"id": "compare", "name": "Compare PDFs", "desc": "Report differences between two PDFs",
     "category": "Compare", "accept": ".pdf", "multiple": True,
     "hint": "Select 2 PDFs to compare."},

    # ============================================================
    # Universal Converter
    # ============================================================
    {"id": "universal",
     "name": "Universal Converter",
     "desc": "Documents · Images · OCR · XML ↔ JSON · Markup · more",
     "category": "Universal",
     "accept": (
         ".jpg,.jpeg,.jpe,.jfif,.jif,.png,.webp,.gif,.tif,.tiff,.bmp,"
         ".ico,.tga,.pcx,.dds,.ppm,.pgm,.pbm,.pnm,"
         ".heic,.heif,.avif,"
         ".cr2,.cr3,.crw,.nef,.nrw,.arw,.srf,.sr2,.dng,.raf,.orf,"
         ".rw2,.pef,.srw,.x3f,.kdc,.dcr,.mrw,.3fr,.fff,.iiq,.rwl,"
         ".md,.markdown,.html,.htm,.docx,.doc,.txt,.xml,.json,"
         ".xlsx,.xls,.xlsm,.csv,.tsv,"
         ".pptx,.ppt,"
         ".dbf,.dxf,.ai,.psd,.vsdx,.xps,.pdf,"
         ".dot,.dotx,.rtf,.odt,.ott,.fodt,.pub,"
         ".xlt,.xltx,.ods,.ots,.fods,"
         ".pot,.potx,.odp,.otp,.fodp"
     ),
     "multiple": False,
     "hint": ("Images: PDF · OCR · or another image format. "
              "Documents: Office/PDF/HTML/Markdown/XML/JSON. "
              "PDF → XLSX preserves cell background and text colors."),
     "options": [
         {
             "name": "format",
             "label": "Output format",
             "type": "select",
             "choices": [
                 {"value": "pdf",     "label": "PDF Document (*.pdf)"},
                 {"value": "docx",    "label": "Word Document (*.docx)"},
                 {"value": "doc",     "label": "Word 97-2003 Document (*.doc)"},
                 {"value": "rtf",     "label": "Rich Text Format (*.rtf)"},
                 {"value": "odt",     "label": "OpenDocument Text (*.odt)"},
                 {"value": "pub",     "label": "Microsoft Publisher (*.pub)"},
                 {"value": "html",    "label": "Web Page (*.html)"},
                 {"value": "md",      "label": "Markdown Document (*.md)"},
                 {"value": "txt",     "label": "Plain Text (*.txt)"},
                 {"value": "xml",     "label": "XML Document (*.xml)"},
                 {"value": "json",    "label": "JSON Document (*.json)"},
                 {"value": "xlsx",    "label": "Excel Workbook (*.xlsx)"},
                 {"value": "xls",     "label": "Excel 97-2003 Workbook (*.xls)"},
                 {"value": "ods",     "label": "OpenDocument Spreadsheet (*.ods)"},
                 {"value": "csv",     "label": "Comma-Separated Values (*.csv)"},
                 {"value": "tsv",     "label": "Tab-Separated Values (*.tsv)"},
                 {"value": "pptx",    "label": "PowerPoint Presentation (*.pptx)"},
                 {"value": "ppt",     "label": "PowerPoint 97-2003 (*.ppt)"},
                 {"value": "odp",     "label": "OpenDocument Presentation (*.odp)"},
                 {"value": "jpg",     "label": "JPEG Image (*.jpg)"},
                 {"value": "jpeg",    "label": "JPEG Image (*.jpeg)"},
                 {"value": "jfif",    "label": "JFIF Image (*.jfif)"},
                 {"value": "png",     "label": "PNG Image (*.png)"},
                 {"value": "webp",    "label": "WebP Image (*.webp)"},
                 {"value": "gif",     "label": "GIF Image (*.gif)"},
                 {"value": "tiff",    "label": "TIFF Image (*.tiff)"},
                 {"value": "bmp",     "label": "BMP Image (*.bmp)"},
                 {"value": "heic",    "label": "HEIC Image (*.heic)"},
                 {"value": "ico",     "label": "Windows Icon (*.ico)"},
                 {"value": "ocr",     "label": "Searchable PDF — OCR (*.pdf)"},
                 {"value": "ocr-txt", "label": "OCR Extracted Text (*.txt)"},
                 {"value": "dbf",     "label": "dBASE Table (*.dbf)"},
                 {"value": "dxf",     "label": "AutoCAD DXF (*.dxf)"},
             ],
         },
         {
             "name": "ocr_lang",
             "label": "OCR language (used only for OCR output)",
             "type": "select",
             "choices": ["eng", "swa", "fra", "deu", "spa", "ita"],
         },
     ]},
]


def get_tool(tool_id):
    for t in TOOLS:
        if t["id"] == tool_id:
            return t
    return None
