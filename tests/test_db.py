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
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 3  # V001, V002, V003
    conn.close()


def test_apply_migrations_hash_mismatch_levanta_erro(tmp_path):
    conn = db.open_connection(tmp_path / "test.db")
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
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
    db.apply_migrations(conn, "fixtures_db", "migrations_sql")
    count = conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0]
    assert count >= 1
    conn.close()
