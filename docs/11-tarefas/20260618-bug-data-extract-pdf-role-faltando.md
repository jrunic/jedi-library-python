---
id: 202606180100
projeto: jedi-library-python
tipo: bug
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Bug — JediAI.data_extract_pdf 0.2.0 monta contents sem campo role, Vertex rejeita com HTTP 400 'Please use a valid role: user, model'"
tags: [bug, jedi-ai, vertex, role, data-extract, 0.2.0]
---

# Bug: `JediAI.data_extract_pdf` 0.2.0 monta `contents` sem `role`

## Status

Aberto — descoberto em 2026-06-18 durante smoke do tili (spec `tili/docs/11-tarefas/20260617-spec-alinhamento-env-vars-jediai.md`, Task 3 do plano).

## Resumo

`jedi_library.ai.JediAI.data_extract_pdf` (release `0.2.0`, SHA `f7a27b9`) constrói `contents` sem o campo `role`, o que faz o Vertex AI retornar HTTP 400 antes de processar a chamada. A regressão é silenciosa nos testes unitários da lib porque eles mockam `_call_vertex_raw` — nunca exercitam o formato real esperado pela API.

## Reprodução

Ambiente:
- `jedi-library-python==0.2.0` (SHA `f7a27b9625832f4f8ad2e7c2bd746ca27be19dd4`)
- `JediAI.from_env()` com `JEDI_AI_GCP_PROJECT_ID` + `GOOGLE_APPLICATION_CREDENTIALS` configurados
- Schema JSON válido (sem `null` em enum, sem `oneOf`/`anyOf`)
- 1 PDF qualquer

Script:

```python
from jedi_library.ai import JediAI

ai = JediAI.from_env()
ai.data_extract_pdf(
    "/path/qualquer.pdf",
    "Extraia o documento e responda em JSON.",
    model="gemini-2.5-flash",
    response_schema={"type": "object", "properties": {"x": {"type": "string"}}},
)
```

**Resultado observado:**

```
google.genai.errors.ClientError: 400 INVALID_ARGUMENT.
{'error': {'code': 400, 'message': "Please use a valid role: user, model.", 'status': 'INVALID_ARGUMENT'}}
```

**Resultado esperado:** chamada Vertex bem-sucedida, retorno `{"result": ..., "usage": ...}`.

## Causa raiz

No commit `7d8bd58` (feat: adiciona response_schema), o helper que monta `contents` em `data_extract_pdf` produz:

```python
contents = [{"parts": [
    {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
    {"text": prompt_text},
]}]
```

Falta o campo `role`. Vertex AI exige `role: "user"` (ou `"model"`) em cada turn de `contents` para identificar quem produziu a mensagem. Sem isso, a request é rejeitada na borda da API.

Reprodução do bypass que confirma a hipótese (smoke do tili):

```python
# Bypass: chamar _client.models.generate_content direto com role explícito
contents = [{
    "role": "user",
    "parts": [
        {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
        {"text": prompt_text},
    ],
}]
ai._client.models.generate_content(
    model="gemini-2.5-flash",
    contents=contents,
    config={"response_mime_type": "application/json", "response_schema": schema},
)
# → 200 OK, JSON estruturado retornado corretamente
```

## Escopo do impacto

- **`data_extract_pdf`** — confirmado quebrado (smoke do tili).
- **`data_extract_ofx`** e **`data_extract_csv`** — provavelmente quebrados pelo mesmo padrão (mesmo helper / mesma omissão). Verificar.
- **`call_vertex_ai`** — depende do formato em que recebe `contents`/`prompt_text`. Verificar.

## Fix proposto

Adicionar `"role": "user"` no único turn de `contents` nos 3 métodos `data_extract_*` (e em `call_vertex_ai` se aplicável):

```python
contents = [{
    "role": "user",
    "parts": [
        {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
        {"text": prompt_text},
    ],
}]
```

## Gap de cobertura de teste

A suite atual passa porque mocka `_call_vertex_raw`:

```python
# (padrão atual dos testes da 0.2.0)
monkeypatch.setattr(JediAI, "_call_vertex_raw", lambda self, contents, model, config: <fake response>)
```

Isso valida que `response_schema` é encaminhado para `config`, mas **não exercita o formato de `contents`**. Adicionar:

1. **Teste de contrato de `contents`:** após call a `data_extract_pdf`, inspecionar `contents` passado ao mock e assertar `contents[0]["role"] == "user"` + `contents[0]["parts"]` contém `inline_data` + `text`.
2. **Smoke test opcional (skip se sem credencial):** chamada real ao Vertex com PDF mínimo (1 página, schema trivial). Marcado com `@pytest.mark.requires_vertex_credentials`; pulado em CI sem secret, rodado manualmente antes de release.

## Critérios de Aceite

- `JediAI.data_extract_pdf(file, prompt, model=..., response_schema=...)` retorna 200 OK contra Vertex real.
- Mesmo para `data_extract_ofx` e `data_extract_csv` (verificar se afetados).
- Teste novo confirma `role: "user"` em `contents[0]`.
- Bump de versão minor (`0.2.1`).

## Referências

- Spec original da feature: `docs/11-tarefas/20260617-spec-response-schema-data-extract.md`
- Smoke que descobriu o bug: tili plan `20260617-plano-alinhamento-env-vars-jediai.md` Task 3
- Documentação Vertex AI / `generate_content` content format: <https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference> (campo `role` obrigatório em `Content`)

## Bloqueio em consumidores

- **tili** está bloqueado para o plumbing de `response_schema` (Task 8 do plano de tili) até este bug ser corrigido e nova versão pinada via `uv.lock`. Workaround temporário no tili (bypassar a lib chamando `_client` direto) **rejeitado** por acoplar com internals.
