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
    mock_g, _, _ = mock_genai
    creds_a = MagicMock()
    creds_b = MagicMock()
    ai_a = JediAI(project="proj-a", credentials=creds_a)
    ai_b = JediAI(project="proj-b", credentials=creds_b)
    assert ai_a._project == "proj-a"
    assert ai_b._project == "proj-b"
    assert ai_a._credentials is not ai_b._credentials
    calls = mock_g.Client.call_args_list
    assert calls[0].kwargs["project"] == "proj-a"
    assert calls[1].kwargs["project"] == "proj-b"


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


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------

def test_from_env_sucesso(monkeypatch, mock_genai):
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


# ---------------------------------------------------------------------------
# call_vertex_ai
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# data_extract_pdf
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# data_extract_ofx / data_extract_csv
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# usage_handler
# ---------------------------------------------------------------------------

def test_sem_handler_nenhum_efeito_colateral(mock_genai, mock_creds):
    ai = JediAI(project="p", credentials=mock_creds)
    response = ai.call_vertex_ai("p")
    assert response["result"] == {"valor": 42}


def test_handler_invocado_em_sucesso(ai_client, mock_genai):
    captured = []
    ai_client._usage_handler = captured.append
    ai_client.call_vertex_ai("p", execution_id="eid")
    assert len(captured) == 1
    assert captured[0]["status"] == "success"
    assert captured[0]["execution_id"] == "eid"
    assert captured[0]["total_token_count"] == 15


def test_handler_invocado_em_erro_antes_de_relancar(ai_client, mock_genai):
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
    assert response["result"] == {"valor": 42}


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
