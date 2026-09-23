#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyPDF Studio v4.1
A universal PDF toolkit + universal document converter.

Now with Pandoc-style "any-to-any" conversion via Reader → AST → Writer.
"""

import sys
from core import utils

# ------------------------------------------------------------------
# Dependency bootstrap
# ------------------------------------------------------------------
REQUIRED = [
    ("pypdf", "pypdf"),
    ("fitz", "PyMuPDF"),
    ("PIL", "Pillow"),
    ("docx", "python-docx"),
    ("openpyxl", "openpyxl"),
    ("pptx", "python-pptx"),
    ("reportlab", "reportlab"),
    ("markdown", "markdown"),
    ("ebooklib", "ebooklib"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
]


def bootstrap():
    print("Checking dependencies...")
    missing = []
    for mod, pip_name in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append((mod, pip_name))
    if missing:
        print(f"\n⚠ Missing {len(missing)} module(s).")
        ans = input("Install now? (yes/no): ").strip().lower()
        if ans in ("yes", "y"):
            for mod, pip_name in missing:
                utils.ensure_module(mod, pip_name)
        else:
            print("Continuing – some features may not work.\n")


# ------------------------------------------------------------------
# Main menu
# ------------------------------------------------------------------
BANNER = r"""
   ____        ____  _____  _____    ____  _             _ _
  |  _ \ _   _|  _ \|  __ \|  ___|  / ___|| |_ _   _  __| (_) ___
  | |_) | | | | |_) | |  | | |_     \___ \| __| | | |/ _` | |/ _ \
  |  __/| |_| |  _ <| |__| |  _|     ___) | |_| |_| | (_| | | (_) |
  |_|    \__, |_| \_\_____/|_|      |____/ \__|\__,_|\__,_|_|\___/
         |___/
              Universal PDF Toolkit & Converter — v4.1
"""


def main_menu():
    while True:
        utils.clear_screen()
        print(BANNER)
        print(" Main Menu")
        print("-" * 62)
        print("  1. Convert TO PDF       (Word, Excel, PPT, Images, ...)")
        print("  2. Convert FROM PDF     (Word, Excel, PPT, Images, ...)")
        print("  3. Merge & Split        (Merge, Split, Extract, ...)")
        print("  4. Edit PDF             (Rotate, Crop, Overlay, ...)")
        print("  5. Watermark            (Text, Image)")
        print("  6. Security             (Protect, Unlock, Sign, Flatten)")
        print("  7. OCR                  (Searchable PDF)")
        print("  8. Compare PDFs")
        print("  9. Utilities            (Compress, Job Application)")
        print(" 10. Universal Converter  (Any → Any: MD, HTML, DOCX, PDF, TXT)")
        print("  0. Exit")
        print("-" * 62)
        choice = input("Choice: ").strip()

        if choice == "0":
            print("\nGoodbye 👋")
            sys.exit(0)
        elif choice == "1":
            from core import convert_to_pdf
            convert_to_pdf.run()
        elif choice == "2":
            from core import convert_from_pdf
            convert_from_pdf.run()
        elif choice == "3":
            from core import merge_split
            merge_split.run()
        elif choice == "4":
            from core import edit
            edit.run()
        elif choice == "5":
            from core import watermark
            watermark.run()
        elif choice == "6":
            from core import security
            security.run()
        elif choice == "7":
            from core import ocr
            ocr.run()
        elif choice == "8":
            from core import compare
            compare.run()
        elif choice == "9":
            try:
                from core import utilities as util_mod
                util_mod.run()
            except ImportError:
                print("Utilities module not installed.")
                utils.pause()
        elif choice == "10":
            from core import converter
            converter.run()
        else:
            print("❌ Invalid choice.")
            utils.pause()


if __name__ == "__main__":
    try:
        bootstrap()
        main_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye.")
