---
id: 202606171800
projeto: jedi-library-python
tipo: diario
status: concluido
tags: [ai, vertex, client-pattern, tdd, refactor, response-schema, jedi-library]
---

# Diário — Redesign `jedi_library.ai` + `response_schema`

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
- Criou tarefa #237 no `jd-tasks` para ADR derivado em `jedi-library` (fechada imediatamente — ADR `20260617-jedi-ai-client-pattern.md` já existia no repo).

**Segunda parte da sessão — `response_schema` em `JediAI` (plano `20260617-plano-response-schema-data-extract.md`):**

- Adicionou helper `_build_config(response_schema)` em `ai.py` — centraliza validação (`isinstance` dict) e construção do config Vertex.
- Estendeu `data_extract_pdf`, `data_extract_ofx`, `data_extract_csv` com `response_schema: dict | None = None`.
- Estendeu `call_vertex_ai` com `response_schema` (mutuamente exclusivo com `generation_config` — `ValueError` se ambos passados).
- 13 novos testes: schema-presente, schema-ausente, schema-malformado por método (4 métodos × 3 casos).
- Bump de versão `0.1.0` → `0.2.0`.
- Suite final: 129 testes passando.

## Decisões Tomadas

- `credentials` é parâmetro keyword-only obrigatório no construtor — sem default, sem ADC implícito. Quebra com o legado é intencional.
- `from_service_account_file()` é o caminho primário; `from_env()` é conveniência single-tenant documentada como tal.
- `cost_context` removido sem adapter — breaking change intencional. Consumidores migram em tarefas separadas (`jedi-etl`, `tili`).
- `_credentials` armazenado no objeto para permitir verificação de isolamento em testes.
- Distribuição continua via branch `main` — não há branch `production` neste repo.
- Teste `test_dois_clientes_com_credentials_distintas_nao_interferem` ajustado: verifica `ai._credentials is not` e `genai.Client.call_args_list` em vez de `ai._client is not` (mock fixture retorna o mesmo objeto para ambas as chamadas).
- `generation_config` e `response_schema` são mutuamente exclusivos em `call_vertex_ai` — caller usa um ou outro; se precisar de ambos, monta `generation_config` completo com `response_schema` dentro.
- `_build_config` centraliza a validação de tipo e construção do config — métodos `data_extract_*` não repetem `isinstance`.

## Padrões Definidos

Já atualizados no `CONTEXTO.md`:
- Seção Autenticação: credenciais explícitas obrigatórias, `from_service_account_file` como caminho primário, `from_env` como conveniência
- Seção Restrições: removidas referências a `cost_context` e `log_usage`; adicionadas restrições do novo padrão
- Estrutura do package: `utils.py` incluído

## Pendências

- Migração dos consumidores (`jedi-etl`, `tili`) para a nova API — tarefas separadas nos repos respectivos
- `uv lock --upgrade-package jedi-library` nos consumidores após esta atualização

## Voz do Usuário

"Tech, temos um plano detalhado em docs/11-tarefas; leia-o"

"A library é distribuida pela branch production, correto?"

"Mantemos como está..."

"/jedi-diario, depois commit e push"

"Que ADR derivado?"

"Cheque. Há um adr recente em jedi-library."

"Feche"

"Leia esse plano: 20260617-plano-response-schema-data-extract.md. Pronto para executar?"

"pode executar"

"Atualize /jedi-diario, commit e push"
