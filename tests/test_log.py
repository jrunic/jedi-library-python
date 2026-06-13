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


def test_service_presente_quando_configurado(capsys):
    log.setup(actor="a", actor_kind="b", service="meu-srv", service_version="1.0")
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["service"] == "meu-srv"
    assert entry["service_version"] == "1.0"


def test_service_ausente_quando_nao_configurado(capsys):
    log.setup(actor="a", actor_kind="b")
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert "service" not in entry
    assert "service_version" not in entry


def test_execution_id_aparece_apos_set(capsys):
    log.setup(actor="a", actor_kind="b")
    log.set_execution_id("exec-123")
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["execution_id"] == "exec-123"


def test_execution_id_desaparece_apos_clear(capsys):
    log.setup(actor="a", actor_kind="b")
    log.set_execution_id("exec-xyz")
    log.clear_execution_id()
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert "execution_id" not in entry


def test_execution_id_sem_vazamento_entre_contextos(capsys):
    log.setup(actor="a", actor_kind="b")
    log.set_execution_id("ctx-pai")

    entries_filho = []

    def filho():
        log.clear_execution_id()
        logging.getLogger("test").info("filho")
        out = capsys.readouterr().out.strip()
        if out:
            entries_filho.append(json.loads(out))

    copy_context().run(filho)

    logging.getLogger("test").info("pai")
    entry_pai = json.loads(capsys.readouterr().out.strip())
    assert entry_pai["execution_id"] == "ctx-pai"
    assert entries_filho and "execution_id" not in entries_filho[0]


def test_metadata_de_extra(capsys):
    log.setup(actor="a", actor_kind="b")
    logging.getLogger("test").info("msg", extra={"task_id": 42, "status": "ok"})
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["metadata"]["task_id"] == 42
    assert entry["metadata"]["status"] == "ok"


def test_exc_estruturado(capsys):
    log.setup(actor="a", actor_kind="b")
    try:
        raise ValueError("valor inválido")
    except ValueError:
        logging.getLogger("test").exception("falha")
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["exc"]["type"] == "ValueError"
    assert "valor inválido" in entry["exc"]["msg"]
    assert "traceback" in entry["exc"]


def test_idempotencia_setup_nao_duplica_handler(capsys):
    log.setup(actor="a", actor_kind="b")
    log.setup(actor="c", actor_kind="d")
    logging.getLogger("test").info("msg")
    lines = [l for l in capsys.readouterr().out.splitlines() if l]
    assert len(lines) == 1


def test_jedi_log_actor_env_sobrescreve_user(capsys, monkeypatch):
    monkeypatch.setenv("JEDI_LOG_ACTOR", "actor-do-env")
    log.setup()
    logging.getLogger("test").info("msg")
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["actor"] == "actor-do-env"
