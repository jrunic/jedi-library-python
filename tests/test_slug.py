from jedi_library import slug


def test_normalize_acento_cedilha():
    assert slug.normalize("Ação Rápida") == "acao-rapida"


def test_normalize_strip_espacos():
    assert slug.normalize("  olá, mundo!  ") == "ola-mundo"


def test_normalize_maiusculas():
    assert slug.normalize("HELLO WORLD") == "hello-world"


def test_normalize_vazio():
    assert slug.normalize("") == ""


def test_normalize_so_espacos():
    assert slug.normalize("   ") == ""


def test_normalize_sem_equivalente_ascii():
    assert slug.normalize("★") == ""


def test_normalize_max_len_corta_no_hifen():
    result = slug.normalize("palavra-longa-aqui-mais-texto", max_len=15)
    assert len(result) <= 15
    assert not result.endswith("-")
    assert not result.startswith("-")


def test_normalize_max_len_sem_hifen_usa_trecho():
    result = slug.normalize("abcdefghijklmno", max_len=5)
    assert len(result) <= 5


def test_unique_slug_sem_colisao():
    assert slug.unique_slug("tarefa", {"outra"}) == "tarefa"


def test_unique_slug_colisao_simples():
    assert slug.unique_slug("tarefa", {"tarefa"}) == "tarefa-2"


def test_unique_slug_colisao_encadeada():
    assert slug.unique_slug("tarefa", {"tarefa", "tarefa-2"}) == "tarefa-3"


def test_unique_slug_input_degenerado():
    assert slug.unique_slug("★", set()) == ""


def test_normalize_unique_deduplica():
    result = slug.normalize_unique(["Financeiro", "FINANCEIRO", "Farmácia", "financeiro"])
    assert result == ["financeiro", "farmacia"]


def test_normalize_unique_preserva_ordem():
    assert slug.normalize_unique(["B", "A", "C"]) == ["b", "a", "c"]


def test_normalize_unique_descarta_vazio():
    result = slug.normalize_unique(["★", "valido", ""])
    assert result == ["valido"]


def test_normalize_idempotente():
    slugs = ["financeiro", "farmacia", "tarefa-importante", "contas-a-pagar"]
    for s in slugs:
        assert slug.normalize(s) == s
