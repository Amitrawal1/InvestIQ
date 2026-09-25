"""Download NSE announcement attachments and cache their extracted text.

The `news.content` column only holds a one-line templated summary
("X has informed the Exchange about Bagging/Receiving of orders/contracts").
The actual news -- order value, rating direction, resignation reason -- lives in
the attached filing. This module fetches that filing and stores its plain text in
`news_attachment_text`, so downstream work (sentiment, extraction) can read the
document instead of the summary.

Nothing here writes to the `news` table; it only reads it.

Usage (from the ml/ folder):
    python3 -m news_pipeline.attachment_text --limit 5
    python3 -m news_pipeline.attachment_text --limit 300 --importance HIGH
    python3 -m news_pipeline.attachment_text --limit 200 --sample --retry-failed
    python3 -m news_pipeline.attachment_text --stats

Design notes:
  * Results are cached by news_id, so a second run never re-downloads. Use
    --retry-failed to revisit rows whose previous attempt errored (a 404 stays
    a 404, but timeouts and NSE throttling are worth another try).
  * One request per second by default, browser-like headers and a warmed-up
    session, exactly like `nse.py` -- nsearchives rejects bare requests.
  * Downloads are capped (--max-bytes, --max-pages) so one 400-page annual
    report cannot blow up an 8 GB machine.
  * A file lock means two runs cannot hammer NSE at once.
"""

import argparse
import fcntl
import io
import logging
import re
import sys
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

import requests

from . import db
from .config import LOG_DIR, MAX_RETRIES

log = logging.getLogger("news_pipeline.attachment_text")

LOG_FILE = LOG_DIR / "attachment_text.log"
LOCK_FILE = LOG_DIR / "attachment_text.lock"

# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

REQUEST_PAUSE_SECONDS = 1.0     # be polite to nsearchives
REQUEST_TIMEOUT = 45
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024   # skip anything bigger, it is a scan or a data dump
MAX_PDF_PAGES = 40              # first N pages are the filing; the rest is annexures
MAX_STORED_CHARS = 200_000      # what we keep in MySQL (MEDIUMTEXT)

# Below this, a PDF that has pages is almost certainly a scanned image
SCANNED_TEXT_THRESHOLD = 200

# ---------------------------------------------------------
# Status values written to news_attachment_text.status
# ---------------------------------------------------------

OK = "ok"                    # usable text extracted
NO_TEXT = "no_text"          # downloaded and parsed, but (almost) no text -> scanned image
NO_URL = "no_url"            # attachment_url missing or a placeholder like "-"
HTTP_ERROR = "http_error"    # 404 / 403 / network failure after retries
TOO_LARGE = "too_large"      # over MAX_DOWNLOAD_BYTES
UNSUPPORTED = "unsupported"  # a file type we do not parse
PARSE_ERROR = "parse_error"  # corrupt / encrypted document

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS news_attachment_text (
    news_id BIGINT NOT NULL PRIMARY KEY,
    url VARCHAR(1000) NULL,
    content_type VARCHAR(120) NULL,
    bytes INT NULL,
    pages INT NULL,
    extracted_chars INT NOT NULL DEFAULT 0,
    text MEDIUMTEXT NULL,
    status VARCHAR(20) NOT NULL,
    http_status INT NULL,
    error VARCHAR(500) NULL,
    fetched_at DATETIME NOT NULL,
    KEY idx_nat_status (status),
    KEY idx_nat_fetched (fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

UPSERT_SQL = """
INSERT INTO news_attachment_text
    (news_id, url, content_type, bytes, pages, extracted_chars, text,
     status, http_status, error, fetched_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    url = VALUES(url), content_type = VALUES(content_type), bytes = VALUES(bytes),
    pages = VALUES(pages), extracted_chars = VALUES(extracted_chars), text = VALUES(text),
    status = VALUES(status), http_status = VALUES(http_status), error = VALUES(error),
    fetched_at = VALUES(fetched_at)
"""


# ---------------------------------------------------------
# Schema / queries  (separate from db.py: that file is owned by the pipeline)
# ---------------------------------------------------------

def ensure_schema(conn):
    cur = conn.cursor()
    cur.execute(TABLE_SQL)
    conn.commit()
    cur.close()


def fetch_todo(conn, limit=None, importance=None, sample=False, retry_failed=False):
    """Announcements with no cached attachment text yet."""

    where = ["n.is_duplicate = 0"]
    params = []

    if importance:
        where.append("n.importance = %s")
        params.append(importance)

    if retry_failed:
        # revisit transient failures, but never re-download something already parsed
        where.append("(a.news_id IS NULL OR a.status IN ('http_error', 'parse_error'))")
    else:
        where.append("a.news_id IS NULL")

    order = "RAND()" if sample else "n.published_at DESC"

    sql = f"""
        SELECT n.id, n.symbol, n.importance, n.attachment_url
        FROM news n
        LEFT JOIN news_attachment_text a ON a.news_id = n.id
        WHERE {" AND ".join(where)}
        ORDER BY {order}
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def save_result(conn, news_id, result):
    text = result.get("text") or None
    if text and len(text) > MAX_STORED_CHARS:
        text = text[:MAX_STORED_CHARS]

    cur = conn.cursor()
    cur.execute(UPSERT_SQL, (
        news_id,
        (result.get("url") or "")[:1000] or None,
        (result.get("content_type") or "")[:120] or None,
        result.get("bytes"),
        result.get("pages"),
        result.get("extracted_chars", 0),
        text,
        result["status"],
        result.get("http_status"),
        (result.get("error") or "")[:500] or None,
        datetime.now(),
    ))
    conn.commit()
    cur.close()


def status_counts(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT status, COUNT(*), AVG(extracted_chars), AVG(bytes)
        FROM news_attachment_text GROUP BY status ORDER BY COUNT(*) DESC
    """)
    rows = cur.fetchall()
    cur.close()
    return rows


# ---------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------

_WS = re.compile(r"[ \t\x0b\f\r]+")
_BLANKS = re.compile(r"\n\s*\n\s*\n+")
_CTRL = re.compile(r"[\x00-\x08\x0e-\x1f]")
# Words split across a line break by PDF layout: "resigna-\ntion"
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


def clean_text(raw):
    if not raw:
        return ""
    text = raw.replace(" ", " ").replace("\x00", "")
    text = _CTRL.sub(" ", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _WS.sub(" ", text)
    text = _BLANKS.sub("\n\n", text)
    return text.strip()


_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def strip_markup(data):
    """Plain text out of an HTML or XML/XBRL payload."""

    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = data.decode("latin-1", errors="replace")
    text = _SCRIPT.sub(" ", text)
    text = _TAG.sub(" ", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    return text


# ---------------------------------------------------------
# Extraction
# ---------------------------------------------------------

def extract_pdf(data, max_pages=MAX_PDF_PAGES):
    """(text, page_count). Empty text means the PDF is a scan with no text layer."""

    import pymupdf  # imported lazily: it is the only heavy dependency here

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("encrypted PDF")
        pages = doc.page_count
        parts = [doc[i].get_text("text") for i in range(min(pages, max_pages))]

    return clean_text("\n".join(parts)), pages


_ZIP_PREFERENCE = (".pdf", ".htm", ".html", ".xml", ".xbrl", ".txt", ".csv")


def extract_zip(data, max_pages=MAX_PDF_PAGES):
    """Pick the most promising member of a ZIP and extract that."""

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist() if not m.is_dir() and m.file_size > 0]
        if not members:
            return "", None, "empty zip"

        def rank(member):
            name = member.filename.lower()
            for i, ext in enumerate(_ZIP_PREFERENCE):
                if name.endswith(ext):
                    return (i, -member.file_size)
            return (len(_ZIP_PREFERENCE), -member.file_size)

        member = min(members, key=rank)
        if member.file_size > MAX_DOWNLOAD_BYTES:
            return "", None, f"zip member too large ({member.file_size} bytes)"

        inner = zf.read(member)

    name = member.filename.lower()
    if name.endswith(".pdf"):
        text, pages = extract_pdf(inner, max_pages)
        return text, pages, f"zip:{member.filename}"
    if name.endswith((".htm", ".html", ".xml", ".xbrl")):
        return clean_text(strip_markup(inner)), None, f"zip:{member.filename}"
    if name.endswith((".txt", ".csv")):
        return clean_text(inner.decode("utf-8", errors="replace")), None, f"zip:{member.filename}"

    return "", None, f"zip member unsupported: {member.filename}"


def sniff(data, url, content_type):
    """File kind from magic bytes first, then content-type, then the URL suffix."""

    head = data[:5]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "zip"

    ct = (content_type or "").lower()
    path = urlparse(url).path.lower()

    if "pdf" in ct or path.endswith(".pdf"):
        return "pdf"
    if "zip" in ct or path.endswith(".zip"):
        return "zip"
    if "html" in ct or path.endswith((".htm", ".html")):
        return "html"
    if "xml" in ct or path.endswith((".xml", ".xbrl")):
        return "xml"
    if ct.startswith("text/") or path.endswith(".txt"):
        return "text"
    if data[:1] in (b"<",):
        return "xml"
    return "unknown"


def extract(data, url, content_type, max_pages=MAX_PDF_PAGES):
    """Raw bytes -> {status, text, extracted_chars, pages, ...}."""

    kind = sniff(data, url, content_type)
    result = {"bytes": len(data), "content_type": content_type, "pages": None}

    try:
        if kind == "pdf":
            text, pages = extract_pdf(data, max_pages)
            result["pages"] = pages
        elif kind == "zip":
            text, pages, note = extract_zip(data, max_pages)
            result["pages"] = pages
            result["content_type"] = (note or content_type)[:120]
        elif kind in ("html", "xml"):
            text = clean_text(strip_markup(data))
        elif kind == "text":
            text = clean_text(data.decode("utf-8", errors="replace"))
        else:
            return {**result, "status": UNSUPPORTED, "text": "", "extracted_chars": 0,
                    "error": f"unsupported file type ({content_type or 'unknown'})"}
    except Exception as exc:
        return {**result, "status": PARSE_ERROR, "text": "", "extracted_chars": 0,
                "error": f"{type(exc).__name__}: {exc}"}

    chars = len(text)
    status = OK if chars >= SCANNED_TEXT_THRESHOLD else NO_TEXT
    error = None if status == OK else f"only {chars} chars extracted (scanned image?)"

    return {**result, "status": status, "text": text, "extracted_chars": chars, "error": error}


# ---------------------------------------------------------
# Downloading
# ---------------------------------------------------------

ARCHIVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/zip,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

WARMUP_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"

# 404 / 410 will not change on a retry; anything else might
_RETRYABLE_STATUS = {403, 408, 429, 500, 502, 503, 504}


class AttachmentDownloader:
    """Polite nsearchives client: warmed-up session, backoff, size cap."""

    def __init__(self, pause=REQUEST_PAUSE_SECONDS, max_bytes=MAX_DOWNLOAD_BYTES,
                 timeout=REQUEST_TIMEOUT, max_retries=MAX_RETRIES):
        self.pause = pause
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = None
        self._last_request = 0.0

    def _new_session(self):
        session = requests.Session()
        session.headers.update(ARCHIVE_HEADERS)
        try:
            session.get(WARMUP_URL, timeout=self.timeout)
        except requests.RequestException as exc:
            log.warning("Warm-up request failed (continuing anyway): %s", exc)
        self.session = session

    def _throttle(self):
        wait = self.pause - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url):
        """{'status': ..., 'data': bytes|None, 'content_type': str, 'http_status': int}."""

        last_error = None
        http_status = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.session is None:
                    self._new_session()

                self._throttle()
                response = self.session.get(url, timeout=self.timeout, stream=True)
                http_status = response.status_code

                if response.status_code >= 400:
                    response.close()
                    last_error = f"HTTP {response.status_code}"
                    if response.status_code not in _RETRYABLE_STATUS:
                        return {"status": HTTP_ERROR, "data": None, "http_status": http_status,
                                "content_type": None, "error": last_error}
                    self.session = None  # fresh cookies often clear NSE 403s
                    raise requests.RequestException(last_error)

                declared = response.headers.get("Content-Length")
                if declared and int(declared) > self.max_bytes:
                    response.close()
                    return {"status": TOO_LARGE, "data": None, "http_status": http_status,
                            "content_type": response.headers.get("Content-Type"),
                            "error": f"{int(declared)} bytes > cap", "bytes": int(declared)}

                chunks, total = [], 0
                for chunk in response.iter_content(65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > self.max_bytes:
                        response.close()
                        return {"status": TOO_LARGE, "data": None, "http_status": http_status,
                                "content_type": response.headers.get("Content-Type"),
                                "error": f">{self.max_bytes} bytes", "bytes": total}

                content_type = response.headers.get("Content-Type")
                response.close()
                return {"status": OK, "data": b"".join(chunks), "http_status": http_status,
                        "content_type": content_type, "error": None}

            except requests.RequestException as exc:
                last_error = str(exc)[:300]
                self.session = None
                if attempt == self.max_retries:
                    break
                backoff = 2 ** attempt
                log.warning("Download failed (%d/%d) %s: %s; retry in %ds",
                            attempt, self.max_retries, url, last_error, backoff)
                time.sleep(backoff)

        return {"status": HTTP_ERROR, "data": None, "http_status": http_status,
                "content_type": None, "error": last_error}


def looks_like_url(value):
    return bool(value) and str(value).strip().lower().startswith(("http://", "https://"))


def fetch_one(downloader, url, max_pages=MAX_PDF_PAGES):
    """Download + extract one attachment. Never raises."""

    if not looks_like_url(url):
        return {"url": url, "status": NO_URL, "text": "", "extracted_chars": 0,
                "error": "no attachment url"}

    got = downloader.get(url)
    if got["status"] != OK:
        return {"url": url, "status": got["status"], "text": "", "extracted_chars": 0,
                "content_type": got.get("content_type"), "bytes": got.get("bytes"),
                "http_status": got.get("http_status"), "error": got.get("error")}

    result = extract(got["data"], url, got.get("content_type"), max_pages)
    result["url"] = url
    result["http_status"] = got.get("http_status")
    return result


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def setup_logging(verbose=True):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    handlers = [file_handler]

    if verbose and sys.stdout.isatty():
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        handlers.append(stream)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = handlers
    for name in ("urllib3", "requests"):
        logging.getLogger(name).setLevel(logging.WARNING)


@contextmanager
def single_instance():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def backfill(conn, limit, importance=None, sample=False, retry_failed=False,
             pause=REQUEST_PAUSE_SECONDS, max_pages=MAX_PDF_PAGES,
             max_bytes=MAX_DOWNLOAD_BYTES):
    """Fill the cache for up to `limit` announcements. Returns a status histogram."""

    rows = fetch_todo(conn, limit, importance, sample, retry_failed)
    if not rows:
        log.info("Nothing to fetch")
        return {}

    log.info("Fetching %d attachments (importance=%s, pause=%.1fs)",
             len(rows), importance or "any", pause)

    downloader = AttachmentDownloader(pause=pause, max_bytes=max_bytes)
    counts = {}
    started = time.monotonic()

    for i, row in enumerate(rows, 1):
        result = fetch_one(downloader, row["attachment_url"], max_pages)
        save_result(conn, row["id"], result)

        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if i % 25 == 0 or i == len(rows):
            elapsed = time.monotonic() - started
            log.info("%d/%d done in %.0fs (%s)", i, len(rows), elapsed,
                     ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        else:
            log.debug("news_id=%s %s %s chars=%s",
                      row["id"], row["symbol"], result["status"], result.get("extracted_chars"))

    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download NSE announcement attachments and cache their text")
    parser.add_argument("--limit", type=int, default=50,
                        help="Max attachments to fetch this run (default 50)")
    parser.add_argument("--importance", choices=["HIGH", "MEDIUM", "LOW"],
                        help="Only announcements of this importance")
    parser.add_argument("--sample", action="store_true",
                        help="Pick rows at random instead of newest-first (for surveys)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Also revisit rows whose previous attempt failed")
    parser.add_argument("--pause", type=float, default=REQUEST_PAUSE_SECONDS,
                        help=f"Seconds between requests (default {REQUEST_PAUSE_SECONDS})")
    parser.add_argument("--max-pages", type=int, default=MAX_PDF_PAGES,
                        help=f"PDF pages to read (default {MAX_PDF_PAGES})")
    parser.add_argument("--max-bytes", type=int, default=MAX_DOWNLOAD_BYTES,
                        help="Skip attachments larger than this")
    parser.add_argument("--stats", action="store_true",
                        help="Print what is cached and exit")
    args = parser.parse_args(argv)

    setup_logging()

    if args.limit < 0:
        parser.error("--limit must be >= 0")

    conn = db.get_connection()
    try:
        ensure_schema(conn)

        if args.stats:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM news_attachment_text")
            total = cur.fetchone()[0]
            cur.close()
            print(f"cached rows: {total}")
            print(f"{'status':<14}{'count':>8}{'avg chars':>12}{'avg bytes':>12}")
            for status, count, avg_chars, avg_bytes in status_counts(conn):
                print(f"{status:<14}{count:>8}{float(avg_chars or 0):>12.0f}{float(avg_bytes or 0):>12.0f}")
            return 0

        with single_instance() as acquired:
            if not acquired:
                log.info("Another attachment_text run is in progress; skipping")
                return 0

            counts = backfill(conn, args.limit, args.importance, args.sample,
                              args.retry_failed, args.pause, args.max_pages, args.max_bytes)
            log.info("Done: %s", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing")
            return 0

    except Exception:
        log.exception("attachment_text run failed")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
