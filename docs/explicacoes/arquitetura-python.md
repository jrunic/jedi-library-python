---
id: 202606121604
projeto: jedi-library-python
tipo: nota
status: ativo
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Arquitetura do package jedi_library (Python 3.12)"
tags: [arquitetura, python]
---

# Arquitetura — jedi-library-python

## Estrutura

```
jedi-library-python/
├── pyproject.toml           # package único "jedi-library", requires-python >=3.12,<3.13
├── jedi_library/
│   ├── __init__.py          # re-exporta submódulos
│   ├── log.py               # port do jediLog GAS
│   ├── ai.py                # port do jediAI GAS (Vertex AI)
│   └── <futuros>            # db.py, slug.py, assets.py... (Onda 1+)
├── src/python/              # legado — não usar; substituído por jedi_library/
├── test/python/             # testes pytest
└── docs/
    └── 81-referencia/
        ├── arquitetura-python.md  (este arquivo)
        └── decisoes/
            ├── 20260612-distribuicao-python-via-git-ssh.md
            └── 20260612-engine-migrations-sql-puro-tabela-schema.md
```

## Instalação pelos consumidores

```bash
uv add 'jedi-library @ git+ssh://git@github.com/jrunic/jedi-library-python.git'
```

Pinning automático via `uv.lock` (commit SHA). Upgrade consciente:

```bash
uv lock --upgrade-package jedi-library
```

## jedi_library.log

**Padrão:** Buffer pattern idêntico ao jediLog GAS.

**Fluxo:**

```
init(config)           → configura contexto, executionId, logSheetId
info/warn/error/debug() → acumula em _buffer
flush()                → batch append na planilha Google Sheets → limpa buffer
```

**Diferenças em relação ao GAS:**

- Contexto prefixado automaticamente com `python:`.
- Auth: `GOOGLE_CREDENTIALS_FILE` → ADC.
- Fallback de disco: quando flush falha, grava `.log` em `JEDI_LOG_FALLBACK_DIR` (default `/tmp`).
- Timestamps ISO string (`YYYY-MM-DD HH:MM:SS`).

**Planilha de log:** `1C2HKxUhA7e-w_0bNFUFuPcpqslTFrYu7Wb214BXwSLw`, aba `data`

## jedi_library.ai

**Padrão:** Funções independentes (sem singleton). Espelha API do jediAI GAS.

**Fluxo:**

```
prepare_prompt(template, variables)  → prompt final com {$variavel} substituído
        ↓
data_extract_pdf(file_path, ...)     → lê PDF, codifica Base64, chama Vertex AI
  ou data_extract_ofx(file_path, ...) → lê OFX UTF-8, concatena ao prompt
  ou data_extract_csv(file_path, ...) → lê CSV UTF-8, concatena ao prompt
        ↓
call_vertex_ai(prompt_text, ...)     → POST Vertex AI, retorna { parsed, usage_metadata, raw_text }
        ↓
log_usage(cost_context, ...)         → append na planilha central de custos
```

**Configuração via env vars (no projeto consumidor):**

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `JEDI_AI_GCP_PROJECT_ID` | — (obrigatório) | ID do projeto GCP do Vertex AI |
| `JEDI_AI_VERTEX_LOCATION` | `us-central1` | Região do endpoint Vertex |
| `GOOGLE_CREDENTIALS_FILE` | `credentials.json` | Service Account JSON |

**Planilha de custos:** `1QIE52tWfDBxMp7Y5We4scCKw8gUSncrbFvX88yfcmLQ`, aba `data`
Schema: `timestamp | project | model | function | inputTokens | outputTokens | status | executionId`

**Modelo default:** `gemini-2.0-flash`

## Ondas de implementação

| Onda | Submódulo | Status |
|------|-----------|--------|
| 0 (split) | `log` | Implementado |
| 0 (split) | `ai` | Implementado |
| 1 | `slug` | Planejado — `jedi_slug` unifica tili.gerar_slug + jd-tasks.normalize_tag |
| 1 | `assets` | Planejado — `pkg_files()` wrapper sobre `importlib.resources` |
| 1 | `db` | Planejado — engine de migrations SQL puro + tabela schema_migrations |
| 2 | `status_flow` | Aguarda demanda |
| 2 | `audit` | Aguarda demanda |
| 2 | `datetime` | Aguarda demanda |
| 3 | `enrich` | Port do jediEnrich GAS |
| 3 | `http` | httpx wrapper |
| 3 | `errors` | Hierarquia de exceções |

## Uso típico

```python
from jedi_library import log, ai
import uuid

exec_id = str(uuid.uuid4())
log.init({"context": "meu-pipeline", "executionId": exec_id})

try:
    prompt = ai.prepare_prompt("Extraia os dados do PDF em JSON: {$instrucao}", {"instrucao": "..."})
    dados = ai.data_extract_pdf(
        file_path="/tmp/doc.pdf",
        prompt_text=prompt,
        cost_context={"project": "meu-projeto", "execution_id": exec_id},
    )
    log.info("Extração concluída.", {"registros": len(dados.get("itens", []))})
except Exception as e:
    log.error("Falha na extração.", e)
    raise
finally:
    log.flush()
```
