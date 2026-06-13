"""Backend de log JSON estruturado em stdout."""
import json
import logging
import os
import socket
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_execution_id: ContextVar[str | None] = ContextVar("_execution_id", default=None)

_actor: str = "unknown"
_actor_kind: str = "unknown"
_service: str | None = None
_service_version: str | None = None

_LOG_RECORD_ATTRS: frozenset[str] = frozenset({
    "name", "msg", "args", "created", "filename", "funcName", "levelname",
    "levelno", "lineno", "module", "msecs", "pathname", "process",
    "processName", "relativeCreated", "stack_info", "thread", "threadName",
    "exc_info", "exc_text", "taskName", "message",
})


class _JediFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        ts = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )
        entry: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "pid": record.process,
            "host": socket.gethostname().split(".")[0],
            "actor": _actor,
            "actor_kind": _actor_kind,
        }
        if _service is not None:
            entry["service"] = _service
        if _service_version is not None:
            entry["service_version"] = _service_version
        eid = _execution_id.get()
        if eid is not None:
            entry["execution_id"] = eid
        metadata = {k: v for k, v in record.__dict__.items() if k not in _LOG_RECORD_ATTRS}
        if metadata:
            entry["metadata"] = metadata
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            entry["exc"] = {
                "type": exc_type.__name__,
                "msg": str(exc_value),
                "traceback": "".join(traceback.format_tb(exc_tb)),
            }
        return json.dumps(entry, ensure_ascii=False)


def setup(
    actor: str | None = None,
    actor_kind: str | None = None,
    service: str | None = None,
    service_version: str | None = None,
) -> None:
    global _actor, _actor_kind, _service, _service_version
    _actor = actor or os.environ.get("JEDI_LOG_ACTOR") or os.environ.get("USER") or "unknown"
    _actor_kind = actor_kind or "unknown"
    _service = service
    _service_version = service_version
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h.formatter, _JediFormatter)]
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JediFormatter())
    root.addHandler(handler)
    if root.level == logging.WARNING or root.level == logging.NOTSET:
        root.setLevel(logging.DEBUG)


def set_execution_id(eid: str) -> None:
    _execution_id.set(eid)


def clear_execution_id() -> None:
    _execution_id.set(None)
