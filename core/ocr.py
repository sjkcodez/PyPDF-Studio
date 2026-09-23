"""OCR: make scanned PDFs searchable using Tesseract."""
from pathlib import Path

from .utils import (
    TEMP_DIR, print_success, print_error,
    print_warning, ask_path, ask_save_path, check_tesseract,
)


def ocr_pdf():
    print("\n--- PDF OCR (searchable PDF) ---")
    if not check_tesseract():
        print_warning(
            "Tesseract not found. Install it:\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  Linux:   sudo apt install tesseract-ocr\n"
            "  macOS:   brew install tesseract"
        )
        return
    src = ask_path("PDF: ", file_ext=(".pdf",))
    lang = input("Language code [eng]: ").strip() or "eng"
    dst = ask_save_path(f"{src.stem}_ocr", ".pdf")
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(src)
        out_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension="pdf", lang=lang)
            ocr_page = fitz.open("pdf", pdf_bytes)
            out_doc.insert_pdf(ocr_page)
        out_doc.save(dst)
        out_doc.close()
        doc.close()
        print_success(f"Saved searchable PDF: {dst}")
    except Exception as e:
        print_error(f"OCR failed: {e}")


MENU = {
    "1": ("OCR PDF (searchable output)", ocr_pdf),
}


def run():
    while True:
        print("\n--- OCR ---")
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
