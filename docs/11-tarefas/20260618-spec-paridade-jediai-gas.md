---
id: 202606180200
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — paridade JediAI Python com pr-finance-files GAS: arquivo genérico, contents externo, generation_config e retry robusto"
tags: [spec, jedi-ai, vertex, paridade, gas, retry, generation-config]
---

# Spec: Paridade `JediAI` Python com pr-finance-files GAS

## Problema

`JediAI` Python (0.2.1) cobre o caso mais comum de extração de PDF, mas fica aquém do que o módulo GAS `pr-finance-files` oferece em quatro pontos:

1. **MimeType hardcoded.** `data_extract_pdf` força `application/pdf`. O pr-finance detecta o mimeType real do arquivo e passa adiante — PDF, imagem, XLSX ou qualquer tipo suportado pelo Vertex. Consumidores Python que queiram extrair imagens não têm API equivalente.

2. **`call_vertex_ai` não aceita `contents` externo.** O pr-finance monta `contents` completo — `[{role, parts: [{inlineData, ...}, {text, ...}]}]` — e passa direto para `callVertexAI`. A versão Python aceita apenas `prompt_text: str`, sem caminho para estruturas multipart avançadas (ex.: múltiplos documentos por chamada, combinação de texto + imagem).

3. **`data_extract_*` sem `generation_config`.** O pr-finance passa `temperature: 0.1, topK: 32, topP: 0.95` junto com `responseMimeType`. Os métodos `data_extract_pdf/ofx/csv` aceitam apenas `response_schema`; não há como ajustar temperatura ou top-k. `call_vertex_ai` já suporta o parâmetro, mas os extractors ficaram para trás.

4. **Retry frágil.** `_call_vertex_raw` retenta apenas em `429`. O GAS retenta também em `5xx` (falhas transitórias de servidor) com jitter aleatório. Sem retry em 5xx, uma falha transitória do Vertex se propaga como erro permanente para o caller.

Quem sente: qualquer consumidor que queira extrair tipo não-PDF, ajustar parâmetros de geração nos extractors, ou operar com resiliência equivalente ao GAS.

## Solução

Quatro adições à classe `JediAI`, todas aditivas (sem breaking change):

1. **`data_extract_file(file_path, mime_type, prompt_text, ...)` —** novo método genérico que aceita qualquer `mime_type` de arquivo binário via `inline_data`. `data_extract_pdf` vira wrapper thin que chama `data_extract_file` com `mime_type="application/pdf"`. `data_extract_ofx` e `data_extract_csv` não são afetados — continuam com concatenação textual, não com `inline_data`.

2. **`contents` como parâmetro opcional em `call_vertex_ai` —** quando `contents` é passado, `prompt_text` não é necessário. Quando `prompt_text` é passado, comportamento atual preservado. Os dois juntos levantam `ValueError`.

3. **`generation_config` em `data_extract_file/pdf/ofx/csv` —** mesmo contrato que `call_vertex_ai`: mutuamente exclusivo com `response_schema`; quando passado, encaminhado como `config` para o Vertex. Permite ajuste de temperatura e núcleo de probabilidade nos extractors.

4. **Retry em 5xx + jitter em `_call_vertex_raw` —** estender a lógica de retry para cobrir respostas `500–599` (exceto `501 Not Implemented`, que é erro permanente). Adicionar jitter ao backoff para reduzir thundering herd em falhas simultâneas de múltiplos callers.

## Histórias de Usuário

1. Como Tech integrando tili, quero extrair um comprovante de Pix recebido como JPEG (foto tirada pelo Orlando no app do banco) com `data_extract_file(path, "image/jpeg", prompt)`, para não precisar pré-converter o arquivo antes de chamar a lib.
2. Como Tech integrando tili, quero passar `generation_config={"temperature": 0.1, "top_k": 32}` em `data_extract_pdf`, para que a extração seja determinística e comparável ao comportamento do módulo GAS.
3. Como Tech construindo fluxo multipart, quero passar `contents=[{role, parts}]` direto para `call_vertex_ai`, para montar chamadas com múltiplas partes sem precisar contornar a API da lib.
4. Como operador em produção, quero que uma falha transitória `503` do Vertex seja retentada automaticamente, para que erros de servidor não causem falhas desnecessárias no pipeline de extração do tili.

## Critérios de Sucesso

- `data_extract_file("/path/doc.jpg", "image/jpeg", prompt)` monta `contents` com `mime_type="image/jpeg"` e `role="user"` — verificável em teste unitário inspecionando `contents` passado ao mock.
- `data_extract_pdf` produz `contents` idêntico ao `data_extract_file` chamado com `mime_type="application/pdf"` — verificável comparando argumentos dos dois mocks.
- `usage["function"]` vale `"data_extract_pdf"` quando chamado via `data_extract_pdf` e `"data_extract_file"` quando chamado via `data_extract_file` diretamente — verificável em testes unitários separados.
- `call_vertex_ai(contents=[{...}])` (sem `prompt_text`) chama `_call_vertex_raw` com o `contents` passado intacto — verificável em teste unitário.
- `call_vertex_ai(prompt_text="p", contents=[...])` levanta `ValueError` descritivo — verificável em teste unitário.
- `call_vertex_ai()` sem `prompt_text` e sem `contents` levanta `ValueError` descritivo — verificável em teste unitário.
- `data_extract_pdf(path, prompt, generation_config={"temperature": 0.1})` encaminha o dict como `config` ao Vertex — verificável em teste inspecionando `config` passado ao mock.
- `data_extract_pdf(path, prompt, generation_config={...}, response_schema={...})` levanta `ValueError` — verificável em teste unitário.
- `data_extract_ofx` e `data_extract_csv` com `generation_config` encaminham corretamente — mesmos critérios dos extractors binários.
- `_call_vertex_raw` retenta resposta `503` até 3 tentativas com backoff crescente — verificável em teste com mock que retorna `503` duas vezes e depois sucesso; confirmar 3 chamadas ao `generate_content`.
- `_call_vertex_raw` não retenta resposta `501` — mock retorna `501`, confirmar 1 única chamada e exceção imediata.
- `_call_vertex_raw` com jitter: sleep aplicado em backoff é diferente do valor exato `2 ** attempt * 2` (jitter foi adicionado) — verificável seedando `random` antes da chamada e inspecionando argumento de `time.sleep`.
- Suite completa de `test_ai.py` verde após as mudanças.
- Versão bumped de `0.2.1` para `0.3.0`.

## Decisões de Implementação

### Módulos a modificar

- `jedi_library/ai.py` — todas as quatro mudanças.
- `tests/test_ai.py` — novos testes para cada critério.
- `pyproject.toml` — bump `0.2.1` → `0.3.0`.

### Interfaces

**`data_extract_file` (novo):**
- Assinatura: `data_extract_file(file_path, mime_type, prompt_text, *, model, execution_id, response_schema, generation_config) -> dict`
- Cobre apenas arquivos binários via `inline_data` — PDF, imagem, XLSX. `data_extract_ofx/csv` continuam com concatenação textual; não delegam para `data_extract_file`.
- Contrato de retorno idêntico a `data_extract_pdf`: `{"result": dict, "usage": dict}`.
- `generation_config` e `response_schema` mutuamente exclusivos (mesmo padrão de `call_vertex_ai`).
- `function` no `usage` é `"data_extract_file"`.

**`data_extract_pdf` (refatorado):**
- Assinatura pública preservada (sem breaking change).
- Implementação delega para `data_extract_file(..., mime_type="application/pdf", ...)`.
- `function` no `usage` continua `"data_extract_pdf"` — para preservar o nome no `usage`, `data_extract_pdf` passa `function_name="data_extract_pdf"` para o helper `_build_usage`, que hoje recebe `function` como parâmetro posicional. `data_extract_file` passa `function_name="data_extract_file"`. Isso evita que callers que inspecionam `usage["function"]` vejam a mudança interna.

**`call_vertex_ai` (estendido):**
- `prompt_text` torna-se opcional (default `None`).
- Novo parâmetro keyword-only `contents: list | None = None`.
- Regra de validação: exatamente um dos dois deve ser não-nulo; ambos `None` ou ambos não-nulos levantam `ValueError` descritivo.
- Quando `contents` é passado, encaminhado diretamente para `_call_vertex_raw`; config montada normalmente (aceita `generation_config` ou `response_schema` como antes).

**`data_extract_ofx` e `data_extract_csv` (estendidos):**
- Ganham `generation_config: dict | None = None` com o mesmo contrato de `data_extract_file`.

**`_call_vertex_raw` (estendido):**
- Retry cobre `429` e `500–599` exceto `501`. Detecção via `google.genai.errors.ClientError` ou `ServerError` (tipo de exceção do SDK, não string match no message — o match de `"429" in str(e)` atual é substituído por inspeção estruturada do `code` do erro).
- Backoff com jitter: `sleep = 2 ** attempt * 2 + random.uniform(0, 0.5)`.
- Sem mudança de assinatura — mudança interna.

### Decisões arquiteturais

- **`data_extract_pdf` como wrapper thin** preserva compatibilidade com todos os callers existentes (tili) sem migration.
- **`data_extract_ofx/csv` não delegam para `data_extract_file`** — o mecanismo é diferente (texto concatenado vs `inline_data`). Unificação forçada criaria complexidade sem benefício.
- **`contents` externo em `call_vertex_ai`** é escape hatch explícito para casos avançados; não é o caminho padrão.
- **`generation_config` mutuamente exclusivo com `response_schema`** segue o contrato estabelecido em `call_vertex_ai` — consistência da API. Isso cria assimetria com o GAS (que combina os dois num único dict). Quem precisar dos dois pode construir o dict manualmente e passar via `generation_config`.
- **`501` não retentável** — `Not Implemented` é erro permanente de configuração. Retentar desperdiça tempo e atrasa o diagnóstico.
- **Detecção de status code via tipo de exceção do SDK** — evita string match frágil (`"500"` pode casar com timestamp ou content-length); o SDK `google-genai` expõe `ClientError.code` e `ServerError.code` de forma estruturada.

## Decisões de Teste

Bom teste aqui verifica o **contrato externo**: o que chega ao Vertex (formato de `contents`, valor de `config`) e o que sai da lib (formato de `response`). Não testa internals do jitter além de confirmar que foi aplicado.

Testes a escrever:
- `test_data_extract_file_monta_mime_type_correto` — inspeciona `contents[0]["parts"][0]["inline_data"]["mime_type"]`.
- `test_data_extract_file_role_user` — inspeciona `contents[0]["role"] == "user"`.
- `test_data_extract_file_usage_function_name` — confirma `usage["function"] == "data_extract_file"`.
- `test_data_extract_pdf_usage_function_name_preservado` — confirma `usage["function"] == "data_extract_pdf"` após refatoração para wrapper.
- `test_data_extract_pdf_delega_mime_type_pdf` — verifica que `contents` passado ao mock tem `mime_type="application/pdf"`.
- `test_call_vertex_ai_com_contents_externo` — confirma que `contents` passado chega intacto ao `_call_vertex_raw`.
- `test_call_vertex_ai_prompt_e_contents_juntos_levanta` — `ValueError`.
- `test_call_vertex_ai_sem_prompt_e_sem_contents_levanta` — `ValueError`.
- `test_data_extract_pdf_com_generation_config` — inspeciona `config` passado ao mock.
- `test_data_extract_pdf_generation_config_e_schema_juntos_levanta` — `ValueError`.
- `test_data_extract_ofx_com_generation_config` — mesmo padrão.
- `test_data_extract_csv_com_generation_config` — mesmo padrão.
- `test_retry_em_503_sucesso_na_terceira` — mock retorna exceção `ServerError(503)` duas vezes, depois sucesso; confirmar 3 chamadas ao `generate_content`.
- `test_sem_retry_em_501` — mock retorna `ClientError(501)`; confirmar 1 chamada e exceção imediata.
- `test_jitter_aplicado_no_backoff` — seeda `random` antes da chamada, captura argumento de `time.sleep`, confirma que difere do valor puro `2 ** attempt * 2`.

Prior art: `test_call_vertex_ai_retry_em_429` (`test_ai.py:200`) — mesmo padrão de mock com `side_effect` para os novos testes de retry.

## Fora de Escopo

- **Múltiplos turns de conversa** (`contents` com mais de um elemento `role: model` intercalado) — escape hatch cobre o caso, mas a lib não valida nem facilita multi-turn.
- **Streaming de resposta** — `generate_content` síncrono; streaming é feature separada.
- **Timeout configurável** — backoff com jitter cobre instabilidade; timeout absoluto por chamada fica para depois.
- **`data_extract_pdf` deprecated** — continua como alias conveniente indefinidamente.
- **Migração de callers existentes** (tili) para `data_extract_file` — tili migra quando precisar de tipo não-PDF; não é obrigação desta spec.
- **`data_extract_ofx/csv` via `inline_data`** — concatenação textual é o mecanismo correto para texto estruturado; `inline_data` é para binários opacos.

## Assumptions

1. `data_extract_file` como método público novo para binários; `data_extract_pdf` vira wrapper thin — sem breaking change.
2. `data_extract_ofx/csv` não delegam para `data_extract_file` — mecanismo textual vs binário são intencionalmente distintos.
3. `call_vertex_ai` com `contents` usa `prompt_text=None` como default — callers existentes que passam `prompt_text` posicional não quebram.
4. `generation_config` em `data_extract_*` mutuamente exclusivo com `response_schema`.
5. Detecção de status code via tipo de exceção do SDK `google-genai`, não string match.
6. Retry 5xx cobre `500–599` exceto `501`; jitter via `random.uniform(0, 0.5)`.
7. Bump `0.2.1` → `0.3.0`.
8. `data_extract_pdf` não deprecado nesta spec.

## Notas

- ADR base: `jedi-library/docs/81-referencia/decisoes/20260617-jedi-ai-client-pattern.md` — Client object pattern e contrato de `usage`.
- Referência GAS: `jedi-etl/src/gas/pr-finance-files/processFiles.gs` e `jedi-library-gas/src/gas/jediAI/callVertexAI.gs` — fonte dos padrões de paridade desta spec.
- Bug corrigido em 0.2.1 (`role: "user"`) é pré-requisito desta spec; está em `main`.
- Consumidor imediato após esta spec: `tili/infra/ia/vertex.py` (migração para `JediAI` + `generation_config` + `response_schema`).
- **Regra-de-2 dispensada via cláusula de exceção** (ADR `20260612-regra-de-2-consumidores-reais`): capacidades cobertas são maduras em `jediAI` GAS (consumidor: pr-finance-files em produção); adoção em tili é iminente. Segundo consumidor Python real: tili (extração de JPEG/imagem do inbox) — confirmado como próximo passo da spec de alinhamento `20260617-spec-alinhamento-env-vars-jediai.md`.
- **Assimetria `generation_config` vs GAS:** o GAS combina `responseMimeType + temperature + topK + topP` num único dict passado a `callVertexAI`. Python mantém `generation_config` e `response_schema` mutuamente exclusivos por consistência interna; quem precisar de ambos constrói o dict manualmente e passa via `generation_config` (incluindo `response_mime_type`).
