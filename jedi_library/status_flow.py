class StateMachine:
    def __init__(self, transitions: dict[str, set[str]], idempotent: bool = True) -> None:
        self._transitions: dict[str, set[str]] = {
            state: set(targets) for state, targets in transitions.items()
        }
        self._idempotent = idempotent

    def can_transition(self, from_state: str, to_state: str) -> bool:
        if self._idempotent and from_state == to_state:
            return True
        return to_state in self._transitions.get(from_state, set())

    def validate_transition(self, from_state: str, to_state: str) -> None:
        if not self.can_transition(from_state, to_state):
            allowed = sorted(self._transitions.get(from_state, set()))
            raise ValueError(
                f"Transição inválida: {from_state!r} → {to_state!r}. "
                f"Permitidas a partir de {from_state!r}: {allowed}"
            )

    def transitions_from(self, state: str) -> set[str]:
        return set(self._transitions.get(state, set()))

    def is_terminal(self, state: str) -> bool:
        return state not in self._transitions or not self._transitions[state]
