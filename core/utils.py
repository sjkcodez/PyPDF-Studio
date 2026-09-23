"""Shared utilities for PyPDF Studio."""
import os
import sys
import platform
import subprocess
import shutil
import logging
from pathlib import Path

# ------------------------------------------------------------------
# Directories
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
ASSETS_DIR = BASE_DIR / "assets"
LOG_DIR = BASE_DIR / "logs"

for d in (OUTPUT_DIR, TEMP_DIR, ASSETS_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOG_FILE = LOG_DIR / "pypdf_studio.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("PyPDFStudio")

# ------------------------------------------------------------------
# Terminal helpers
# ------------------------------------------------------------------
def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def print_header(title: str):
    print("\n" + "=" * 62)
    print(title.center(62))
    print("=" * 62)


def print_success(msg: str):
    print(f"\n✅ {msg}")


def print_error(msg: str):
    print(f"\n❌ {msg}")


def print_warning(msg: str):
    print(f"\n⚠️  {msg}")


def pause():
    input("\nPress Enter to continue...")


# ------------------------------------------------------------------
# Input helpers
# ------------------------------------------------------------------
def ask_path(prompt: str, must_exist: bool = True, file_ext: tuple = None) -> Path:
    while True:
        raw = input(prompt).strip().strip('"').strip("'")
        if not raw:
            print("❌ Path cannot be empty.")
            continue
        p = Path(raw).expanduser()
        if must_exist and not p.exists():
            print(f"❌ File not found: {p}")
            continue
        if file_ext and p.suffix.lower() not in file_ext:
            print(f"❌ Expected one of {file_ext}, got '{p.suffix}'")
            continue
        return p


def ask_save_path(default_name: str, ext: str = ".pdf") -> Path:
    raw = input(f"Output filename (default: {default_name}): ").strip().strip('"').strip("'")
    name = raw if raw else default_name
    if not name.lower().endswith(ext):
        name += ext
    return OUTPUT_DIR / name


# ------------------------------------------------------------------
# Dependency checks
# ------------------------------------------------------------------
def ensure_module(module_name: str, pip_name: str = None) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        print(f"\n📦 Installing '{pip_name or module_name}' ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name or module_name])
            print(f"✅ Installed {pip_name or module_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to install {pip_name or module_name}: {e}")
            return False


def find_executable(name: str):
    return shutil.which(name)


def check_tesseract() -> bool:
    return find_executable("tesseract") is not None


def check_libreoffice():
    for name in ("soffice", "libreoffice"):
        path = find_executable(name)
        if path:
            return path
    return None


def check_ffmpeg() -> bool:
    return find_executable("ffmpeg") is not None
