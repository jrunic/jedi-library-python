---
id: 202606122130
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — implementar jedi_library.status_flow com classe StateMachine"
tags: [spec, python, status-flow, fsm, state-machine, transicoes]
---

# Spec: `jedi_library.status_flow` — Motor de Máquina de Estados

> Task de implementação: [[20260612-jedi-status-flow]]

## Problema

O `jd-tasks` mantém lógica de transição de estados inline. Outros projetos que precisam de máquina de estados finita repetem essa lógica. A regra de idempotência (mesmo status → mesmo status é ok) está implícita em vários pontos, não encapsulada. Um segundo projeto implementando a mesma regra diferente cria inconsistência silenciosa.

## Solução

Classe `StateMachine` que recebe um mapa de transições no construtor e expõe quatro métodos: verificar permissão, validar (raise em transição inválida), listar transições possíveis e detectar estados terminais. Idempotência configurável, default ON. Sem dependências externas.

## Histórias de Usuário

1. Como API do `jd-tasks`, quero validar uma transição e receber erro com mensagem clara antes de persistir, sem escrever essa lógica no endpoint.
2. Como UI do `jd-tasks`, quero listar as transições possíveis a partir do estado atual para renderizar apenas os botões válidos.
3. Como regra de negócio, quero que `PATCH status=done` em tarefa já `done` não falhe (idempotência default ON).
4. Como projeto com regra diferente de idempotência, quero poder desativar o comportamento default na construção da máquina.
5. Como consumidor que muta o dict de transições após construir a máquina, quero que a máquina não seja afetada.

## Critérios de Sucesso

- Transição configurada como válida retorna `True` em `can_transition`; transição não configurada retorna `False`.
- `can_transition(estado, estado)` → `True` com `idempotent=True` (default); `False` com `idempotent=False`.
- `validate_transition` em transição inválida levanta `ValueError` com o texto `"Transição inválida"` e lista os estados permitidos a partir do estado atual.
- `transitions_from` retorna o conjunto de destinos; estado desconhecido retorna conjunto vazio sem raise.
- `is_terminal` retorna `True` para estados sem transições configuradas, `False` para os demais.
- `can_transition` com estado desconhecido como origem retorna `False` sem raise.
- Mutar o dict original após construção não altera o comportamento da máquina.

## Decisões de Implementação

- Novo módulo `status_flow`, sem dependências externas
- Construtor copia o mapa de transições (profundidade de cópia suficiente para proteger os sets internos)
- `can_transition` verifica idempotência antes do lookup
- `validate_transition` delega para `can_transition`; mensagem de erro inclui transições permitidas ordenadas
- `transitions_from` retorna cópia do set interno (não referência)
- Módulo re-exportado em `__init__.py`

## Decisões de Teste

- Testes comportamentais: instanciar com mapa fixo e verificar cada método
- Cobrir: transição válida e inválida, idempotência on/off, estado terminal, estado desconhecido como origem, imutabilidade pós-construção
- Não testar estado interno — apenas interface pública

## Fora de Escopo

- Persistência de estado
- Histórico de transições / audit trail
- Hooks ou callbacks em transição
- Validação de nomes de estados (estado desconhecido não levanta, retorna `False`/conjunto vazio)

## Assumptions

1. Python 3.12, stdlib suficiente
2. pytest como runner
3. Regra de idempotência default ON alinha com comportamento atual do `jd-tasks`

## Notas

- ADR `20260612-jedi-status-flow-criacao.md` no repo agnóstico define o contrato.
- Fonte doadora: módulo `status_flow` do `jd-tasks`.
