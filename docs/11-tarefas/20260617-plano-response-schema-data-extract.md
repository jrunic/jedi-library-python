---
id: 202606172300
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
tags: [plano-execucao, python, ai, vertex, structured-output, response-schema, tdd]
spec: ../../../jedi-library/docs/11-tarefas/20260617-spec-response-schema-data-extract.md
descricao: "Plano — adicionar response_schema a data_extract_* e call_vertex_ai de JediAI"
---

# `response_schema` em `JediAI.data_extract_*` — Plano de Implementação

**Objetivo:** Estender `data_extract_pdf`, `data_extract_ofx`, `data_extract_csv` e `call_vertex_ai` com parâmetro `response_schema: dict | None = None` que, quando presente, é incluído no `config` enviado ao Vertex AI — ativando Structured Output sem quebrar callers existentes.

**Arquitetura:** Helper privado de módulo `_build_config(response_schema)` centraliza a construção do `config` dict. Cada método público valida o tipo de `response_schema` antes de chamar `_call_vertex_raw`. `_call_vertex_raw` e helpers de usage não mudam. Mudança é additive — `response_schema=None` preserva comportamento atual.

**Pilha técnica:** Python 3.12, `google-genai`, `pytest`, `unittest.mock`.

**Baseline:** 116 testes passando.

**Comando de teste:** `cd /Users/jedi/jedi-brain/15-repositorios/jedi-library-python && uv run pytest tests/ -q`

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jedi_library/ai.py` | Modificar | `_build_config()` + `response_schema` nos 4 métodos |
| `tests/test_ai.py` | Modificar | Testes de schema presente, ausente, malformado |
| `pyproject.toml` | Modificar | Bump de versão `0.1.0` → `0.2.0` |

---

## Task 1: `_build_config()` + `response_schema` em `data_extract_pdf`, `data_extract_ofx`, `data_extract_csv`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (~linhas 1-50 helper; 186-281 métodos)
- Modificar: `tests/test_ai.py`

- [ ] **Step 1: Adiciona 9 testes falhantes a `tests/test_ai.py`**

```python
# Adicionar ao tests/test_ai.py — seção response_schema (data_extract_*)

# --- data_extract_pdf ---

def test_data_extract_pdf_schema_incluido_no_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    schema = {"type": "object", "properties": {"valor": {"type": "integer"}}}
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake pdf")
    ai_client.data_extract_pdf(str(pdf_file), "extraia", response_schema=schema)
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config["response_schema"] == schema
    assert config["response_mime_type"] == "application/json"


def test_data_extract_pdf_sem_schema_config_sem_response_schema(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake pdf")
    ai_client.data_extract_pdf(str(pdf_file), "extraia")
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert "response_schema" not in config
    assert config["response_mime_type"] == "application/json"


def test_data_extract_pdf_schema_nao_dict_levanta_value_error(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake pdf")
    with pytest.raises(ValueError, match="dict"):
        ai_client.data_extract_pdf(str(pdf_file), "p", response_schema="nao-e-dict")
    mock_client.models.generate_content.assert_not_called()


# --- data_extract_ofx ---

def test_data_extract_ofx_schema_incluido_no_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    schema = {"type": "object", "properties": {"total": {"type": "number"}}}
    ofx_file = tmp_path / "extrato.ofx"
    ofx_file.write_text("OFX DATA", encoding="utf-8")
    ai_client.data_extract_ofx(str(ofx_file), "extraia", response_schema=schema)
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config["response_schema"] == schema
    assert config["response_mime_type"] == "application/json"


def test_data_extract_ofx_sem_schema_config_sem_response_schema(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    ofx_file = tmp_path / "extrato.ofx"
    ofx_file.write_text("OFX DATA", encoding="utf-8")
    ai_client.data_extract_ofx(str(ofx_file), "extraia")
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert "response_schema" not in config


def test_data_extract_ofx_schema_nao_dict_levanta_value_error(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    ofx_file = tmp_path / "e.ofx"
    ofx_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="dict"):
        ai_client.data_extract_ofx(str(ofx_file), "p", response_schema=["lista"])
    mock_client.models.generate_content.assert_not_called()


# --- data_extract_csv ---

def test_data_extract_csv_schema_incluido_no_config(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    schema = {"type": "object", "properties": {"linhas": {"type": "array"}}}
    csv_file = tmp_path / "dados.csv"
    csv_file.write_text("col1,col2\n1,2", encoding="utf-8")
    ai_client.data_extract_csv(str(csv_file), "extraia", response_schema=schema)
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config["response_schema"] == schema
    assert config["response_mime_type"] == "application/json"


def test_data_extract_csv_sem_schema_config_sem_response_schema(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    csv_file = tmp_path / "dados.csv"
    csv_file.write_text("col1,col2\n1,2", encoding="utf-8")
    ai_client.data_extract_csv(str(csv_file), "extraia")
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert "response_schema" not in config


def test_data_extract_csv_schema_nao_dict_levanta_value_error(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    csv_file = tmp_path / "d.csv"
    csv_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="dict"):
        ai_client.data_extract_csv(str(csv_file), "p", response_schema=42)
    mock_client.models.generate_content.assert_not_called()
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_data_extract_pdf_schema_incluido_no_config -v
```
Esperado: `FAILED` — `data_extract_pdf() got an unexpected keyword argument 'response_schema'`

- [ ] **Step 3: Adiciona `_build_config()` em `jedi_library/ai.py`** (após `_read_file_bytes`, antes da classe)

```python
def _build_config(response_schema: dict | None) -> dict:
    if response_schema is not None and not isinstance(response_schema, dict):
        raise ValueError(
            f"response_schema deve ser dict, recebido {type(response_schema).__name__}."
        )
    config: dict = {"response_mime_type": "application/json"}
    if response_schema is not None:
        config["response_schema"] = response_schema
    return config
```

Validação centralizada aqui — os métodos públicos não precisam repetir o `isinstance` check.

- [ ] **Step 4: Atualiza `data_extract_pdf` em `jedi_library/ai.py` (linha ~186)**

```python
    def data_extract_pdf(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
        """Extrai dados de PDF via Vertex AI.

        Args:
            file_path: Caminho local do PDF (máx 7 MB).
            prompt_text: Prompt instruindo resposta em JSON.
            model: ID do modelo Vertex AI.
            execution_id: Identificador de execução incluído no usage.
            response_schema: JSON Schema (dict) para Structured Output.
                Quando presente, o Vertex garante que a resposta adere ao schema.
                Quando None, retorna JSON livre conforme o prompt.
        """
        pdf_bytes = _read_file_bytes(file_path)
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise ValueError(
                f"PDF excede limite de 7 MB para inlineData ({len(pdf_bytes)} bytes)."
            )
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        contents = [{"parts": [
            {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
            {"text": prompt_text},
        ]}]

        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

        try:
            response = self._call_vertex_raw(
                contents, model, _build_config(response_schema)
            )
            token_counts = _extract_token_counts(response)
            result = json.loads(response.text)
        except Exception:
            status = "error"
            raise
        finally:
            _usage = _build_usage(model, "data_extract_pdf", token_counts, status, execution_id)
            self._dispatch_usage(_usage)

        return {"result": result, "usage": _usage}
```

- [ ] **Step 5: Atualiza `data_extract_ofx` em `jedi_library/ai.py` (linha ~223)**

```python
    def data_extract_ofx(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
        """Extrai dados de arquivo OFX via Vertex AI.

        Args:
            file_path: Caminho local do arquivo OFX (UTF-8).
            prompt_text: Prompt base (conteúdo OFX concatenado automaticamente).
            model: ID do modelo Vertex AI.
            execution_id: Identificador de execução incluído no usage.
            response_schema: JSON Schema (dict) para Structured Output.
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_prompt = prompt_text + "\n\n" + content

        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

        try:
            response = self._call_vertex_raw(
                full_prompt, model, _build_config(response_schema)
            )
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

- [ ] **Step 6: Atualiza `data_extract_csv` em `jedi_library/ai.py` (linha ~253)**

```python
    def data_extract_csv(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
        """Extrai dados de arquivo CSV via Vertex AI.

        Args:
            file_path: Caminho local do CSV (UTF-8).
            prompt_text: Prompt base (conteúdo CSV concatenado automaticamente).
            model: ID do modelo Vertex AI.
            execution_id: Identificador de execução incluído no usage.
            response_schema: JSON Schema (dict) para Structured Output.
        """
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_prompt = prompt_text + "\n\n" + content

        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

        try:
            response = self._call_vertex_raw(
                full_prompt, model, _build_config(response_schema)
            )
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

- [ ] **Step 7: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 43 testes passando (34 anteriores + 9 novos).

- [ ] **Step 8: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 125 passed.

- [ ] **Step 9: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona response_schema a data_extract_pdf/ofx/csv"
```

---

## Task 2: `response_schema` em `call_vertex_ai`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (linha ~159)
- Modificar: `tests/test_ai.py`

- [ ] **Step 1: Adiciona 4 testes falhantes a `tests/test_ai.py`**

```python
# Adicionar ao tests/test_ai.py — seção response_schema (call_vertex_ai)

def test_call_vertex_ai_schema_incluido_no_config(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    schema = {"type": "object", "properties": {"resposta": {"type": "string"}}}
    ai_client.call_vertex_ai("prompt", response_schema=schema)
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert config["response_schema"] == schema
    assert config["response_mime_type"] == "application/json"


def test_call_vertex_ai_sem_schema_config_sem_response_schema(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    ai_client.call_vertex_ai("prompt")
    config = mock_client.models.generate_content.call_args.kwargs["config"]
    assert "response_schema" not in config


def test_call_vertex_ai_schema_nao_dict_levanta_value_error(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    with pytest.raises(ValueError, match="dict"):
        ai_client.call_vertex_ai("prompt", response_schema="invalido")
    mock_client.models.generate_content.assert_not_called()


def test_call_vertex_ai_schema_e_generation_config_juntos_levanta_value_error(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    with pytest.raises(ValueError, match="generation_config"):
        ai_client.call_vertex_ai(
            "prompt",
            generation_config={"temperature": 0.5},
            response_schema={"type": "object"},
        )
    mock_client.models.generate_content.assert_not_called()
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_call_vertex_ai_schema_incluido_no_config -v
```
Esperado: `FAILED` — `call_vertex_ai() got an unexpected keyword argument 'response_schema'`

- [ ] **Step 3: Atualiza `call_vertex_ai` em `jedi_library/ai.py` (linha ~159)**

```python
    def call_vertex_ai(
        self,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        generation_config: dict | None = None,
        response_schema: dict | None = None,
        execution_id: str | None = None,
    ) -> dict:
        """Chama o Vertex AI e retorna result + usage + raw_text.

        Args:
            prompt_text: Texto do prompt (JSON response esperado).
            model: ID do modelo Vertex AI.
            generation_config: Config completo de geração — caller monta o dict.
                Mutuamente exclusivo com response_schema (passe um OU outro).
            response_schema: JSON Schema (dict) para Structured Output.
                Mutuamente exclusivo com generation_config.
            execution_id: Identificador de execução incluído no usage.

        Raises:
            ValueError: Se generation_config e response_schema forem passados juntos,
                ou se response_schema não for dict.
        """
        if generation_config is not None and response_schema is not None:
            raise ValueError(
                "Passe generation_config OU response_schema, não os dois. "
                "Se precisa de ambos, inclua response_schema dentro de generation_config."
            )
        config = generation_config if generation_config is not None else _build_config(response_schema)
        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}
        raw_text = ""

        try:
            response = self._call_vertex_raw(prompt_text, model, config)
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

- [ ] **Step 4: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 47 testes passando (43 + 4 novos).

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 129 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona response_schema a call_vertex_ai (mutuamente exclusivo com generation_config)"
```

---

## Task 3: Bump de versão

**Arquivos:**
- Modificar: `pyproject.toml` (linha 3)

- [ ] **Step 1: Atualiza versão em `pyproject.toml`**

```toml
version = "0.2.0"
```

- [ ] **Step 2: Suite final verde**

```
uv run pytest tests/ -q
```
Esperado: 129 passed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump versão para 0.2.0 (feature: response_schema em JediAI)"
```

---

## Auto-Revisão

### 1. Cobertura da Spec

| Requisito | Task |
|---|---|
| `data_extract_pdf` aceita `response_schema: dict \| None = None` | T1 |
| `data_extract_ofx` aceita `response_schema` | T1 |
| `data_extract_csv` aceita `response_schema` | T1 |
| Schema presente → mergeado no config enviado ao Vertex | T1 |
| Schema ausente → comportamento atual preservado (backward-compatible) | T1 |
| Schema não-dict → `ValueError` antes de chamar Vertex | T1 |
| `call_vertex_ai` aceita `response_schema` (opcional na spec) | T2 |
| `generation_config` + `response_schema` juntos → `ValueError` (mutuamente exclusivos) | T2 |
| Validação `isinstance` centralizada em `_build_config` (DRY) | T1 Step 3 |
| Testes: schema-presente, schema-ausente, schema-malformado por método | T1+T2 |
| `_call_vertex_raw` não modificado | (sem task — invariante verificável: não consta em nenhum step) |
| Bump de versão minor `0.1.0` → `0.2.0` | T3 |

### 2. Scan de Placeholders

Nenhum "TBD", "TODO", "depois" ou "..." encontrado.

### 3. Consistência de Tipos/Nomes

- `_build_config` definido em T1 Step 3 (com validação interna), usado em T1 Steps 4-6 e T2 Step 3 — consistente.
- `response_schema: dict | None = None` — mesmo tipo em todos os 4 métodos — consistente.
- `ValueError` com `match="dict"` (testes de schema-malformado) bate com `"deve ser dict"` na mensagem de `_build_config` — consistente.
- `ValueError` com `match="generation_config"` (teste de exclusão mútua em T2) bate com `"Passe generation_config OU response_schema"` na mensagem — consistente.
- `mock_client.models.generate_content.call_args.kwargs["config"]` — mesmo padrão de acesso em todos os 13 testes novos — consistente.
- Contagens: T1=43/125, T2=47/129, T3=129 — verificadas.
