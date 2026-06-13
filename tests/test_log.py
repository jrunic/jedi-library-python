import json
import logging
import socket
from contextvars import copy_context

import pytest

from jedi_library import log
from jedi_library.log import _JediFormatter


@pytest.fixture(autouse=True)
def reset_log():
    yield
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h.formatter, _JediFormatter)]
    log.clear_execution_id()


def test_emite_json_valido_por_linha(capsys):
    log.setup(actor="tester", actor_kind="test")
    logging.getLogger("test").info("hello")
    lines = [l for l in capsys.readouterr().out.splitlines() if l]
    assert len(lines) == 1
    json.loads(lines[0])  # levanta se inválido


def test_campos_obrigatorios_presentes(capsys):
    log.setup(actor="tester", actor_kind="test")
    logging.getLogger("test.mod").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    for f in ("ts", "level", "logger", "msg", "module", "func", "line", "pid", "host", "actor", "actor_kind"):
        assert f in entry


def test_ts_utc_termina_em_z(capsys):
    log.setup(actor="tester", actor_kind="test")
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["ts"].endswith("Z")


def test_host_sem_dominio(capsys):
    log.setup(actor="tester", actor_kind="test")
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert "." not in entry["host"]
    assert entry["host"] == socket.gethostname().split(".")[0]
