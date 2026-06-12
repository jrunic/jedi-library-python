---
id: 202606121950
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/status_flow.py com can_transition() e validate_transition()"
tags: [tarefa, python, status-flow, fsm, transicoes]
---

# Tarefa — Implementação de `jedi_library.status_flow`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-status-flow-criacao.md`.

Onda 2 — iniciar quando tili Fase 3 começar (ou assim que `jd-tasks` quiser migrar).

## Entregáveis

### `jedi_library/status_flow.py`

```python
def can_transition(
    current: str,
    target: str,
    transitions: dict[str, list[str]],
) -> bool:
    return target in transitions.get(current, [])

def validate_transition(
    current: str,
    target: str,
    transitions: dict[str, list[str]],
) -> None:
    if not can_transition(current, target, transitions):
        raise ValueError(
            f"Transição inválida: '{current}' → '{target}'. "
            f"Permitidas a partir de '{current}': {transitions.get(current, [])}"
        )
```

### Testes (`test/python/test_status_flow.py`)

```python
TRANSITIONS = {"open": ["in_progress", "cancelled"], "in_progress": ["done", "open"]}
```

- `can_transition("open", "in_progress", TRANSITIONS)` → `True`
- `can_transition("open", "done", TRANSITIONS)` → `False`
- `can_transition("done", "open", TRANSITIONS)` → `False` (estado terminal)
- `validate_transition("open", "in_progress", TRANSITIONS)` → sem raise
- `validate_transition("open", "done", TRANSITIONS)` → `ValueError`

## Critérios de conclusão

- [ ] `status_flow.py` com `can_transition` + `validate_transition`.
- [ ] Testes passando.
- [ ] `__init__.py` exporta `status_flow`.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-status-flow-criacao.md`.
- Fonte doadora: `jd-tasks/api/status_flow.py`.
