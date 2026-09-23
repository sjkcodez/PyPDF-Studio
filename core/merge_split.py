"""Merge, split, extract, remove, and sort PDF pages."""
from pathlib import Path

from .utils import (
    OUTPUT_DIR, print_success, print_error,
    ask_path, ask_save_path,
)


def _read_pdfs():
    print("Enter PDF paths (one per line, blank to finish).")
    files = []
    while True:
        raw = input("PDF: ").strip().strip('"')
        if not raw:
            break
        p = Path(raw).expanduser()
        if not p.exists() or p.suffix.lower() != ".pdf":
            print(f"❌ Not a PDF: {p}")
            continue
        files.append(p)
    return files


def merge_pdfs():
    print("\n--- Merge PDFs ---")
    files = _read_pdfs()
    if len(files) < 2:
        print_error("Need at least 2 PDFs.")
        return
    dst = ask_save_path("merged", ".pdf")
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for f in files:
            writer.append(str(f))
        with open(dst, "wb") as out:
            writer.write(out)
        writer.close()
        print_success(f"Merged {len(files)} files → {dst}")
    except Exception as e:
        print_error(f"Merge failed: {e}")


def _parse_pages(spec: str, total: int):
    """Parse '1-3,5,7' into a list of 0-based indexes."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            out.extend(range(a - 1, b))
        else:
            out.append(int(part) - 1)
    return [i for i in out if 0 <= i < total]


def split_pdf():
    print("\n--- Split PDF ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        total = len(reader.pages)
        print(f"Total pages: {total}")
        spec = input("Page ranges (e.g. 1-3,5,7): ").strip()
        indexes = _parse_pages(spec, total)
        if not indexes:
            print_error("No valid pages.")
            return
        for i in indexes:
            w = PdfWriter()
            w.add_page(reader.pages[i])
            out = OUTPUT_DIR / f"{src.stem}_page_{i+1}.pdf"
            with open(out, "wb") as f:
                w.write(f)
        print_success(f"Wrote {len(indexes)} single-page PDF(s) to {OUTPUT_DIR}")
    except Exception as e:
        print_error(f"Split failed: {e}")


def extract_pages():
    print("\n--- Extract Pages ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        total = len(reader.pages)
        print(f"Total pages: {total}")
        spec = input("Pages to extract (e.g. 1-3,7): ").strip()
        idx = _parse_pages(spec, total)
        dst = ask_save_path(f"{src.stem}_extracted", ".pdf")
        w = PdfWriter()
        for i in idx:
            w.add_page(reader.pages[i])
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Extract failed: {e}")


def remove_pages():
    print("\n--- Remove Pages ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        total = len(reader.pages)
        print(f"Total pages: {total}")
        spec = input("Pages to REMOVE (e.g. 2,4-5): ").strip()
        remove = set(_parse_pages(spec, total))
        dst = ask_save_path(f"{src.stem}_cleaned", ".pdf")
        w = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in remove:
                w.add_page(page)
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Remove failed: {e}")


def sort_pages():
    print("\n--- Reorder Pages ---")
    src = ask_path("PDF file: ", file_ext=(".pdf",))
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src))
        total = len(reader.pages)
        print(f"Total pages: {total}")
        order = input("New order (e.g. 3,1,2): ").strip()
        idx = [int(x) - 1 for x in order.split(",") if x.strip()]
        idx = [i for i in idx if 0 <= i < total]
        dst = ask_save_path(f"{src.stem}_sorted", ".pdf")
        w = PdfWriter()
        for i in idx:
            w.add_page(reader.pages[i])
        with open(dst, "wb") as f:
            w.write(f)
        print_success(f"Saved: {dst}")
    except Exception as e:
        print_error(f"Sort failed: {e}")


MENU = {
    "1": ("Merge PDFs", merge_pdfs),
    "2": ("Split PDF (into single pages)", split_pdf),
    "3": ("Extract Pages", extract_pages),
    "4": ("Remove Pages", remove_pages),
    "5": ("Sort/Reorder Pages", sort_pages),
}


def run():
    while True:
        print("\n--- Merge & Split ---")
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
