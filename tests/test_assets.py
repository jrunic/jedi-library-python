from jedi_library import assets


def test_read_text_retorna_conteudo():
    content = assets.read_text("jedi_library._fixtures", "textos.txt")
    assert "Olá" in content


def test_read_text_utf8_acentos():
    content = assets.read_text("jedi_library._fixtures", "textos.txt")
    assert "ã" in content


def test_list_files_retorna_ordenado_lexicograficamente():
    result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
    names = [f.name for f in result]
    assert names == sorted(names)


def test_list_files_filtra_por_padrao_sql():
    result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
    for f in result:
        assert f.name.endswith(".sql")


def test_list_files_exclui_nao_casados():
    all_files = assets.list_files("jedi_library._fixtures", "sql", "*")
    sql_files = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
    all_names = {f.name for f in all_files}
    sql_names = {f.name for f in sql_files}
    assert "nota.txt" in all_names
    assert "nota.txt" not in sql_names


def test_list_files_conteudo_legivel():
    result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
    assert len(result) == 2
    content = result[0].read_text(encoding="utf-8")
    assert "CREATE TABLE" in content
