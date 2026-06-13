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
