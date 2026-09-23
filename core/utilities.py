"""Compress, Job Application builder."""
from pathlib import Path

from .utils import (
    OUTPUT_DIR, print_success, print_error,
    ask_path, ask_save_path,
)


def compress_pdf():
    print("\n--- Compress PDF ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    quality = input("Image quality (low/medium/high) [medium]: ").strip().lower() or "medium"
    try:
        import fitz
        dst = ask_save_path(f"{src.stem}_compressed", ".pdf")
        doc = fitz.open(src)
        doc.save(dst, garbage=4, deflate=True, clean=True)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Compress failed: {e}")


def job_application_pdf():
    print("\n--- Create Job Application PDF ---")
    print("Provide paths to your documents (blank to skip).")
    resume = input("Resume PDF: ").strip().strip('"')
    cover = input("Cover letter PDF: ").strip().strip('"')
    certs = input("Certificates PDF (optional): ").strip().strip('"')
    dst = ask_save_path("job_application", ".pdf")
    try:
        from pypdf import PdfWriter
        w = PdfWriter()
        for f in (resume, cover, certs):
            if f:
                p = Path(f).expanduser()
                if p.exists():
                    w.append(str(p))
        with open(dst, "wb") as out:
            w.write(out)
        w.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Job application build failed: {e}")


MENU = {
    "1": ("Compress PDF", compress_pdf),
    "2": ("Create Job Application PDF", job_application_pdf),
}


def run():
    while True:
        print("\n--- Utilities ---")
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
