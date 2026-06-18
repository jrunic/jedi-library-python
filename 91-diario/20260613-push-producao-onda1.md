---
id: 202606131000
projeto: jedi-library-python
tipo: diario
status: concluido
escopo: repo:jedi-library-python
plataforma: local-macbook-jedi-labs
dominios: [tecnologia]
tags: [diario, push, producao]
---

# Diário — Push para Produção (Onda 1)

## Contexto

Sessão curta de encerramento: commit do restante não staged + push dos 18 commits da Onda 1 para `origin/main`.

## O Que Foi Feito

- `git rm` dos arquivos legados (`src/python/jedi_log.py`, `test/python/test_log.py`, pycache).
- Commit dos arquivos não staged: CLAUDE.md, docs de tarefas/specs/planos, script de ação perigosa.
- `git push origin main` — 18 commits publicados em `git@github.com:jrunic/jedi-library-python.git`.

## Decisões Tomadas

- Biblioteca em produção. Consumidores podem instalar via `uv add 'jedi-library @ git+ssh://git@github.com/jrunic/jedi-library-python.git'`.

## Padrões Definidos

Nenhum novo nesta sessão.

## Pendências

- Migração de `jd-tasks` para `jedi_library.db`.
- Migração dos consumidores (jd-tasks, tili, jedi-etl) para o novo `jedi_library.log`.
- Consumidores com SQL files próprios precisam declarar `package-data` no seu `pyproject.toml`.

## Voz do Usuário

> O padrão para uso da library pelos repositórios depende do repo em production; vamos fazer o push em production.
