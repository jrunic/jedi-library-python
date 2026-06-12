"""
ai.py — Python port of the jediAI GAS library.

Espelha a API GAS: prepare_prompt, data_extract_pdf, data_extract_ofx,
data_extract_csv, data_extract_xlsx, call_vertex_ai, log_usage.

Auth: Service Account via GOOGLE_CREDENTIALS_FILE → ADC.
Modelo default: gemini-2.0-flash (ver ADR vertex-ai-padrao-jedi-labs).

Regras obrigatórias (equivalentes ao GAS):
  - cost_context={'project': ..., 'execution_id': ...} obrigatório em data_extract_*.
  - Prompts devem instruir o modelo a responder exclusivamente em JSON.
  - Nunca suprimir exceções de data_extract_* — log_usage de erro já foi registrado.
  - Combinar com jedi_library.log usando o mesmo execution_id.
"""

import base64
import json
import os
import time
from typing import Any, Optional

_google_genai: Any = None
_google_auth: Any = None
_build: Any = None

try:
    import google.genai as _ggi  # type: ignore
    import google.auth as _ga  # type: ignore
    from googleapiclient.discovery import build as _b  # type: ignore

    _google_genai = _ggi
    _google_auth = _ga
    _build = _b
    _LIBS_AVAILABLE = True
except ImportError:
    _LIBS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.0-flash"
COST_SHEET_ID = "1QIE52tWfDBxMp7Y5We4scCKw8gUSncrbFvX88yfcmLQ"
COST_SHEET_TAB = "data"
MAX_PDF_BYTES = 7 * 1024 * 1024  # 7 MB — limite inlineData Vertex AI

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _get_credentials(scopes: list[str]) -> Any:
    if not _LIBS_AVAILABLE:
        raise RuntimeError("google-auth e google-genai não instalados.")
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.abspath(creds_path)
    try:
        if os.path.exists(creds_path):
            from google.oauth2.service_account import Credentials  # type: ignore
            return Credentials.from_service_account_file(creds_path, scopes=scopes)
    except Exception:
        pass
    creds, _ = _google_auth.default(scopes=scopes)
    return creds


def _get_project_id() -> str:
    proj = os.environ.get("JEDI_AI_GCP_PROJECT_ID", "").strip()
    if not proj:
        raise ValueError(
            "JEDI_AI_GCP_PROJECT_ID não configurado. "
            "Defina a variável de ambiente no projeto consumidor."
        )
    return proj


def _get_vertex_location() -> str:
    return os.environ.get("JEDI_AI_VERTEX_LOCATION", "us-central1").strip()


def _build_genai_client() -> Any:
    if not _LIBS_AVAILABLE:
        raise RuntimeError("google-genai não instalado.")
    project = _get_project_id()
    location = _get_vertex_location()
    return _google_genai.Client(vertexai=True, project=project, location=location)


def _sheets_service() -> Any:
    if _build is None:
        raise RuntimeError("google-api-python-client não instalado.")
    creds = _get_credentials(["https://www.googleapis.com/auth/spreadsheets"])
    return _build("sheets", "v4", credentials=creds)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def prepare_prompt(template: str, variables: Optional[dict] = None) -> str:
    """
    Substitui placeholders {$variavel} no template pelo valor correspondente.

    Args:
        template: String com placeholders {$nome}.
        variables: Dict de substituições. Ausência de chave lança ValueError.

    Returns:
        Texto final do prompt.
    """
    if not variables:
        return template
    result = template
    for key, value in variables.items():
        placeholder = "{$" + key + "}"
        if placeholder not in result:
            raise ValueError(f"Placeholder '{placeholder}' não encontrado no template.")
        result = result.replace(placeholder, str(value))
    # Verifica se sobrou algum placeholder não substituído
    import re
    remaining = re.findall(r"\{\$\w+\}", result)
    if remaining:
        raise ValueError(f"Placeholders não substituídos no template: {remaining}")
    return result


def call_vertex_ai(
    prompt_text: str,
    model: str = DEFAULT_MODEL,
    generation_config: Optional[dict] = None,
) -> dict:
    """
    Chama o Vertex AI e retorna { parsed, usage_metadata, raw_text }.

    Faz JSON.parse do raw_text — prompt deve instruir o modelo a responder em JSON.
    Retry exponencial em erro 429.

    Args:
        prompt_text: Texto do prompt (com conteúdo do documento embutido se necessário).
        model: ID do modelo Vertex AI.
        generation_config: Config opcional de geração (temperatura, etc.).

    Returns:
        dict com keys: parsed (object), usage_metadata (dict), raw_text (str).

    Raises:
        ValueError: Se a resposta não for JSON válido.
        RuntimeError: Em erro de autenticação ou rede após retries.
    """
    client = _build_genai_client()
    config = generation_config or {"response_mime_type": "application/json"}

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=config,
            )
            raw_text = response.text
            usage = {
                "prompt_token_count": getattr(response.usage_metadata, "prompt_token_count", 0),
                "candidates_token_count": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_token_count": getattr(response.usage_metadata, "total_token_count", 0),
            }
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Resposta do modelo não é JSON válido. "
                    f"Verifique se o prompt instrui resposta em JSON. Raw: {raw_text[:200]}"
                ) from e
            return {"parsed": parsed, "usage_metadata": usage, "raw_text": raw_text}
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                time.sleep(2 ** attempt * 2)
                continue
            raise
    raise RuntimeError("Falha após 3 tentativas no Vertex AI.")


def data_extract_pdf(
    file_path: str,
    prompt_text: str,
    cost_context: dict,
    model: str = DEFAULT_MODEL,
) -> Any:
    """
    Extrai dados de PDF via Vertex AI.

    Args:
        file_path: Caminho local do arquivo PDF.
        prompt_text: Prompt (instruindo resposta em JSON).
        cost_context: Dict obrigatório com 'project' e 'execution_id'.
        model: ID do modelo.

    Returns:
        Objeto Python resultado do JSON.parse da resposta.

    Raises:
        ValueError: Se cost_context ausente, PDF > 7 MB ou resposta não-JSON.
    """
    if not cost_context or not cost_context.get("project") or not cost_context.get("execution_id"):
        raise ValueError(
            "cost_context obrigatório com 'project' e 'execution_id'. "
            "Sem cost_context, nenhum custo é registrado."
        )

    pdf_bytes = _read_file_bytes(file_path)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF excede limite de 7 MB para inlineData ({len(pdf_bytes)} bytes). "
            f"Use um arquivo menor ou implemente upload via Files API."
        )

    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    # Monta contents com inline_data (espelho do jediAI GAS dataExtractPDF)
    client = _build_genai_client()
    contents = [
        {"parts": [
            {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
            {"text": prompt_text},
        ]}
    ]

    status = "success"
    usage: dict = {}
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config={"response_mime_type": "application/json"},
        )
        raw_text = response.text
        usage = {
            "prompt_token_count": getattr(response.usage_metadata, "prompt_token_count", 0),
            "candidates_token_count": getattr(response.usage_metadata, "candidates_token_count", 0),
            "total_token_count": getattr(response.usage_metadata, "total_token_count", 0),
        }
        result = json.loads(raw_text)
    except Exception as e:
        status = "error"
        log_usage(cost_context=cost_context, model=model, function="data_extract_pdf",
                  usage=usage, status=status)
        raise
    finally:
        if status == "success":
            log_usage(cost_context=cost_context, model=model, function="data_extract_pdf",
                      usage=usage, status=status)
    return result


def data_extract_ofx(
    file_path: str,
    prompt_text: str,
    cost_context: dict,
    model: str = DEFAULT_MODEL,
) -> Any:
    """
    Extrai dados de arquivo OFX (texto UTF-8) via Vertex AI.

    Args:
        file_path: Caminho local do arquivo OFX.
        prompt_text: Prompt base (conteúdo OFX será concatenado).
        cost_context: Dict obrigatório com 'project' e 'execution_id'.
        model: ID do modelo.
    """
    if not cost_context or not cost_context.get("project") or not cost_context.get("execution_id"):
        raise ValueError("cost_context obrigatório com 'project' e 'execution_id'.")

    with open(file_path, encoding="utf-8", errors="replace") as f:
        ofx_text = f.read()

    full_prompt = prompt_text + "\n\n" + ofx_text

    status = "success"
    usage: dict = {}
    try:
        result_data = call_vertex_ai(full_prompt, model=model)
        usage = result_data["usage_metadata"]
        result = result_data["parsed"]
    except Exception as e:
        status = "error"
        log_usage(cost_context=cost_context, model=model, function="data_extract_ofx",
                  usage=usage, status=status)
        raise
    log_usage(cost_context=cost_context, model=model, function="data_extract_ofx",
              usage=usage, status=status)
    return result


def data_extract_csv(
    file_path: str,
    prompt_text: str,
    cost_context: dict,
    model: str = DEFAULT_MODEL,
) -> Any:
    """Extrai dados de arquivo CSV via Vertex AI."""
    if not cost_context or not cost_context.get("project") or not cost_context.get("execution_id"):
        raise ValueError("cost_context obrigatório com 'project' e 'execution_id'.")

    with open(file_path, encoding="utf-8", errors="replace") as f:
        csv_text = f.read()

    full_prompt = prompt_text + "\n\n" + csv_text

    status = "success"
    usage: dict = {}
    try:
        result_data = call_vertex_ai(full_prompt, model=model)
        usage = result_data["usage_metadata"]
        result = result_data["parsed"]
    except Exception as e:
        status = "error"
        log_usage(cost_context=cost_context, model=model, function="data_extract_csv",
                  usage=usage, status=status)
        raise
    log_usage(cost_context=cost_context, model=model, function="data_extract_csv",
              usage=usage, status=status)
    return result


def log_usage(
    cost_context: dict,
    model: str,
    function: str,
    usage: dict,
    status: str,
) -> None:
    """
    Registra consumo de tokens na planilha central de custos.

    Nunca lança exceção — falha de log não deve interromper o fluxo principal.

    Schema da aba 'data':
        timestamp | project | model | function | inputTokens | outputTokens | status | executionId
    """
    try:
        from datetime import datetime
        row = [[
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cost_context.get("project", ""),
            model,
            function,
            usage.get("prompt_token_count", 0),
            usage.get("candidates_token_count", 0),
            status,
            cost_context.get("execution_id", ""),
        ]]
        service = _sheets_service()
        service.spreadsheets().values().append(
            spreadsheetId=COST_SHEET_ID,
            range=f"{COST_SHEET_TAB}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()
    except Exception:
        pass  # log_usage é fail-safe — nunca relança


def _read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()
