"""PDF page-level editing: rotate, crop, overlay, page numbers."""
from pathlib import Path

from .utils import (
    OUTPUT_DIR, print_success, print_error,
    ask_path, ask_save_path,
)


def rotate_pages():
    print("\n--- Rotate Pages ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        import fitz
        angle = int(input("Rotation angle (90/180/270): ").strip())
        if angle not in (90, 180, 270):
            print_error("Angle must be 90, 180, or 270.")
            return
        spec = input("Pages to rotate (e.g. 1-3, all): ").strip().lower()
        dst = ask_save_path(f"{src.stem}_rotated", ".pdf")
        doc = fitz.open(src)
        if spec in ("all", ""):
            indexes = range(len(doc))
        else:
            indexes = [int(x) - 1 for x in spec.replace(" ", "").split(",") if x]
        for i in indexes:
            page = doc[i]
            page.set_rotation((page.rotation + angle) % 360)
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Rotate failed: {e}")


def crop_pages():
    print("\n--- Crop Pages (trim margins) ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        import fitz
        print("Enter margins in points (1 pt = 1/72 inch):")
        left = float(input("Left [0]: ").strip() or 0)
        right = float(input("Right [0]: ").strip() or 0)
        top = float(input("Top [0]: ").strip() or 0)
        bottom = float(input("Bottom [0]: ").strip() or 0)
        dst = ask_save_path(f"{src.stem}_cropped", ".pdf")
        doc = fitz.open(src)
        for page in doc:
            r = page.rect
            new_rect = fitz.Rect(r.x0 + left, r.y0 + top, r.x1 - right, r.y1 - bottom)
            page.set_cropbox(new_rect)
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Crop failed: {e}")


def overlay_pdfs():
    print("\n--- Overlay PDFs (background + foreground) ---")
    bg = ask_path("Background PDF: ", file_ext=(".pdf",))
    fg = ask_path("Overlay PDF: ", file_ext=(".pdf",))
    dst = ask_save_path(f"{fg.stem}_overlay", ".pdf")
    try:
        from pypdf import PdfReader, PdfWriter
        bg_reader = PdfReader(str(bg))
        fg_reader = PdfReader(str(fg))
        w = PdfWriter()
        n = max(len(bg_reader.pages), len(fg_reader.pages))
        for i in range(n):
            base = bg_reader.pages[i % len(bg_reader.pages)]
            top = fg_reader.pages[i % len(fg_reader.pages)]
            base.merge_page(top)
            w.add_page(base)
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Overlay failed: {e}")


def add_page_numbers():
    print("\n--- Add Page Numbers ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        import fitz
        position = input("Position (bottom-center/top-right/bottom-right) [bottom-center]: ").strip() or "bottom-center"
        dst = ask_save_path(f"{src.stem}_numbered", ".pdf")
        doc = fitz.open(src)
        for i, page in enumerate(doc, start=1):
            r = page.rect
            text = str(i)
            if position == "top-right":
                point = fitz.Point(r.x1 - 60, 30)
            elif position == "bottom-right":
                point = fitz.Point(r.x1 - 60, r.y1 - 20)
            else:  # bottom-center
                point = fitz.Point(r.x0 + r.width / 2 - 10, r.y1 - 20)
            page.insert_text(point, text, fontsize=10)
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Add page numbers failed: {e}")


MENU = {
    "1": ("Rotate Pages", rotate_pages),
    "2": ("Crop Pages", crop_pages),
    "3": ("Overlay Two PDFs", overlay_pdfs),
    "4": ("Add Page Numbers", add_page_numbers),
}


def run():
    while True:
        print("\n--- Edit PDF ---")
        for k, (label, _) in MENU.items():
            print(f" {k}. {label}")
        print(" 0. Back")
        c = input("Choice: ").strip()
        if c == "0":
            return
        if c in MENU:
            MENU[c][1]()
        else:
            print("❌ Invalid choice.")
