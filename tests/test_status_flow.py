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
