---
id: 202606122150
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — implementar jedi_library.db com open_connection, apply_migrations e transaction; engine SQLite SQL-puro com sqlparse splitter"
tags: [spec, python, sqlite, migrations, sql-puro, schema-migrations, sqlparse]
---

# Spec: `jedi_library.db` — Engine SQLite com Migrations SQL-Puro

> Task de implementação: [[20260612-jedi-db]]

## Problema

O `jd-tasks` tem uma engine de migrations SQLite ad-hoc com aprendizados de incidentes em produção: `executescript` não é atômico, DROP TABLE com FK ativa não funciona, e `schema_migrations` com hash é superior ao `PRAGMA user_version`. Cada projeto que precisa de SQLite recria essa lógica, repetindo os mesmos erros. Sem um context manager de transação canônico, consumidores esquecem `commit` ou `rollback`.

## Solução

Módulo `db` com três primitivas: abertura de conexão com defaults seguros da frota, aplicação de migrations versionadas com rollback por arquivo, e context manager de transação. A engine usa SQL puro via `sqlparse` como splitter e armazena versão e hash de cada migration aplicada.

## Histórias de Usuário

1. Como qualquer script Python da frota que abre SQLite, quero abrir uma conexão com FK enforcement, WAL mode e row factory já configurados, sem lembrar os PRAGMAs necessários.
2. Como bootstrap de aplicação, quero aplicar automaticamente todas as migrations pendentes em ordem, com rollback granular em caso de erro em qualquer uma.
3. Como pipeline com operações relacionadas, quero um context manager de transação que faz commit em sucesso e rollback automático em exceção.
4. Como operador em produção, quero que uma migration modificada após ser aplicada levante erro imediato (verificação de hash), impedindo estado corrupto.
5. Como autor de migration com SQL complexo (triggers, strings com `;`), quero que o splitter lide corretamente com isso sem quebrar.

## Critérios de Sucesso

- Abertura de conexão retorna conexão com FK=ON, WAL mode e row factory configurados.
- Abertura com path em diretório inexistente cria o diretório automaticamente.
- `apply_migrations` cria tabela de controle de versões na primeira execução.
- Migrations aplicadas em ordem lexicográfica por nome de arquivo.
- Segunda chamada de `apply_migrations` não re-aplica migrations já registradas (idempotência).
- Migration modificada após aplicação levanta erro com informação sobre o hash divergente.
- Erro durante migration: rollback daquela migration; tabela de controle não registra a versão com falha.
- Arquivo de migration fora do padrão de nomenclatura é ignorado silenciosamente.
- Após aplicar todas as migrations, FK check detecta violações e levanta erro.
- SQL com `;` em string literal e em corpo de trigger aplicado sem erro.
- Context manager de transação: commit em sucesso; rollback e re-raise em exceção.

## Decisões de Implementação

- Novo módulo `db`; depende de `jedi_library.assets` para localizar arquivos de migration empacotados — `assets` deve existir antes
- `sqlparse>=0.5,<1.0` como única nova dependência externa; declarar em `pyproject.toml`
- Convenção de nomenclatura de migrations: prefixo `V` seguido de número, separador duplo underline, descrição, extensão `.sql` (ordem lexicográfica determina aplicação)
- Tabela de controle armazena versão (chave primária), hash SHA-256 do conteúdo e timestamp de aplicação
- FK enforcement desabilitado durante a execução das migrations e reabilitado no `finally` (requisito do SQLite para operações de schema)
- SAVEPOINT por migration: rollback granular sem abortar a sessão
- Pulos de versão (ex: V001 → V003 sem V002) não são verificados pela engine — responsabilidade do consumidor garantir a sequência

## Decisões de Teste

- Usar banco em memória (`:memory:`) ou diretório temporário do pytest — sem banco em disco fixo
- Criar package de fixtures com migrations SQL mínimas para os testes
- Não mockar `sqlite3` — testes de integração real com o banco (lição do `jd-tasks`)
- Cobrir: conexão com defaults, criação de diretório pai, aplicação em ordem, idempotência, hash mismatch, rollback de savepoint, arquivo fora do padrão, FK check pós-migration, splitter com `;` em string literal e em trigger, context manager commit e rollback

## Fora de Escopo

- PostgreSQL ou outros bancos
- Down-migrations (rollback de schema)
- Multi-tenant
- Pool de conexões
- ORM ou query builder
- Detecção de pulo de versão

## Assumptions

1. `jedi_library.assets` implementado antes de `jedi_library.db`
2. `sqlparse>=0.5,<1.0` disponível via `uv`
3. pytest como runner, com fixture `tmp_path` disponível
4. Pulos de versão não são verificados — consumidor garante sequência contínua

## Notas

- ADR de implementação: `docs/81-referencia/decisoes/20260612-engine-migrations-sql-puro-tabela-schema.md` (neste repo).
- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-db-criacao.md`.
- ADR de template FK SQLite: `20260519-migration-sqlite-com-fk-template-canonico.md`.
- Gabarito de implementação: módulo de migrations do `tili` — ler antes de escrever.
- `jd-tasks` migrará para esta engine após implementação — tarefa separada.
