"""
Universal converter for PyPDF Studio.

Pipeline:
    input file → [READER] → AST → [WRITER] → output file
"""
from pathlib import Path

from core.readers import get_reader, READERS
from core.writers import get_writer, WRITERS
from core.utils import OUTPUT_DIR, print_success, print_error


SUPPORTED_INPUTS  = sorted(set(READERS.keys()))
SUPPORTED_OUTPUTS = sorted(set(WRITERS.keys()))


def list_supported():
    print("\n📥 Supported input extensions :", ", ".join(SUPPORTED_INPUTS))
    print("📤 Supported output formats   :", ", ".join(SUPPORTED_OUTPUTS))
    print("\nℹ️  Note: .indd, .dwg, and .mpp are proprietary formats with no")
    print("   pure-Python support. Export them from their original apps first.")


def convert_file(input_path: str, output_format: str, output_path: str = None) -> bool:
    src = Path(input_path).expanduser()
    if not src.exists():
        print_error(f"Input file not found: {src}")
        return False

    reader = get_reader(src.suffix)
    if reader is None:
        print_error(f"No reader for '{src.suffix}'. Supported: {SUPPORTED_INPUTS}")
        return False

    writer = get_writer(output_format)
    if writer is None:
        print_error(f"No writer for '{output_format}'. Supported: {SUPPORTED_OUTPUTS}")
        return False

    if output_path is None:
        ext = "." + output_format.lstrip(".")
        output_path = OUTPUT_DIR / (src.stem + "_converted" + ext)
    else:
        output_path = Path(output_path)

    try:
        print(f"\n🔄 Reading {src.name} ...")
        ast = reader(str(src))

        if "title" not in ast.metadata or not ast.metadata["title"]:
            ast.metadata["title"] = src.stem

        print(f"🧠 AST built: {len(ast.children)} block(s)")
        print(f"✍️  Writing {output_format.upper()} → {output_path.name} ...")

        writer(ast, str(output_path))
        print_success(f"Saved: {output_path}")
        return True

    except Exception as e:
        print_error(f"Conversion failed: {e}")
        return False


def interactive_convert():
    list_supported()
    print()

    raw = input("Path to input file: ").strip().strip('"').strip("'")
    if not raw:
        print_error("No input provided.")
        return
    src = Path(raw).expanduser()
    if not src.exists():
        print_error(f"Not found: {src}")
        return

    print("\nChoose output format:")
    for i, fmt in enumerate(SUPPORTED_OUTPUTS, 1):
        print(f"  {i}. {fmt}")
    choice = input("Number or name: ").strip().lower()

    if choice.isdigit():
        idx = int(choice) - 1
        if not (0 <= idx < len(SUPPORTED_OUTPUTS)):
            print_error("Invalid number.")
            return
        fmt = SUPPORTED_OUTPUTS[idx]
    else:
        fmt = choice

    if fmt not in SUPPORTED_OUTPUTS:
        print_error(f"Unsupported output format: {fmt}")
        return

    default_name = src.stem + "_converted." + fmt
    out_name = input(f"Output filename (default: {default_name}): ").strip()
    out_path = OUTPUT_DIR / (out_name if out_name else default_name)

    convert_file(str(src), fmt, str(out_path))


def batch_convert():
    list_supported()
    raw = input("\nFolder path: ").strip().strip('"').strip("'")
    folder = Path(raw).expanduser()
    if not folder.is_dir():
        print_error(f"Not a folder: {folder}")
        return

    fmt = input("Target format (e.g. pdf, docx, md, html, txt, xml, dbf, dxf): ").strip().lower()
    if fmt not in SUPPORTED_OUTPUTS:
        print_error(f"Unsupported format: {fmt}")
        return

    converted = 0
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in SUPPORTED_INPUTS:
            out = OUTPUT_DIR / (f.stem + "_converted." + fmt)
            if convert_file(str(f), fmt, str(out)):
                converted += 1

    print_success(f"Batch complete. {converted} file(s) converted.")


def run():
    while True:
        print("\n--- Universal Converter (Reader → AST → Writer) ---")
        print(" 1. Convert a file (any-to-any)")
        print(" 2. Batch convert a folder")
        print(" 3. Show supported formats")
        print(" 0. Back")
        c = input("Choice: ").strip()
        if c == "0":
            return
        elif c == "1":
            interactive_convert()
        elif c == "2":
            batch_convert()
        elif c == "3":
            list_supported()
        else:
            print("❌ Invalid choice.")
