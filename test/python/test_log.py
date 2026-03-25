"""
test_log.py – pytest suite for jedi_log.py

All tests run in complete isolation: the Google Sheets API and google.auth
calls are mocked so that no real network requests are made.
"""

import importlib
import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers to reload the module between tests so that module-level state is
# always reset to a clean slate.
# ---------------------------------------------------------------------------


def _reload_jedi_log():
    """Import (or re-import) jedi_log with a clean module state."""
    if "jedi_log" in sys.modules:
        del sys.modules["jedi_log"]
    # Ensure the src/python directory is on the path
    import importlib.util
    import os

    spec_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "src", "python", "jedi_log.py"
    )
    spec = importlib.util.spec_from_file_location("jedi_log", spec_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["jedi_log"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_SA_EMAIL = "test-sa@project.iam.gserviceaccount.com"
BASE_CONFIG = {"context": "test_context", "executionId": "exec-001"}


@pytest.fixture()
def log(mock_google_auth):
    """Return a freshly loaded jedi_log module, auth already mocked."""
    module = _reload_jedi_log()
    module.init(BASE_CONFIG)
    return module


@pytest.fixture()
def mock_google_auth():
    """
    Patch google.auth.default() so no real credentials are needed.
    Returns a fake Service Account credential with a known e-mail.
    """
    fake_cred = MagicMock()
    fake_cred.service_account_email = FAKE_SA_EMAIL

    with patch("google.auth.default", return_value=(fake_cred, "fake-project")):
        yield fake_cred


@pytest.fixture()
def mock_sheets_api():
    """
    Patch googleapiclient.discovery.build to return a mock Sheets service.
    Returns the mock ``append().execute`` callable for assertion.
    """
    mock_execute = MagicMock(return_value={})
    mock_append = MagicMock()
    mock_append.return_value.execute = mock_execute

    mock_service = MagicMock()
    mock_service.spreadsheets.return_value.values.return_value.append = mock_append

    with patch("jedi_log.build", return_value=mock_service):
        yield mock_append, mock_execute


# ---------------------------------------------------------------------------
# Tests — Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_clears_buffer(self, log):
        """Re-calling init() must discard any previously buffered entries."""
        log.info("entry before re-init")
        assert len(log._buffer) == 1

        log.init(BASE_CONFIG)
        assert log._buffer == [], "buffer should be empty after re-init"

    def test_init_uses_param_sheet_id(self, mock_google_auth):
        """Explicit logSheetId in config takes highest priority."""
        module = _reload_jedi_log()
        module.init({**BASE_CONFIG, "logSheetId": "explicit-id"})
        assert module._log_sheet_id == "explicit-id"

    def test_init_uses_env_sheet_id(self, mock_google_auth, monkeypatch):
        """Falls back to LOGS_SHEET_ID env var when param is absent."""
        monkeypatch.setenv("LOGS_SHEET_ID", "env-sheet-id")
        module = _reload_jedi_log()
        module.init(BASE_CONFIG)
        assert module._log_sheet_id == "env-sheet-id"

    def test_init_uses_default_sheet_id(self, mock_google_auth, monkeypatch):
        """Falls back to DEFAULT_LOG_SHEET_ID when both param and env var are absent."""
        monkeypatch.delenv("LOGS_SHEET_ID", raising=False)
        module = _reload_jedi_log()
        module.init(BASE_CONFIG)
        assert module._log_sheet_id == module.DEFAULT_LOG_SHEET_ID

    def test_init_sets_user_email(self, log):
        """init() must populate _user_email from the mocked credential."""
        assert log._user_email == FAKE_SA_EMAIL


# ---------------------------------------------------------------------------
# Tests — Level filtering
# ---------------------------------------------------------------------------


class TestLevelFiltering:
    def test_set_level_filters_entries(self, log):
        """Entries below the configured level must not be added to the buffer."""
        log.set_level(log.Level.WARNING)
        log.debug("ignored debug")
        log.info("ignored info")
        log.warn("kept warning")
        log.error("kept error", Exception("boom"))

        assert len(log._buffer) == 2
        levels = [e["level"] for e in log._buffer]
        assert "WARNING" in levels
        assert "ERROR" in levels
        assert "DEBUG" not in levels
        assert "INFO" not in levels

    def test_is_debug_enabled_true(self, log):
        log.set_level(log.Level.DEBUG)
        assert log.is_debug_enabled() is True

    def test_is_debug_enabled_false_when_info(self, log):
        log.set_level(log.Level.INFO)
        assert log.is_debug_enabled() is False


# ---------------------------------------------------------------------------
# Tests — Entry methods
# ---------------------------------------------------------------------------


class TestEntryMethods:
    def test_info_adds_entry(self, log):
        log.info("test message", {"key": "value"})
        assert len(log._buffer) == 1
        entry = log._buffer[0]
        assert entry["level"] == "INFO"
        assert entry["message"] == "test message"
        assert json.loads(entry["metadata"]) == {"key": "value"}

    def test_warn_adds_entry(self, log):
        log.warn("warning message")
        assert log._buffer[0]["level"] == "WARNING"

    def test_error_extracts_stack_trace(self, log):
        """error() must serialise both errorMessage and stack into metadata."""
        try:
            raise ValueError("something went wrong")
        except ValueError as exc:
            log.error("erro capturado", exc)

        assert len(log._buffer) == 1
        meta = json.loads(log._buffer[0]["metadata"])
        assert meta["errorMessage"] == "something went wrong"
        assert "ValueError" in meta["stack"]
        assert "something went wrong" in meta["stack"]

    def test_debug_ignored_at_info_level(self, log):
        log.set_level(log.Level.INFO)
        log.debug("granular detail")
        assert log._buffer == []


# ---------------------------------------------------------------------------
# Tests — Flush
# ---------------------------------------------------------------------------


class TestFlush:
    def test_flush_empty_buffer_noop(self, log, mock_sheets_api):
        """flush() on an empty buffer must not call the Sheets API."""
        mock_append, mock_execute = mock_sheets_api
        log.flush()
        mock_append.assert_not_called()

    def test_flush_builds_correct_payload(self, log, mock_sheets_api):
        """flush() must pass the exact rows matrix to the Sheets append call."""
        mock_append, mock_execute = mock_sheets_api

        log.info("primeira mensagem", {"step": 1})
        log.warn("segunda mensagem")
        log.flush()

        assert mock_append.called, "append() should have been called"
        call_kwargs = mock_append.call_args.kwargs

        assert call_kwargs["spreadsheetId"] == log._log_sheet_id or (
            mock_append.call_args.args
            and mock_append.call_args.args[0] == log._log_sheet_id
        )

        body = call_kwargs.get("body") or mock_append.call_args.args[-1]
        rows = body["values"]

        assert len(rows) == 2

        # Validate column positions: [timestamp, context, level, message,
        #                              executionId, metadata, userEmail]
        first = rows[0]
        assert first[1] == "test_context"   # context
        assert first[2] == "INFO"           # level
        assert first[3] == "primeira mensagem"  # message
        assert first[4] == "exec-001"       # executionId
        assert first[6] == FAKE_SA_EMAIL    # userEmail

        second = rows[1]
        assert second[2] == "WARNING"

    def test_flush_clears_buffer(self, log, mock_sheets_api):
        """Buffer must be empty after a successful flush."""
        log.info("mensagem")
        log.flush()
        assert log._buffer == []

    def test_flush_clears_buffer_on_api_error(self, log, mock_google_auth):
        """Even when the API raises, the buffer must be cleared (fail-safe)."""
        log.info("mensagem")

        mock_service = MagicMock()
        mock_service.spreadsheets.return_value.values.return_value.append.return_value.execute.side_effect = (
            Exception("API error")
        )

        with patch("jedi_log.build", return_value=mock_service):
            log.flush()

        assert log._buffer == []

    def test_user_email_in_payload(self, log, mock_sheets_api):
        """userEmail column must be populated from the mocked credential."""
        mock_append, _ = mock_sheets_api
        log.info("com email")
        log.flush()

        body = mock_append.call_args.kwargs.get("body") or mock_append.call_args.args[
            -1
        ]
        rows = body["values"]
        assert rows[0][6] == FAKE_SA_EMAIL
