---
id: 202606122210
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — implementar jedi_library.slug com normalize(), unique_slug() e normalize_unique()"
tags: [plano-execucao, python, slug, normalize, unicode]
spec: docs/11-tarefas/20260612-spec-jedi-slug.md
---

# jedi_library.slug — Plano de Implementação

**Objetivo:** Criar módulo com normalização de texto para slugs kebab-case e funções de unicidade.
**Arquitetura:** Pipeline NFKD→ASCII→lower→kebab; ContextVar não necessário; sem estado global.
**Pilha técnica:** Python 3.12, stdlib (unicodedata, re)

---

## Task 1 — normalize(), unique_slug(), normalize_unique()

**Arquivos:**
- criar `jedi_library/slug.py`
- criar `tests/test_slug.py`

### Step 1 — Escreve `tests/test_slug.py` completo

```python
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
```

### Step 2 — Roda testes → FAIL esperado

```bash
uv run pytest tests/test_slug.py -v
```

Output esperado: `ModuleNotFoundError` ou `ImportError` — `slug` não existe ainda.

### Step 3 — Cria `jedi_library/slug.py`

```python
import re
import unicodedata


def normalize(text: str, max_len: int = 0) -> str:
    if not text or not text.strip():
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii")
    lower = ascii_text.lower()
    slugged = re.sub(r"[^a-z0-9]+", "-", lower).strip("-")
    if not slugged:
        return ""
    if max_len > 0 and len(slugged) > max_len:
        truncated = slugged[:max_len]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            truncated = truncated[:last_hyphen]
        slugged = truncated.strip("-")
    return slugged


def unique_slug(text: str, existing: set[str]) -> str:
    base = normalize(text)
    if not base:
        return ""
    if base not in existing:
        return base
    counter = 2
    while True:
        candidate = f"{base}-{counter}"
        if candidate not in existing:
            return candidate
        counter += 1


def normalize_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = normalize(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
```

### Step 4 — Roda testes → PASS

```bash
uv run pytest tests/test_slug.py -v
```

Output esperado:

```
tests/test_slug.py::test_normalize_acento_cedilha PASSED
tests/test_slug.py::test_normalize_strip_espacos PASSED
tests/test_slug.py::test_normalize_maiusculas PASSED
tests/test_slug.py::test_normalize_vazio PASSED
tests/test_slug.py::test_normalize_so_espacos PASSED
tests/test_slug.py::test_normalize_sem_equivalente_ascii PASSED
tests/test_slug.py::test_normalize_max_len_corta_no_hifen PASSED
tests/test_slug.py::test_normalize_max_len_sem_hifen_usa_trecho PASSED
tests/test_slug.py::test_unique_slug_sem_colisao PASSED
tests/test_slug.py::test_unique_slug_colisao_simples PASSED
tests/test_slug.py::test_unique_slug_colisao_encadeada PASSED
tests/test_slug.py::test_unique_slug_input_degenerado PASSED
tests/test_slug.py::test_normalize_unique_deduplica PASSED
tests/test_slug.py::test_normalize_unique_preserva_ordem PASSED
tests/test_slug.py::test_normalize_unique_descarta_vazio PASSED
tests/test_slug.py::test_normalize_idempotente PASSED

16 passed in 0.XXs
```

### Step 5 — Commit

```bash
git add jedi_library/slug.py tests/test_slug.py
git commit -m "feat(slug): add normalize(), unique_slug(), normalize_unique() — NFKD pipeline"
```

---

## Task 2 — Re-exporta em `__init__.py`

**Arquivo:** modificar `jedi_library/__init__.py`

### Step 1 — Atualiza `__init__.py`

```python
from jedi_library import log, ai, slug

__all__ = ["log", "ai", "slug"]
```

### Step 2 — Verifica import via CLI

```bash
python -c "from jedi_library import slug; print(slug.normalize('Ação'))"
```

Output esperado: `acao`

### Step 3 — Roda suite completa → todos passing

```bash
uv run pytest tests/ -v
```

Output esperado: todos os testes existentes (log, ai, slug) passando sem regressão.

### Step 4 — Commit

```bash
git add jedi_library/__init__.py
git commit -m "feat(slug): re-exporta slug em jedi_library/__init__.py"
```

---

## Nota: critério das 91 tags de produção

A spec exige `normalize(tag) == tag` para as 91 tags reais do `jd-tasks`. Esse critério não entra aqui — `test_normalize_idempotente` cobre o invariante com amostras representativas. A validação contra as 91 tags reais ocorre na tarefa de migração do `jd-tasks` para usar `jedi_library.slug`, quando o consumidor pode carregar o dataset real e rodar o assertion como smoke test pré-migração. Registrado como dependência da tarefa `jedi-library-python → jd-tasks migration`.
