---
id: 202606121930
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/assets.py com read_text() e list_files() sobre importlib.resources"
tags: [tarefa, python, assets, importlib, resources, pipx]
---

# Tarefa — Implementação de `jedi_library.assets`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-assets-criacao.md`.

Wrapper canônico da frota sobre `importlib.resources`. Resolve cicatriz pipx do tili (Fase 2) e viabiliza `jedi_db`.

## Entregáveis

### `jedi_library/assets.py`

```python
import importlib.resources
from fnmatch import fnmatch
from importlib.resources.abc import Traversable


def read_text(
    package: str,
    resource: str,
    *,
    encoding: str = "utf-8",
) -> str:
    """Lê recurso empacotado como texto.

    Exemplos:
        read_text("tili.infra.db.migrations_sql", "V001__init.sql")
        read_text("jedi_library", "templates/prompt.md")
    """
    return (
        importlib.resources.files(package)
        .joinpath(resource)
        .read_text(encoding=encoding)
    )


def list_files(
    package: str,
    subdir: str,
    pattern: str = "*",
) -> list[Traversable]:
    """Lista arquivos em subdir do package que casam com pattern (fnmatch).
    Ordem lexicográfica do nome.

    Exemplo:
        for f in list_files("tili.infra.db.migrations_sql", ".", "V*.sql"):
            sql = f.read_text(encoding="utf-8")
    """
    root = importlib.resources.files(package).joinpath(subdir)
    return sorted(
        (f for f in root.iterdir() if f.is_file() and fnmatch(f.name, pattern)),
        key=lambda f: f.name,
    )
```

### Testes (`test/python/test_assets.py`)

- `read_text("jedi_library", "sql/test_fixture.sql")` retorna conteúdo esperado (criar fixture).
- `list_files("jedi_library", "sql", "*.sql")` retorna lista ordenada.
- Pattern `"V*.sql"` filtra corretamente.
- Encoding `utf-8` é honrado (criar fixture com caracteres acentuados).

### Documentação no CONTEXTO.md do repo

Adicionar ao `CONTEXTO.md` do `jedi-library-python`:

> ### Packaging de recursos no consumidor
>
> Para que `jedi_assets.read_text` / `list_files` enxerguem arquivos `.sql` / templates dentro do package, o consumidor deve declarar em seu `pyproject.toml`:
>
> ```toml
> [tool.setuptools.package-data]
> "<nome_do_package>" = ["migrations/*.sql", "templates/*.md"]
> ```
>
> Funciona em editable + sem declaração; quebra em wheel/pipx sem ela.

## Critérios de conclusão

- [ ] `assets.py` com 2 funções.
- [ ] Testes passando.
- [ ] `__init__.py` exporta `assets`.
- [ ] CONTEXTO.md do repo documenta packaging do consumidor.
- [ ] PR referencia ADR.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-assets-criacao.md`.
- Dependência downstream: `jedi_db.apply_migrations` consome `list_files`.
