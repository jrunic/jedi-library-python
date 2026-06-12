---
descricao: Índice navegável de 81-referencia (repo:jedi-library-python, dominio=tecnologia) — gerado automaticamente
tipo: index
status: ativo
escopo: jedi-labs
plataforma: "*"
indice: oculto
---

# Índice de 81-referencia/ — escopo `repo:jedi-library-python` · domínio `tecnologia`

*Gerado automaticamente. Editar as `descricao` e `dominios` nos arquivos fonte, não este índice.*

## (raiz)

- `arquitetura-python.md` — Arquitetura do package jedi_library (Python 3.12)
- `arquitetura.md` — Arquitetura Python — ver arquitetura-python.md para detalhes completos
- `contexto.md` — Contexto de negócio do jedi-library-python: o que é, por que existe, quem usa

## decisoes

- `decisoes/20260612-distribuicao-python-via-git-ssh.md` — ADR — distribuição do jedi-library-python via `uv add git+ssh://...` direto do GitHub, package único `jedi_library` com submódulos; sem wheel/PyPI até demanda real
- `decisoes/20260612-engine-migrations-sql-puro-tabela-schema.md` — ADR — engine de migrations do jedi_db usa arquivos SQL puro carregados via importlib.resources + tabela schema_migrations(versao, hash, aplicada_em) para versionamento explícito; PRAGMA user_version rejeitado; jd-tasks migra para esse padrão
