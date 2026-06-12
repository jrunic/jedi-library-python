---
id: 202606122000
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/audit.py com log_audit() fail-safe e schema SQL canônico de audit_log"
tags: [tarefa, python, audit, sqlite, rastreabilidade, fail-safe]
---

# Tarefa — Implementação de `jedi_library.audit`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-audit-criacao.md`.

**Dependências:** `jedi_library.db` (conexão) e `jedi_library.assets` (para schema SQL packaged).

Onda 2 — iniciar junto com `jedi_status_flow`.

## Entregáveis

### `jedi_library/sql/create_audit_log.sql`

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operacao TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    ts TEXT NOT NULL,
    origem TEXT
);
```

Este arquivo é um resource packaged — acessível via `pkg_files("jedi_library", "sql/create_audit_log.sql")`.

### `jedi_library/audit.py`

```python
import json
import logging
import sqlite3
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

def log_audit(
    conn: sqlite3.Connection,
    operacao: str,
    payload: dict,
    *,
    ts: datetime | None = None,
    origem: str | None = None,
) -> None:
    ts_str = (ts or datetime.now(tz=UTC)).isoformat()
    try:
        conn.execute(
            "INSERT INTO audit_log(operacao, payload_json, ts, origem) VALUES (?, ?, ?, ?)",
            (operacao, json.dumps(payload, ensure_ascii=False), ts_str, origem),
        )
    except Exception:
        logger.error("Falha ao registrar audit_log: operacao=%s", operacao, exc_info=True)
```

### Testes (`test/python/test_audit.py`)

- Conexão em memória + `CREATE TABLE audit_log ...` → `log_audit` insere corretamente.
- Campos `ts`, `operacao`, `payload_json`, `origem` verificados no SELECT.
- Falha de DB (tabela inexistente) → sem raise, erro logado.
- `ts=None` → usa `datetime.now(UTC)` (verificar que coluna não está vazia).

### `jedi_library/sql/__init__.py`

Arquivo vazio para que `jedi_library/sql/` seja reconhecido como package data por `importlib.resources`.

### `pyproject.toml`

Garantir que `jedi_library/sql/` é incluído como package data (se necessário com `[tool.setuptools.package-data]`).

## Critérios de conclusão

- [ ] `audit.py` com `log_audit` fail-safe.
- [ ] `sql/create_audit_log.sql` packaged e acessível via `pkg_files`.
- [ ] Testes passando incluindo caso de falha silenciosa.
- [ ] `__init__.py` exporta `audit`.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-audit-criacao.md`.
- Fontes doadoras: `jd-tasks/api/routes/audit.py`, `jd-tasks/api/crud.py::log_audit`.
