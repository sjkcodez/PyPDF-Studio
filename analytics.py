"""SQLite-backed analytics for PyPDF Studio.

Tracks:
  • Page visits       (path, IP, UA, device, referrer, session_id)
  • Conversions       (tool, input/output ext, sizes, duration, success/fail)
  • Downloads         (filename, IP, session_id)

Writes are best-effort: a failure here never breaks a conversion.

Persistence:
  • SQLite lives in `logs/analytics.db` — fast, local.
  • Every event is ALSO mirrored to Google Sheets via core.sheet_logger
    (batched, async). On Render's ephemeral disk, the SQLite file is
    rehydrated from Sheets on each cold start.

Timestamps:
  • Stored as Unix epoch seconds (time.time()) — timezone-agnostic.
  • Displayed via datetime.fromtimestamp() — shows container local time.
"""
import csv
import io
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core import sheet_logger


# ============================================================
# Configuration
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DB_PATH = LOG_DIR / "analytics.db"

_LOCK = threading.Lock()


# ============================================================
# Schema
# ============================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    device      TEXT,
    os          TEXT,
    browser     TEXT,
    path        TEXT,
    referrer    TEXT,
    session_id  TEXT
);

CREATE TABLE IF NOT EXISTS conversions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           REAL    NOT NULL,
    tool_id      TEXT,
    input_ext    TEXT,
    output_ext   TEXT,
    input_size   INTEGER,
    output_size  INTEGER,
    duration_ms  INTEGER,
    ip           TEXT,
    session_id   TEXT,
    success      INTEGER,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS downloads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    filename    TEXT,
    ip          TEXT,
    session_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_visits_ts    ON visits(ts);
CREATE INDEX IF NOT EXISTS idx_conv_ts      ON conversions(ts);
CREATE INDEX IF NOT EXISTS idx_dl_ts        ON downloads(ts);
"""


def _connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


# ============================================================
# User-Agent parsing (lightweight)
# ============================================================
def _detect_device(ua: str) -> str:
    if not ua:
        return "unknown"
    u = ua.lower()
    if "ipad" in u or ("android" in u and "mobile" not in u) or "tablet" in u:
        return "tablet"
    if "mobile" in u or any(x in u for x in (
        "iphone", "ipod", "windows phone", "blackberry", "opera mini"
    )):
        return "mobile"
    return "desktop"


def _detect_os(ua: str) -> str:
    u = (ua or "").lower()
    if "windows" in u:
        return "Windows"
    if "iphone" in u or "ipad" in u or "ios" in u:
        return "iOS"
    if "mac os x" in u or "macintosh" in u:
        return "macOS"
    if "android" in u:
        return "Android"
    if "linux" in u:
        return "Linux"
    return "unknown"


def _detect_browser(ua: str) -> str:
    u = (ua or "").lower()
    if "edg/" in u or "edgios" in u or "edga" in u:
        return "Edge"
    if "opr/" in u or "opera" in u:
        return "Opera"
    if "firefox" in u:
        return "Firefox"
    if "chrome" in u or "crios" in u:
        return "Chrome"
    if "safari" in u:
        return "Safari"
    return "unknown"


# ============================================================
# Recording
# ============================================================
def record_visit(ip: str, ua: str, path: str, referrer: str, session_id: str):
    # ---- DIAGNOSTIC: function was entered ----
    print(f"[analytics] record_visit called: path={path}", flush=True)

    # --- Local SQLite write (fast) ---
    try:
        with _LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """INSERT INTO visits
                       (ts, ip, user_agent, device, os, browser,
                        path, referrer, session_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        time.time(), ip or "", ua or "",
                        _detect_device(ua), _detect_os(ua), _detect_browser(ua),
                        path or "", referrer or "", session_id or "",
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[analytics] SQLite visit insert failed: {e}", flush=True)

    # --- Mirror to Google Sheets (async, batched) ---
    print("[analytics] mirroring visit to sheet_logger...", flush=True)
    try:
        sheet_logger.log_visit(
            ip=ip or "",
            path=path or "",
            referrer=referrer or "",
            device=_detect_device(ua),
            browser=_detect_browser(ua),
            session_id=session_id or "",
        )
        print("[analytics] visit mirror OK", flush=True)
    except Exception as e:
        print(f"[analytics] visit mirror FAILED: {e}", flush=True)


def record_conversion(
    tool_id: str,
    input_ext: str,
    output_ext: str,
    input_size: int,
    output_size: int,
    duration_ms: int,
    ip: str,
    session_id: str,
    success: bool,
    error: str = "",
):
    # ---- DIAGNOSTIC ----
    print(f"[analytics] record_conversion called: {tool_id} "
          f"success={success}", flush=True)

    # --- Local SQLite write ---
    try:
        with _LOCK:
            conn = _connect()
            try:
                conn.execute(
                    """INSERT INTO conversions
                       (ts, tool_id, input_ext, output_ext, input_size,
                        output_size, duration_ms, ip, session_id,
                        success, error)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        time.time(), tool_id or "", input_ext or "",
                        output_ext or "", int(input_size or 0),
                        int(output_size or 0), int(duration_ms or 0),
                        ip or "", session_id or "",
                        1 if success else 0, (error or "")[:300],
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[analytics] SQLite conversion insert failed: {e}", flush=True)

    # --- Mirror to Google Sheets ---
    print("[analytics] mirroring conversion to sheet_logger...", flush=True)
    try:
        sheet_logger.log_conversion(
            tool_id=tool_id or "",
            input_ext=input_ext or "",
            output_ext=output_ext or "",
            input_size=int(input_size or 0),
            output_size=int(output_size or 0),
            duration_ms=int(duration_ms or 0),
            success=bool(success),
            error=error or "",
            session_id=session_id or "",
        )
        print("[analytics] conversion mirror OK", flush=True)
    except Exception as e:
        print(f"[analytics] conversion mirror FAILED: {e}", flush=True)


def record_download(filename: str, ip: str, session_id: str):
    # ---- DIAGNOSTIC ----
    print(f"[analytics] record_download called: {filename}", flush=True)

    # --- Local SQLite write ---
    try:
        with _LOCK:
            conn = _connect()
            try:
                conn.execute(
                    "INSERT INTO downloads (ts, filename, ip, session_id) "
                    "VALUES (?, ?, ?, ?)",
                    (time.time(), filename or "", ip or "", session_id or ""),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[analytics] SQLite download insert failed: {e}", flush=True)

    # --- Mirror to Google Sheets ---
    print("[analytics] mirroring download to sheet_logger...", flush=True)
    try:
        sheet_logger.log_download(
            filename=filename or "",
            ip=ip or "",
            session_id=session_id or "",
        )
        print("[analytics] download mirror OK", flush=True)
    except Exception as e:
        print(f"[analytics] download mirror FAILED: {e}", flush=True)


# ============================================================
# Query / aggregation
# ============================================================
def _since_ts(days: float) -> float:
    if days <= 0:
        return 0.0
    return time.time() - days * 86400


def get_stats(days: float = 7.0) -> dict:
    """Return everything the admin dashboard needs, in one dict."""
    since = _since_ts(days)
    out = {
        "days": days,
        "totals": {},
        "top_tools": [],
        "devices": [],
        "browsers": [],
        "os": [],
        "daily_visits": [],
        "recent_conversions": [],
        "recent_downloads": [],
    }

    conn = _connect()
    try:
        out["totals"]["visits"] = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE ts >= ?", (since,)
        ).fetchone()[0]

        out["totals"]["unique_visitors"] = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM visits "
            "WHERE ts >= ? AND session_id != ''",
            (since,),
        ).fetchone()[0]

        out["totals"]["conversions"] = conn.execute(
            "SELECT COUNT(*) FROM conversions WHERE ts >= ?", (since,)
        ).fetchone()[0]

        out["totals"]["conversions_ok"] = conn.execute(
            "SELECT COUNT(*) FROM conversions WHERE ts >= ? AND success = 1",
            (since,),
        ).fetchone()[0]

        out["totals"]["downloads"] = conn.execute(
            "SELECT COUNT(*) FROM downloads WHERE ts >= ?", (since,)
        ).fetchone()[0]

        rows = conn.execute(
            """SELECT tool_id,
                      COUNT(*)                                  AS uses,
                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,
                      AVG(duration_ms)                          AS avg_ms
               FROM conversions
               WHERE ts >= ?
               GROUP BY tool_id
               ORDER BY uses DESC
               LIMIT 15""",
            (since,),
        ).fetchall()
        out["top_tools"] = [
            {
                "tool_id": r["tool_id"],
                "uses": r["uses"],
                "success_rate": (r["ok"] / r["uses"] * 100.0) if r["uses"] else 0.0,
                "avg_ms": int(r["avg_ms"] or 0),
            }
            for r in rows
        ]

        out["devices"] = _group_count(conn, "visits", "device", since)
        out["browsers"] = _group_count(conn, "visits", "browser", since)
        out["os"] = _group_count(conn, "visits", "os", since)

        daily_n = int(min(max(days, 1), 14))
        out["daily_visits"] = _daily_counts(conn, "visits", daily_n)

        rows = conn.execute(
            """SELECT ts, tool_id, input_ext, output_ext, duration_ms,
                      success, input_size
               FROM conversions
               ORDER BY ts DESC
               LIMIT 25""",
        ).fetchall()
        out["recent_conversions"] = [
            {
                "ts_str": datetime.fromtimestamp(r["ts"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "tool_id": r["tool_id"],
                "input_ext": r["input_ext"],
                "output_ext": r["output_ext"],
                "duration_ms": r["duration_ms"],
                "success": bool(r["success"]),
                "input_size": r["input_size"],
            }
            for r in rows
        ]

        rows = conn.execute(
            "SELECT ts, filename FROM downloads ORDER BY ts DESC LIMIT 15"
        ).fetchall()
        out["recent_downloads"] = [
            {
                "ts_str": datetime.fromtimestamp(r["ts"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "filename": r["filename"],
            }
            for r in rows
        ]

    finally:
        conn.close()
    return out


def _group_count(conn, table: str, column: str, since: float):
    rows = conn.execute(
        f"SELECT {column} AS k, COUNT(*) AS n FROM {table} "
        f"WHERE ts >= ? GROUP BY {column} ORDER BY n DESC LIMIT 10",
        (since,),
    ).fetchall()
    total = sum(r["n"] for r in rows) or 1
    return [
        {"name": r["k"] or "unknown", "count": r["n"],
         "pct": r["n"] / total * 100.0}
        for r in rows
    ]


def _daily_counts(conn, table: str, days: int):
    out = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_ts = day.timestamp()
        next_ts = day_ts + 86400
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE ts >= ? AND ts < ?",
            (day_ts, next_ts),
        ).fetchone()[0]
        out.append({
            "date": day.strftime("%Y-%m-%d"),
            "label": day.strftime("%b %d"),
            "count": n,
        })
    return out


def export_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    conn = _connect()
    try:
        for table in ("visits", "conversions", "downloads"):
            w.writerow([f"# ---- {table} ----"])
            cur = conn.execute(f"SELECT * FROM {table} ORDER BY ts ASC")
            cols = [d[0] for d in cur.description]
            w.writerow(cols)
            for row in cur.fetchall():
                w.writerow([row[c] for c in cols])
            w.writerow([])
    finally:
        conn.close()
    return buf.getvalue()


def reset_all():
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript("""
                DELETE FROM visits;
                DELETE FROM conversions;
                DELETE FROM downloads;
                DELETE FROM sqlite_sequence
                    WHERE name IN ('visits', 'conversions', 'downloads');
            """)
            conn.commit()
        finally:
            conn.close()


# Initialise the DB on first import
init_db()
