"""Security: protect, unlock, sign, flatten."""
from pathlib import Path

from .utils import (
    print_success, print_error,
    ask_path, ask_save_path,
)


def protect_pdf():
    print("\n--- Protect PDF (add password) ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    user_pw = input("User password: ").strip()
    owner_pw = input("Owner password (blank = same as user): ").strip() or user_pw
    dst = ask_save_path(f"{src.stem}_protected", ".pdf")
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        w = PdfWriter()
        for p in reader.pages:
            w.add_page(p)
        w.encrypt(user_password=user_pw, owner_password=owner_pw)
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Protect failed: {e}")


def unlock_pdf():
    print("\n--- Unlock PDF ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    pw = input("Password: ").strip()
    dst = ask_save_path(f"{src.stem}_unlocked", ".pdf")
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        if reader.is_encrypted:
            reader.decrypt(pw)
        w = PdfWriter()
        for p in reader.pages:
            w.add_page(p)
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Unlock failed: {e}")


def sign_pdf():
    print("\n--- Sign PDF (image signature) ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    sig = ask_path("Signature image (png/jpg): ", file_ext=(".png", ".jpg", ".jpeg"))
    try:
        import fitz
        dst = ask_save_path(f"{src.stem}_signed", ".pdf")
        doc = fitz.open(src)
        page = doc[-1]  # last page
        rect = page.rect
        sig_rect = fitz.Rect(rect.x1 - 200, rect.y1 - 100, rect.x1 - 50, rect.y1 - 30)
        page.insert_image(sig_rect, filename=str(sig))
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Sign failed: {e}")


def flatten_pdf():
    print("\n--- Flatten PDF (remove form fields / annotations) ---")
    src = ask_path("PDF: ", file_ext=(".pdf",))
    dst = ask_save_path(f"{src.stem}_flattened", ".pdf")
    try:
        import fitz
        doc = fitz.open(src)
        for page in doc:
            # Bake annotations into the content stream
            annots = list(page.annots()) if page.annots() else []
            for a in annots:
                page.add_redact_annot(a.rect)
            page.apply_redactions()
        doc.save(dst)
        doc.close()
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Flatten failed: {e}")


MENU = {
    "1": ("Protect PDF (add password)", protect_pdf),
    "2": ("Unlock PDF (remove password)", unlock_pdf),
    "3": ("Sign PDF (add signature image)", sign_pdf),
    "4": ("Flatten PDF", flatten_pdf),
}


def run():
    while True:
        print("\n--- Security ---")
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
