---
descricao: "README — jedi-library-python: package jedi_library (Python 3.12)"
id: 202606121607
projeto: jedi-library-python
tipo: readme
status: ativo
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
tags: [readme]
---

# jedi-library-python

Package Python 3.12 das bibliotecas Jedi Labs — `jedi_library`.

## Família de repositórios

| Repo | Conteúdo |
|---|---|
| [jedi-library](https://github.com/jrunic/jedi-library) | Governança e conceito agnóstico de linguagem |
| [jedi-library-gas](https://github.com/jrunic/jedi-library-gas) | Implementações GAS/V8 |
| **jedi-library-python** (este) | Implementações Python 3.12 |

## Instalação

```bash
uv add 'jedi-library @ git+ssh://git@github.com/jrunic/jedi-library-python.git'
```

Pinning automático via `uv.lock`. Upgrade consciente:

```bash
uv lock --upgrade-package jedi-library
```

## Uso

```python
from jedi_library import log, ai
import uuid

exec_id = str(uuid.uuid4())
log.init({"context": "meu-pipeline", "executionId": exec_id})

try:
    dados = ai.data_extract_pdf(
        file_path="/tmp/doc.pdf",
        prompt_text="Extraia em JSON: ...",
        cost_context={"project": "meu-projeto", "execution_id": exec_id},
    )
    log.info("Extração concluída.", {"registros": len(dados.get("itens", []))})
except Exception as e:
    log.error("Falha.", e)
    raise
finally:
    log.flush()
```

## Variáveis de ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `JEDI_AI_GCP_PROJECT_ID` | Sim (para `ai`) | Projeto GCP do Vertex AI |
| `GOOGLE_CREDENTIALS_FILE` | Não | Path da Service Account JSON |
| `JEDI_AI_VERTEX_LOCATION` | Não | Região Vertex (default: `us-central1`) |
| `JEDI_LOG_FALLBACK_DIR` | Não | Dir fallback de log em disco (default: `/tmp`) |

## Documentação

- `CONTEXTO.md` — regras Python, convenções, distribuição
- `docs/81-referencia/arquitetura-python.md` — estrutura, fluxos, ondas de implementação
