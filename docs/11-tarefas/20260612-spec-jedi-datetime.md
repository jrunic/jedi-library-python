---
id: 202606122120
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — implementar jedi_library.datetime_utils com constantes TZ e funções now/now_iso/today TZ-explícitas"
tags: [spec, python, datetime, timezone, zoneinfo, cuiaba, sao-paulo, utc]
---

# Spec: `jedi_library.datetime_utils` — Funções de Data/Hora TZ-Explícitas

> Task de implementação: [[20260612-jedi-datetime]]

## Problema

Código Python que cria datetimes sem timezone produz valores naive que representam silenciosamente o horário local da máquina — comportamento não-determinístico entre servidores em fusos distintos. O Jedi Labs opera em Cuiabá e São Paulo, e os logs usam UTC. Sem abstração canônica, cada projeto repete a definição dos fusos e o risco de datetime naive é constante.

## Solução

Módulo `datetime_utils` com três constantes de fuso (Cuiabá, São Paulo, UTC) e três funções que exigem fuso como argumento obrigatório — sem default. Stdlib-only.

## Histórias de Usuário

1. Como script que agenda tarefas no contexto do Orlando (Cuiabá), quero uma constante de fuso já configurada para não lembrar a string de timezone.
2. Como log de auditoria comparando eventos de servidores em fusos distintos, quero timestamp UTC universal que elimina ambiguidade de offset.
3. Como relatório que exibe "data de hoje" para o usuário, quero a data sem hora para formatação simples.
4. Como desenvolvedor que esqueceu de passar o fuso, quero um erro imediato em vez de datetime naive silencioso.

## Critérios de Sucesso

- Constantes `CUIABA_TZ`, `SP_TZ`, `UTC` correspondem aos fusos corretos.
- `now(fuso)` retorna datetime aware no fuso passado.
- `now(CUIABA_TZ)` e `now(SP_TZ)` no mesmo instante diferem em menos de 2 segundos (mesmo ponto no tempo, offsets diferentes).
- `now_iso(fuso)` retorna string ISO 8601 com offset numérico.
- `now_iso(UTC)` contém `"+00:00"`.
- `today(fuso)` retorna objeto `date` (sem hora).
- Chamar qualquer função sem argumento levanta `TypeError` (sem default de fuso).
- Sem dependências externas.

## Decisões de Implementação

- Novo módulo `datetime_utils`, apenas stdlib (`datetime`, `zoneinfo`)
- TZ obrigatório por assinatura de função — sem valor padrão
- `now_iso` usa `.isoformat()` do Python — retorna offset numérico (ex: `+00:00`), não `Z`
- Módulo re-exportado em `__init__.py`

## Decisões de Teste

- Testes unitários; sem mock de tempo (as funções delegam para stdlib)
- Verificar tipo de retorno, tzinfo, formato da string ISO, e TypeError na ausência de argumento
- Teste CBA vs SP: instanciar os dois em sequência e verificar diferença absoluta < 2s (não verificar offset fixo — DST pode mudar)

## Fora de Escopo

- Formatação de datas para exibição ao usuário
- Parsing de strings de data
- Outros fusos além de Cuiabá, São Paulo e UTC
- Mock de datetime para testes determinísticos

## Assumptions

1. Python 3.12 com `zoneinfo` na stdlib; `tzdata` não necessário em macOS e Linux modernos
2. pytest como runner

## Notas

- ADR `20260612-jedi-datetime-criacao.md` no repo agnóstico define o contrato.
- Fonte doadora: módulo `datetime_utils` do `jd-tasks`.
- Aderência com UTC em logs: ADR `20260612-schema-log-json-aderente-incidentes.md`.
