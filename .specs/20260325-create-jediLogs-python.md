# Contexto e Objetivo

Você é um Engenheiro de Software Sênior especialista em Python e integrações com Google Cloud.

Sua tarefa é portar uma biblioteca de logging legada do Google Apps Script (GAS) chamada `jediLog`
para Python. O objetivo principal desta biblioteca é acumular logs em um buffer de memória e
enviá-los em lote para uma Planilha do Google apenas quando o método `flush()` for invocado. Isso
evita gargalos e esgotamento da cota de requisições da API.

Você deve gerar dois arquivos:

1. O módulo principal: `src/python/jedi_log.py` (ou `src/python/jedi_log/__init__.py`)
2. O arquivo de testes: `test/python/test_log.py`

# Requisitos do Módulo Python (`jedi_log`)

## 1. Interface e Métodos Obrigatórios

A classe ou módulo deve expor estritamente a seguinte interface (com Type Hints):

- `init(config: dict)`: Recebe `context`, `executionId` e `logSheetId`. Inicializa as variáveis de
  estado e zera o buffer.
- `info(message: str, metadata: dict = None)`
- `warn(message: str, metadata: dict = None)`
- `error(message: str, error_object: Exception)`: Obrigatório extrair a stack trace do
  `error_object` e incluir no payload.
- `debug(message: str, metadata: dict = None)`
- `flush()`: Método crítico. Pega a lista de dicionários no buffer e faz um "batch append" no Google
  Sheets. Limpa o buffer após o sucesso.
- `set_level(level: int)`
- `is_debug_enabled() -> bool`

## 2. Regras de Ouro (Restrições Arquiteturais)

- **Padrão de Buffer:** Nenhum log de `info`, `warn`, `error` ou `debug` faz requisição HTTP/API.
  Eles apenas dão `append` em uma lista (buffer) interna.
- **Integração com Sheets:** No método `flush()`, utilize a biblioteca `google-api-python-client`
  para enviar os dados. Presuma que as credenciais do Google (Service Account) serão injetadas ou
  gerenciadas via variáveis de ambiente padrão (`GOOGLE_APPLICATION_CREDENTIALS`).
- **logSheetId** estará definida na variável de ambiente `LOGS_SHEET_ID`.
- **Estrutura do Payload de Log:** Cada linha a ser inserida no Sheets deve conter:
  `[timestamp, context, level, message, executionId, metadata (JSON string)]`.
- **Idioma:** Variáveis, código, classes e docstrings em Inglês.

# Requisitos do Arquivo de Testes (`test_log.py`)

Crie uma suíte de testes robusta usando `pytest` (ou `unittest`).

- **Isolamento:** Aplique mocks ou monkeypatching na chamada da API do Google Sheets (`gspread` ou
  equivalente) dentro do `flush()`. Os testes NÃO podem fazer requisições reais de rede.
- **Cobertura:** \* Teste se a inicialização (`init`) limpa buffers anteriores.
  - Teste se logs abaixo do nível configurado (`set_level`) são ignorados.
  - Teste a extração de stack trace no método `error`.
  - Teste se o método `flush` constrói a matriz de dados corretamente e chama a função de append da
    API mockada com os parâmetros exatos.

# Formato de Saída

Forneça apenas o código Python completo, limpo e devidamente comentado. Comece pelo módulo
`jedi_log` e em seguida forneça o `test_log.py`.
