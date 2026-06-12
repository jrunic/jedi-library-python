---
id: 202606121602
projeto: jedi-library-python
tipo: contexto
status: ativo
escopo: repo:jedi-library-python
plataforma: "*"
descricao: "Escopo e restrições do repositório jedi-library-python — implementações Python 3.12"
tags: [contexto, library, python, jedi-labs]
---

# CONTEXTO.md

## Propósito

Implementações Python 3.12 das bibliotecas Jedi Labs — package único `jedi_library` com submódulos. Consumidores instalam via `uv add git+ssh://github.com/jrunic/jedi-library-python.git`. Governança e conceito das libs vivem em `jedi-library` (repo agnóstico).

## Modo de Atuação

Modo Código — biblioteca Python com API estável. Mudanças que quebram consumidores exigem bump de versão no `pyproject.toml` e `uv lock --upgrade-package jedi-library` nos consumidores.

## Agente padrão

Tech (SRE).

## Convenções Python

### Nomenclatura

- **Funções e variáveis:** `snake_case`
- **Estado privado de módulo:** prefixo `_` (ex: `_buffer`, `_log_level`)
- **Constantes:** `UPPER_SNAKE_CASE`
- **Classes/Enums:** `PascalCase`

### Estrutura do package

```
jedi_library/
├── __init__.py      # re-exporta submódulos
├── log.py           # port do jediLog GAS
├── ai.py            # port do jediAI GAS (Vertex AI)
└── <futuros>        # db.py, slug.py, assets.py... (Onda 1+)
```

Convenção de import: sempre `from jedi_library import log` ou `from jedi_library import ai` — nunca `import jedi_log` direto.

### Pin de versão

- `requires-python = ">=3.12,<3.13"` — alinhado com pin da frota (ADR `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260511-versoes-fixas-runtime-frota.md`).
- `.venv` criado com `uv venv --python 3.12`.

### Autenticação

- Nunca hardcodar credenciais no código.
- Prioridade: `GOOGLE_CREDENTIALS_FILE` (Service Account JSON) → ADC (`google.auth.default()`).
- Credenciais vivem em `~/.config/jedi-secrets/<projeto>/google-credentials.json`.

### Logging

- Contexto é automaticamente prefixado com `python:` — não adicionar manualmente.
- `userEmail` é resolvido do Service Account ou da conta ADC; não forçar valor.
- Fallback: buffer gravado em disco quando flush para Sheets falha (env `JEDI_LOG_FALLBACK_DIR`).

### Migrations (`jedi_library.db`)

- Arquivos SQL puro: `migrations_sql/V001-descricao.sql`, `V002-...sql` (ordem alfabética determina aplicação).
- Tabela `schema_migrations(versao TEXT, hash TEXT, aplicada_em TEXT)` — não `PRAGMA user_version`.
- Engine recusa pulos de versão (V001 → V003 sem V002).
- Ver ADR `docs/81-referencia/decisoes/20260612-engine-migrations-sql-puro-tabela-schema.md`.

### Distribuição

- Consumidores instalam via `uv add 'jedi-library @ git+ssh://git@github.com/jrunic/jedi-library-python.git'`.
- Pinning automático via `uv.lock` (commit SHA gravado).
- Upgrade consciente: `uv lock --upgrade-package jedi-library`.
- Ver ADR `docs/81-referencia/decisoes/20260612-distribuicao-python-via-git-ssh.md`.

## Regra de 2 consumidores reais

Novos submódulos entram quando há 2 consumidores reais. Exceção registrada para libs já maduras em GAS com adoção iminente. Ver ADR em `jedi-library/docs/81-referencia/decisoes/20260612-regra-de-2-consumidores-reais.md`.

## Referências

- Conceito das libs e governança cross-language: `jedi-library/CONTEXTO.md`
- Implementações GAS: `jedi-library-gas/CONTEXTO.md`
- ADR de split: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260612-jedi-library-trio-repos.md`
- ADR de pin Python da frota: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260511-versoes-fixas-runtime-frota.md`
