"""Add watermarks to PDFs."""
from pathlib import Path

from .utils import (
    print_success, print_error,
    ask_path, ask_save_path,
)


def text_watermark():
    print("\n--- Text Watermark ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    text = input("Watermark text: ").strip() or "CONFIDENTIAL"
    try:
        import fitz
        dst = ask_save_path(f"{src.stem}_watermarked", ".pdf")
        doc = fitz.open(src)
        for page in doc:
            r = page.rect
            page.insert_text(
                fitz.Point(r.x0 + 60, r.y0 + r.height / 2),
                text,
                fontsize=60,
                rotate=45,
                color=(0.85, 0.85, 0.85),
                fill_opacity=0.35,
            )
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Watermark failed: {e}")


def image_watermark():
    print("\n--- Image Watermark ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    img = ask_path("Watermark image: ", file_ext=(".png", ".jpg", ".jpeg"))
    try:
        import fitz
        dst = ask_save_path(f"{src.stem}_wm", ".pdf")
        doc = fitz.open(src)
        for page in doc:
            r = page.rect
            wm_rect = fitz.Rect(
                r.x0 + r.width / 4, r.y0 + r.height / 4,
                r.x1 - r.width / 4, r.y1 - r.height / 4,
            )
            page.insert_image(wm_rect, filename=str(img), overlay=True, alpha=0.3)
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Image watermark failed: {e}")


MENU = {
    "1": ("Text Watermark", text_watermark),
    "2": ("Image Watermark", image_watermark),
}


def run():
    while True:
        print("\n--- Watermark ---")
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
