---
id: 202606121930
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/assets.py com pkg_files() wrapper sobre importlib.resources"
tags: [tarefa, python, assets, importlib, resources, pipx]
---

# Tarefa — Implementação de `jedi_library.assets`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-assets-criacao.md`.

Resolve cicatriz pipx do tili (Fase 2) e padroniza acesso a resources packaged.

## Entregáveis

### `jedi_library/assets.py`

```python
import importlib.resources
from pathlib import Path

def pkg_files(package: str, resource: str) -> Path:
    """Retorna Path para resource dentro de um pacote instalado (pipx-safe)."""
    return importlib.resources.files(package).joinpath(resource)
```

### Testes (`test/python/test_assets.py`)

- `pkg_files("jedi_library", "sql")` retorna um `Path`.
- Path não levanta exceção ao ser construído (não precisa existir no teste).
- Verificar que o retorno é compatível com `open()`.

## Critérios de conclusão

- [ ] `assets.py` com `pkg_files`.
- [ ] Testes passando.
- [ ] `__init__.py` exporta `assets`.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-assets-criacao.md`.
