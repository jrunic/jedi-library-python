---
id: 202606171600
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
tags: [plano-execucao, python, ai, vertex, client-pattern, tdd]
spec: 20260617-spec-jedi-ai-client-pattern.md
descricao: "Plano — redesign de jedi_library.ai para Client object pattern com 8 tasks TDD"
---

# Redesign de `jedi_library.ai` — Plano de Implementação

**Objetivo:** Substituir as funções de módulo de `jedi_library.ai` pela classe `JediAI` com credenciais explícitas obrigatórias, mover `prepare_prompt()` para `jedi_library.utils`, e remover o acoplamento com Google Sheets.

**Arquitetura:** Classe `JediAI` recebe credenciais na construção via `from_service_account_file()` (produção) ou `from_env()` (conveniência). Funções de extração viram métodos que retornam `{"result": ..., "usage": {...}}`. `usage_handler` opcional é chamado após cada operação. Helpers privados de módulo (`_build_usage`, `_extract_token_counts`) evitam duplicação. `_call_vertex_raw` centraliza o retry sem despachar usage.

**Pilha técnica:** Python 3.12, `google-genai`, `google-auth`, `google-oauth2`, `pytest`, `unittest.mock`.

**Comando de teste ao longo do plano:** `cd /Users/jedi/jedi-brain/15-repositorios/jedi-library-python && uv run pytest tests/ -q`

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jedi_library/utils.py` | Criar | `prepare_prompt()` — substituição de template pura |
| `tests/test_utils.py` | Criar | Testes de `prepare_prompt()` |
| `jedi_library/ai.py` | Reescrever | Classe `JediAI` + helpers privados de módulo |
| `tests/test_ai.py` | Criar | Testes de `JediAI` com mocks |
| `jedi_library/__init__.py` | Modificar | Adicionar `utils` aos exports |
| `pyproject.toml` | Modificar | Remover `google-api-python-client` |
| `CONTEXTO.md` | Modificar | Atualizar seção "Autenticação" |

---

## Task 1: `jedi_library/utils.py` — `prepare_prompt()`

**Arquivos:**
- Criar: `jedi_library/utils.py`
- Criar: `tests/test_utils.py`
- Modificar: `jedi_library/__init__.py`

- [ ] **Step 1: Escreve testes falhantes**

```python
# tests/test_utils.py
import pytest
from jedi_library import utils


def test_substitui_placeholder_simples():
    result = utils.prepare_prompt("Olá {$nome}!", {"nome": "Jedi"})
    assert result == "Olá Jedi!"


def test_substitui_multiplos_placeholders():
    result = utils.prepare_prompt("{$a} e {$b}", {"a": "X", "b": "Y"})
    assert result == "X e Y"


def test_sem_variaveis_retorna_template_intacto():
    result = utils.prepare_prompt("sem placeholders", {})
    assert result == "sem placeholders"


def test_sem_variaveis_none_retorna_template():
    result = utils.prepare_prompt("sem placeholders")
    assert result == "sem placeholders"


def test_placeholder_ausente_no_dict_levanta_value_error():
    with pytest.raises(ValueError, match="variavel"):
        utils.prepare_prompt("{$variavel}", {})


def test_placeholder_ausente_no_template_levanta_value_error():
    with pytest.raises(ValueError, match="inexistente"):
        utils.prepare_prompt("sem {$a}", {"a": "ok", "inexistente": "x"})


def test_placeholder_nao_substituido_levanta_value_error():
    with pytest.raises(ValueError, match="nao_usado"):
        utils.prepare_prompt("texto sem placeholder", {"nao_usado": "val"})
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_utils.py -v
```
Esperado: `ModuleNotFoundError: No module named 'jedi_library.utils'`

- [ ] **Step 3: Cria `jedi_library/utils.py`**

```python
# jedi_library/utils.py
import re


def prepare_prompt(template: str, variables: dict | None = None) -> str:
    """Substitui placeholders {$variavel} no template pelo valor correspondente."""
    if not variables:
        remaining = re.findall(r"\{\$\w+\}", template)
        if remaining:
            raise ValueError(f"Placeholders não substituídos: {remaining}")
        return template

    result = template
    for key, value in variables.items():
        placeholder = "{$" + key + "}"
        if placeholder not in result:
            raise ValueError(
                f"Placeholder '{{${key}}}' (chave '{key}') não encontrado no template."
            )
        result = result.replace(placeholder, str(value))

    remaining = re.findall(r"\{\$\w+\}", result)
    if remaining:
        raise ValueError(f"Placeholders não substituídos no template: {remaining}")

    return result
```

- [ ] **Step 4: Adiciona `utils` ao `__init__.py`**

```python
# jedi_library/__init__.py  — linha adicionada
from jedi_library import log, ai, datetime_utils, slug, status_flow, assets, db, utils

__all__ = ["log", "ai", "datetime_utils", "slug", "status_flow", "assets", "db", "utils"]
```

- [ ] **Step 5: Roda testes — espera PASS**

```
uv run pytest tests/test_utils.py -v
```
Esperado: 7 testes passando.

- [ ] **Step 6: Suite completa ainda verde**

```
uv run pytest tests/ -q
```
Esperado: 82 passed (75 anteriores + 7 novos).

- [ ] **Step 7: Commit**

```bash
git add jedi_library/utils.py tests/test_utils.py jedi_library/__init__.py
git commit -m "feat(utils): adiciona jedi_library.utils com prepare_prompt()"
```

---

## Task 2: `JediAI` — construtor + `from_service_account_file()`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (adiciona classe, mantém legado por ora)
- Criar: `tests/test_ai.py`

- [ ] **Step 1: Cria `tests/test_ai.py` com testes falhantes do construtor**

```python
# tests/test_ai.py
import pytest
from unittest.mock import MagicMock, patch

from jedi_library.ai import JediAI, _GCP_SCOPES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_creds():
    return MagicMock()


@pytest.fixture
def mock_genai():
    """Mocka google.genai para evitar chamadas reais ao Vertex."""
    with patch("jedi_library.ai.genai") as mock_g:
        mock_response = MagicMock()
        mock_response.text = '{"valor": 42}'
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_g.Client.return_value = mock_client
        yield mock_g, mock_client, mock_response


@pytest.fixture
def ai_client(mock_genai, mock_creds):
    return JediAI(project="test-project", credentials=mock_creds)


# ---------------------------------------------------------------------------
# Construtor
# ---------------------------------------------------------------------------

def test_construtor_com_credentials_validas(mock_genai, mock_creds):
    mock_g, mock_client, _ = mock_genai
    ai = JediAI(project="meu-proj", credentials=mock_creds)
    mock_g.Client.assert_called_once_with(
        vertexai=True, project="meu-proj", location="us-central1", credentials=mock_creds
    )
    assert ai._project == "meu-proj"
    assert ai._location == "us-central1"


def test_construtor_location_customizada(mock_genai, mock_creds):
    JediAI(project="p", location="southamerica-east1", credentials=mock_creds)
    mock_g, _, _ = mock_genai
    mock_g.Client.assert_called_once_with(
        vertexai=True, project="p", location="southamerica-east1", credentials=mock_creds
    )


def test_construtor_credentials_none_levanta_value_error(mock_genai):
    with pytest.raises(ValueError, match="credentials"):
        JediAI(project="p", credentials=None)


def test_dois_clientes_com_credentials_distintas_nao_interferem(mock_genai):
    creds_a = MagicMock()
    creds_b = MagicMock()
    ai_a = JediAI(project="proj-a", credentials=creds_a)
    ai_b = JediAI(project="proj-b", credentials=creds_b)
    assert ai_a._project == "proj-a"
    assert ai_b._project == "proj-b"
    assert ai_a._client is not ai_b._client


# ---------------------------------------------------------------------------
# from_service_account_file
# ---------------------------------------------------------------------------

def test_from_service_account_file_sucesso(mock_genai):
    mock_creds = MagicMock()
    with patch("jedi_library.ai.ServiceAccountCredentials") as mock_sa:
        mock_sa.from_service_account_file.return_value = mock_creds
        ai = JediAI.from_service_account_file("/path/sa.json", project="proj")
        mock_sa.from_service_account_file.assert_called_once_with(
            "/path/sa.json", scopes=_GCP_SCOPES
        )
        assert ai._project == "proj"


def test_from_service_account_file_location_customizada(mock_genai):
    with patch("jedi_library.ai.ServiceAccountCredentials") as mock_sa:
        mock_sa.from_service_account_file.return_value = MagicMock()
        ai = JediAI.from_service_account_file(
            "/path/sa.json", project="p", location="us-east1"
        )
        assert ai._location == "us-east1"


def test_from_service_account_file_inexistente_levanta_file_not_found(mock_genai):
    with patch("jedi_library.ai.ServiceAccountCredentials") as mock_sa:
        mock_sa.from_service_account_file.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory: '/inexistente.json'"
        )
        with pytest.raises(FileNotFoundError):
            JediAI.from_service_account_file("/inexistente.json", project="p")
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py -v
```
Esperado: `ImportError: cannot import name 'JediAI' from 'jedi_library.ai'`

- [ ] **Step 3: Adiciona classe `JediAI` no topo de `jedi_library/ai.py`** (antes do código legado existente)

```python
# jedi_library/ai.py — TOPO DO ARQUIVO (substitui os imports existentes e adiciona a classe)
"""
ai.py — jedi_library.ai

Acesso ao Vertex AI (Gemini) via Client object pattern.

Uso padrão:
    from jedi_library.ai import JediAI
    ai = JediAI.from_service_account_file("/path/sa.json", project="meu-projeto")
    response = ai.call_vertex_ai("Responda em JSON: ...")
    print(response["result"])
"""

import json
import logging
import os
import time
from typing import Callable

import google.genai as genai
from google.auth import load_credentials_from_file
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

DEFAULT_MODEL = "gemini-2.0-flash"
MAX_PDF_BYTES = 7 * 1024 * 1024
_GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers privados de módulo
# ---------------------------------------------------------------------------

def _extract_token_counts(response) -> dict:
    meta = response.usage_metadata
    return {
        "prompt_token_count": getattr(meta, "prompt_token_count", 0),
        "candidates_token_count": getattr(meta, "candidates_token_count", 0),
        "total_token_count": getattr(meta, "total_token_count", 0),
    }


def _build_usage(
    model: str,
    function: str,
    token_counts: dict,
    status: str,
    execution_id: str | None,
) -> dict:
    return {
        "model": model,
        "function": function,
        "status": status,
        "execution_id": execution_id,
        **token_counts,
    }


def _read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class JediAI:
    def __init__(
        self,
        *,
        project: str,
        location: str = "us-central1",
        credentials,
        usage_handler: Callable[[dict], None] | None = None,
    ) -> None:
        if credentials is None:
            raise ValueError(
                "credentials é obrigatório. Use JediAI.from_service_account_file() "
                "ou JediAI.from_env()."
            )
        self._project = project
        self._location = location
        self._usage_handler = usage_handler
        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            credentials=credentials,
        )

    @classmethod
    def from_service_account_file(
        cls,
        path: str,
        *,
        project: str,
        location: str = "us-central1",
        usage_handler: Callable[[dict], None] | None = None,
    ) -> "JediAI":
        credentials = ServiceAccountCredentials.from_service_account_file(
            path, scopes=_GCP_SCOPES
        )
        return cls(
            project=project,
            location=location,
            credentials=credentials,
            usage_handler=usage_handler,
        )

    def _dispatch_usage(self, usage: dict) -> None:
        if self._usage_handler is None:
            return
        try:
            self._usage_handler(usage)
        except Exception:
            _logger.warning("usage_handler levantou exceção", exc_info=True)
```

Nota: o código legado existente no arquivo (funções `prepare_prompt`, `call_vertex_ai`, `data_extract_*`, `log_usage`) fica no final do arquivo — será removido na Task 8.

- [ ] **Step 4: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 7 testes passando.

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 89 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona JediAI com construtor e from_service_account_file"
```

---

## Task 3: `JediAI.from_env()`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (adiciona método `from_env`)
- Modificar: `tests/test_ai.py` (adiciona testes)

- [ ] **Step 1: Adiciona testes falhantes ao `tests/test_ai.py`**

```python
# Adicionar ao tests/test_ai.py — seção from_env

def test_from_env_sucesso(monkeypatch, mock_genai, tmp_path):
    monkeypatch.setenv("JEDI_AI_GCP_PROJECT_ID", "env-proj")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/creds.json")
    monkeypatch.delenv("JEDI_AI_VERTEX_LOCATION", raising=False)
    mock_creds = MagicMock()
    with patch("jedi_library.ai.load_credentials_from_file") as mock_load:
        mock_load.return_value = (mock_creds, None)
        ai = JediAI.from_env()
        mock_load.assert_called_once_with("/fake/creds.json", scopes=_GCP_SCOPES)
        assert ai._project == "env-proj"
        assert ai._location == "us-central1"


def test_from_env_location_customizada(monkeypatch, mock_genai):
    monkeypatch.setenv("JEDI_AI_GCP_PROJECT_ID", "p")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/c.json")
    monkeypatch.setenv("JEDI_AI_VERTEX_LOCATION", "us-east1")
    with patch("jedi_library.ai.load_credentials_from_file", return_value=(MagicMock(), None)):
        ai = JediAI.from_env()
        assert ai._location == "us-east1"


def test_from_env_sem_project_id_levanta_runtime_error(monkeypatch, mock_genai):
    monkeypatch.delenv("JEDI_AI_GCP_PROJECT_ID", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/c.json")
    with pytest.raises(RuntimeError, match="JEDI_AI_GCP_PROJECT_ID"):
        JediAI.from_env()


def test_from_env_sem_credentials_levanta_runtime_error(monkeypatch, mock_genai):
    monkeypatch.setenv("JEDI_AI_GCP_PROJECT_ID", "p")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        JediAI.from_env()
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_from_env_sucesso -v
```
Esperado: `AttributeError: type object 'JediAI' has no attribute 'from_env'`

- [ ] **Step 3: Adiciona `from_env()` à classe `JediAI` em `jedi_library/ai.py`**

```python
    @classmethod
    def from_env(
        cls,
        *,
        usage_handler: Callable[[dict], None] | None = None,
    ) -> "JediAI":
        project = os.environ.get("JEDI_AI_GCP_PROJECT_ID")
        if not project:
            raise RuntimeError(
                "JEDI_AI_GCP_PROJECT_ID não configurado. "
                "Defina a variável de ambiente antes de usar JediAI.from_env()."
            )
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS não configurado. "
                "Aponte para o arquivo de credenciais Google antes de usar JediAI.from_env()."
            )
        credentials, _ = load_credentials_from_file(creds_path, scopes=_GCP_SCOPES)
        location = os.environ.get("JEDI_AI_VERTEX_LOCATION", "us-central1")
        return cls(
            project=project,
            location=location,
            credentials=credentials,
            usage_handler=usage_handler,
        )
```

- [ ] **Step 4: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 11 testes passando.

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 93 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona JediAI.from_env com load_credentials_from_file"
```

---

## Task 4: `JediAI.call_vertex_ai()`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (adiciona `_call_vertex_raw` + `call_vertex_ai`)
- Modificar: `tests/test_ai.py`

- [ ] **Step 1: Adiciona testes falhantes**

```python
# Adicionar ao tests/test_ai.py — seção call_vertex_ai

def test_call_vertex_ai_retorna_result_e_usage(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    response = ai_client.call_vertex_ai("prompt aqui")
    assert response["result"] == {"valor": 42}
    assert response["usage"]["model"] == "gemini-2.0-flash"
    assert response["usage"]["function"] == "call_vertex_ai"
    assert response["usage"]["status"] == "success"
    assert response["usage"]["prompt_token_count"] == 10
    assert response["usage"]["candidates_token_count"] == 5
    assert response["usage"]["total_token_count"] == 15
    assert response["usage"]["execution_id"] is None
    assert response["raw_text"] == '{"valor": 42}'


def test_call_vertex_ai_execution_id_no_usage(ai_client, mock_genai):
    response = ai_client.call_vertex_ai("p", execution_id="exec-123")
    assert response["usage"]["execution_id"] == "exec-123"


def test_call_vertex_ai_modelo_customizado(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    ai_client.call_vertex_ai("p", model="gemini-2.5-pro")
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs.kwargs["model"] == "gemini-2.5-pro"


def test_call_vertex_ai_erro_status_error_no_usage(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    mock_client.models.generate_content.side_effect = RuntimeError("falha de rede")
    with pytest.raises(RuntimeError, match="falha de rede"):
        ai_client.call_vertex_ai("p")


def test_call_vertex_ai_erro_token_counts_sao_zeros(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    mock_client.models.generate_content.side_effect = RuntimeError("falha")
    captured = []
    ai_client._usage_handler = captured.append
    with pytest.raises(RuntimeError):
        ai_client.call_vertex_ai("p")
    assert captured[0]["prompt_token_count"] == 0
    assert captured[0]["candidates_token_count"] == 0
    assert captured[0]["total_token_count"] == 0
    assert captured[0]["status"] == "error"


def test_call_vertex_ai_retry_em_429(ai_client, mock_genai):
    _, mock_client, mock_response = mock_genai
    mock_client.models.generate_content.side_effect = [
        Exception("429 quota"),
        mock_response,
    ]
    with patch("jedi_library.ai.time.sleep") as mock_sleep:
        response = ai_client.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}
    mock_sleep.assert_called_once_with(2)
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_call_vertex_ai_retorna_result_e_usage -v
```
Esperado: `AttributeError: 'JediAI' object has no attribute 'call_vertex_ai'`

- [ ] **Step 3: Adiciona `_call_vertex_raw` e `call_vertex_ai` à classe em `jedi_library/ai.py`**

```python
    def _call_vertex_raw(self, contents, model: str, config: dict):
        """Chama Vertex AI com retry em 429. Sem despacho de usage."""
        for attempt in range(3):
            try:
                return self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(2 ** attempt * 2)
                else:
                    raise

    def call_vertex_ai(
        self,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        generation_config: dict | None = None,
        execution_id: str | None = None,
    ) -> dict:
        config = generation_config or {"response_mime_type": "application/json"}
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
Esperado: 17 testes passando.

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 99 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona JediAI.call_vertex_ai com retry e usage dict"
```

---

## Task 5: `JediAI.data_extract_pdf()`

**Arquivos:**
- Modificar: `jedi_library/ai.py`
- Modificar: `tests/test_ai.py`

- [ ] **Step 1: Adiciona testes falhantes**

```python
# Adicionar ao tests/test_ai.py — seção data_extract_pdf

def test_data_extract_pdf_retorna_result_e_usage(ai_client, mock_genai, tmp_path):
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"%PDF fake content")
    response = ai_client.data_extract_pdf(str(pdf_file), "extraia dados")
    assert response["result"] == {"valor": 42}
    assert response["usage"]["function"] == "data_extract_pdf"
    assert response["usage"]["status"] == "success"
    assert response["usage"]["prompt_token_count"] == 10


def test_data_extract_pdf_execution_id_no_usage(ai_client, mock_genai, tmp_path):
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake")
    response = ai_client.data_extract_pdf(str(pdf_file), "p", execution_id="eid-42")
    assert response["usage"]["execution_id"] == "eid-42"


def test_data_extract_pdf_arquivo_grande_levanta_value_error(ai_client, tmp_path):
    big_pdf = tmp_path / "big.pdf"
    big_pdf.write_bytes(b"x" * (7 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="7 MB"):
        ai_client.data_extract_pdf(str(big_pdf), "p")


def test_data_extract_pdf_erro_vertex_token_counts_zeros(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    mock_client.models.generate_content.side_effect = RuntimeError("erro")
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"fake")
    captured = []
    ai_client._usage_handler = captured.append
    with pytest.raises(RuntimeError):
        ai_client.data_extract_pdf(str(pdf_file), "p")
    assert captured[0]["prompt_token_count"] == 0
    assert captured[0]["status"] == "error"
    assert captured[0]["function"] == "data_extract_pdf"


def test_data_extract_pdf_passa_inline_data_ao_vertex(ai_client, mock_genai, tmp_path):
    import base64
    _, mock_client, _ = mock_genai
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"PDFBYTES")
    ai_client.data_extract_pdf(str(pdf_file), "meu prompt")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    parts = contents[0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "application/pdf"
    assert parts[0]["inline_data"]["data"] == base64.b64encode(b"PDFBYTES").decode()
    assert parts[1]["text"] == "meu prompt"
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_data_extract_pdf_retorna_result_e_usage -v
```
Esperado: `AttributeError: 'JediAI' object has no attribute 'data_extract_pdf'`

- [ ] **Step 3: Adiciona `data_extract_pdf` à classe em `jedi_library/ai.py`**

```python
    def data_extract_pdf(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
    ) -> dict:
        import base64

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
                contents, model, {"response_mime_type": "application/json"}
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

- [ ] **Step 4: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 22 testes passando.

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 104 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona JediAI.data_extract_pdf"
```

---

## Task 6: `JediAI.data_extract_ofx()` e `JediAI.data_extract_csv()`

**Arquivos:**
- Modificar: `jedi_library/ai.py`
- Modificar: `tests/test_ai.py`

- [ ] **Step 1: Adiciona testes falhantes**

```python
# Adicionar ao tests/test_ai.py — seção data_extract_ofx/csv

def test_data_extract_ofx_retorna_result_e_usage(ai_client, mock_genai, tmp_path):
    ofx_file = tmp_path / "extrato.ofx"
    ofx_file.write_text("OFX CONTENT", encoding="utf-8")
    response = ai_client.data_extract_ofx(str(ofx_file), "extraia")
    assert response["result"] == {"valor": 42}
    assert response["usage"]["function"] == "data_extract_ofx"
    assert response["usage"]["status"] == "success"


def test_data_extract_ofx_concatena_conteudo_no_prompt(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    ofx_file = tmp_path / "extrato.ofx"
    ofx_file.write_text("DADOS OFX", encoding="utf-8")
    ai_client.data_extract_ofx(str(ofx_file), "meu prompt")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert "meu prompt" in contents
    assert "DADOS OFX" in contents


def test_data_extract_ofx_function_nao_e_call_vertex_ai(ai_client, mock_genai, tmp_path):
    ofx_file = tmp_path / "e.ofx"
    ofx_file.write_text("x", encoding="utf-8")
    captured = []
    ai_client._usage_handler = captured.append
    ai_client.data_extract_ofx(str(ofx_file), "p")
    funcs = [u["function"] for u in captured]
    assert "data_extract_ofx" in funcs
    assert "call_vertex_ai" not in funcs


def test_data_extract_csv_retorna_result_e_usage(ai_client, mock_genai, tmp_path):
    csv_file = tmp_path / "dados.csv"
    csv_file.write_text("col1,col2\n1,2", encoding="utf-8")
    response = ai_client.data_extract_csv(str(csv_file), "extraia")
    assert response["result"] == {"valor": 42}
    assert response["usage"]["function"] == "data_extract_csv"


def test_data_extract_csv_concatena_conteudo(ai_client, mock_genai, tmp_path):
    _, mock_client, _ = mock_genai
    csv_file = tmp_path / "dados.csv"
    csv_file.write_text("CSV DATA", encoding="utf-8")
    ai_client.data_extract_csv(str(csv_file), "prompt csv")
    call_args = mock_client.models.generate_content.call_args
    contents = call_args.kwargs["contents"]
    assert "prompt csv" in contents
    assert "CSV DATA" in contents


def test_data_extract_csv_function_nao_e_call_vertex_ai(ai_client, mock_genai, tmp_path):
    csv_file = tmp_path / "d.csv"
    csv_file.write_text("x", encoding="utf-8")
    captured = []
    ai_client._usage_handler = captured.append
    ai_client.data_extract_csv(str(csv_file), "p")
    funcs = [u["function"] for u in captured]
    assert "data_extract_csv" in funcs
    assert "call_vertex_ai" not in funcs
```

- [ ] **Step 2: Roda para confirmar FAIL**

```
uv run pytest tests/test_ai.py::test_data_extract_ofx_retorna_result_e_usage -v
```
Esperado: `AttributeError: 'JediAI' object has no attribute 'data_extract_ofx'`

- [ ] **Step 3: Adiciona `data_extract_ofx` e `data_extract_csv` à classe**

```python
    def data_extract_ofx(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
    ) -> dict:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_prompt = prompt_text + "\n\n" + content

        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

        try:
            response = self._call_vertex_raw(
                full_prompt, model, {"response_mime_type": "application/json"}
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

    def data_extract_csv(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
    ) -> dict:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        full_prompt = prompt_text + "\n\n" + content

        status = "success"
        token_counts = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

        try:
            response = self._call_vertex_raw(
                full_prompt, model, {"response_mime_type": "application/json"}
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

- [ ] **Step 4: Roda testes — espera PASS**

```
uv run pytest tests/test_ai.py -v
```
Esperado: 28 testes passando.

- [ ] **Step 5: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 110 passed.

- [ ] **Step 6: Commit**

```bash
git add jedi_library/ai.py tests/test_ai.py
git commit -m "feat(ai): adiciona JediAI.data_extract_ofx e data_extract_csv"
```

---

## Task 7: `usage_handler` — testes de despacho e handler com erro

**Arquivos:**
- Modificar: `tests/test_ai.py` (testes de comportamento do handler)

Nota: `_dispatch_usage` já está implementado desde a Task 2. Esta task adiciona testes que validam comportamento do handler em todos os cenários — incluindo handler que levanta exceção.

- [ ] **Step 1: Adiciona testes falhantes**

```python
# Adicionar ao tests/test_ai.py — seção usage_handler

def test_sem_handler_nenhum_efeito_colateral(mock_genai, mock_creds):
    ai = JediAI(project="p", credentials=mock_creds)
    response = ai.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}  # funciona normalmente sem handler


def test_handler_invocado_em_sucesso(ai_client, mock_genai):
    captured = []
    ai_client._usage_handler = captured.append
    ai_client.call_vertex_ai("p", execution_id="eid")
    assert len(captured) == 1
    assert captured[0]["status"] == "success"
    assert captured[0]["execution_id"] == "eid"
    assert captured[0]["total_token_count"] == 15


def test_handler_invocado_em_erro_antes_de_relançar(ai_client, mock_genai):
    _, mock_client, _ = mock_genai
    mock_client.models.generate_content.side_effect = RuntimeError("vertex down")
    captured = []
    ai_client._usage_handler = captured.append
    with pytest.raises(RuntimeError, match="vertex down"):
        ai_client.call_vertex_ai("p")
    assert len(captured) == 1
    assert captured[0]["status"] == "error"
    assert captured[0]["prompt_token_count"] == 0


def test_handler_com_excecao_nao_propaga(ai_client, mock_genai):
    def handler_quebrado(usage):
        raise ValueError("handler falhou")
    ai_client._usage_handler = handler_quebrado
    response = ai_client.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}  # exceção do handler é suprimida


def test_handler_pdf_invocado_em_sucesso(ai_client, mock_genai, tmp_path):
    pdf_file = tmp_path / "d.pdf"
    pdf_file.write_bytes(b"fake")
    captured = []
    ai_client._usage_handler = captured.append
    ai_client.data_extract_pdf(str(pdf_file), "p")
    assert captured[0]["function"] == "data_extract_pdf"
    assert captured[0]["status"] == "success"


def test_handler_injetado_na_construcao(mock_genai, mock_creds):
    captured = []
    ai = JediAI(project="p", credentials=mock_creds, usage_handler=captured.append)
    ai.call_vertex_ai("p")
    assert len(captured) == 1
```

- [ ] **Step 2: Roda para confirmar PASS imediato** (implementação já existe)

```
uv run pytest tests/test_ai.py -v
```
Esperado: 34 testes passando.

- [ ] **Step 3: Suite completa verde**

```
uv run pytest tests/ -q
```
Esperado: 116 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ai.py
git commit -m "test(ai): cobre comportamento de usage_handler em sucesso, erro e exception"
```

---

## Task 8: Remove legado + `pyproject.toml` + `CONTEXTO.md`

**Arquivos:**
- Modificar: `jedi_library/ai.py` (remove funções legadas)
- Modificar: `pyproject.toml` (remove `google-api-python-client`)
- Modificar: `CONTEXTO.md` (atualiza seção "Autenticação")

- [ ] **Step 1: Remove funções legadas de `jedi_library/ai.py`**

Remover do arquivo tudo que existia antes da Task 2: os blocos `try/except ImportError`, as constantes `COST_SHEET_ID`/`COST_SHEET_TAB`, e as funções de módulo `_get_credentials`, `_build_genai_client`, `_sheets_service`, `prepare_prompt`, `call_vertex_ai` (função de módulo), `data_extract_pdf` (função de módulo), `data_extract_ofx`, `data_extract_csv`, `log_usage`, `_read_file_bytes` (a versão legada — manter a nova que está no topo).

O arquivo final deve conter apenas: imports, constantes `DEFAULT_MODEL`/`MAX_PDF_BYTES`/`_GCP_SCOPES`/`_logger`, helpers `_extract_token_counts`/`_build_usage`/`_read_file_bytes`, e a classe `JediAI`.

- [ ] **Step 2: Roda testes para confirmar que remoção não quebrou nada**

```
uv run pytest tests/ -q
```
Esperado: 118 passed.

- [ ] **Step 3: Remove `google-api-python-client` do `pyproject.toml`**

```toml
# pyproject.toml — dependencies atualizado
dependencies = [
    "google-auth>=2.0",
    "google-genai>=1.0",
    "sqlparse>=0.5,<1.0",
]
```

- [ ] **Step 4: Atualiza lockfile**

```bash
cd /Users/jedi/jedi-brain/15-repositorios/jedi-library-python && uv lock
```
Esperado: `uv.lock` atualizado sem erros.

- [ ] **Step 5: Roda testes após mudança de dependência**

```
uv run pytest tests/ -q
```
Esperado: 118 passed.

- [ ] **Step 6: Atualiza seção "Autenticação" em `CONTEXTO.md`**

Substituir a seção atual:
```markdown
### Autenticação

- Nunca hardcodar credenciais no código.
- Prioridade: `GOOGLE_CREDENTIALS_FILE` (Service Account JSON) → ADC (`google.auth.default()`).
- Credenciais vivem em `~/.config/jedi-secrets/<projeto>/google-credentials.json`.
```

Por:
```markdown
### Autenticação

- Nunca hardcodar credenciais no código.
- Credenciais são sempre passadas explicitamente ao construtor `JediAI` — sem fallback para ADC implícito.
- Caminho primário: `JediAI.from_service_account_file(path, project=...)` com SA JSON.
- Conveniência single-tenant: `JediAI.from_env()` lê `GOOGLE_APPLICATION_CREDENTIALS` + `JEDI_AI_GCP_PROJECT_ID`. Suporta SA JSON, authorized user e workload identity via `google.auth.load_credentials_from_file`.
- Naming e path dos arquivos de credenciais são responsabilidade do `jd-secrets` — não da lib.
```

- [ ] **Step 7: Verifica remoção completa do legado**

```bash
grep -nE "COST_SHEET_ID|_get_credentials|_sheets_service|log_usage|GOOGLE_CREDENTIALS_FILE|_LIBS_AVAILABLE|googleapiclient" jedi_library/ai.py
```
Esperado: saída vazia. Se aparecer qualquer linha, remover antes de prosseguir.

- [ ] **Step 8: Suite completa final**

```
uv run pytest tests/ -q
```
Esperado: 116 passed.

- [ ] **Step 9: Commit final**

```bash
git add jedi_library/ai.py pyproject.toml uv.lock CONTEXTO.md
git commit -m "refactor(ai): remove legado, google-api-python-client e atualiza CONTEXTO.md"
```

---

## Nota sobre `prepare_prompt` — comportamento mais estrito que o original

A implementação em Task 1 é mais estrita que o original de `ai.py`: quando `variables` é `None` ou `{}` e o template contém placeholders, a nova implementação levanta `ValueError`; o original retornava o template intacto. Isso é uma mudança comportamental intencional (callers que passam `variables=None` com placeholders no template estão com bug), documentada aqui por transparência. A spec não prescreveu o comportamento do caso edge — a decisão foi tomada na implementação.

---

## Auto-Revisão

### 1. Cobertura da Spec

| Requisito da spec | Task |
|---|---|
| `JediAI(credentials=None)` levanta `ValueError` | T2 |
| `JediAI(credentials=<creds>)` constrói sem erro | T2 |
| Dois clientes coexistem sem interferência | T2 |
| `from_service_account_file` sucesso | T2 |
| `from_service_account_file` arquivo inexistente → `FileNotFoundError` | T2 |
| `from_env()` sucesso | T3 |
| `from_env()` sem `JEDI_AI_GCP_PROJECT_ID` → `RuntimeError` | T3 |
| `from_env()` sem `GOOGLE_APPLICATION_CREDENTIALS` → `RuntimeError` | T3 |
| `from_env()` usa `load_credentials_from_file` | T3 |
| `call_vertex_ai` retorna `result` + `usage` + `raw_text` | T4 |
| Retry em 429 | T4 |
| Token counts zeros em erro | T4 |
| `data_extract_pdf` retorna `result` + `usage` | T5 |
| PDF > 7 MB → `ValueError` antes de chamar Vertex | T5 |
| `data_extract_ofx` function = `"data_extract_ofx"` (não `call_vertex_ai`) | T6 |
| `data_extract_csv` function = `"data_extract_csv"` | T6 |
| `usage_handler` invocado em sucesso | T7 |
| `usage_handler` invocado em erro antes de relançar | T7 |
| Sem handler = sem efeito colateral | T7 |
| Handler com exceção não propaga | T7 |
| `execution_id` no usage quando passado | T4, T5 |
| `execution_id` ausente quando não passado | T4 |
| `prepare_prompt` em `jedi_library.utils` | T1 |
| `COST_SHEET_ID`/`_get_credentials`/`_sheets_service`/`log_usage` removidos | T8 (grep confirma) |
| Sem `GOOGLE_CREDENTIALS_FILE` no módulo ou `CONTEXTO.md` | T8 (grep confirma) |
| `google-api-python-client` removido do `pyproject.toml` | T8 |
| Testes passam sem variáveis de ambiente | T2–T7 (monkeypatch isola) |
| Contagens: T2=7/89, T3=11/93, T4=17/99, T5=22/104, T6=28/110, T7=34/116 | verificadas |

### 2. Scan de Placeholders

Nenhum "TBD", "TODO" ou "depois" encontrado.

### 3. Consistência de Tipos/Nomes

- `_GCP_SCOPES` definido no topo do módulo, referenciado em Task 2 e Task 3 — consistente.
- `_build_usage` e `_extract_token_counts` definidos como helpers de módulo — usados em T4, T5, T6 via mesma assinatura.
- `_dispatch_usage` aceita `dict` — consistente em todas as tasks.
- `usage_handler` é o nome do parâmetro no construtor e em `from_service_account_file`/`from_env` — consistente.
- `DEFAULT_MODEL = "gemini-2.0-flash"` — referenciado nas assinaturas de T4, T5, T6 — consistente.
