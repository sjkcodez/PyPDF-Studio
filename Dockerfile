# ============================================================
# PyPDF Studio — production Docker image
# Bundles Python 3.11 + all system binaries the app needs.
# Base: python:3.11-slim (Debian 13 "trixie")
# ============================================================
FROM python:3.11-slim

# ---- System binaries ----------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # --- OCR (pytesseract) ---
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-swa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    tesseract-ocr-ita \
    # --- Office / ODF conversion ---
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    # --- PDF post-processing ---
    ghostscript \
    # --- HEIC / HEIF image support ---
    libheif-dev \
    libheif1 \
    # --- RAW camera image support ---
    libraw-dev \
    libraw23t64 \
    # --- WeasyPrint runtime libs ---
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    # --- misc ---
    fontconfig \
    fonts-dejavu-core \
    libmagic1 \
    # --- image codecs ---
    libjpeg62-turbo \
    libwebp7 \
    libtiff6 \
    # --- curl for healthchecks ---
    curl \
    # --- timezone database (required for TZ= env var to work) ---
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# ---- Python environment -------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Africa/Dar_es_Salaam

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application
COPY . .

# ---- Persistent directories ---------------------------------
RUN mkdir -p /app/logs /app/output /app/uploads /app/temp \
             /app/static/avatar /app/secrets

# ---- Runtime ------------------------------------------------
ENV PORT=10000
EXPOSE 10000

CMD ["gunicorn", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--bind", "0.0.0.0:10000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
