"""Convert many document/image formats TO PDF."""
from pathlib import Path

from .utils import (
    OUTPUT_DIR, TEMP_DIR, logger,
    print_success, print_error, print_warning,
    ask_path, ask_save_path, check_libreoffice,
)


# ------------------------------------------------------------------
# LibreOffice-based conversions (Word, Excel, PPT, Publisher, ODF, RTF)
# ------------------------------------------------------------------
def _libreoffice_convert(input_path: Path, out_dir: Path) -> Path:
    soffice = check_libreoffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice not found. Install it from https://www.libreoffice.org/ "
            "to convert Office documents to PDF."
        )
    import subprocess
    cmd = [soffice, "--headless", "--convert-to", "pdf",
           "--outdir", str(out_dir), str(input_path)]
    subprocess.run(cmd, check=True, timeout=300)
    result = out_dir / (input_path.stem + ".pdf")
    if not result.exists():
        raise RuntimeError(f"LibreOffice did not produce {result}")
    return result


def _run_libreoffice_tool(label, extensions):
    print(f"\n--- {label} → PDF ---")
    src = ask_path("Path to input file: ", file_ext=extensions)
    dst = ask_save_path(src.stem, ".pdf")
    try:
        out = _libreoffice_convert(src, dst.parent)
        if out != dst:
            out.replace(dst)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(str(e))


def word_to_pdf():
    _run_libreoffice_tool("Word", (".doc", ".docx"))


def powerpoint_to_pdf():
    _run_libreoffice_tool("PowerPoint", (".ppt", ".pptx"))


def excel_to_pdf():
    _run_libreoffice_tool("Excel", (".xls", ".xlsx"))


def publisher_to_pdf():
    _run_libreoffice_tool("Publisher", (".pub",))


def openoffice_to_pdf():
    _run_libreoffice_tool("OpenOffice", (".odt", ".odg", ".ods", ".odp"))


def rtf_to_pdf():
    _run_libreoffice_tool("RTF", (".rtf",))


# ------------------------------------------------------------------
# Images to PDF
# ------------------------------------------------------------------
def images_to_pdf():
    print("\n--- Images → PDF ---")
    print("Enter image paths one per line (blank line to finish).")
    files = []
    while True:
        raw = input("Image path: ").strip().strip('"')
        if not raw:
            break
        p = Path(raw).expanduser()
        if not p.exists():
            print(f"❌ Not found: {p}")
            continue
        files.append(p)
    if not files:
        print_error("No images provided.")
        return
    try:
        from PIL import Image
        dst = ask_save_path("images_combined", ".pdf")
        imgs = []
        for f in files:
            img = Image.open(f).convert("RGB")
            imgs.append(img)
        imgs[0].save(dst, save_all=True, append_images=imgs[1:])
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Image to PDF failed: {e}")


# ------------------------------------------------------------------
# Text / Markdown / RTF-lite
# ------------------------------------------------------------------
def text_to_pdf():
    print("\n--- Text → PDF ---")
    src = ask_path("Path to .txt file: ", file_ext=(".txt",))
    dst = ask_save_path(src.stem, ".pdf")
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(dst), pagesize=LETTER)
        width, height = LETTER
        y = height - 50
        for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
            if y < 50:
                c.showPage()
                y = height - 50
            c.drawString(50, y, line[:110])
            y -= 14
        c.save()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Text to PDF failed: {e}")


def markdown_to_pdf():
    print("\n--- Markdown → PDF ---")
    src = ask_path("Path to .md file: ", file_ext=(".md", ".markdown"))
    dst = ask_save_path(src.stem, ".pdf")
    try:
        import markdown
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        html = markdown.markdown(src.read_text(encoding="utf-8"))
        text = html.replace("<p>", "").replace("</p>", "\n")
        text = text.replace("<h1>", "\n# ").replace("</h1>", "\n")
        text = text.replace("<h2>", "\n## ").replace("</h2>", "\n")
        text = text.replace("<li>", " • ").replace("</li>", "\n")
        c = canvas.Canvas(str(dst), pagesize=LETTER)
        width, height = LETTER
        y = height - 50
        for line in text.splitlines():
            if y < 50:
                c.showPage()
                y = height - 50
            c.drawString(50, y, line[:110])
            y -= 14
        c.save()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Markdown to PDF failed: {e}")


# ------------------------------------------------------------------
# HTML / Webpage / EPUB
# ------------------------------------------------------------------
def html_to_pdf():
    print("\n--- HTML → PDF ---")
    src = ask_path("Path to .html file: ", file_ext=(".html", ".htm"))
    dst = ask_save_path(src.stem, ".pdf")
    try:
        from weasyprint import HTML
        HTML(filename=str(src)).write_pdf(str(dst))
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"HTML to PDF failed: {e}")


def webpage_to_pdf():
    print("\n--- Webpage → PDF ---")
    url = input("Enter URL: ").strip()
    if not url.startswith(("http://", "https://")):
        print_error("Invalid URL.")
        return
    dst = ask_save_path("webpage", ".pdf")
    try:
        from weasyprint import HTML
        HTML(url).write_pdf(str(dst))
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Webpage to PDF failed: {e}")


def epub_to_pdf():
    print("\n--- EPUB → PDF ---")
    src = ask_path("Path to .epub file: ", file_ext=(".epub",))
    dst = ask_save_path(src.stem, ".pdf")
    try:
        from ebooklib import epub
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        book = epub.read_epub(str(src))
        text_parts = []
        for item in book.get_items():
            if item.get_type() == 9:  # ITEM_DOCUMENT
                text_parts.append(item.get_content().decode("utf-8", errors="replace"))
        combined = "\n".join(text_parts)
        import re
        plain = re.sub(r"<[^>]+>", " ", combined)
        c = canvas.Canvas(str(dst), pagesize=LETTER)
        width, height = LETTER
        y = height - 50
        for line in plain.splitlines():
            for chunk in [line[i:i+110] for i in range(0, len(line), 110)] or [""]:
                if y < 50:
                    c.showPage()
                    y = height - 50
                c.drawString(50, y, chunk)
                y -= 14
        c.save()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"EPUB to PDF failed: {e}")


# ------------------------------------------------------------------
# Public dispatch menu
# ------------------------------------------------------------------
TO_PDF_MENU = {
    "1": ("Word to PDF", word_to_pdf),
    "2": ("PowerPoint to PDF", powerpoint_to_pdf),
    "3": ("Excel to PDF", excel_to_pdf),
    "4": ("Images to PDF", images_to_pdf),
    "5": ("Publisher to PDF", publisher_to_pdf),
    "6": ("OpenOffice to PDF", openoffice_to_pdf),
    "7": ("Text to PDF", text_to_pdf),
    "8": ("RTF to PDF", rtf_to_pdf),
    "9": ("Markdown to PDF", markdown_to_pdf),
    "10": ("EPUB to PDF", epub_to_pdf),
    "11": ("HTML to PDF", html_to_pdf),
    "12": ("Webpage (URL) to PDF", webpage_to_pdf),
}


def run():
    while True:
        print("\n--- Convert TO PDF ---")
        for k, (label, _) in TO_PDF_MENU.items():
            print(f" {k:>2}. {label}")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        if choice in TO_PDF_MENU:
            TO_PDF_MENU[choice][1]()
        else:
            print("❌ Invalid choice.")
