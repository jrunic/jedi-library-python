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
├── __init__.py        # re-exporta submódulos
├── log.py             # logging JSON estruturado em stdout
├── ai.py              # Vertex AI (Gemini) — classe JediAI
├── datetime_utils.py  # constantes TZ e funções TZ-explícitas
├── slug.py            # normalização NFKD + unicidade
├── status_flow.py     # StateMachine de transições
├── assets.py          # importlib.resources wrapper
├── db.py              # engine SQLite com migrations SQL-puro
├── utils.py           # utilitários de string (prepare_prompt)
└── _fixtures/         # fixture interna para testes de assets/db
```

Convenção de import: sempre `from jedi_library import log` — nunca `import jedi_log` direto.

### Pin de versão

- `requires-python = ">=3.12,<3.13"` — alinhado com pin da frota (ADR `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260511-versoes-fixas-runtime-frota.md`).
- `.venv` criado com `uv venv --python 3.12`.

### Autenticação

- Nunca hardcodar credenciais no código.
- Credenciais são sempre passadas explicitamente ao construtor `JediAI` — sem fallback para ADC implícito.
- Caminho primário: `JediAI.from_service_account_file(path, project=...)` com SA JSON.
- Conveniência single-tenant: `JediAI.from_env()` lê `GOOGLE_APPLICATION_CREDENTIALS` + `JEDI_AI_GCP_PROJECT_ID`. Suporta SA JSON, authorized user e workload identity via `google.auth.load_credentials_from_file`.
- Naming e path dos arquivos de credenciais são responsabilidade do `jd-secrets` — não da lib.

### Logging

- Backend: JSON estruturado em stdout, uma linha por evento. Sem Google Sheets.
- Setup único no bootstrap: `log.setup(actor="nome", actor_kind="service", service="app", service_version="1.0")`.
- Consumidores usam stdlib logging normalmente após setup: `logging.getLogger(__name__).info("msg", extra={...})`.
- Correlação de runs: `log.set_execution_id(eid)` / `log.clear_execution_id()` — ContextVar, thread-safe.
- Resolução de actor: parâmetro → `JEDI_LOG_ACTOR` env → `USER` env → `"unknown"`.

### Migrations (`jedi_library.db`)

- Arquivos SQL puro: `migrations_sql/V001__descricao.sql` (separador duplo underline `__`).
- Ordem lexicográfica por nome de arquivo; versão = prefixo antes do `__` (ex: `"V001"`).
- Tabela `schema_migrations(versao TEXT PRIMARY KEY, hash TEXT, aplicada_em TEXT)` — não `PRAGMA user_version`.
- Cada migration commitada independentemente (SAVEPOINT); falha em V002 não desfaz V001.
- Pulos de versão (V001 → V003) não são verificados — responsabilidade do consumidor.
- FK desabilitado durante migrations, reabilitado no `finally`; FK check pós-apply.
- `sqlparse>=0.5,<1.0` como splitter (suporta `;` em strings literais e triggers).
- Consumidores precisam declarar `package-data` no seu `pyproject.toml` para SQL files em wheel/pipx.
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

### Testes

- Diretório: `tests/` com `pytest`.
- `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = [".", "tests"]`.
- Fixture packages de migrations (ex: `tests/fixtures_db/`) precisam de `__init__.py` em cada nível para `importlib.resources` funcionar.
- Testes de `db` usam banco em memória ou `tmp_path` — nunca banco fixo em disco.
- Não mockar `sqlite3` — testes de integração real com o banco.

## Restrições

- `requires-python = ">=3.12,<3.13"` — nunca usar outra versão; pin da frota (ADR `20260511`).
- `from jedi_library import <submodulo>` — nunca `import jedi_log` ou `import jedi_ai` direto; convenção do package único.
- `JediAI` exige `credentials` explícito na construção — `credentials=None` levanta `ValueError`.
- Prompts para `JediAI.call_vertex_ai` devem instruir o modelo a responder exclusivamente em JSON — o parser lança `ValueError` em resposta não-JSON.
- `JEDI_AI_GCP_PROJECT_ID` e `GOOGLE_APPLICATION_CREDENTIALS` são obrigatórios em `JediAI.from_env()` — ausência levanta `RuntimeError`.
- Nunca suprimir exceções de `data_extract_*` com `except: pass` — `usage_handler` de erro já foi disparado; suprimir oculta falhas do pipeline.
- Separador de migrations é `__` (duplo underline): `V001__descricao.sql` — nunca `V001-descricao.sql`.
- Fixture packages para `jedi_library.db` precisam de `__init__.py` em cada nível do diretório.
