"""LibreOffice headless wrapper for Office format conversion."""
import shutil
import subprocess
from pathlib import Path


def find_soffice():
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


def is_available():
    return find_soffice() is not None


def convert(input_path, target_ext, out_dir):
    """Convert input_path to target_ext using LibreOffice headless.

    target_ext should be like 'docx' (no leading dot).
    Returns the path to the converted file.
    """
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice not found. Install it:\n"
            "  Ubuntu/Debian: sudo apt install -y libreoffice\n"
            "  Fedora:        sudo dnf install -y libreoffice\n"
            "  macOS:         brew install --cask libreoffice\n"
            "  Windows:       https://www.libreoffice.org/download/"
        )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        soffice, "--headless", "--norestore", "--nolockcheck",
        "--convert-to", target_ext,
        "--outdir", str(out_dir),
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice failed: {result.stderr.strip() or result.stdout.strip()}"
        )

    expected = out_dir / (Path(input_path).stem + "." + target_ext)
    if expected.exists():
        return expected

    candidates = sorted(out_dir.glob(f"*.{target_ext}"))
    if not candidates:
        raise RuntimeError(f"LibreOffice produced no .{target_ext} file")
    return candidates[0]
