---
id: 202606122330
projeto: jedi-library-python
tipo: diario
status: concluido
escopo: repo:jedi-library-python
plataforma: local-macbook-jedi-labs
dominios: [tecnologia]
tags: [diario, tdd, log, datetime, slug, status-flow, assets, db, sqlparse]
---

# Diário — Implementação Onda 1: 6 módulos Python

## Contexto

Sessão de implementação completa das 6 libs da Onda 1 do `jedi-library-python`, executadas logo após a sabatina que produziu as specs. Fluxo `dev-02 → dev-03 → advisor → dev-04` com subagente por task.

## O Que Foi Feito

- **Specs revisadas:** lidas as 6 specs geradas em sessão anterior (`spec-jedi-log`, `spec-jedi-datetime`, `spec-jedi-slug`, `spec-jedi-status-flow`, `spec-jedi-assets`, `spec-jedi-db`).
- **Planos gerados** via `dev-03-escreve-plano` em paralelo (6 agentes simultâneos): um plano por módulo com código completo, TDD VERMELHO→VERDE, comandos exatos.
- **Advisor consultado** antes da execução. Identificou 3 blockers:
  1. `test/` vs `tests/` — resolvido confirmando `tests/` como novo padrão.
  2. `pyproject.toml` inconsistente entre planos (log usava `pythonpath=["."]`, db precisava de `[".", "tests"]`) — corrigido no plano de log.
  3. Rollback test fraco (não testava SAVEPOINT real) — corrigido: adicionada fixture `fixtures_db_broken` com V002 SQL inválido + `apply_migrations` corrigido para commitar por migration (sem o `commit()` por migration, V001 não persistia quando V002 falhava).
- **Execução em ondas** via `dev-04-desenvolve-com-tdd` com subagente por task:
  - Onda 0: infra pytest (pyproject.toml + tests/ + venv Python 3.12)
  - Onda 1 (paralela): log Task 1, datetime Task 1, slug Task 1, status_flow Task 1, assets Task 1
  - Onda 2 (paralela): assets Task 2, log Tasks 2+3
  - Onda 3: `__init__.py` unificado (4 módulos em único agente para evitar conflito de arquivo)
  - Onda 4 (sequencial): db Task 1 → Task 2 → Task 3 → Task 4 → Task 5
- **Resultado final:** 75 testes passando, 14 commits limpos, 0 regressões.
- **CONTEXTO.md atualizado** com estrutura do package, logging novo, migrations (separador `__`), seção de testes.

## Decisões Tomadas

- **`tests/` como novo padrão** (vs legado `test/python/`) — confirmado pelo Orlando.
- **`pythonpath = [".", "tests"]` no pytest** — necessário para fixture packages de migrations (`fixtures_db/`) serem importáveis via `importlib.resources`.
- **Commit por migration no `apply_migrations`** — `conn.commit()` após cada `RELEASE SAVEPOINT`. Sem isso, V001 não fica persistida quando V002 falha (tudo fica no mesmo transaction não-commitado).
- **Fixture `_fixtures/` interna ao package** — assets tests funcionam com editable install sem config extra de package-data.
- **`tests/fixtures_db_broken/` com V002 SQL inválido** — único jeito de testar o caminho de rollback do SAVEPOINT de forma honesta.

## Padrões Definidos

Todos registrados no `CONTEXTO.md`:

- Estrutura do package agora inclui os 7 módulos (log, ai, datetime_utils, slug, status_flow, assets, db) + `_fixtures/`.
- Logging: JSON stdout via `log.setup()`, não Sheets.
- Migrations: separador `__` (duplo underline), commit por migration, pulos de versão não verificados pela engine.
- Testes: `tests/`, `pythonpath = [".", "tests"]`, fixture packages com `__init__.py` em cada nível, banco real (sem mock de sqlite3).

## Pendências

- Migração dos consumidores para o novo `jedi_library.log` (jd-tasks, tili, jedi-etl) — tarefas separadas em cada repo.
- Migração do `jd-tasks` para usar `jedi_library.db` — tarefa separada.
- Consumidores que empacotam SQL files precisam declarar `package-data` no seu `pyproject.toml` — documentado no CONTEXTO.md, não executado aqui.
- Status das specs e planos: ainda em `rascunho` — atualizar para `concluido` quando consumidores migrarem.

## Voz do Usuário

> Tech, veja as specs que fizemos há pouco.

> Quero que desenhe os planos usando /dev-03-escreve-plano

> Peça ao advisor para checar os planos

> Vamos a execucao, com subagente por task
