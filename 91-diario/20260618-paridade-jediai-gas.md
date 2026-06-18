---
id: 202606181530
projeto: jedi-library-python
tipo: diario
status: concluido
tags: [jedi-ai, vertex, paridade, gas, retry, generation-config, data-extract]
---

# Diário — Paridade JediAI Python com pr-finance-files GAS

## Contexto

Execução do plano `20260618-plano-paridade-jediai-gas.md`, gerado na sessão anterior. Objetivo: trazer a `JediAI` Python para paridade com a implementação GAS de `pr-finance-files`, adicionando `data_extract_file` genérico, `generation_config` nos extractors, retry robusto em 5xx e `contents` externo em `call_vertex_ai`.

## O Que Foi Feito

- **Task 1 — Retry 5xx + jitter em `_call_vertex_raw`:** detecção de código de erro via `getattr(e, "code", None)` (não string match); retry em 429 e 5xx exceto 501; backoff `2 ** attempt * 2 + random.uniform(0, 0.5)`. Commit `e921acb`.
- **Task 2 — `data_extract_file`:** novo método genérico para binários via `inline_data`; aceita qualquer `mime_type`; limite 7 MB; `generation_config` XOR `response_schema`. Commit `4a0c2ae`.
- **Task 3 — `data_extract_pdf` como wrapper thin:** delega para `data_extract_file` passando `_function_name="data_extract_pdf"` para preservar `usage["function"]`. Removeu ~20 linhas de lógica duplicada. Commit `6a8ca73`.
- **Task 4 — `generation_config` em `data_extract_ofx` e `data_extract_csv`:** paridade de interface com `data_extract_file`. Commit `b6a8071`.
- **Task 5 — `call_vertex_ai` com `contents` externo:** `prompt_text` virou `str | None = None`; novo parâmetro `contents: list | None`; validação mútua. Commit `ca88742`.
- **Task 6 — Bump `0.2.1` → `0.3.0`.** Commit `3d4f95c`.
- Suite final: **148 testes, 0 falhas**.
- `CONTEXTO.md` atualizado com seção `## API JediAI — Padrões v0.3`.

## Decisões Tomadas

- `data_extract_pdf` passa a ser wrapper de `data_extract_file` — não implementação independente. Paridade de interface entre todos os `data_extract_*`.
- `generation_config` e `response_schema` são mutuamente exclusivos em toda a API `JediAI`.
- Retry usa `getattr(e, "code", None)` — o SDK `google-genai` seta `.code` dinamicamente no `__init__`, não aparece em `dir()` mas funciona via `getattr`.

## Padrões Definidos

Atualizados em `CONTEXTO.md`:
- Seção `## API JediAI — Padrões v0.3` com contratos de `data_extract_*`, `call_vertex_ai` e retry.
- Restrição nova: `generation_config` e `response_schema` mutuamente exclusivos.

## Pendências

- Consumidores de `jedi-library` (ex: `pr-finance-files`) precisam rodar `uv lock --upgrade-package jedi-library` para pegar a v0.3.0.

## Voz do Usuário

- "Leia o plano gerado há pouco"
- "Além de data_extract_pdf, temos outros data_extracts?"
- "ok, execute o plano. subagente por task"
- "/jedi-diario; commit e push"
