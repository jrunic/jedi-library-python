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
