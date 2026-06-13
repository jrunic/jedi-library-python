---
id: 202606122205
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — implementar jedi_library.datetime_utils com constantes TZ e funções now/now_iso/today TZ-explícitas"
tags: [plano-execucao, python, datetime, timezone, zoneinfo]
spec: docs/11-tarefas/20260612-spec-jedi-datetime.md
---

# jedi_library.datetime_utils — Plano de Implementação

**Objetivo:** Criar módulo com constantes de fuso (Cuiabá, São Paulo, UTC) e três funções TZ-explícitas sem default.
**Arquitetura:** Wrapper fino sobre stdlib datetime/zoneinfo; TZ obrigatório por assinatura; sem estado global.
**Pilha técnica:** Python 3.12, stdlib (datetime, zoneinfo)

---

## Task 1: Constantes e funções now/now_iso/today

**Arquivos:** criar `jedi_library/datetime_utils.py`, criar `tests/test_datetime_utils.py`

### Step 1 — Escreve o arquivo de testes completo

Criar `tests/test_datetime_utils.py`:

```python
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
```

### Step 2 — Roda testes → FAIL esperado

```bash
uv run pytest tests/test_datetime_utils.py -v
```

**Output esperado:**
```
ERROR tests/test_datetime_utils.py - ModuleNotFoundError: No module named 'jedi_library.datetime_utils'
```

O erro confirma que o módulo ainda não existe — red correto no ciclo TDD.

### Step 3 — Cria `jedi_library/datetime_utils.py`

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

CUIABA_TZ = ZoneInfo("America/Cuiaba")
SP_TZ = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")


def now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz=tz)


def now_iso(tz: ZoneInfo) -> str:
    return datetime.now(tz=tz).isoformat()


def today(tz: ZoneInfo) -> date:
    return datetime.now(tz=tz).date()
```

### Step 4 — Roda testes → PASS esperado

```bash
uv run pytest tests/test_datetime_utils.py -v
```

**Output esperado:**
```
tests/test_datetime_utils.py::test_cuiaba_tz_zona_correta PASSED
tests/test_datetime_utils.py::test_sp_tz_zona_correta PASSED
tests/test_datetime_utils.py::test_utc_zona_correta PASSED
tests/test_datetime_utils.py::test_now_retorna_datetime_aware PASSED
tests/test_datetime_utils.py::test_now_retorna_fuso_correto PASSED
tests/test_datetime_utils.py::test_now_cuiaba_e_sp_mesmo_instante PASSED
tests/test_datetime_utils.py::test_now_iso_retorna_string PASSED
tests/test_datetime_utils.py::test_now_iso_utc_contem_offset_numerico PASSED
tests/test_datetime_utils.py::test_today_retorna_date_nao_datetime PASSED
tests/test_datetime_utils.py::test_now_sem_argumento_levanta_type_error PASSED
tests/test_datetime_utils.py::test_now_iso_sem_argumento_levanta_type_error PASSED
tests/test_datetime_utils.py::test_today_sem_argumento_levanta_type_error PASSED

12 passed in 0.XXs
```

### Step 5 — Commit

```bash
git add jedi_library/datetime_utils.py tests/test_datetime_utils.py
git commit -m "feat(datetime_utils): constantes TZ e funções now/now_iso/today TZ-explícitas"
```

---

## Task 2: Re-exporta em `__init__.py`

**Arquivos:** modificar `jedi_library/__init__.py`

### Step 1 — Atualiza `__init__.py`

Conteúdo completo do arquivo após a alteração:

```python
from jedi_library import log, ai, datetime_utils

__all__ = ["log", "ai", "datetime_utils"]
```

### Step 2 — Verifica import direto

```bash
python -c "from jedi_library import datetime_utils; print(datetime_utils.CUIABA_TZ)"
```

**Output esperado:**
```
America/Cuiaba
```

### Step 3 — Roda suite completa

```bash
uv run pytest tests/ -v
```

**Output esperado:** todos os testes da suite (incluindo os de outros módulos já existentes) passando sem falha.

### Step 4 — Commit

```bash
git add jedi_library/__init__.py
git commit -m "feat(datetime_utils): re-exporta datetime_utils em __init__.py"
```

---

## Auto-revisão

| Critério da spec | Coberto? | Evidência |
|---|---|---|
| `CUIABA_TZ`, `SP_TZ`, `UTC` são `ZoneInfo` | Sim | `test_cuiaba_tz_zona_correta`, `test_sp_tz_zona_correta`, `test_utc_zona_correta` |
| `now()` retorna `datetime` aware | Sim | `test_now_retorna_datetime_aware` |
| `now()` aplica o fuso passado | Sim | `test_now_retorna_fuso_correto` |
| `now(CUIABA_TZ)` e `now(SP_TZ)` diferem < 2s | Sim | `test_now_cuiaba_e_sp_mesmo_instante` |
| `now_iso()` retorna string ISO 8601 | Sim | `test_now_iso_retorna_string` |
| `now_iso(UTC)` contém `"+00:00"` (não "Z") | Sim | `test_now_iso_utc_contem_offset_numerico` |
| `today()` retorna `date`, não `datetime` | Sim | `test_today_retorna_date_nao_datetime` |
| TZ obrigatório — `TypeError` sem argumento | Sim | `test_now_sem_argumento_levanta_type_error`, `test_now_iso_sem_argumento_levanta_type_error`, `test_today_sem_argumento_levanta_type_error` |
| Stdlib pura (sem deps externas) | Sim | Apenas `datetime`, `zoneinfo` no módulo |
| Re-exportado em `__init__.py` | Sim | Task 2, Step 1 |
| 12 testes no total | Sim | 12 funções `test_*` |
| Sem placeholders | Sim | Código completo em cada step |
| Nomes consistentes (`datetime_utils`) | Sim | Módulo, import, `__all__`, testes |
