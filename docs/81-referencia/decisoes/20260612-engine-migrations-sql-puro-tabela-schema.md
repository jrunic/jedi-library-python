---
descricao: ADR — engine de migrations do jedi_db usa arquivos SQL puro carregados via importlib.resources + tabela schema_migrations(versao, hash, aplicada_em) para versionamento explícito; PRAGMA user_version rejeitado; jd-tasks migra para esse padrão
id: 202606121540
projeto: jedi-library-python
tipo: decisao
status: aceito
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
tags: [adr, jedi-library-python, jedi-db, sqlite, migrations, schema, sql]
---

# Engine de migrations do `jedi_db`: SQL puro + tabela `schema_migrations`

## Contexto

A Onda 1 do inventário Python inclui `jedi_db` — engine de migrations + `abrir_conexao` + assar 3 hard-limits (FK OFF fora de tx, SAVEPOINT, ban do `upper()` C-locale). Os 2 consumidores reais (tili e jd-tasks) divergem em duas dimensões:

1. **Formato das migrations:**
   - `tili` usa `migrations_sql/V*.sql` carregados via `importlib.resources` (SQL puro, splitter de statements + savepoint engine testados na cicatriz dos hard-limits da Fase 2).
   - `jd-tasks` usa `migrations/V*.py` (Python). 5 migrations já em produção.

2. **Versionamento de schema:**
   - `tili` usa tabela `schema_migrations(versao, hash, aplicada_em)`.
   - `jd-tasks` usa `PRAGMA user_version` (inteiro nativo do SQLite).

## Decisão

`jedi_db` adota:

- **Migrations em SQL puro** (`migrations_sql/V*.sql`) carregados via `importlib.resources`.
- **Tabela `schema_migrations(versao TEXT, hash TEXT, aplicada_em TEXT)`** como mecanismo de versionamento.

Engine importa a cicatriz já testada do tili (splitter de statements, savepoint, FK OFF fora de tx).

`jd-tasks` migra para esse padrão como custo de adoção:

- Tradução das 5 `.py` migrations existentes para `.sql` equivalentes.
- Criação da tabela `schema_migrations` e backfill das linhas v1..v5 com hash dos `.sql` traduzidos.

## Alternativas consideradas

- **Python migrations** — rejeitada. Engine SQL puro é mais simples, declarativo, auditável sem ambiente Python ativo.
- **`PRAGMA user_version`** — rejeitada. É só um inteiro: não diz quando aplicou, qual hash do `.sql` rodou, quem rodou.
- **Híbrido** — rejeitada. Combina o pior dos dois.

## Consequências

- `jedi_db` herda a cicatriz dos 3 hard-limits do tili (zero custo de re-aprender em produção).
- `jd-tasks` paga um custo único de ~1h para traduzir 5 migrations e backfillar a tabela.
- Hash do `.sql` em disco vs hash gravado em `schema_migrations` é a defesa contra "editei a migration na mão".
- API pública mínima inicial: `jedi_library.db.abrir_conexao(path)`, `jedi_library.db.aplicar_migrations(conn, migrations_dir)`, `jedi_library.db.versao_atual(conn)`.
- Ordem alfabética dos arquivos `V001-...sql`, `V002-...sql` determina ordem de aplicação; engine recusa pulos.

## Referências

- ADR de regra de 2 consumidores: `jedi-library/docs/81-referencia/decisoes/20260612-regra-de-2-consumidores-reais.md`.
- ADR de split: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260612-jedi-library-trio-repos.md`.
- ADR de template canônico de migration: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260519-migration-sqlite-com-fk-template-canonico.md`.
