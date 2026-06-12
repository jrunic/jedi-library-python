---
id: 202606122010
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/datetime_utils.py com constantes TZ e funções now/now_iso/today TZ-explícitas"
tags: [tarefa, python, datetime, timezone, zoneinfo, cuiaba, sao-paulo, utc]
---

# Tarefa — Implementação de `jedi_library.datetime_utils`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-datetime-criacao.md`.

API enxuta (3 funções + 3 constantes) com TZ sempre explícito. Sem default. Independente de outras libs.

## Entregáveis

### `jedi_library/datetime_utils.py`

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

CUIABA_TZ = ZoneInfo("America/Cuiaba")
SP_TZ     = ZoneInfo("America/Sao_Paulo")
UTC       = ZoneInfo("UTC")


def now(tz: ZoneInfo) -> datetime:
    """datetime.now(tz) TZ-aware."""
    return datetime.now(tz)


def now_iso(tz: ZoneInfo) -> str:
    """now(tz).isoformat() — string ISO 8601 com offset."""
    return now(tz).isoformat()


def today(tz: ZoneInfo) -> date:
    """now(tz).date() — só a data."""
    return now(tz).date()
```

### Testes (`test/python/test_datetime_utils.py`)

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

from jedi_library.datetime_utils import (
    CUIABA_TZ, SP_TZ, UTC,
    now, now_iso, today,
)


def test_constantes_corretas():
    assert CUIABA_TZ == ZoneInfo("America/Cuiaba")
    assert SP_TZ == ZoneInfo("America/Sao_Paulo")
    assert UTC == ZoneInfo("UTC")


def test_now_retorna_aware():
    dt = now(SP_TZ)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == SP_TZ


def test_now_cuiaba_vs_sp():
    # CBA é UTC-4; SP é UTC-3 (sem DST). 1h de diferença.
    dt_cba = now(CUIABA_TZ)
    dt_sp = now(SP_TZ)
    # Mesmo instante; offsets diferentes.
    assert abs((dt_cba - dt_sp).total_seconds()) < 2


def test_now_iso_termina_com_offset():
    iso = now_iso(SP_TZ)
    assert isinstance(iso, str)
    # ISO com offset (não Z, exceto UTC)
    assert iso[-6] in {"+", "-"} or iso.endswith("+00:00")


def test_now_iso_utc():
    iso = now_iso(UTC)
    assert "+00:00" in iso


def test_today_retorna_date():
    d = today(SP_TZ)
    assert isinstance(d, date)


def test_tz_obrigatorio():
    # Sem default — chamar sem argumento é erro de tipo
    import pytest
    with pytest.raises(TypeError):
        now()
```

## Critérios de conclusão

- [ ] `datetime_utils.py` com 3 funções + 3 constantes.
- [ ] TZ sempre obrigatório (sem default — `TypeError` se omitido).
- [ ] Testes passando incluindo CBA vs SP offset.
- [ ] `__init__.py` exporta `datetime_utils`.
- [ ] PR referencia ADR.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-datetime-criacao.md`.
- Fonte doadora: `jd-tasks/src/jd_tasks/api/datetime_utils.py`.
- Aderência com infra de logs: ADR `20260612-schema-log-json-aderente-incidentes.md` (UTC).
