---
descricao: ADR — distribuição do jedi-library-python via `uv add git+ssh://...` direto do GitHub, package único `jedi_library` com submódulos; sem wheel/PyPI até demanda real
id: 202606121530
projeto: jedi-library-python
tipo: decisao
status: aceito
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
tags: [adr, jedi-library-python, distribuicao, uv, pinning, pacote]
---

# Distribuição de `jedi-library-python` via `uv add git+ssh` + package único

## Contexto

O split da `jedi-library` em três repos (decidido na sabatina de 2026-06-12) cria o repo `jedi-library-python` como package Python standalone. Pendência D4 do inventário era exatamente como consumidores instalam.

Três caminhos foram considerados:

- **Submódulo git + `pip install -e ./submodule`** — funcionou para GAS (clasp não exige instalação Python); para Python, é desconfortável e foi exatamente onde o port adormeceu (jedi-etl criou `jedi_logger` local em vez de instalar o submódulo).
- **`uv add git+ssh://...`** — uv resolve direto do GitHub; pinning automático via `uv.lock` (commit SHA gravado).
- **Wheel local + registry interno** — release explícito com semver; exige rotina de build/publish (overkill agora).

## Decisão

**Consumidores Python instalam via `uv add 'jedi-library @ git+ssh://git@github.com/jrunic/jedi-library-python.git'`.**

- `jedi-library-python` tem `pyproject.toml` na raiz (não em subdiretório — repo é o próprio package).
- Expõe **package único `jedi_library`** com submódulos: `from jedi_library import log; log.info(...)`. Não múltiplos packages independentes.
- Pinning fica no `uv.lock` do consumidor — commit SHA exato gravado automaticamente.
- Upgrade é ato consciente: `uv lock --upgrade-package jedi-library`.
- `requires-python = ">=3.12,<3.13"` no `pyproject.toml`, alinhado com pin da frota (ADR `20260511-versoes-fixas-runtime-frota.md`).

## Alternativas consideradas

- **Submódulo git + pip editable** — rejeitada. Histórico do port `jedi_log.py` adormecido prova que o atrito de submódulo Python afasta adoção. jedi-etl preferiu reimplementar `jedi_logger` local a usar o submódulo.
- **Wheel local + `uv add --find-links=file://...`** — rejeitada. Exige rotina de build/publish para 1 lib hoje (`log`) + 3 candidatas na Onda 1 (`slug`, `assets`, `db`). Custo > benefício.
- **PyPI privado (TestPyPI ou self-hosted)** — rejeitada. Overkill para escala atual.
- **Múltiplos packages no mesmo repo** — rejeitada. Package único com submódulos é trivial via `uv add jedi-library` que cobre tudo.

## Consequências

- Consumidores Python precisam de SSH key configurada no host onde `uv sync` roda. Hoje todos os hosts Jedi Labs têm — sem problema.
- Releases são identificadas por commit SHA enquanto não houver semver tag. Quando demanda real exigir versionamento explícito, criar tag + bump no `pyproject.toml` é caminho aditivo, não breaking.
- Convenção de import: sempre `from jedi_library import <submodulo>`, nunca `import jedi_log` direto.

## Referências

- ADR de split: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260612-jedi-library-trio-repos.md`.
- ADR de regra de 2 consumidores: `jedi-library/docs/81-referencia/decisoes/20260612-regra-de-2-consumidores-reais.md`.
- ADR de pin Python da frota: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260511-versoes-fixas-runtime-frota.md`.
