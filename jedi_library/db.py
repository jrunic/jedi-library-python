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
