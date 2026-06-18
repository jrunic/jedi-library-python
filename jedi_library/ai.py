"""
ai.py — jedi_library.ai

Acesso ao Vertex AI (Gemini) via Client object pattern.

Uso padrão:
    from jedi_library.ai import JediAI
    ai = JediAI.from_service_account_file("/path/sa.json", project="meu-projeto")
    response = ai.call_vertex_ai("Responda em JSON: ...")
    print(response["result"])
"""

import base64
import json
import logging
import os
import random
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


def _build_config(response_schema: dict | None) -> dict:
    if response_schema is not None and not isinstance(response_schema, dict):
        raise ValueError(
            f"response_schema deve ser dict, recebido {type(response_schema).__name__}."
        )
    config: dict = {"response_mime_type": "application/json"}
    if response_schema is not None:
        config["response_schema"] = response_schema
    return config


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
        self._credentials = credentials
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

    def _dispatch_usage(self, usage: dict) -> None:
        if self._usage_handler is None:
            return
        try:
            self._usage_handler(usage)
        except Exception:
            _logger.warning("usage_handler levantou exceção", exc_info=True)

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

    def call_vertex_ai(
        self,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        generation_config: dict | None = None,
        response_schema: dict | None = None,
        execution_id: str | None = None,
    ) -> dict:
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

    def data_extract_pdf(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
        pdf_bytes = _read_file_bytes(file_path)
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise ValueError(
                f"PDF excede limite de 7 MB para inlineData ({len(pdf_bytes)} bytes)."
            )
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        contents = [{"role": "user", "parts": [
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

    def data_extract_ofx(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
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

    def data_extract_csv(
        self,
        file_path: str,
        prompt_text: str,
        *,
        model: str = DEFAULT_MODEL,
        execution_id: str | None = None,
        response_schema: dict | None = None,
    ) -> dict:
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

