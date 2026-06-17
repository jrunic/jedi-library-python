---
id: 202606171800
projeto: jedi-library-python
tipo: diario
status: concluido
tags: [ai, vertex, client-pattern, tdd, refactor, jedi-library]
---

# Diário — Redesign `jedi_library.ai` para Client object pattern

## Contexto

Sessão de execução do plano `20260617-plano-jedi-ai-client-pattern.md`. O `jedi_library.ai` existente tinha auth opaca via `GOOGLE_CREDENTIALS_FILE` com fallback silencioso para ADC, acoplamento com Google Sheets (`log_usage`/`COST_SHEET_ID`) e `cost_context` obrigatório em todo `data_extract_*`. Esses três problemas tornavam multi-tenant inviável e todo consumidor dependente de infraestrutura específica do Jedi Labs.

## O Que Foi Feito

- **Task 1:** Criou `jedi_library/utils.py` com `prepare_prompt()` (função pura de substituição de template, movida de `ai.py`). 7 testes. Exportada em `__init__.py`.
- **Tasks 2–7:** Implementou classe `JediAI` completa em `ai.py`:
  - Construtor com `credentials` explícito obrigatório (`credentials=None` → `ValueError`)
  - `from_service_account_file()` — caminho primário de produção
  - `from_env()` — conveniência single-tenant via `google.auth.load_credentials_from_file`
  - `call_vertex_ai()` com retry em 429, retorna `{"result", "usage", "raw_text"}`
  - `data_extract_pdf()`, `data_extract_ofx()`, `data_extract_csv()` — retornam `{"result", "usage"}`
  - `_dispatch_usage()` — invoca `usage_handler` em sucesso e erro; suprime exceção do handler
- **Task 8:** Removeu todo legado (`COST_SHEET_ID`, `_get_credentials`, `_sheets_service`, `log_usage`, `prepare_prompt` de módulo, `google-api-python-client`). Atualizou `pyproject.toml`, `CONTEXTO.md`.
- Criou tarefa #237 no `jd-tasks` para ADR derivado em `jedi-library`.

## Decisões Tomadas

- `credentials` é parâmetro keyword-only obrigatório no construtor — sem default, sem ADC implícito. Quebra com o legado é intencional.
- `from_service_account_file()` é o caminho primário; `from_env()` é conveniência single-tenant documentada como tal.
- `cost_context` removido sem adapter — breaking change intencional. Consumidores migram em tarefas separadas (`jedi-etl`, `tili`).
- `_credentials` armazenado no objeto para permitir verificação de isolamento em testes.
- Distribuição continua via branch `main` — não há branch `production` neste repo.
- Teste `test_dois_clientes_com_credentials_distintas_nao_interferem` ajustado: verifica `ai._credentials is not` e `genai.Client.call_args_list` em vez de `ai._client is not` (mock fixture retorna o mesmo objeto para ambas as chamadas).

## Padrões Definidos

Já atualizados no `CONTEXTO.md`:
- Seção Autenticação: credenciais explícitas obrigatórias, `from_service_account_file` como caminho primário, `from_env` como conveniência
- Seção Restrições: removidas referências a `cost_context` e `log_usage`; adicionadas restrições do novo padrão
- Estrutura do package: `utils.py` incluído

## Pendências

- Migração dos consumidores (`jedi-etl`, `tili`) para a nova API — tarefas separadas nos repos respectivos
- ADR conceitual em `jedi-library` (repo agnóstico) — tarefa #237 no `jd-tasks`
- Bump de versão no `pyproject.toml` e `uv lock --upgrade-package jedi-library` nos consumidores

## Voz do Usuário

"Tech, temos um plano detalhado em docs/11-tarefas; leia-o"

"A library é distribuida pela branch production, correto?"

"Mantemos como está..."

"/jedi-diario, depois commit e push"
