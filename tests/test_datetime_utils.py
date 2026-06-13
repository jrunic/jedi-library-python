import pytest
from datetime import datetime, date

from jedi_library import datetime_utils as dt


def test_cuiaba_tz_zona_correta():
    assert dt.CUIABA_TZ.key == "America/Cuiaba"


def test_sp_tz_zona_correta():
    assert dt.SP_TZ.key == "America/Sao_Paulo"


def test_utc_zona_correta():
    assert dt.UTC.key == "UTC"


def test_now_retorna_datetime_aware():
    result = dt.now(dt.CUIABA_TZ)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_now_retorna_fuso_correto():
    result = dt.now(dt.CUIABA_TZ)
    assert result.tzinfo.key == "America/Cuiaba"


def test_now_cuiaba_e_sp_mesmo_instante():
    t_cba = dt.now(dt.CUIABA_TZ)
    t_sp = dt.now(dt.SP_TZ)
    diff = abs((t_cba - t_sp).total_seconds())
    assert diff < 2


def test_now_iso_retorna_string():
    assert isinstance(dt.now_iso(dt.UTC), str)


def test_now_iso_utc_contem_offset_numerico():
    result = dt.now_iso(dt.UTC)
    assert "+00:00" in result


def test_today_retorna_date_nao_datetime():
    result = dt.today(dt.CUIABA_TZ)
    assert isinstance(result, date)
    assert not isinstance(result, datetime)


def test_now_sem_argumento_levanta_type_error():
    with pytest.raises(TypeError):
        dt.now()  # type: ignore


def test_now_iso_sem_argumento_levanta_type_error():
    with pytest.raises(TypeError):
        dt.now_iso()  # type: ignore


def test_today_sem_argumento_levanta_type_error():
    with pytest.raises(TypeError):
        dt.today()  # type: ignore
