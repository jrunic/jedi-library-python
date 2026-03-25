"""
jedi_log.py – Python port of the jediLog GAS library.

Architecture (Buffer Pattern):
    - info / warn / error / debug NEVER make network calls.
    - They only append a dict to an in-memory list (_buffer).
    - flush() batches all pending entries into a single Google Sheets API call,
      then clears the buffer.

Google Sheets access:
    - Uses google-api-python-client with Application Default Credentials.
    - Set GOOGLE_APPLICATION_CREDENTIALS to a Service Account JSON key file,
      or rely on another ADC mechanism (Workload Identity, gcloud login, etc.).

Sheet ID fallback chain (highest priority first):
    1. logSheetId key in the config dict passed to init()
    2. LOGS_SHEET_ID environment variable
    3. DEFAULT_LOG_SHEET_ID constant
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Optional, cast

google: Any = None
ServiceAccountCredentials: Any = None
build: Optional[Callable[..., Any]] = None

# ---------------------------------------------------------------------------
# Optional Google auth imports – graceful fallback so unit tests work without
# the package installed when the module is imported (mocking handles the rest).
# ---------------------------------------------------------------------------
try:
    import google.auth as _google_auth  # type: ignore
    from google.oauth2.service_account import Credentials as _ServiceAccountCredentials  # type: ignore
    from googleapiclient.discovery import build as _build  # type: ignore

    google = _google_auth
    ServiceAccountCredentials = _ServiceAccountCredentials
    build = _build

    _GOOGLE_LIBS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GOOGLE_LIBS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class Level(IntEnum):
    """Numeric log levels, equivalent to the GAS LOG_LEVEL enum."""

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


LOG_SHEET_TAB: str = "data"
DEFAULT_LOG_SHEET_ID: str = "1C2HKxUhA7e-w_0bNFUFuPcpqslTFrYu7Wb214BXwSLw"

# ---------------------------------------------------------------------------
# Private module-level state (mirrors _state.gs)
# ---------------------------------------------------------------------------

_buffer: list[dict[str, str]] = []
_level: int = Level.INFO
_context: str = ""
_execution_id: str = ""
_log_sheet_id: str = ""
_user_email: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prefix_context(context: str) -> str:
    """Prefixa contextos do worker Python para facilitar rastreabilidade."""
    c = (context or "").strip()
    if not c:
        return "python:"
    if c.startswith("python:"):
        return c
    return f"python:{c}"


def _resolve_user_email() -> str:
    """
    Attempt to retrieve the e-mail associated with the active Google credential.

    For a Service Account key, google.auth.default() returns a credential whose
    ``service_account_email`` attribute holds the SA e-mail.  Other credential
    types may expose ``client_id`` instead.  Falls back to an empty string so
    that failures here never block initialisation.
    """
    try:
        credentials = _get_google_credentials()
        if credentials is None:
            return ""
        return (
            getattr(credentials, "service_account_email", None)
            or getattr(credentials, "client_id", None)
            or ""
        )
    except Exception:  # noqa: BLE001
        return ""

def _get_google_credentials() -> Optional[Any]:
    """
    Resolve Google credentials with fallback compatible with this project.

    Priority:
      1) ADC via google.auth.default()
      2) Service account JSON from env GOOGLE_CREDENTIALS_FILE (default: credentials.json)
    """
    if not _GOOGLE_LIBS_AVAILABLE or google is None:
        return None

    try:
        google_auth = cast(Any, google)
        creds, _ = google_auth.default()
        return creds
    except Exception:
        pass

    try:
        if ServiceAccountCredentials is None:
            return None
        credentials_path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        if not os.path.isabs(credentials_path):
            credentials_path = os.path.abspath(credentials_path)
        if not os.path.exists(credentials_path):
            return None
        service_account_credentials = cast(Any, ServiceAccountCredentials)
        return service_account_credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    except Exception:
        return None


def _add_entry(level: int, level_name: str, message: str, metadata_str: str) -> None:
    """
    Append a log entry dict to the in-memory buffer if *level* meets the
    configured threshold.  This is the only internal writer; it performs no I/O.
    """
    if level < _level:
        return

    _buffer.append(
        {
            # Google Sheets reconhece automaticamente este formato como datetime.
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "context": _context,
            "level": level_name,
            "message": message,
            "executionId": _execution_id,
            "metadata": metadata_str,
            "userEmail": _user_email,
        }
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init(config: dict) -> None:
    """
    Initialise (or re-initialise) the logging session.

    Resets all state and the buffer.  Must be called once at the entry point of
    the consuming script before any logging takes place.

    Args:
        config: Dictionary with the following keys:
            - context (str): Module or function name for traceability.
            - executionId (str): Unique execution UUID.
            - logSheetId (str, optional): Google Sheet ID for log storage.
    """
    global _buffer, _level, _context, _execution_id, _log_sheet_id, _user_email

    try:
        _buffer = []
        _context = _prefix_context(config.get("context", ""))
        _execution_id = config.get("executionId", "")
        _level = Level.INFO

        # Sheet ID resolution: param → env var → default constant
        _log_sheet_id = (
            config.get("logSheetId")
            or os.environ.get("LOGS_SHEET_ID")
            or DEFAULT_LOG_SHEET_ID
        )

        _user_email = _resolve_user_email()

        logger.info(
            "[jedi_log] Initialized. context=%s | executionId=%s",
            _context,
            _execution_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[jedi_log] Error during init: %s", exc)


def info(message: str, metadata: Optional[dict] = None) -> None:
    """
    Record an INFO-level entry.

    Use for significant, successful milestones in the business flow.

    Args:
        message: Human-readable message (Portuguese-BR per project convention).
        metadata: Optional dict with contextual technical data.
    """
    try:
        meta = json.dumps(metadata) if metadata is not None else ""
        logger.info("[INFO] %s", message)
        _add_entry(Level.INFO, "INFO", message, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[jedi_log] Error in info(): %s", exc)


def warn(message: str, metadata: Optional[dict] = None) -> None:
    """
    Record a WARNING-level entry.

    Use for unexpected behaviour that does not break the flow.

    Args:
        message: Human-readable message (Portuguese-BR per project convention).
        metadata: Optional dict with contextual technical data.
    """
    try:
        meta = json.dumps(metadata) if metadata is not None else ""
        logger.warning("[WARN] %s", message)
        _add_entry(Level.WARNING, "WARNING", message, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[jedi_log] Error in warn(): %s", exc)


def error(message: str, error_object: Exception) -> None:
    """
    Record an ERROR-level entry.

    Must be called exclusively inside except blocks.  The stack trace from
    *error_object* is serialised into the metadata column.

    Args:
        message: Human-readable message (Portuguese-BR per project convention).
        error_object: The caught exception; its traceback will be extracted.
    """
    try:
        meta = ""
        if error_object is not None:
            meta = json.dumps(
                {
                    "errorMessage": str(error_object),
                    "stack": "".join(
                        traceback.format_exception(
                            type(error_object),
                            error_object,
                            error_object.__traceback__,
                        )
                    ),
                }
            )
        logger.error("[ERROR] %s", message)
        _add_entry(Level.ERROR, "ERROR", message, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[jedi_log] Error in error(): %s", exc)


def debug(message: str, metadata: Optional[dict] = None) -> None:
    """
    Record a DEBUG-level entry.

    This level should be disabled in production via set_level(Level.INFO).
    Wrap calls in ``if is_debug_enabled():`` to avoid costly serialisations.

    Args:
        message: Human-readable message (Portuguese-BR per project convention).
        metadata: Optional dict with variable states or API payloads.
    """
    try:
        meta = json.dumps(metadata) if metadata is not None else ""
        logger.debug("[DEBUG] %s", message)
        _add_entry(Level.DEBUG, "DEBUG", message, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[jedi_log] Error in debug(): %s", exc)


def flush() -> None:
    """
    Persist all buffered entries to the Google Sheet in a single API call.

    Behaviour guarantees (mirrors GAS flush.gs):
    - Skips the API call when the buffer is empty.
    - Clears the buffer after a successful write.
    - Fail-safe: internal exceptions are caught and logged; the buffer is always
      cleared to prevent unbounded memory growth between retries.

    Row format appended to the ``data`` tab:
        [timestamp, context, level, message, executionId, metadata (JSON), userEmail]

    Credentials:
        Uses Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS).
    """
    global _buffer

    try:
        if not _buffer:
            return

        if not _log_sheet_id:
            msg = "[jedi_log] logSheetId not configured. Buffer discarded."
            logger.warning(msg)
            print(msg, file=sys.stderr)
            _buffer = []
            return

        if not _GOOGLE_LIBS_AVAILABLE:
            msg = (
                "[jedi_log] Google libs unavailable (google-auth/googleapiclient). "
                "Buffer discarded."
            )
            logger.warning(msg)
            print(msg, file=sys.stderr)
            _buffer = []
            return

        if build is None:
            msg = "[jedi_log] Google Sheets client builder unavailable. Buffer discarded."
            logger.warning(msg)
            print(msg, file=sys.stderr)
            _buffer = []
            return

        # Build the rows matrix — order must match column layout in the sheet
        rows = [
            [
                entry["timestamp"],
                entry["context"],
                entry["level"],
                entry["message"],
                entry["executionId"],
                entry["metadata"],
                entry["userEmail"],
            ]
            for entry in _buffer
        ]

        credentials = _get_google_credentials()
        if credentials is None:
            msg = (
                "[jedi_log] No Google credentials available (ADC or service account file). "
                "Buffer discarded."
            )
            logger.warning(msg)
            print(msg, file=sys.stderr)
            _buffer = []
            return

        # Single batch append via Google Sheets API
        build_sheets_service = cast(Callable[..., Any], build)
        service = build_sheets_service("sheets", "v4", credentials=credentials)
        body = {"values": rows}
        range_notation = f"{LOG_SHEET_TAB}!A1"

        service.spreadsheets().values().append(
            spreadsheetId=_log_sheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()

        logger.info("[jedi_log] Flush complete: %d entry/entries written.", len(rows))
        _buffer = []

    except Exception as exc:  # noqa: BLE001
        msg = f"[jedi_log] Error during flush: {exc}"
        logger.warning(msg)
        print(msg, file=sys.stderr)
        _buffer = []


def set_level(level: int) -> None:
    """
    Set the minimum log level.  Entries below this level are silently ignored.

    Args:
        level: A ``Level`` enum value (e.g. ``Level.INFO``).
    """
    global _level
    if isinstance(level, int):
        _level = level


def set_context(context: str) -> None:
    """Atualiza o contexto corrente para as próximas entradas em buffer."""
    global _context
    _context = _prefix_context(context)


def is_debug_enabled() -> bool:
    """
    Return True if the current level allows DEBUG entries.

    Use this guard before computing expensive payloads:

        if jedi_log.is_debug_enabled():
            jedi_log.debug("Payload dump", {"data": expensive_serialisation()})

    Returns:
        bool: True only when level == Level.DEBUG.
    """
    return _level == Level.DEBUG
