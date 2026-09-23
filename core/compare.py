"""Compare two PDFs and report differences."""
from pathlib import Path

from .utils import (
    OUTPUT_DIR, print_success, print_error,
    ask_path, ask_save_path,
)


def compare_pdfs():
    print("\n--- Compare Two PDFs ---")
    a = ask_path("First PDF: ", file_ext=(".pdf",))
    b = ask_path("Second PDF: ", file_ext=(".pdf",))
    dst = ask_save_path(f"compare_{a.stem}_vs_{b.stem}", ".txt")
    try:
        import fitz
        da = fitz.open(a)
        db = fitz.open(b)
        lines = []
        lines.append(f"Comparing:\n  A = {a}\n  B = {b}\n")
        lines.append(f"Pages: A={len(da)}  B={len(db)}\n")
        n = max(len(da), len(db))
        diffs = 0
        for i in range(n):
            ta = da[i].get_text() if i < len(da) else ""
            tb = db[i].get_text() if i < len(db) else ""
            if ta != tb:
                diffs += 1
                lines.append(f"\n--- Page {i+1} differs ---")
                sa = set(ta.split())
                sb = set(tb.split())
                only_a = sorted(sa - sb)[:50]
                only_b = sorted(sb - sa)[:50]
                if only_a:
                    lines.append("  Only in A: " + ", ".join(only_a))
                if only_b:
                    lines.append("  Only in B: " + ", ".join(only_b))
        lines.append(f"\nTotal pages with differences: {diffs}")
        dst.write_text("\n".join(lines), encoding="utf-8")
        da.close()
        db.close()
        print_success(f"Report saved: {dst}")
    except Exception as e:
        print_error(f"Compare failed: {e}")


MENU = {
    "1": ("Compare Two PDFs", compare_pdfs),
}


def run():
    while True:
        print("\n--- Compare ---")
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
