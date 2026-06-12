---
id: 202606122010
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — implementar jedi_library/datetime_utils.py com constantes TZ e funções TZ-aware para a frota Jedi Labs"
tags: [tarefa, python, datetime, timezone, zoneinfo, cuiaba, sao-paulo]
---

# Tarefa — Implementação de `jedi_library.datetime_utils`

## Contexto

ADR: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-datetime-criacao.md`.

Onda 2 — pode ser desenvolvida em paralelo com `jedi_status_flow` e `jedi_audit` (zero dependências).

## Entregáveis

### `jedi_library/datetime_utils.py`

```python
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

CUIABA_TZ = ZoneInfo("America/Cuiaba")
SP_TZ = ZoneInfo("America/Sao_Paulo")

def now_tz(tz: ZoneInfo = CUIABA_TZ) -> datetime:
    """datetime.now() TZ-aware. Default: America/Cuiaba."""
    return datetime.now(tz=tz)

def parse_iso(s: str, tz: ZoneInfo = CUIABA_TZ) -> datetime:
    """Parse ISO string para datetime TZ-aware. Naive strings recebem tz."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)

def to_iso(dt: datetime) -> str:
    """Serializa datetime para string ISO canônica."""
    return dt.isoformat()
```

### Testes (`test/python/test_datetime_utils.py`)

- `now_tz()` retorna `tzinfo = CUIABA_TZ`.
- `now_tz(SP_TZ)` retorna `tzinfo = SP_TZ`.
- `parse_iso("2026-06-12T10:00:00")` → aware com CUIABA_TZ.
- `parse_iso("2026-06-12T10:00:00-04:00")` → convertido para CUIABA_TZ.
- `to_iso(now_tz())` retorna string que passa em `datetime.fromisoformat`.

## Critérios de conclusão

- [ ] `datetime_utils.py` com constantes + 3 funções.
- [ ] Testes passando.
- [ ] `__init__.py` exporta `datetime_utils`.

## Referências

- ADR conceitual: `jedi-library/docs/81-referencia/decisoes/20260612-jedi-datetime-criacao.md`.
- Fonte doadora: `jd-tasks/api/datetime_utils.py`.
- Timezones do Orlando: `USUARIO.md` §Timezones.
