---
id: 202606171500
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — redesign de jedi_library.ai para Client object pattern: classe JediAI, credenciais explícitas obrigatórias, usage_handler injetado, Sheets e GOOGLE_CREDENTIALS_FILE removidos"
tags: [spec, python, ai, vertex, auth, client-pattern]
---

# Spec: Redesign de `jedi_library.ai` — Client object pattern

## Problema

`jedi_library.ai` tem três acoplamentos de infraestrutura que violam o princípio de independência da biblioteca:

1. **Auth acoplada ao ambiente de maneira opaca.** `_get_credentials()` tenta `GOOGLE_CREDENTIALS_FILE` (env var jedi-specific, não padrão Google) e, se o arquivo não existir, cai silenciosamente para ADC. O Vertex AI funciona por ADC residual do ambiente — descrito na sessão de 2026-06-16 como "funcionamento por sorte".

2. **Env vars como auth primária inviabiliza multi-tenant em um processo.** O cenário futuro do Jedi Labs tem vários callers no mesmo host com credenciais diferentes (market4u, vida-imagem, maré-mansa). Env vars permitem apenas uma configuração ativa por processo — múltiplos clientes com credenciais distintas não são possíveis sem process isolation forçada.

3. **`COST_SHEET_ID` hardcoded.** Um ID de planilha Google Sheets específico está baked-in no código da lib. A lib conhece detalhes de infraestrutura que não são dela.

4. **`log_usage()` escreve em Sheets.** A lib autentica, constrói um cliente Sheets e grava linhas na planilha de custos. Isso exige `google-api-python-client` e credenciais com escopo Sheets em todo consumidor — incluindo contextos onde não há uso de Sheets.

5. **`prepare_prompt()` misturada com AI.** Função de substituição de template sem relação com auth ou Vertex está em `ai.py` porque nasceu junto com as funções de extração. Pertence a um módulo de utilitários de string, não ao cliente AI.

Efeito: consumidores não conseguem usar `jedi_library.ai` sem acoplar seu ambiente a infraestrutura específica do Jedi Labs. Testes unitários exigem mocks de API Google. Multi-tenant em um processo é inviável.

## Solução

Redesenhar `jedi_library.ai` como um **Client object pattern** com credenciais explícitas obrigatórias: a classe `JediAI` recebe credenciais na construção — sem fallback para env vars, sem ADC implícito. Cada caller constrói seu próprio cliente com suas credenciais; múltiplos clientes com credenciais distintas coexistem naturalmente no mesmo processo. `from_env()` é convenência para scripts single-tenant, não o caminho primário. O custo de tokens é retornado no response e opcionalmente roteado para um handler injetado pelo caller. A lib não conhece mais Sheets. `prepare_prompt()` é movida para `jedi_library.utils` como função de módulo independente.

## Histórias de Usuário

1. Como `jedi-etl` multi-tenant, quero construir um `JediAI` por tenant com SA JSON distinto para cada um, e reutilizar cada cliente em todas as chamadas daquele tenant, sem que um interfira no outro.
2. Como `jedi-etl`, quero passar um `usage_handler` que grava na planilha de custos, para manter o rastreamento sem que a lib saiba de Sheets.
3. Como script de teste, quero construir `JediAI(project=..., location=..., credentials=mock_creds)` sem variáveis de ambiente, para rodar offline sem mocks de env.
4. Como consumidor que não precisa rastrear custos, quero não passar `usage_handler` e ter a lib silenciosa sobre uso de tokens.
5. Como desenvolvedor depurando uma extração, quero inspecionar o campo `usage` do response sem precisar de um handler configurado.
6. Como script CLI single-tenant, quero usar `JediAI.from_service_account_file(path, project=...)` sem construir as credenciais manualmente.
7. Como script cron simples, quero usar `JediAI.from_env()` como convenência quando o processo já tem `GOOGLE_APPLICATION_CREDENTIALS` setado.
8. Como novo consumidor, quero que qualquer factory falhe explicitamente com mensagem clara se algum parâmetro obrigatório estiver ausente.

## Critérios de Sucesso

- `JediAI(project=..., location=..., credentials=<creds>)` constrói sem erro com credenciais explícitas.
- `JediAI(project=..., location=..., credentials=None)` levanta `ValueError` — `credentials` é obrigatório.
- Dois `JediAI` com credenciais distintas coexistem no mesmo processo sem interferência.
- `JediAI.from_service_account_file(path, project=..., location=...)` carrega o SA JSON e constrói o cliente.
- `JediAI.from_service_account_file` levanta `FileNotFoundError` com path incluído se o arquivo não existir — exceção nativa do Python, suficiente para debug e incidente.
- `JediAI.from_env()` levanta `RuntimeError` se `JEDI_AI_GCP_PROJECT_ID` ou `GOOGLE_APPLICATION_CREDENTIALS` estiverem ausentes — sem fallback silencioso.
- `data_extract_pdf`, `data_extract_ofx`, `data_extract_csv` e `call_vertex_ai` retornam `{"result": ..., "usage": {...}}`.
- Campo `usage` contém: `model`, `function`, `prompt_token_count`, `candidates_token_count`, `total_token_count`, `status` (`"success"` ou `"error"`), `execution_id` quando passado. Em erro de rede ou auth (sem response do Vertex), contagens de tokens são `0` — padrão da indústria para aggregation-safe em handlers de custo.
- Quando `usage_handler` foi injetado na construção, cada chamada bem-sucedida ou com erro o invoca com o dict de usage — inclusive em exceção (antes de relançar).
- Quando `usage_handler` não foi passado, nenhuma chamada de log ou Sheets ocorre.
- `log_usage()` público não existe mais na API pública do módulo.
- `COST_SHEET_ID`, `_get_credentials()` e `_sheets_service()` não existem mais no módulo.
- Nenhuma referência a `GOOGLE_CREDENTIALS_FILE` permanece no módulo ou no `CONTEXTO.md` do repo.
- `test_ai.py` cobre todos os métodos públicos com mock de `genai.Client` — sem chamada real ao Vertex.
- Testes passam sem variáveis de ambiente configuradas.

## Decisões de Implementação

**Classe `JediAI`**

- **Construtor direto** — caminho canônico para todos os cenários, incluindo multi-tenant:
  `__init__(self, *, project: str, location: str = "us-central1", credentials, usage_handler: Callable[[dict], None] | None = None)`.
  `credentials` é posicional-keyword obrigatório (sem default). Cria `genai.Client(vertexai=True, project=project, location=location, credentials=credentials)` na construção.

- **`from_service_account_file(cls, path, *, project, location="us-central1", usage_handler=None)`** — factory principal para produção. Carrega `google.oauth2.service_account.Credentials` com scope `cloud-platform` a partir do arquivo SA JSON, delega ao construtor. Levanta `RuntimeError` se o arquivo não existir.

- **`from_env(cls, *, usage_handler=None)`** — convenência para scripts e crons single-tenant onde process isolation já garante o contexto. Lê `JEDI_AI_GCP_PROJECT_ID` e `GOOGLE_APPLICATION_CREDENTIALS` (ambos obrigatórios, `RuntimeError` se ausentes), `JEDI_AI_VERTEX_LOCATION` (opcional, default `"us-central1"`). Carrega credenciais via `google.auth.load_credentials_from_file(path, scopes=[...])` — aceita SA JSON, authorized user credentials e workload identity, alinhado com o comportamento padrão do ADC. Documentado como convenência, não como caminho primário.

**Métodos públicos**

- `call_vertex_ai(prompt_text, *, model=DEFAULT_MODEL, generation_config=None, execution_id=None) -> dict`: retorna `{"result": <parsed>, "usage": {...}, "raw_text": str}`. `result` é o `json.loads` do texto da resposta. Retry exponencial em 429 (3 tentativas). Invoca `_dispatch_usage()` após execução.
- `data_extract_pdf(file_path, prompt_text, *, model=DEFAULT_MODEL, execution_id=None) -> dict`: retorna `{"result": ..., "usage": {...}}`. Valida tamanho (7 MB) e levanta `ValueError` antes de chamar Vertex. Monta `inline_data`, chama Vertex, invoca `_dispatch_usage()`.
- `data_extract_ofx(file_path, prompt_text, *, model=DEFAULT_MODEL, execution_id=None) -> dict`: lê UTF-8, concatena ao prompt, delega a `call_vertex_ai` passando `function="data_extract_ofx"` internamente para o usage.
- `data_extract_csv(file_path, prompt_text, *, model=DEFAULT_MODEL, execution_id=None) -> dict`: mesmo padrão do OFX.

**`cost_context` removido**

`cost_context={'project': ..., 'execution_id': ...}` era obrigatório — removido. `project` é conhecido pelo cliente (passado na construção). `execution_id` vira parâmetro opcional direto nos métodos. O handler injetado pelo caller tem seu próprio contexto para enriquecer o dict de usage.


**Schema do dict `usage`**

```
model: str
function: str          # "data_extract_pdf" | "data_extract_ofx" | "data_extract_csv" | "call_vertex_ai"
prompt_token_count: int        # 0 em caso de erro sem response
candidates_token_count: int    # 0 em caso de erro sem response
total_token_count: int         # 0 em caso de erro sem response
status: "success" | "error"
execution_id: str | None
```

**`prepare_prompt()` movida para `jedi_library.utils`**

Função pura de substituição de template — sem estado, sem auth, sem Vertex. Cria ou amplia o módulo `jedi_library/utils.py`. Re-exportada em `__init__.py`. Testes em `tests/test_utils.py` (ou arquivo existente se já houver).

**`_dispatch_usage()` (privado)**

Método interno que monta o dict de usage e chama `self._usage_handler(usage)` se handler configurado. Erros no handler são capturados e logados via `logging.getLogger(__name__).warning(...)` — padrão Python para libs, preserva controle do destino pelo consumidor.

**Remoções definitivas**

- `COST_SHEET_ID` e `COST_SHEET_TAB` — constantes removidas
- `_get_credentials()` — função removida
- `_sheets_service()` — função removida
- `log_usage()` — função pública removida
- `prepare_prompt()` — movida para `jedi_library.utils`
- Import de `googleapiclient.discovery` — removido

**Atualização de `CONTEXTO.md`**

A seção "Autenticação" do repo é reescrita: remove referência a `GOOGLE_CREDENTIALS_FILE` e ao path canônico `~/.config/jedi-secrets/`. A convenção passa a ser: credenciais são sempre passadas explicitamente ao construtor `JediAI`; o caller é responsável por carregá-las (via `from_service_account_file` ou objeto `google.oauth2` diretamente). `from_env()` documentado como convenência single-tenant.

## Decisões de Teste

- Testes em `tests/test_ai.py` — arquivo novo, não existe hoje.
- Mock de `google.genai.Client` via `unittest.mock.patch` — sem chamada real ao Vertex.
- Mock de `google.oauth2.service_account.Credentials.from_service_account_file` para testar `from_service_account_file()`.
- Cobrir:
  - Construção com credenciais explícitas (sucesso)
  - Construção com `credentials=None` (espera `ValueError`)
  - Dois clientes com credenciais distintas no mesmo processo — sem interferência entre eles
  - `from_service_account_file` com arquivo válido (sucesso)
  - `from_service_account_file` com arquivo inexistente (espera `FileNotFoundError` com path no message)
  - `from_env()` com todas as env setadas usando `load_credentials_from_file` (sucesso)
  - `from_env()` sem `JEDI_AI_GCP_PROJECT_ID` (espera `RuntimeError`)
  - `from_env()` sem `GOOGLE_APPLICATION_CREDENTIALS` (espera `RuntimeError`)
  - Retorno enriquecido com `result` + `usage` em todos os métodos
  - `usage_handler` invocado em sucesso com campos corretos
  - `usage_handler` invocado em erro com contagens zeradas (`prompt_token_count=0` etc.) antes de relançar a exceção
  - Sem handler = sem efeito colateral
  - `execution_id` presente no usage quando passado, ausente quando não passado
  - `function` correto no usage para cada método (`data_extract_ofx` registra `"data_extract_ofx"`, não `"call_vertex_ai"`)
  - `data_extract_pdf` com arquivo > 7 MB levanta `ValueError` antes de chamar Vertex
  - Retry em 429 (3 tentativas com backoff)
  - `prepare_prompt()` acessível via `jedi_library.utils` (importação e comportamento)
- Padrão de testes existente: ver `tests/test_log.py` e `tests/test_db.py` para convenções de fixture e asserção.

## Fora de Escopo

- Migração dos consumidores (`jedi-etl`, `tili`) — tarefas separadas nos repos respectivos.
- `data_extract_xlsx` — não existe hoje, não entra nesta spec.
- Handler padrão para Sheets — responsabilidade do caller (`jedi-etl` implementará o seu).
- ADR conceitual em `jedi-library` (repo agnóstico) — tarefa derivada, não bloqueia implementação.
- Bump de versão no `pyproject.toml` e atualização do `uv.lock` nos consumidores — tarefas derivadas.
- Thread-safety de `genai.Client` — delegada ao SDK; não testada aqui.

## Assumptions

1. Python 3.12 (padrão da frota — ADR `20260511-versoes-fixas-runtime-frota.md`).
2. Credenciais explícitas são obrigatórias — sem fallback para ADC implícito. Construtor sem `credentials` levanta `ValueError`; factories sem env/arquivo levantam `RuntimeError`. Comportamento por sorte é eliminado.
3. `from_service_account_file()` é o caminho primário de produção; `from_env()` é convenência single-tenant via `google.auth.load_credentials_from_file()` (aceita SA JSON, authorized user, workload identity).
4. `FileNotFoundError` nativo do Python passa sem wrap — path no message é suficiente para debug e incidente.
5. Token counts em erro de rede/auth são `0` — padrão da indústria para aggregation-safe.
6. `prepare_prompt()` move para `jedi_library.utils` — módulo novo, função pura de string.
7. Sem backward compat — lib é interna; consumidores migram em tarefas separadas.
8. `cost_context` obrigatório é removido sem adapter — breaking change intencional.
9. `log_usage()` público desaparece da API — callers que a chamavam diretamente precisam migrar para handler.
10. Testes com mock do `genai.Client` — sem chamada real ao Vertex em CI.
11. `CONTEXTO.md` do repo é atualizado nesta mesma implementação.
12. ADR conceitual em `jedi-library` é tarefa derivada criada no `jd-tasks` ao fechar esta spec.

## Notas

- ADR de referência: `$JEDI_BRAIN_FOLDER/81-referencia/decisoes/20260612-vertex-ai-padrao-jedi-labs.md`.
- O design de credenciais explícitas por cliente é o mesmo padrão dos SDKs Google (`google-cloud-bigquery`, `google-cloud-storage`) e do SDK Anthropic — caller constrói o cliente com suas credenciais, lib não opina sobre a origem.
- `DEFAULT_MODEL = "gemini-2.0-flash"` permanece como constante — overridável por parâmetro `model` em todos os métodos.
- `MAX_PDF_BYTES = 7 * 1024 * 1024` permanece como constante interna.
- O cenário multi-tenant (vários `JediAI` por processo) é o driver da decisão de credenciais explícitas; process isolation (Plano C cron-por-tenant) continua válida e é servida igualmente bem pelo `from_service_account_file`.
