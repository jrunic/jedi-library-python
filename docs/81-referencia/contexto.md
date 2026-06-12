---
id: 202606121612
projeto: jedi-library-python
tipo: referencia
status: ativo
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Contexto de negócio do jedi-library-python: o que é, por que existe, quem usa"
tags: [contexto, python]
---

# Contexto — jedi-library-python

## O que é

Package Python 3.12 das bibliotecas Jedi Labs — `jedi_library`. Instalado via `uv add git+ssh://...`. Submódulos: `log` (Onda 0), `ai` (Onda 0), e demais a partir da Onda 1 (db, slug, assets...).

## Por que existe

O lado Python da `jedi-library` era praticamente vazio (só `jedi_log.py` orphan). O split de 2026-06-12 criou este repo para hospedar as implementações Python com estrutura adequada: `pyproject.toml`, package único, `uv add` como mecanismo de distribuição. O histórico de adormecimento do port Python via submódulo foi o motivador direto (ADR `20260612-distribuicao-python-via-git-ssh.md`).

## Quem usa (planejado/ativo)

- `jedi-etl` — usa Vertex AI direto hoje; migração para `jedi_library.ai` planejada pós-Onda 0.
- `tili` — Fase 3 (planejado: log + ai + db + enrich).
- `jd-gera-imagem` — migração para `jedi_library.ai` planejada.
- `jd-tasks` — Onda 1 (db, migrations).

## Governança

Conceito e API das libs vivem em `jedi-library` (repo agnóstico). Regras de uso Python e detalhes de implementação vivem aqui.
