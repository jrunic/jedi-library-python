---
id: 202606181100
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — paridade JediAI Python com pr-finance-files GAS: data_extract_file, contents externo, generation_config e retry robusto"
tags: [plano-execucao, jedi-ai, vertex, paridade, gas, retry, generation-config]
spec: docs/11-tarefas/20260618-spec-paridade-jediai-gas.md
---

# Paridade JediAI Python com pr-finance-files GAS — Plano de Implementação

**Objetivo:** Adicionar `data_extract_file` genérico, `contents` externo em `call_vertex_ai`, `generation_config` nos extractors e retry 5xx+jitter em `_call_vertex_raw` — sem breaking change.

**Arquitetura:** `data_extract_file` é o novo núcleo para binários via `inline_data`; `data_extract_pdf` vira wrapper thin que delega para ele passando `_function_name="data_extract_pdf"` para preservar o `usage["function"]`. `_call_vertex_raw` ganha detecção estruturada de código de erro via `getattr(e, "code", None)` em vez de string match, cobrindo 429 e 5xx exceto 501. `call_vertex_ai` recebe `contents: list | None = None` como escape hatch explícito para multipart.

**Pilha técnica:** Python 3.12, `google-genai`, `pytest`, `unittest.mock`.

---

## Mapa de Arquivos

| Arquivo | Operação | Responsabilidade |
|---|---|---|
| `jedi_library/ai.py` | Modificar | Todas as quatro mudanças |
| `tests/test_ai.py` | Modificar | Novos testes + atualização de `test_call_vertex_ai_retry_em_429` |
| `pyproject.toml` | Modificar | Bump `0.2.1` → `0.3.0` |

---

## Task 1: Retry 5xx + jitter em `_call_vertex_raw`

**Arquivos:**
- Modificar: `jedi_library/ai.py` — `_call_vertex_raw` + import `random`
- Modificar: `tests/test_ai.py` — `test_call_vertex_ai_retry_em_429` (atualização) + 3 novos testes

- [ ] **Step 1: Adiciona classe auxiliar de erro nos testes**

No topo de `tests/test_ai.py`, após os imports existentes, adicionar:

```python
class _FakeServerError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"server error {code}")

class _FakeClientError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"client error {code}")
```

- [ ] **Step 2: Atualiza `test_call_vertex_ai_retry_em_429` para usar `.code`**

Localizar `test_call_vertex_ai_retry_em_429` em `tests/test_ai.py:200` e substituir:

```python
def test_call_vertex_ai_retry_em_429(ai_client, mock_genai):
    _, mock_client, mock_response = mock_genai
    mock_client.models.generate_content.side_effect = [
        _FakeClientError(429),
        mock_response,
    ]
    with patch("jedi_library.ai.time.sleep") as mock_sleep:
        response = ai_client.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}
    mock_sleep.assert_called_once()
    sleep_arg = mock_sleep.call_args[0][0]
    assert sleep_arg >= 2  # base backoff de 2^0 * 2 = 2
```

- [ ] **Step 3: Escreve testes falhantes para 5xx e jitter**

Adicionar ao final de `tests/test_ai.py`, antes de fechar o arquivo:

```python
# ---------------------------------------------------------------------------
# _call_vertex_raw — retry 5xx e jitter
# ---------------------------------------------------------------------------

def test_retry_em_503_sucesso_na_terceira(ai_client, mock_genai):
    _, mock_client, mock_response = mock_genai
    mock_client.models.generate_content.side_effect = [
        _FakeServerError(503),
        _FakeServerError(503),
        mock_response,
    ]
    with patch("jedi_library.ai.time.sleep"):
        response = ai_client.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}
    assert mock_client.models.generate_content.call_count == 3


def test_sem_retry_em_501(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    mock_client.models.generate_content.side_effect = _FakeServerError(501)
    with pytest.raises(_FakeServerError):
        ai_client.call_vertex_ai("p")
    assert mock_client.models.generate_content.call_count == 1


def test_jitter_aplicado_no_backoff(ai_client, mock_genai):
    _, mock_client, mock_response = mock_genai
    mock_client.models.generate_content.side_effect = [
        _FakeClientError(429),
        mock_response,
    ]
    with patch("jedi_library.ai.time.sleep") as mock_sleep:
        with patch("jedi_library.ai.random.uniform", return_value=0.3):
            ai_client.call_vertex_ai("p")
    sleep_arg = mock_sleep.call_args[0][0]
    # 2**0 * 2 + 0.3 = 2.3; valor puro seria 2
    assert sleep_arg == pytest.approx(2.3)
```

- [ ] **Step 4: Roda os 3 novos testes para verificar que falham**

```bash
cd /Users/jedi/jedi-brain/15-repositorios/jedi-library-python
uv run pytest tests/test_ai.py::test_retry_em_503_sucesso_na_terceira tests/test_ai.py::test_sem_retry_em_501 tests/test_ai.py::test_jitter_aplicado_no_backoff -v
```

Esperado: `FAILED` — `_call_vertex_raw` ainda usa string match e não cobre 5xx.

- [ ] **Step 5: Verifica empiricamente que o SDK expõe `.code` nas exceções**

```bash
uv run python -c "
from google.genai import errors
print('attrs ClientError:', [a for a in dir(errors.ClientError) if not a.startswith('_')])
try:
    raise errors.ClientError(429, {'error': {'message': 'test'}}, None)
except errors.ClientError as e:
    print('code via getattr:', getattr(e, 'code', None))
"
```

Esperado: `code via getattr: 429`. Se retornar `None` ou AttributeError, o atributo tem nome diferente — ajustar `getattr(e, "code", None)` para o nome real antes de prosseguir.

- [ ] **Step 5.5: Adiciona `import random` em `jedi_library/ai.py`**

Localizar linha 17 (`import time`) e inserir `import random` logo acima:

```python
import random
import time
```

- [ ] **Step 6: Reescreve `_call_vertex_raw` com detecção estruturada**

Substituir o método `_call_vertex_raw` existente (`ai.py:158-168`) por:

```python
def _call_vertex_raw(self, contents, model: str, config: dict):
    for attempt in range(3):
        try:
            return self._client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as e:
            code = getattr(e, "code", None)
            is_429 = code == 429
            is_5xx_retryable = (
                code is not None and 500 <= code <= 599 and code != 501
            )
            if (is_429 or is_5xx_retryable) and attempt < 2:
                time.sleep(2 ** attempt * 2 + random.uniform(0, 0.5))
            else:
                raise
```

- [ ] **Step 7: Roda a suite completa de `test_ai.py`**

```bash
uv run pytest tests/test_ai.py -v
```

Esperado: todos os testes `PASSED`, incluindo `test_call_vertex_ai_retry_em_429` atualizado.

- [ ] **Step 8: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): retry 5xx + jitter em _call_vertex_raw — paridade com pr-finance-files GAS"
```

---

## Task 2: `data_extract_file` — novo método genérico para binários

**Arquivos:**
- Modificar: `jedi_library/ai.py` — novo método `data_extract_file`
- Modificar: `tests/test_ai.py` — 5 novos testes

- [ ] **Step 1: Escreve testes falhantes para `data_extract_file`**

Adicionar ao final de `tests/test_ai.py`:

```python
# ---------------------------------------------------------------------------
# data_extract_file
# ---------------------------------------------------------------------------

def test_data_extract_file_monta_mime_type_correto(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    img = tmp_path / "foto.jpg"
    img.write_bytes(b"\xff\xd8\xff fake jpeg")
    ai_client.data_extract_file(str(img), "image/jpeg", "extraia dados")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert contents[0]["parts"][0]["inline_data"]["mime_type"] == "image/jpeg"


def test_data_extract_file_role_user(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    img = tmp_path / "doc.png"
    img.write_bytes(b"PNG fake")
    ai_client.data_extract_file(str(img), "image/png", "extraia")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert contents[0]["role"] == "user"


def test_data_extract_file_usage_function_name(ai_client, mock_genai, tmp_path):
    img = tmp_path / "doc.jpg"
    img.write_bytes(b"fake")
    response = ai_client.data_extract_file(str(img), "image/jpeg", "p")
    assert response["usage"]["function"] == "data_extract_file"


def test_data_extract_file_com_generation_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    img = tmp_path / "doc.jpg"
    img.write_bytes(b"fake")
    ai_client.data_extract_file(
        str(img), "image/jpeg", "p",
        generation_config={"temperature": 0.1, "top_k": 32}
    )
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config == {"temperature": 0.1, "top_k": 32}


def test_data_extract_file_generation_config_e_schema_juntos_levanta(ai_client, tmp_path):
    img = tmp_path / "doc.jpg"
    img.write_bytes(b"fake")
    with pytest.raises(ValueError, match="generation_config"):
        ai_client.data_extract_file(
            str(img), "image/jpeg", "p",
            generation_config={"temperature": 0.1},
            response_schema={"type": "object"},
        )


def test_data_extract_file_arquivo_grande_levanta_value_error(ai_client, tmp_path):
    big_file = tmp_path / "foto.jpg"
    big_file.write_bytes(b"x" * (7 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="7 MB"):
        ai_client.data_extract_file(str(big_file), "image/jpeg", "p")
```

- [ ] **Step 2: Roda os testes para verificar que falham**

```bash
uv run pytest tests/test_ai.py::test_data_extract_file_monta_mime_type_correto tests/test_ai.py::test_data_extract_file_role_user tests/test_ai.py::test_data_extract_file_usage_function_name tests/test_ai.py::test_data_extract_file_com_generation_config tests/test_ai.py::test_data_extract_file_generation_config_e_schema_juntos_levanta tests/test_ai.py::test_data_extract_file_arquivo_grande_levanta_value_error -v
```

Esperado: `FAILED` — `JediAI` não tem `data_extract_file`.

- [ ] **Step 3: Implementa `data_extract_file` em `ai.py`**

Inserir após o método `data_extract_pdf` (após linha 239, antes de `def data_extract_ofx`):

```python
def data_extract_file(
    self,
    file_path: str,
    mime_type: str,
    prompt_text: str,
    *,
    model: str = DEFAULT_MODEL,
    execution_id: str | None = None,
    response_schema: dict | None = None,
    generation_config: dict | None = None,
    _function_name: str = "data_extract_file",
) -> dict:
    if generation_config is not None and response_schema is not None:
        raise ValueError(
            "Passe generation_config OU response_schema, não os dois. "
            "Se precisa de ambos, inclua response_schema dentro de generation_config."
        )
    file_bytes = _read_file_bytes(file_path)
    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError(
            f"Arquivo excede limite de 7 MB para inlineData ({len(file_bytes)} bytes)."
        )
    file_b64 = base64.b64encode(file_bytes).decode("utf-8")
    contents = [{"role": "user", "parts": [
        {"inline_data": {"mime_type": mime_type, "data": file_b64}},
        {"text": prompt_text},
    ]}]
    config = generation_config if generation_config is not None else _build_config(response_schema)

    status = "success"
    token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

    try:
        response = self._call_vertex_raw(contents, model, config)
        token_counts = _extract_token_counts(response)
        result = json.loads(response.text)
    except Exception:
        status = "error"
        raise
    finally:
        _usage = _build_usage(model, _function_name, token_counts, status, execution_id)
        self._dispatch_usage(_usage)

    return {"result": result, "usage": _usage}
```

- [ ] **Step 4: Roda os testes novos**

```bash
uv run pytest tests/test_ai.py::test_data_extract_file_monta_mime_type_correto tests/test_ai.py::test_data_extract_file_role_user tests/test_ai.py::test_data_extract_file_usage_function_name tests/test_ai.py::test_data_extract_file_com_generation_config tests/test_ai.py::test_data_extract_file_generation_config_e_schema_juntos_levanta tests/test_ai.py::test_data_extract_file_arquivo_grande_levanta_value_error -v
```

Esperado: todos `PASSED`.

- [ ] **Step 5: Roda suite completa**

```bash
uv run pytest tests/test_ai.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona data_extract_file — extração genérica de binário via inline_data"
```

---

## Task 3: `data_extract_pdf` vira wrapper thin de `data_extract_file`

**Arquivos:**
- Modificar: `jedi_library/ai.py` — `data_extract_pdf` delega para `data_extract_file`
- Modificar: `tests/test_ai.py` — 3 novos testes

- [ ] **Step 1: Escreve testes falhantes**

Adicionar ao final de `tests/test_ai.py`:

```python
# ---------------------------------------------------------------------------
# data_extract_pdf como wrapper de data_extract_file
# ---------------------------------------------------------------------------

def test_data_extract_pdf_delega_mime_type_pdf(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake pdf")
    ai_client.data_extract_pdf(str(pdf_file), "prompt")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert contents[0]["parts"][0]["inline_data"]["mime_type"] == "application/pdf"


def test_data_extract_pdf_usage_function_name_preservado(ai_client, mock_genai, tmp_path):
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake")
    response = ai_client.data_extract_pdf(str(pdf_file), "p")
    assert response["usage"]["function"] == "data_extract_pdf"


def test_data_extract_pdf_com_generation_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake")
    ai_client.data_extract_pdf(
        str(pdf_file), "p",
        generation_config={"temperature": 0.1, "top_k": 32}
    )
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config == {"temperature": 0.1, "top_k": 32}
```

- [ ] **Step 2: Roda os testes para verificar que falham**

```bash
uv run pytest tests/test_ai.py::test_data_extract_pdf_delega_mime_type_pdf tests/test_ai.py::test_data_extract_pdf_usage_function_name_preservado tests/test_ai.py::test_data_extract_pdf_com_generation_config -v
```

Esperado: `test_data_extract_pdf_com_generation_config` falha — `data_extract_pdf` não aceita `generation_config` ainda. Os outros dois já passam ou dependem da refatoração.

- [ ] **Step 3: Substitui implementação de `data_extract_pdf` em `ai.py`**

Substituir o método `data_extract_pdf` inteiro (linhas `203–239`) por:

```python
def data_extract_pdf(
    self,
    file_path: str,
    prompt_text: str,
    *,
    model: str = DEFAULT_MODEL,
    execution_id: str | None = None,
    response_schema: dict | None = None,
    generation_config: dict | None = None,
) -> dict:
    return self.data_extract_file(
        file_path,
        "application/pdf",
        prompt_text,
        model=model,
        execution_id=execution_id,
        response_schema=response_schema,
        generation_config=generation_config,
        _function_name="data_extract_pdf",
    )
```

- [ ] **Step 4: Roda suite completa**

```bash
uv run pytest tests/test_ai.py -v
```

Esperado: todos `PASSED`. Em especial confirmar que testes de `data_extract_pdf` preexistentes (`test_data_extract_pdf_retorna_result_e_usage`, `test_data_extract_pdf_arquivo_grande_levanta_value_error`, etc.) continuam passando.

- [ ] **Step 5: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "refactor(ai): data_extract_pdf vira wrapper thin de data_extract_file"
```

---

## Task 4: `generation_config` em `data_extract_ofx` e `data_extract_csv`

**Arquivos:**
- Modificar: `jedi_library/ai.py` — `data_extract_ofx` e `data_extract_csv`
- Modificar: `tests/test_ai.py` — 4 novos testes (2 por método)

- [ ] **Step 1: Escreve testes falhantes**

Adicionar ao final de `tests/test_ai.py`:

```python
# ---------------------------------------------------------------------------
# generation_config em data_extract_ofx e data_extract_csv
# ---------------------------------------------------------------------------

def test_data_extract_ofx_com_generation_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    ofx_file = tmp_path / "extrato.ofx"
    ofx_file.write_text("OFX DATA", encoding="utf-8")
    ai_client.data_extract_ofx(
        str(ofx_file), "p",
        generation_config={"temperature": 0.1}
    )
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config == {"temperature": 0.1}


def test_data_extract_ofx_generation_config_e_schema_juntos_levanta(ai_client, tmp_path):
    ofx_file = tmp_path / "e.ofx"
    ofx_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="generation_config"):
        ai_client.data_extract_ofx(
            str(ofx_file), "p",
            generation_config={"temperature": 0.1},
            response_schema={"type": "object"},
        )


def test_data_extract_csv_com_generation_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    csv_file = tmp_path / "dados.csv"
    csv_file.write_text("col1,col2\n1,2", encoding="utf-8")
    ai_client.data_extract_csv(
        str(csv_file), "p",
        generation_config={"temperature": 0.1}
    )
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config == {"temperature": 0.1}


def test_data_extract_csv_generation_config_e_schema_juntos_levanta(ai_client, tmp_path):
    csv_file = tmp_path / "d.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="generation_config"):
        ai_client.data_extract_csv(
            str(csv_file), "p",
            generation_config={"temperature": 0.1},
            response_schema={"type": "object"},
        )
```

- [ ] **Step 2: Roda os testes para verificar que falham**

```bash
uv run pytest tests/test_ai.py::test_data_extract_ofx_com_generation_config tests/test_ai.py::test_data_extract_ofx_generation_config_e_schema_juntos_levanta tests/test_ai.py::test_data_extract_csv_com_generation_config tests/test_ai.py::test_data_extract_csv_generation_config_e_schema_juntos_levanta -v
```

Esperado: `FAILED` — `data_extract_ofx` e `data_extract_csv` não aceitam `generation_config`.

- [ ] **Step 3: Atualiza `data_extract_ofx` em `ai.py`**

Substituir o método `data_extract_ofx` inteiro por:

```python
def data_extract_ofx(
    self,
    file_path: str,
    prompt_text: str,
    *,
    model: str = DEFAULT_MODEL,
    execution_id: str | None = None,
    response_schema: dict | None = None,
    generation_config: dict | None = None,
) -> dict:
    if generation_config is not None and response_schema is not None:
        raise ValueError(
            "Passe generation_config OU response_schema, não os dois. "
            "Se precisa de ambos, inclua response_schema dentro de generation_config."
        )
    with open(file_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    full_prompt = prompt_text + "\n\n" + content
    config = generation_config if generation_config is not None else _build_config(response_schema)

    status = "success"
    token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

    try:
        response = self._call_vertex_raw(full_prompt, model, config)
        token_counts = _extract_token_counts(response)
        result = json.loads(response.text)
    except Exception:
        status = "error"
        raise
    finally:
        _usage = _build_usage(model, "data_extract_ofx", token_counts, status, execution_id)
        self._dispatch_usage(_usage)

    return {"result": result, "usage": _usage}
```

- [ ] **Step 4: Atualiza `data_extract_csv` em `ai.py`**

Substituir o método `data_extract_csv` inteiro por:

```python
def data_extract_csv(
    self,
    file_path: str,
    prompt_text: str,
    *,
    model: str = DEFAULT_MODEL,
    execution_id: str | None = None,
    response_schema: dict | None = None,
    generation_config: dict | None = None,
) -> dict:
    if generation_config is not None and response_schema is not None:
        raise ValueError(
            "Passe generation_config OU response_schema, não os dois. "
            "Se precisa de ambos, inclua response_schema dentro de generation_config."
        )
    with open(file_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    full_prompt = prompt_text + "\n\n" + content
    config = generation_config if generation_config is not None else _build_config(response_schema)

    status = "success"
    token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

    try:
        response = self._call_vertex_raw(full_prompt, model, config)
        token_counts = _extract_token_counts(response)
        result = json.loads(response.text)
    except Exception:
        status = "error"
        raise
    finally:
        _usage = _build_usage(model, "data_extract_csv", token_counts, status, execution_id)
        self._dispatch_usage(_usage)

    return {"result": result, "usage": _usage}
```

- [ ] **Step 5: Roda suite completa**

```bash
uv run pytest tests/test_ai.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): generation_config em data_extract_ofx e data_extract_csv"
```

---

## Task 5: `contents` externo em `call_vertex_ai`

**Arquivos:**
- Modificar: `jedi_library/ai.py` — `call_vertex_ai`
- Modificar: `tests/test_ai.py` — 3 novos testes

- [ ] **Step 1: Escreve testes falhantes**

Adicionar ao final de `tests/test_ai.py`:

```python
# ---------------------------------------------------------------------------
# call_vertex_ai — contents externo
# ---------------------------------------------------------------------------

def test_call_vertex_ai_com_contents_externo(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    contents = [{"role": "user", "parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": "base64aqui"}},
        {"text": "extraia"},
    ]}]
    ai_client.call_vertex_ai(contents=contents)
    call_args = mock_client.models.generate_content.call_args
    assert call_args.kwargs["contents"] == contents


def test_call_vertex_ai_prompt_e_contents_juntos_levanta(ai_client, mock_genai):
    with pytest.raises(ValueError, match="prompt_text"):
        ai_client.call_vertex_ai(
            "meu prompt",
            contents=[{"role": "user", "parts": [{"text": "outro"}]}],
        )


def test_call_vertex_ai_sem_prompt_e_sem_contents_levanta(ai_client, mock_genai):
    with pytest.raises(ValueError, match="prompt_text"):
        ai_client.call_vertex_ai()
```

- [ ] **Step 2: Roda os testes para verificar que falham**

```bash
uv run pytest tests/test_ai.py::test_call_vertex_ai_com_contents_externo tests/test_ai.py::test_call_vertex_ai_prompt_e_contents_juntos_levanta tests/test_ai.py::test_call_vertex_ai_sem_prompt_e_sem_contents_levanta -v
```

Esperado: `FAILED` — `call_vertex_ai` não aceita `contents` e não valida ausência de ambos.

- [ ] **Step 3: Atualiza `call_vertex_ai` em `ai.py`**

Substituir o método `call_vertex_ai` inteiro (linhas `170–201`) por:

```python
def call_vertex_ai(
    self,
    prompt_text: str | None = None,
    *,
    model: str = DEFAULT_MODEL,
    generation_config: dict | None = None,
    response_schema: dict | None = None,
    execution_id: str | None = None,
    contents: list | None = None,
) -> dict:
    if prompt_text is not None and contents is not None:
        raise ValueError(
            "Passe prompt_text OU contents, não os dois."
        )
    if prompt_text is None and contents is None:
        raise ValueError(
            "Um de prompt_text ou contents é obrigatório."
        )
    if generation_config is not None and response_schema is not None:
        raise ValueError(
            "Passe generation_config OU response_schema, não os dois. "
            "Se precisa de ambos, inclua response_schema dentro de generation_config."
        )
    config = generation_config if generation_config is not None else _build_config(response_schema)
    _contents = contents if contents is not None else prompt_text
    status = "success"
    token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}
    raw_text = ""

    try:
        response = self._call_vertex_raw(_contents, model, config)
        raw_text = response.text
        token_counts = _extract_token_counts(response)
        result = json.loads(raw_text)
    except Exception:
        status = "error"
        raise
    finally:
        _usage = _build_usage(model, "call_vertex_ai", token_counts, status, execution_id)
        self._dispatch_usage(_usage)

    return {"result": result, "usage": _usage, "raw_text": raw_text}
```

- [ ] **Step 4: Roda suite completa**

```bash
uv run pytest tests/test_ai.py -v
```

Esperado: todos `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): call_vertex_ai aceita contents externo para chamadas multipart"
```

---

## Task 6: Bump de versão `0.2.1` → `0.3.0`

**Arquivos:**
- Modificar: `pyproject.toml` — campo `version`

- [ ] **Step 1: Atualiza versão em `pyproject.toml`**

Na linha 3 de `pyproject.toml`, substituir:

```toml
version = "0.2.1"
```

por:

```toml
version = "0.3.0"
```

- [ ] **Step 2: Roda suite completa uma última vez**

```bash
uv run pytest tests/ -v
```

Esperado: todos `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump versão 0.2.1 → 0.3.0 (feature: paridade JediAI com pr-finance-files GAS)"
```

---

## Auto-Revisão

### 1. Cobertura da Spec

| Requisito da Spec | Task |
|---|---|
| `data_extract_file` com qualquer `mime_type` | Task 2 |
| `data_extract_pdf` delega para `data_extract_file` | Task 3 |
| `usage["function"]` preservado em `data_extract_pdf` | Task 3 |
| `generation_config` em `data_extract_file/pdf` | Task 3 (via Task 2) |
| `generation_config` em `data_extract_ofx` e `data_extract_csv` | Task 4 |
| `contents` externo em `call_vertex_ai` | Task 5 |
| `prompt_text` e `contents` juntos → `ValueError` | Task 5 |
| Nenhum dos dois → `ValueError` | Task 5 |
| Retry 5xx (exceto 501) + jitter | Task 1 |
| Detecção estruturada via `.code` (não string match) | Task 1 |
| Bump `0.2.1` → `0.3.0` | Task 6 |

Todos os critérios de sucesso da spec cobertos.

### 2. Scan de Placeholders

Nenhum TBD, TODO ou "..." encontrado.

### 3. Consistência de Tipos/Nomes

- `_function_name` introduzido na Task 2 é o mesmo nome usado na Task 3 — consistente.
- `generation_config` usado com mesmo contrato em Tasks 2, 3, 4 e 5 — consistente.
- `contents` como `list | None` em Task 5 — consistente com uso em `_call_vertex_raw` existente.
- `_FakeServerError` e `_FakeClientError` introduzidos na Task 1 são reutilizados nas Tasks subsequentes — consistente.
