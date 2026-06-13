---
id: 202606122100
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — reescrita de jedi_library.log para stdout JSON estruturado (Path B); descontinua backend Google Sheets"
tags: [spec, python, log, json, stdout, observabilidade]
---

# Spec: Reescrita de `jedi_library.log` — stdout JSON (Path B)

> Task de implementação: [[20260612-jedi-log]]

## Problema

O módulo `log` atual grava logs em Google Sheets via API, exigindo credenciais Google em todo consumidor, conexão de rede no momento do log e um buffer com flush assíncrono. Isso cria acoplamento desnecessário para scripts que só precisam de observabilidade local, dificulta testes (mocks de API) e não integra com ferramentas padrão de coleta de logs. O schema também não é aderente ao `incidents.jsonl` da infra.

## Solução

Substituir o backend Sheets por um formatter que emite JSON estruturado em stdout, uma linha por evento. A implementação usa apenas stdlib Python. A identidade do ator é resolvida via parâmetro ou variável de ambiente. Correlação de runs é propagada via ContextVar.

## Histórias de Usuário

1. Como script Python no `jd-tasks`, quero que logs sejam emitidos em JSON no stdout para que journald e Cloud Logging os coletem automaticamente sem configuração extra.
2. Como desenvolvedor escrevendo um novo consumidor da lib, quero chamar uma função de setup uma vez no bootstrap e nunca mais pensar em autenticação Google para logs.
3. Como engenheiro analisando um incidente, quero que cada linha de log contenha `execution_id`, `host`, `actor` e `service` para correlacionar eventos em múltiplos processos.
4. Como pipeline com múltiplas runs concorrentes, quero definir `execution_id` para rastrear logs de cada run isoladamente, sem poluição entre contextos.
5. Como script que falha com exceção, quero que o log de erro contenha tipo, mensagem e stack trace em campo estruturado, não embutido no campo de mensagem.

## Critérios de Sucesso

- Cada chamada de log emite exatamente uma linha JSON válida no stdout.
- Campos obrigatórios presentes em toda linha: `ts` (UTC, terminando em `Z`), `level`, `logger`, `msg`, `module`, `func`, `line`, `pid`, `host`, `actor`, `actor_kind`.
- `host` é short hostname (sem domínio).
- `service` e `service_version` presentes quando configurados; ausentes quando não configurados.
- `execution_id` aparece após ser definido; desaparece após ser removido — sem vazamento entre contextos.
- Dados extras passados na chamada de log aparecem em campo `metadata` aninhado.
- Exceções capturadas produzem campo `exc` com subtipo, mensagem e stack trace estruturados.
- Segunda chamada de setup não duplica handler (idempotência).
- Variável de ambiente `JEDI_LOG_ACTOR` sobrescreve resolução por `$USER`.
- Nenhuma dependência Google permanece no módulo.

## Decisões de Implementação

- Reescrita completa do módulo `log` (não adição de backend paralelo)
- Dependências do módulo legado Sheets foram removidas nesta sessão; `ai` mantém as dependências Google que usa
- Interface pública: formatter configurável, função de setup idempotente, função de controle de `execution_id`
- Resolução de `actor`: parâmetro de setup → `JEDI_LOG_ACTOR` env → `USER` env → `"unknown"` (mesma ordem para `actor_kind`)
- `execution_id` propagado via ContextVar — thread-safe, isolado por coroutine
- Handler emite em stdout (não stderr) — logs são dados estruturados, não diagnóstico de processo
- Setup idempotente: substitui handlers existentes em vez de acumular
- Campos internos do LogRecord são excluídos do `metadata` para não poluir a saída
- Módulo re-exportado em `__init__.py`

## Decisões de Teste

- Capturar stdout durante o teste e verificar o JSON emitido (comportamento externo, não internals do formatter)
- Cobrir: JSON válido por linha, campos obrigatórios, `ts` em UTC, `host` sem domínio, campos opcionais presentes/ausentes conforme configuração, `execution_id` via ContextVar sem vazamento, `metadata` de extra, `exc` estruturado, idempotência de setup, override por env var
- Testes existentes (Sheets-based) foram deletados nesta sessão — base nova do zero

## Fora de Escopo

- Backend Google Sheets (descontinuado — ADR `20260612-jedi-log-criacao.md`)
- Rotação de arquivos de log em disco
- Integração com Cloud Logging SDK (coleta via stdout é suficiente)
- Migração dos consumidores (`jd-tasks`, `tili`, `jedi-etl`) — tarefas separadas nos respectivos repos
- Configuração de nível por logger nomeado

## Assumptions

1. Python 3.12 com stdlib suficiente para a implementação (sem deps externas)
2. pytest como runner; `capsys` disponível para captura de stdout
3. Nenhum consumidor externo usa a API Sheets hoje — migrações via tarefas separadas

## Notas

- ADRs canônicos: `20260612-jedi-log-criacao.md` (decisão) e `20260612-schema-log-json-aderente-incidentes.md` (schema).
- Schema do `incidents.jsonl` (infra-manager) é a referência de campos; spec não o repete.
