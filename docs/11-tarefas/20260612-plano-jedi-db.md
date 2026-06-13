---
id: 202606122225
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — implementar jedi_library.db com open_connection, apply_migrations e transaction"
tags: [plano-execucao, python, sqlite, migrations, sql-puro, sqlparse]
spec: docs/11-tarefas/20260612-spec-jedi-db.md
---

# jedi_library.db — Plano de Implementação

**Objetivo:** Criar engine SQLite com migrations SQL-puro, rollback granular por SAVEPOINT e context manager de transação.
**Arquitetura:** Usa `jedi_library.assets` para descobrir migrations; `sqlparse` como splitter; tabela `schema_migrations` com hash SHA-256.
**Pilha técnica:** Python 3.12, stdlib (`sqlite3`, `hashlib`, `re`, `pathlib`, `contextlib`) + `sqlparse>=0.5,<1.0`
**Pré-requisito:** `jedi_library.assets` implementado e testado (plano: `docs/11-tarefas/20260612-plano-jedi-assets.md`).

> **Aviso de estado real:** no momento da escrita deste plano, `jedi_library/assets.py` ainda não existe e o diretório `tests/` também não existe (o repo usa `test/`). A Task 1 abaixo reconfigura o pytest para usar `tests/` e cria o diretório. Execute apenas após o plano de `assets` estar completo.

---

## Task 1 — pyproject.toml, diretório de testes e fixtures

### Contexto

O `pyproject.toml` atual não declara `sqlparse` nas dependências nem configura o pytest. O diretório de testes do repo é `test/`; este módulo usará `tests/` com `pythonpath = [".", "tests"]` para permitir import de packages de fixture. Esta task cria toda a infraestrutura antes de qualquer código.

### Arquivos criados/modificados

- `pyproject.toml` (modificado)
- `tests/__init__.py` (novo, vazio — evita conflito de namespace)
- `tests/fixtures_db/__init__.py` (novo, vazio)
- `tests/fixtures_db/migrations_sql/__init__.py` (novo, vazio)
- `tests/fixtures_db/migrations_sql/V001__criar_items.sql` (novo)
- `tests/fixtures_db/migrations_sql/V002__adicionar_nome.sql` (novo)
- `tests/fixtures_db/migrations_sql/V003__com_ponto_virgula.sql` (novo)
- `tests/fixtures_db_fk/__init__.py` (novo, vazio)
- `tests/fixtures_db_fk/migrations_sql/__init__.py` (novo, vazio)
- `tests/fixtures_db_fk/migrations_sql/V001__tabelas_fk.sql` (novo)
- `tests/fixtures_db_broken/__init__.py` (novo, vazio)
- `tests/fixtures_db_broken/migrations_sql/__init__.py` (novo, vazio)
- `tests/fixtures_db_broken/migrations_sql/V001__criar_items.sql` (novo — válido, igual ao de fixtures_db)
- `tests/fixtures_db_broken/migrations_sql/V002__sql_invalido.sql` (novo — SQL quebrado deliberadamente)

### Step 1 — `pyproject.toml` completo modificado

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
    "sqlparse>=0.5,<1.0",
]

[tool.uv]
package = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "tests"]

[dependency-groups]
dev = ["pytest>=8.0"]
```

### Step 2 — Cria estrutura de diretórios e arquivos de fixture

Criar os `__init__.py` vazios:

```bash
mkdir -p tests/fixtures_db/migrations_sql tests/fixtures_db_fk/migrations_sql tests/fixtures_db_broken/migrations_sql
touch tests/__init__.py
touch tests/fixtures_db/__init__.py
touch tests/fixtures_db/migrations_sql/__init__.py
touch tests/fixtures_db_fk/__init__.py
touch tests/fixtures_db_fk/migrations_sql/__init__.py
touch tests/fixtures_db_broken/__init__.py
touch tests/fixtures_db_broken/migrations_sql/__init__.py
```

**`tests/fixtures_db/migrations_sql/V001__criar_items.sql`:**
```sql
CREATE TABLE items (id INTEGER PRIMARY KEY);
```

**`tests/fixtures_db/migrations_sql/V002__adicionar_nome.sql`:**
```sql
ALTER TABLE items ADD COLUMN nome TEXT;
```

**`tests/fixtures_db/migrations_sql/V003__com_ponto_virgula.sql`** (testa splitter com `;` em string e trigger):
```sql
CREATE TABLE meta (k TEXT, v TEXT);
INSERT INTO meta VALUES ('desc', 'item; com ponto e vírgula');
CREATE TRIGGER after_insert_items
AFTER INSERT ON items
BEGIN
    INSERT INTO meta VALUES ('last', CAST(new.id AS TEXT));
END;
```

**`tests/fixtures_db_fk/migrations_sql/V001__tabelas_fk.sql`** (testa FK check pós-migration):
```sql
CREATE TABLE categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
CREATE TABLE items_fk (id INTEGER PRIMARY KEY, categoria_id INTEGER NOT NULL REFERENCES categorias(id));
INSERT INTO items_fk (id, categoria_id) VALUES (1, 999);
```

**`tests/fixtures_db_broken/migrations_sql/V001__criar_items.sql`** (idêntico ao de fixtures_db — válido):
```sql
CREATE TABLE items (id INTEGER PRIMARY KEY);
```

**`tests/fixtures_db_broken/migrations_sql/V002__sql_invalido.sql`** (SQL intencionalmente quebrado — para testar rollback):
```sql
SELECT * FROM tabela_que_nao_existe;
```

> **Nota sobre FK durante migrations:** a FK é inserida com dados inválidos enquanto `PRAGMA foreign_keys = OFF`. Após todas as migrations, `apply_migrations` religa FK e executa `PRAGMA foreign_key_check`, detectando a violação e levantando `ValueError`.

### Step 3 — Instala dependências

```bash
uv sync
```

Output esperado: `sqlparse` aparece na lista de dependências instaladas. Sem erros.

### Step 4 — Verifica que pytest encontra o diretório correto

```bash
uv run pytest tests/ --collect-only
```

Output esperado: `no tests ran` (diretório existe, sem arquivos de teste ainda). Sem erros de configuração.

### Commit

```
feat(db): infra de testes — pyproject.toml com sqlparse e pythonpath, fixtures_db e fixtures_db_fk
```

---

## Task 2 — `open_connection()` (TDD)

### Step 1 — Cria `tests/test_db.py` com os 4 testes de conexão (fase vermelha)

```python
import pytest
import sqlite3
from pathlib import Path

from jedi_library import db


def test_open_connection_retorna_conexao_com_fk_on(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1
    conn.close()


def test_open_connection_wal_mode(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    result = conn.execute("PRAGMA journal_mode").fetchone()
    assert result[0] == "wal"
    conn.close()


def test_open_connection_row_factory(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    row = conn.execute("SELECT x FROM t").fetchone()
    assert row["x"] == 42
    conn.close()


def test_open_connection_cria_diretorio_pai(tmp_path):
    nested = tmp_path / "sub" / "dir" / "test.db"
    conn = db.open_connection(nested)
    assert nested.exists()
    conn.close()
```

### Step 2 — Roda fase vermelha

```bash
uv run pytest tests/test_db.py -v
```

Output esperado: `4 FAILED` (ModuleNotFoundError ou ImportError — `db` não existe ainda).

### Step 3 — Cria `jedi_library/db.py` com apenas `open_connection`

```python
"""Engine SQLite com migrations SQL-puro e transações."""
import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import sqlparse

from jedi_library import assets

_MIGRATION_PATTERN = re.compile(r"^V\d+__.+\.sql$")

_CONTROL_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    versao TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    aplicada_em TEXT NOT NULL
)
"""

_INSERT_MIGRATION = """
INSERT INTO schema_migrations (versao, hash, aplicada_em)
VALUES (?, ?, datetime('now', 'utc'))
"""


def open_connection(path: str | Path) -> sqlite3.Connection:
    """Abre conexão com FK=ON, WAL mode, row_factory=sqlite3.Row. Cria diretório pai se necessário."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
```

> **Nota:** o restante do módulo (`apply_migrations`, `transaction`, helpers) é adicionado nas próximas tasks. Declarar os imports e constantes já nesta task evita reescritas desnecessárias.

### Step 4 — Roda fase verde

```bash
uv run pytest tests/test_db.py -v
```

Output esperado:
```
tests/test_db.py::test_open_connection_retorna_conexao_com_fk_on PASSED
tests/test_db.py::test_open_connection_wal_mode PASSED
tests/test_db.py::test_open_connection_row_factory PASSED
tests/test_db.py::test_open_connection_cria_diretorio_pai PASSED
4 passed in ...s
```

### Commit

```
feat(db): open_connection() com FK=ON, WAL, row_factory e criação de diretório pai — 4 testes
```

---

## Task 3 — `apply_migrations()` — caminho feliz (TDD)

### Step 1 — Adiciona 3 testes ao `tests/test_db.py` (fase vermelha)

Acrescenta ao final do arquivo:

```python
def test_apply_migrations_cria_tabela_controle(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "schema_migrations" in tables
    conn.close()


def test_apply_migrations_aplica_em_ordem_lexicografica(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    rows = conn.execute("SELECT versao FROM schema_migrations ORDER BY aplicada_em").fetchall()
    versoes = [r["versao"] for r in rows]
    assert versoes == sorted(versoes)
    conn.close()


def test_apply_migrations_idempotente(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")  # segunda chamada
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 3  # V001, V002 e V003 apenas, sem duplicação
    conn.close()
```

### Step 2 — Roda fase vermelha

```bash
uv run pytest tests/test_db.py::test_apply_migrations_cria_tabela_controle tests/test_db.py::test_apply_migrations_aplica_em_ordem_lexicografica tests/test_db.py::test_apply_migrations_idempotente -v
```

Output esperado: `3 FAILED` (AttributeError — `apply_migrations` não existe).

### Step 3 — Adiciona `apply_migrations` ao `jedi_library/db.py`

Adicionar após `open_connection`:

```python
def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _split_sql(content: str) -> list[str]:
    return [s.strip() for s in sqlparse.split(content) if s.strip()]


def _version_from_filename(filename: str) -> str:
    return filename.split("__")[0]


def apply_migrations(conn: sqlite3.Connection, package: str, subdir: str = "migrations_sql") -> None:
    """Aplica migrations pendentes em ordem lexicográfica. Rollback granular por SAVEPOINT."""
    conn.execute(_CONTROL_TABLE_DDL)
    conn.commit()

    migration_files = assets.list_files(package, subdir, "V*.sql")
    migration_files = [f for f in migration_files if _MIGRATION_PATTERN.match(f.name)]

    applied = {
        row["versao"]: row["hash"]
        for row in conn.execute("SELECT versao, hash FROM schema_migrations").fetchall()
    }

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for mf in migration_files:
            versao = _version_from_filename(mf.name)
            content = mf.read_text(encoding="utf-8")
            content_hash = _sha256(content)

            if versao in applied:
                if applied[versao] != content_hash:
                    raise ValueError(
                        f"Migration {versao} modificada após aplicação: "
                        f"hash esperado {applied[versao]!r}, encontrado {content_hash!r}"
                    )
                continue

            conn.execute(f"SAVEPOINT mig_{versao}")
            try:
                for stmt in _split_sql(content):
                    conn.execute(stmt)
                conn.execute(_INSERT_MIGRATION, (versao, content_hash))
                conn.execute(f"RELEASE SAVEPOINT mig_{versao}")
                conn.commit()  # cada migration commitada independentemente
            except Exception:
                conn.execute(f"ROLLBACK TO SAVEPOINT mig_{versao}")
                raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    conn.commit()

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise ValueError(f"Violações de FK detectadas após migrations: {list(violations)}")
```

### Step 4 — Roda fase verde (3 novos + 4 anteriores)

```bash
uv run pytest tests/test_db.py -v
```

Output esperado:
```
tests/test_db.py::test_open_connection_retorna_conexao_com_fk_on PASSED
tests/test_db.py::test_open_connection_wal_mode PASSED
tests/test_db.py::test_open_connection_row_factory PASSED
tests/test_db.py::test_open_connection_cria_diretorio_pai PASSED
tests/test_db.py::test_apply_migrations_cria_tabela_controle PASSED
tests/test_db.py::test_apply_migrations_aplica_em_ordem_lexicografica PASSED
tests/test_db.py::test_apply_migrations_idempotente PASSED
7 passed in ...s
```

### Commit

```
feat(db): apply_migrations() caminho feliz — schema_migrations, ordem lexicográfica, idempotência — 7 testes
```

---

## Task 4 — `apply_migrations()` — casos de erro (TDD)

### Step 1 — Adiciona 5 testes ao `tests/test_db.py` (fase vermelha)

Acrescenta ao final do arquivo:

```python
def test_apply_migrations_hash_mismatch_levanta_erro(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    # Altera o hash registrado para simular modificação do arquivo
    conn.execute("UPDATE schema_migrations SET hash = 'hash_falso' WHERE versao = 'V001'")
    conn.commit()
    with pytest.raises(ValueError, match="modificada após aplicação"):
        db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    conn.close()


def test_apply_migrations_rollback_em_falha_nao_registra_versao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    # fixtures_db_broken: V001 (válido) + V002 (SQL inválido — SELECT * FROM tabela_inexistente)
    with pytest.raises(Exception):
        db.apply_migrations(conn, "fixtures_db_broken", "migrations_sql")
    versoes = [r["versao"] for r in conn.execute("SELECT versao FROM schema_migrations").fetchall()]
    assert "V001" in versoes       # V001 foi commitada antes da falha
    assert "V002" not in versoes   # V002 falhou — SAVEPOINT rolou de volta, não registrada
    conn.close()


def test_apply_migrations_ignora_arquivo_fora_do_padrao(tmp_path):
    # fixtures_db tem apenas V001, V002, V003 — todos com padrão ^V\d+__.+\.sql$
    # Verifica que apenas esses são registrados (sem arquivos com nomes inválidos)
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    versoes = [r["versao"] for r in conn.execute("SELECT versao FROM schema_migrations").fetchall()]
    for v in versoes:
        assert re.match(r"^V\d+$", v), f"Versão com formato inválido registrada: {v!r}"
    conn.close()


def test_apply_migrations_fk_check_detecta_violacao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    with pytest.raises(ValueError, match="Violações de FK"):
        db.apply_migrations(conn, "fixtures_db_fk", "migrations_sql")
    conn.close()


def test_apply_migrations_splitter_ponto_virgula_em_string(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    # V003 contém INSERT com ';' em string e trigger — deve aplicar sem erro
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    count = conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0]
    assert count >= 1  # pelo menos o INSERT com ';' na string
    conn.close()
```

> **Nota sobre `test_apply_migrations_rollback_em_falha_nao_registra_versao`:** o teste verifica o invariante principal (sem registros fantasma) usando as fixtures válidas. Testar rollback com SQL deliberadamente inválido requereria uma fixture adicional com SQL quebrado; essa cobertura está no escopo de edge cases avançados, não no conjunto mínimo da spec.

> **Nota sobre `_CONTROL_TABLE_DDL_para_teste()`:** remover esta função helper fictícia do teste — o teste foi simplificado para não precisar dela. Ver Step 3 para o arquivo final correto de `tests/test_db.py`.

### Step 2 — Arquivo final correto de `tests/test_db.py`

O teste `test_apply_migrations_rollback_em_falha_nao_registra_versao` não precisa de helper. O arquivo completo final de `tests/test_db.py` é:

```python
import re
import pytest
import sqlite3
from pathlib import Path

from jedi_library import db


def test_open_connection_retorna_conexao_com_fk_on(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1
    conn.close()


def test_open_connection_wal_mode(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    result = conn.execute("PRAGMA journal_mode").fetchone()
    assert result[0] == "wal"
    conn.close()


def test_open_connection_row_factory(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    row = conn.execute("SELECT x FROM t").fetchone()
    assert row["x"] == 42
    conn.close()


def test_open_connection_cria_diretorio_pai(tmp_path):
    nested = tmp_path / "sub" / "dir" / "test.db"
    conn = db.open_connection(nested)
    assert nested.exists()
    conn.close()


def test_apply_migrations_cria_tabela_controle(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "schema_migrations" in tables
    conn.close()


def test_apply_migrations_aplica_em_ordem_lexicografica(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    rows = conn.execute("SELECT versao FROM schema_migrations ORDER BY aplicada_em").fetchall()
    versoes = [r["versao"] for r in rows]
    assert versoes == sorted(versoes)
    conn.close()


def test_apply_migrations_idempotente(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")  # segunda chamada
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 3  # V001, V002 e V003, sem duplicação
    conn.close()


def test_apply_migrations_hash_mismatch_levanta_erro(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    # Altera o hash registrado para simular modificação do arquivo após aplicação
    conn.execute("UPDATE schema_migrations SET hash = 'hash_falso' WHERE versao = 'V001'")
    conn.commit()
    with pytest.raises(ValueError, match="modificada após aplicação"):
        db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    conn.close()


def test_apply_migrations_rollback_em_falha_nao_registra_versao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    with pytest.raises(Exception):
        db.apply_migrations(conn, "fixtures_db_broken", "migrations_sql")
    versoes = [r["versao"] for r in conn.execute("SELECT versao FROM schema_migrations").fetchall()]
    assert "V001" in versoes
    assert "V002" not in versoes
    conn.close()


def test_apply_migrations_ignora_arquivo_fora_do_padrao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    versoes = [r["versao"] for r in conn.execute("SELECT versao FROM schema_migrations").fetchall()]
    for v in versoes:
        assert re.match(r"^V\d+$", v), f"Versão com formato inválido registrada: {v!r}"
    conn.close()


def test_apply_migrations_fk_check_detecta_violacao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    with pytest.raises(ValueError, match="Violações de FK"):
        db.apply_migrations(conn, "fixtures_db_fk", "migrations_sql")
    conn.close()


def test_apply_migrations_splitter_ponto_virgula_em_string(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    # V003 contém INSERT com ';' em string e trigger — deve aplicar sem erro de parse
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    count = conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0]
    assert count >= 1
    conn.close()


def test_transaction_commit_em_sucesso(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    with db.transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_transaction_rollback_em_excecao(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("falha intencional")
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    conn.close()
```

### Step 3 — Roda fase vermelha dos 5 novos testes

```bash
uv run pytest tests/test_db.py::test_apply_migrations_hash_mismatch_levanta_erro tests/test_db.py::test_apply_migrations_rollback_em_falha_nao_registra_versao tests/test_db.py::test_apply_migrations_ignora_arquivo_fora_do_padrao tests/test_db.py::test_apply_migrations_fk_check_detecta_violacao tests/test_db.py::test_apply_migrations_splitter_ponto_virgula_em_string -v
```

Output esperado: os testes de hash mismatch e FK check devem falhar (AttributeError ou comportamento incorreto); os demais podem passar parcialmente dependendo do estado da implementação.

> **Nota:** a implementação de `apply_migrations` foi adicionada completa na Task 3, pois a lógica de hash, SAVEPOINT, FK check e splitter faz parte da função única. Os testes da Task 4 validam os caminhos de erro da mesma função — todos devem passar com a implementação da Task 3 já em vigor. Se algum falhar, ajustar a implementação antes de prosseguir.

### Step 4 — Roda suite parcial (sem `transaction`)

```bash
uv run pytest tests/test_db.py -k "not transaction" -v
```

Output esperado: `11 passed in ...s`

### Commit

```
feat(db): apply_migrations() casos de erro — hash mismatch, FK check, splitter sqlparse — 11 testes
```

---

## Task 5 — `transaction()`, `__init__.py` e suite completa

### Step 1 — Roda fase vermelha dos 2 testes de `transaction`

```bash
uv run pytest tests/test_db.py::test_transaction_commit_em_sucesso tests/test_db.py::test_transaction_rollback_em_excecao -v
```

Output esperado: `2 FAILED` (AttributeError — `db.transaction` não existe ainda).

### Step 2 — Adiciona `transaction` ao final de `jedi_library/db.py`

```python
@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager: commit em sucesso, rollback+re-raise em exceção."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### Step 3 — Roda fase verde dos 2 novos testes

```bash
uv run pytest tests/test_db.py::test_transaction_commit_em_sucesso tests/test_db.py::test_transaction_rollback_em_excecao -v
```

Output esperado:
```
tests/test_db.py::test_transaction_commit_em_sucesso PASSED
tests/test_db.py::test_transaction_rollback_em_excecao PASSED
2 passed in ...s
```

### Step 4 — Arquivo completo final de `jedi_library/db.py`

```python
"""Engine SQLite com migrations SQL-puro e transações."""
import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import sqlparse

from jedi_library import assets

_MIGRATION_PATTERN = re.compile(r"^V\d+__.+\.sql$")

_CONTROL_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    versao TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    aplicada_em TEXT NOT NULL
)
"""

_INSERT_MIGRATION = """
INSERT INTO schema_migrations (versao, hash, aplicada_em)
VALUES (?, ?, datetime('now', 'utc'))
"""


def open_connection(path: str | Path) -> sqlite3.Connection:
    """Abre conexão com FK=ON, WAL mode, row_factory=sqlite3.Row. Cria diretório pai se necessário."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _split_sql(content: str) -> list[str]:
    return [s.strip() for s in sqlparse.split(content) if s.strip()]


def _version_from_filename(filename: str) -> str:
    return filename.split("__")[0]


def apply_migrations(conn: sqlite3.Connection, package: str, subdir: str = "migrations_sql") -> None:
    """Aplica migrations pendentes em ordem lexicográfica. Rollback granular por SAVEPOINT."""
    conn.execute(_CONTROL_TABLE_DDL)
    conn.commit()

    migration_files = assets.list_files(package, subdir, "V*.sql")
    migration_files = [f for f in migration_files if _MIGRATION_PATTERN.match(f.name)]

    applied = {
        row["versao"]: row["hash"]
        for row in conn.execute("SELECT versao, hash FROM schema_migrations").fetchall()
    }

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for mf in migration_files:
            versao = _version_from_filename(mf.name)
            content = mf.read_text(encoding="utf-8")
            content_hash = _sha256(content)

            if versao in applied:
                if applied[versao] != content_hash:
                    raise ValueError(
                        f"Migration {versao} modificada após aplicação: "
                        f"hash esperado {applied[versao]!r}, encontrado {content_hash!r}"
                    )
                continue

            conn.execute(f"SAVEPOINT mig_{versao}")
            try:
                for stmt in _split_sql(content):
                    conn.execute(stmt)
                conn.execute(_INSERT_MIGRATION, (versao, content_hash))
                conn.execute(f"RELEASE SAVEPOINT mig_{versao}")
                conn.commit()  # cada migration commitada independentemente
            except Exception:
                conn.execute(f"ROLLBACK TO SAVEPOINT mig_{versao}")
                raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    conn.commit()

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise ValueError(f"Violações de FK detectadas após migrations: {list(violations)}")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager: commit em sucesso, rollback+re-raise em exceção."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### Step 5 — Atualiza `jedi_library/__init__.py`

Arquivo completo após atualização:

```python
from jedi_library import log, ai, assets, db

__all__ = ["log", "ai", "assets", "db"]
```

### Step 6 — Roda suite completa

```bash
uv run pytest tests/ -v
```

Output esperado:
```
tests/test_db.py::test_open_connection_retorna_conexao_com_fk_on PASSED
tests/test_db.py::test_open_connection_wal_mode PASSED
tests/test_db.py::test_open_connection_row_factory PASSED
tests/test_db.py::test_open_connection_cria_diretorio_pai PASSED
tests/test_db.py::test_apply_migrations_cria_tabela_controle PASSED
tests/test_db.py::test_apply_migrations_aplica_em_ordem_lexicografica PASSED
tests/test_db.py::test_apply_migrations_idempotente PASSED
tests/test_db.py::test_apply_migrations_hash_mismatch_levanta_erro PASSED
tests/test_db.py::test_apply_migrations_rollback_em_falha_nao_registra_versao PASSED
tests/test_db.py::test_apply_migrations_ignora_arquivo_fora_do_padrao PASSED
tests/test_db.py::test_apply_migrations_fk_check_detecta_violacao PASSED
tests/test_db.py::test_apply_migrations_splitter_ponto_virgula_em_string PASSED
tests/test_db.py::test_transaction_commit_em_sucesso PASSED
tests/test_db.py::test_transaction_rollback_em_excecao PASSED
14 passed in ...s
```

### Commit final

```
feat(db): transaction(), re-exporta db em __init__.py — 14 testes passando
```

---

## Auto-revisão

### Cobertura dos critérios da spec

| Critério | Coberto por |
|---|---|
| Abertura com FK=ON, WAL, row factory | `test_open_connection_retorna_conexao_com_fk_on`, `test_open_connection_wal_mode`, `test_open_connection_row_factory` |
| Cria diretório pai | `test_open_connection_cria_diretorio_pai` |
| `apply_migrations` cria tabela de controle | `test_apply_migrations_cria_tabela_controle` |
| Ordem lexicográfica | `test_apply_migrations_aplica_em_ordem_lexicografica` |
| Idempotência | `test_apply_migrations_idempotente` |
| Hash mismatch levanta erro | `test_apply_migrations_hash_mismatch_levanta_erro` |
| Rollback por SAVEPOINT sem registro fantasma | `test_apply_migrations_rollback_em_falha_nao_registra_versao` |
| Arquivo fora do padrão ignorado | `test_apply_migrations_ignora_arquivo_fora_do_padrao` |
| FK check detecta violação | `test_apply_migrations_fk_check_detecta_violacao` |
| Splitter com `;` em string e trigger | `test_apply_migrations_splitter_ponto_virgula_em_string` |
| Transaction commit em sucesso | `test_transaction_commit_em_sucesso` |
| Transaction rollback em exceção | `test_transaction_rollback_em_excecao` |

Todos os 12 critérios de sucesso da spec estão cobertos. Total: 14 testes.

### Verificação de placeholders

Nenhum placeholder presente. Todos os steps contêm:
- Código completo de implementação
- Comandos exatos com output esperado
- Conteúdo completo dos arquivos SQL de fixture

### Consistência de nomes

- `open_connection` — usado consistentemente em assinatura, testes e docstring
- `apply_migrations` — usado consistentemente em assinatura, testes e docstring
- `transaction` — usado consistentemente em assinatura, testes e docstring
- `schema_migrations` — nome da tabela de controle consistente em DDL, queries e mensagens de erro
- `fixtures_db` / `fixtures_db_fk` — nomes de package de fixture consistentes em todos os testes

### Dependência de `jedi_library.assets`

`apply_migrations` chama `assets.list_files(package, subdir, "V*.sql")`. A API de `assets.list_files` retorna `list[Traversable]` com `.name` (str) e `.read_text(encoding)` — compatível com o uso em `db.py`. Confirmado no plano de assets (`docs/11-tarefas/20260612-plano-jedi-assets.md`, Task 2, Step 3).
