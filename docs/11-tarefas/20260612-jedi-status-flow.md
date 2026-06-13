---
id: 202606121950
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/status_flow.py com classe StateMachine"
tags: [tarefa, python, status-flow, fsm, state-machine, transicoes]
---

# Tarefa — Implementação de `jedi_library.status_flow`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-status-flow-criacao.md`.

Classe `StateMachine` que encapsula dict de transições e oferece 4 métodos. Idempotência built-in default ON (casa com regra do jd-tasks).

## Entregáveis

### `jedi_library/status_flow.py`

```python
class StateMachine:
    """Motor genérico de máquina de estados.

    Exemplo:
        FLOW = StateMachine({
            "backlog":   {"doing", "done", "cancelado"},
            "doing":     {"backlog", "done", "cancelado"},
            "done":      set(),
            "cancelado": set(),
        })

        if FLOW.can_transition(current, target): ...
    """

    def __init__(
        self,
        transitions: dict[str, set[str]],
        *,
        idempotent: bool = True,
    ) -> None:
        self._transitions = {k: set(v) for k, v in transitions.items()}
        self._idempotent = idempotent

    def can_transition(self, current: str, target: str) -> bool:
        if self._idempotent and current == target:
            return True
        return target in self._transitions.get(current, set())

    def validate_transition(self, current: str, target: str) -> None:
        if not self.can_transition(current, target):
            permitidos = sorted(self._transitions.get(current, set()))
            raise ValueError(
                f"Transição inválida: '{current}' → '{target}'. "
                f"Permitidas a partir de '{current}': {permitidos}"
            )

    def transitions_from(self, current: str) -> set[str]:
        return set(self._transitions.get(current, set()))

    def is_terminal(self, state: str) -> bool:
        return not self._transitions.get(state, set())
```

### Testes (`test/test_status_flow.py`)

```python
import pytest
from jedi_library.status_flow import StateMachine


TRANSITIONS = {
    "backlog":   {"doing", "done", "cancelado"},
    "doing":     {"backlog", "done", "cancelado"},
    "done":      set(),
    "cancelado": set(),
}


def test_can_transition_valida():
    sm = StateMachine(TRANSITIONS)
    assert sm.can_transition("backlog", "doing")
    assert sm.can_transition("doing", "done")


def test_can_transition_invalida():
    sm = StateMachine(TRANSITIONS)
    assert not sm.can_transition("done", "backlog")
    assert not sm.can_transition("done", "doing")


def test_idempotent_default_on():
    sm = StateMachine(TRANSITIONS)
    assert sm.can_transition("done", "done")
    assert sm.can_transition("cancelado", "cancelado")


def test_idempotent_off():
    sm = StateMachine(TRANSITIONS, idempotent=False)
    assert not sm.can_transition("done", "done")


def test_validate_raises_value_error():
    sm = StateMachine(TRANSITIONS)
    with pytest.raises(ValueError, match="Transição inválida"):
        sm.validate_transition("done", "backlog")


def test_transitions_from():
    sm = StateMachine(TRANSITIONS)
    assert sm.transitions_from("backlog") == {"doing", "done", "cancelado"}
    assert sm.transitions_from("done") == set()
    assert sm.transitions_from("inexistente") == set()


def test_is_terminal():
    sm = StateMachine(TRANSITIONS)
    assert sm.is_terminal("done")
    assert sm.is_terminal("cancelado")
    assert not sm.is_terminal("backlog")


def test_estado_desconhecido_nao_transiciona():
    sm = StateMachine(TRANSITIONS)
    assert not sm.can_transition("inexistente", "doing")


def test_transitions_imutaveis_apos_init():
    transitions = {"a": {"b"}}
    sm = StateMachine(transitions)
    transitions["a"].add("c")  # muta o dict original
    assert sm.transitions_from("a") == {"b"}   # lib copiou no init
```

## Critérios de conclusão

- [ ] `status_flow.py` com `StateMachine` + 4 métodos.
- [ ] Imutabilidade pós-init (consumidor mutando o dict original não afeta a máquina).
- [ ] Testes passando incluindo idempotência on/off e estado desconhecido.
- [ ] `__init__.py` exporta `status_flow`.
- [ ] PR referencia ADR.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-status-flow-criacao.md`.
- Fonte doadora: `jd-tasks/src/jd_tasks/api/status_flow.py`.
