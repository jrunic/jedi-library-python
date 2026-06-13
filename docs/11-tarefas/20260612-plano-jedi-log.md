---
id: 202606122200
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — reescrita de jedi_library.log para stdout JSON estruturado (Path B)"
tags: [plano-execucao, python, log, json, stdout]
spec: docs/11-tarefas/20260612-spec-jedi-log.md
---

# jedi_library.log — Plano de Implementação

**Objetivo:** Reescrever log.py para emitir JSON estruturado em stdout via Python logging; descontinuar backend Sheets.
**Arquitetura:** Formatter customizado (_JediFormatter) plugado no root logger; ContextVar para execution_id; estado global para actor/service configurado via setup().
**Pilha técnica:** Python 3.12, stdlib (logging, json, socket, contextvars, datetime, traceback)

---

## Task 0: Setup infraestrutura pytest

**Arquivos:** `pyproject.toml` (modificar), `tests/` (criar diretório)

### Step 0.1 — Adicionar seções pytest ao pyproject.toml

Substituir o conteúdo de `pyproject.toml` pelo seguinte:

```toml
[project]
name = "jedi-library"
version = "0.1.0"
description = "Utilities for Jedi Labs Python projects"
requires-python = ">=3.12,<3.13"
dependencies = [
    "google-auth>=2.0",
    "google-api-python-client>=2.0",
    "google-genai>=1.0",
]

[tool.uv]
package = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "tests"]

[dependency-groups]
dev = ["pytest>=8.0"]
```

### Step 0.2 — Criar diretório tests/

```bash
mkdir -p tests && touch tests/.gitkeep
```

Output esperado: nenhum (sucesso silencioso).

### Step 0.3 — Verificar e recriar .venv com Python 3.12

O repo tem `requires-python = ">=3.12,<3.13"`. Se existir `.venv` compilado com outra versão (verificar: `python --version` dentro do venv), recriar:

```bash
uv venv --python 3.12 && uv sync --group dev
```

Output esperado: `Using Python 3.12.x` na criação do venv.

### Step 0.4 — Sincronizar dependências de dev

```bash
uv sync --group dev
```

Output esperado (aproximado):
```
Resolved 12 packages in 0.XXs
Installed 4 packages in 0.XXs
 + iniconfig==2.0.0
 + packaging==24.X
 + pluggy==1.X.X
 + pytest==8.X.X
```

### Step 0.5 — Verificar pytest sem testes

```bash
uv run pytest tests/ -v
```

Output esperado:
```
========================= no tests ran in 0.XXs ==========================
```

### Step 0.6 — Commit

```bash
git add pyproject.toml tests/.gitkeep
git commit -m "chore(infra): pytest infra — pyproject.toml com pythonpath=[.,tests], diretório tests/"
```

---

## Task 1: _JediFormatter e campos obrigatórios

**Arquivos:** `jedi_library/log.py` (reescrever), `tests/test_log.py` (criar)

### Step 1.1 — Escrever testes (vermelho)

Criar `tests/test_log.py` com os quatro primeiros testes e a fixture de reset:

```python
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
```

### Step 1.2 — Rodar → FAIL esperado

```bash
uv run pytest tests/test_log.py -v
```

Output esperado (falha porque log.py atual é Sheets-based e não tem `setup()`):
```
FAILED tests/test_log.py::test_emite_json_valido_por_linha - AttributeError: module 'jedi_library.log' has no attribute 'setup'
FAILED tests/test_log.py::test_campos_obrigatorios_presentes - ...
FAILED tests/test_log.py::test_ts_utc_termina_em_z - ...
FAILED tests/test_log.py::test_host_sem_dominio - ...
4 failed in 0.XXs
```

### Step 1.3 — Reescrever jedi_library/log.py (verde)

Substituir o conteúdo completo de `jedi_library/log.py`:

```python
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
```

### Step 1.4 — Rodar → PASS esperado

```bash
uv run pytest tests/test_log.py -v -k "json_valido or obrigatorios or utc or sem_dominio"
```

Output esperado:
```
PASSED tests/test_log.py::test_emite_json_valido_por_linha
PASSED tests/test_log.py::test_campos_obrigatorios_presentes
PASSED tests/test_log.py::test_ts_utc_termina_em_z
PASSED tests/test_log.py::test_host_sem_dominio
4 passed in 0.XXs
```

### Step 1.5 — Commit

```bash
git add jedi_library/log.py tests/test_log.py
git commit -m "feat(log): _JediFormatter + setup() — JSON stdout, campos obrigatórios"
```

---

## Task 2: Campos opcionais (service, execution_id)

**Arquivos:** `tests/test_log.py` (adicionar testes), `jedi_library/log.py` já tem a lógica implementada na Task 1

> **Nota:** Como o log.py foi escrito completo na Task 1 (incluindo service, execution_id e set/clear), esta task valida esse comportamento via testes adicionais. O ciclo TDD inverte a ordem: testes novos → confirmação de que passam (o código já existe).

### Step 2.1 — Adicionar testes ao tests/test_log.py

Acrescentar ao final do arquivo:

```python
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
```

### Step 2.2 — Rodar → PASS esperado

```bash
uv run pytest tests/test_log.py -v -k "service or execution_id"
```

Output esperado:
```
PASSED tests/test_log.py::test_service_presente_quando_configurado
PASSED tests/test_log.py::test_service_ausente_quando_nao_configurado
PASSED tests/test_log.py::test_execution_id_aparece_apos_set
PASSED tests/test_log.py::test_execution_id_desaparece_apos_clear
PASSED tests/test_log.py::test_execution_id_sem_vazamento_entre_contextos
5 passed in 0.XXs
```

### Step 2.3 — Commit

```bash
git add tests/test_log.py
git commit -m "test(log): testes de service e execution_id (campos opcionais)"
```

---

## Task 3: metadata, exc, idempotência, env var

**Arquivos:** `tests/test_log.py` (adicionar testes finais)

### Step 3.1 — Adicionar testes restantes ao tests/test_log.py

Acrescentar ao final do arquivo:

```python
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
```

### Step 3.2 — Rodar → FAIL esperado para alguns testes

```bash
uv run pytest tests/test_log.py -v -k "metadata or exc or idempotencia or env"
```

> Se o log.py foi escrito completo na Task 1, estes testes devem passar diretamente. Caso algum falhe (ex: metadata inclui atributos internos não filtrados), ajustar `_LOG_RECORD_ATTRS` em log.py para cobrir o atributo extra identificado.

Output esperado:
```
PASSED tests/test_log.py::test_metadata_de_extra
PASSED tests/test_log.py::test_exc_estruturado
PASSED tests/test_log.py::test_idempotencia_setup_nao_duplica_handler
PASSED tests/test_log.py::test_jedi_log_actor_env_sobrescreve_user
4 passed in 0.XXs
```

### Step 3.3 — Suite completa

```bash
uv run pytest tests/test_log.py -v
```

Output esperado:
```
PASSED tests/test_log.py::test_emite_json_valido_por_linha
PASSED tests/test_log.py::test_campos_obrigatorios_presentes
PASSED tests/test_log.py::test_ts_utc_termina_em_z
PASSED tests/test_log.py::test_host_sem_dominio
PASSED tests/test_log.py::test_service_presente_quando_configurado
PASSED tests/test_log.py::test_service_ausente_quando_nao_configurado
PASSED tests/test_log.py::test_execution_id_aparece_apos_set
PASSED tests/test_log.py::test_execution_id_desaparece_apos_clear
PASSED tests/test_log.py::test_execution_id_sem_vazamento_entre_contextos
PASSED tests/test_log.py::test_metadata_de_extra
PASSED tests/test_log.py::test_exc_estruturado
PASSED tests/test_log.py::test_idempotencia_setup_nao_duplica_handler
PASSED tests/test_log.py::test_jedi_log_actor_env_sobrescreve_user
13 passed in 0.XXs
```

### Step 3.4 — Commit final

```bash
git add tests/test_log.py
git commit -m "test(log): suite completa — metadata, exc, idempotência, env var (13 testes)"
```

---

## Auto-revisão

### Cobertura dos critérios da spec

| Critério | Coberto | Teste |
|---|---|---|
| Emite JSON válido em stdout | sim | test_emite_json_valido_por_linha |
| Uma linha por evento | sim | test_emite_json_valido_por_linha |
| Campos obrigatórios presentes | sim | test_campos_obrigatorios_presentes |
| `ts` UTC terminado em `Z` | sim | test_ts_utc_termina_em_z |
| `host` sem domínio | sim | test_host_sem_dominio |
| `service` / `service_version` presentes quando configurados | sim | test_service_presente_quando_configurado |
| `service` / `service_version` ausentes quando não configurados | sim | test_service_ausente_quando_nao_configurado |
| `execution_id` aparece após set_execution_id() | sim | test_execution_id_aparece_apos_set |
| `execution_id` desaparece após clear_execution_id() | sim | test_execution_id_desaparece_apos_clear |
| ContextVar sem vazamento entre contextos | sim | test_execution_id_sem_vazamento_entre_contextos |
| `metadata` de extra={} sem atributos internos | sim | test_metadata_de_extra |
| `exc` estruturado com type/msg/traceback | sim | test_exc_estruturado |
| Idempotência: setup() 2x → 1 linha por evento | sim | test_idempotencia_setup_nao_duplica_handler |
| Resolução actor: JEDI_LOG_ACTOR env var | sim | test_jedi_log_actor_env_sobrescreve_user |
| Resolução actor: parâmetro direto | sim | todos os testes com actor="..." |
| `setup()` sem parâmetros: fallback para env/USER/unknown | sim | test_jedi_log_actor_env_sobrescreve_user + comportamento de setup() |
| stdlib apenas (sem google-sheets) | sim | nenhum import externo em log.py |

### Scan de placeholders

Nenhum placeholder encontrado. Todos os steps têm código completo e comandos exatos.

### Consistência de nomes e tipos

- `_JediFormatter` — PascalCase (classe interna com underscore de módulo privado) ✓
- `_execution_id` — ContextVar com tipo `str | None`, default `None` ✓
- `_actor`, `_actor_kind`, `_service`, `_service_version` — estado global de módulo com prefixo `_` ✓
- `_LOG_RECORD_ATTRS` — `frozenset[str]`, UPPER_SNAKE_CASE ✓
- `setup()`, `set_execution_id()`, `clear_execution_id()` — snake_case, API pública ✓
- `entry: dict[str, Any]` — tipagem explícita ✓
- Imports: `from jedi_library import log` e `from jedi_library.log import _JediFormatter` ✓

### Gaps não cobertos (fora do escopo deste plano)

- `USER` env como fallback de último recurso (testado indiretamente; não há teste isolado — aceitável pois a lógica `or os.environ.get("USER") or "unknown"` é trivial)
- `actor_kind` com valor `None` no parâmetro: cai em `"unknown"` via `or` ✓ (comportamento correto, não precisa de teste adicional)
