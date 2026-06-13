---
id: 202606122215
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — implementar jedi_library.status_flow com classe StateMachine"
tags: [plano-execucao, python, status-flow, fsm, state-machine]
spec: docs/11-tarefas/20260612-spec-jedi-status-flow.md
---

# jedi_library.status_flow — Plano de Implementação

**Objetivo:** Criar módulo com `StateMachine` que encapsula validação de transições de estado com idempotência configurável.
**Arquitetura:** Classe com cópia defensiva do mapa de transições no construtor; sem estado mutável após construção; sem dependências externas.
**Pilha técnica:** Python 3.12, stdlib pura.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `jedi_library/status_flow.py` | Criar | Classe `StateMachine` — lógica de transições |
| `tests/test_status_flow.py` | Criar | Suite TDD — 15 testes comportamentais |
| `jedi_library/__init__.py` | Modificar | Re-exportar `status_flow` junto com `log` e `ai` |

---

## Task 1: StateMachine completo

**Arquivos:**
- Criar: `jedi_library/status_flow.py`
- Criar: `tests/test_status_flow.py`

- [ ] **Step 1: Escreve `tests/test_status_flow.py` completo**

```python
import pytest
from jedi_library import status_flow

TRANSITIONS = {
    "pendente": {"em_andamento", "cancelado"},
    "em_andamento": {"concluido", "cancelado"},
    "concluido": set(),
    "cancelado": set(),
}


@pytest.fixture
def fsm():
    return status_flow.StateMachine(TRANSITIONS)


def test_transicao_valida_retorna_true(fsm):
    assert fsm.can_transition("pendente", "em_andamento") is True


def test_transicao_invalida_retorna_false(fsm):
    assert fsm.can_transition("pendente", "concluido") is False


def test_idempotencia_default_on(fsm):
    assert fsm.can_transition("concluido", "concluido") is True


def test_idempotencia_off():
    fsm = status_flow.StateMachine(TRANSITIONS, idempotent=False)
    assert fsm.can_transition("concluido", "concluido") is False


def test_validate_transition_valida_nao_levanta(fsm):
    fsm.validate_transition("pendente", "em_andamento")


def test_validate_transition_invalida_levanta_value_error(fsm):
    with pytest.raises(ValueError, match="Transição inválida"):
        fsm.validate_transition("pendente", "concluido")


def test_validate_transition_mensagem_lista_permitidas(fsm):
    with pytest.raises(ValueError) as exc_info:
        fsm.validate_transition("pendente", "concluido")
    msg = str(exc_info.value)
    assert "cancelado" in msg or "em_andamento" in msg


def test_transitions_from_retorna_conjunto_correto(fsm):
    assert fsm.transitions_from("pendente") == {"em_andamento", "cancelado"}


def test_transitions_from_estado_desconhecido_retorna_vazio(fsm):
    assert fsm.transitions_from("inexistente") == set()


def test_is_terminal_estado_sem_transicoes(fsm):
    assert fsm.is_terminal("concluido") is True
    assert fsm.is_terminal("cancelado") is True


def test_is_terminal_estado_com_transicoes(fsm):
    assert fsm.is_terminal("pendente") is False


def test_can_transition_estado_desconhecido_retorna_false(fsm):
    assert fsm.can_transition("inexistente", "concluido") is False


def test_imutabilidade_pos_construcao():
    original = {"pendente": {"em_andamento"}}
    fsm = status_flow.StateMachine(original)
    original["pendente"].add("cancelado")
    assert "cancelado" not in fsm.transitions_from("pendente")


def test_transitions_from_retorna_copia(fsm):
    result = fsm.transitions_from("pendente")
    result.add("novo_estado")
    assert "novo_estado" not in fsm.transitions_from("pendente")
```

- [ ] **Step 2: Roda testes para verificar que falham**

```bash
uv run pytest tests/test_status_flow.py -v
```

Esperado: `ModuleNotFoundError` ou `ImportError` — `status_flow` não existe ainda. Todos os 14 testes coletados com ERRORS/FAIL.

- [ ] **Step 3: Cria `jedi_library/status_flow.py`**

```python
class StateMachine:
    def __init__(self, transitions: dict[str, set[str]], idempotent: bool = True) -> None:
        """Copia o mapa de transições para proteger de mutações externas."""
        self._transitions: dict[str, set[str]] = {
            state: set(targets) for state, targets in transitions.items()
        }
        self._idempotent = idempotent

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Retorna True se transição é válida. Estado desconhecido → False (sem raise)."""
        if self._idempotent and from_state == to_state:
            return True
        return to_state in self._transitions.get(from_state, set())

    def validate_transition(self, from_state: str, to_state: str) -> None:
        """Raise ValueError com lista de transições permitidas se inválida."""
        if not self.can_transition(from_state, to_state):
            allowed = sorted(self._transitions.get(from_state, set()))
            raise ValueError(
                f"Transição inválida: {from_state!r} → {to_state!r}. "
                f"Permitidas a partir de {from_state!r}: {allowed}"
            )

    def transitions_from(self, state: str) -> set[str]:
        """Retorna cópia do set de destinos. Estado desconhecido → set() vazio."""
        return set(self._transitions.get(state, set()))

    def is_terminal(self, state: str) -> bool:
        """True se estado não tem transições configuradas."""
        return state not in self._transitions or not self._transitions[state]
```

- [ ] **Step 4: Roda testes para verificar que passam**

```bash
uv run pytest tests/test_status_flow.py -v
```

Esperado:
```
tests/test_status_flow.py::test_transicao_valida_retorna_true PASSED
tests/test_status_flow.py::test_transicao_invalida_retorna_false PASSED
tests/test_status_flow.py::test_idempotencia_default_on PASSED
tests/test_status_flow.py::test_idempotencia_off PASSED
tests/test_status_flow.py::test_validate_transition_valida_nao_levanta PASSED
tests/test_status_flow.py::test_validate_transition_invalida_levanta_value_error PASSED
tests/test_status_flow.py::test_validate_transition_mensagem_lista_permitidas PASSED
tests/test_status_flow.py::test_transitions_from_retorna_conjunto_correto PASSED
tests/test_status_flow.py::test_transitions_from_estado_desconhecido_retorna_vazio PASSED
tests/test_status_flow.py::test_is_terminal_estado_sem_transicoes PASSED
tests/test_status_flow.py::test_is_terminal_estado_com_transicoes PASSED
tests/test_status_flow.py::test_can_transition_estado_desconhecido_retorna_false PASSED
tests/test_status_flow.py::test_imutabilidade_pos_construcao PASSED
tests/test_status_flow.py::test_transitions_from_retorna_copia PASSED

14 passed in X.XXs
```

- [ ] **Step 5: Commit**

```bash
git add jedi_library/status_flow.py tests/test_status_flow.py
git commit -m "feat(status_flow): StateMachine com idempotência configurável e cópia defensiva"
```

---

## Task 2: Re-exporta em `__init__.py`

**Arquivos:**
- Modificar: `jedi_library/__init__.py`

- [ ] **Step 1: Atualiza `jedi_library/__init__.py`**

Arquivo completo após modificação:

```python
from jedi_library import log, ai, status_flow

__all__ = ["log", "ai", "status_flow"]
```

- [ ] **Step 2: Verifica import funciona**

```bash
uv run python -c "from jedi_library import status_flow; fsm = status_flow.StateMachine({'a': {'b'}}); print(fsm.can_transition('a', 'b'))"
```

Esperado: `True`

- [ ] **Step 3: Roda suite completa**

```bash
uv run pytest tests/ -v
```

Esperado: todos os testes existentes + os 14 novos passando, sem regressões.

- [ ] **Step 4: Commit**

```bash
git add jedi_library/__init__.py
git commit -m "feat(status_flow): re-exporta status_flow em jedi_library.__init__"
```

---

## Auto-Revisão

### Cobertura da Spec

| Critério da spec | Task que implementa |
|---|---|
| Transição configurada → `True`; não configurada → `False` | Task 1 — `test_transicao_valida_retorna_true`, `test_transicao_invalida_retorna_false` |
| `can_transition(x, x)` → `True` com `idempotent=True` | Task 1 — `test_idempotencia_default_on` |
| `can_transition(x, x)` → `False` com `idempotent=False` | Task 1 — `test_idempotencia_off` |
| `validate_transition` inválida → `ValueError` com `"Transição inválida"` | Task 1 — `test_validate_transition_invalida_levanta_value_error` |
| `validate_transition` válida → não levanta | Task 1 — `test_validate_transition_valida_nao_levanta` |
| Mensagem de erro lista estados permitidos | Task 1 — `test_validate_transition_mensagem_lista_permitidas` |
| `transitions_from` estado desconhecido → set() sem raise | Task 1 — `test_transitions_from_estado_desconhecido_retorna_vazio` |
| `is_terminal` → `True` para estados sem transições | Task 1 — `test_is_terminal_estado_sem_transicoes` |
| `is_terminal` → `False` para estados com transições | Task 1 — `test_is_terminal_estado_com_transicoes` |
| `can_transition` origem desconhecida → `False` sem raise | Task 1 — `test_can_transition_estado_desconhecido_retorna_false` |
| Mutar dict original pós-construção não afeta máquina | Task 1 — `test_imutabilidade_pos_construcao` |
| `transitions_from` retorna cópia (não referência) | Task 1 — `test_transitions_from_retorna_copia` |
| Módulo re-exportado em `__init__.py` | Task 2 |

Gaps: nenhum.

### Scan de Placeholders

Nenhum "TBD", "TODO", "depois", "..." encontrado.

### Consistência de Tipos/Nomes

- `StateMachine` usado consistentemente nas duas tasks.
- `can_transition`, `validate_transition`, `transitions_from`, `is_terminal` — nomes idênticos na implementação e nos testes.
- `TRANSITIONS` fixture reutilizado via `fsm` fixture — nomes consistentes.
- `_transitions`, `_idempotent` — atributos privados definidos no construtor, usados nos quatro métodos.
