import pytest
from jedi_library import utils


def test_substitui_placeholder_simples():
    result = utils.prepare_prompt("Olá {$nome}!", {"nome": "Jedi"})
    assert result == "Olá Jedi!"


def test_substitui_multiplos_placeholders():
    result = utils.prepare_prompt("{$a} e {$b}", {"a": "X", "b": "Y"})
    assert result == "X e Y"


def test_sem_variaveis_retorna_template_intacto():
    result = utils.prepare_prompt("sem placeholders", {})
    assert result == "sem placeholders"


def test_sem_variaveis_none_retorna_template():
    result = utils.prepare_prompt("sem placeholders")
    assert result == "sem placeholders"


def test_placeholder_ausente_no_dict_levanta_value_error():
    with pytest.raises(ValueError, match="variavel"):
        utils.prepare_prompt("{$variavel}", {})


def test_placeholder_ausente_no_template_levanta_value_error():
    with pytest.raises(ValueError, match="inexistente"):
        utils.prepare_prompt("sem {$a}", {"a": "ok", "inexistente": "x"})


def test_placeholder_nao_substituido_levanta_value_error():
    with pytest.raises(ValueError, match="nao_usado"):
        utils.prepare_prompt("texto sem placeholder", {"nao_usado": "val"})
