---
id: 202606121910
projeto: jedi-library-python
tipo: tarefa
status: aberto
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Tarefa — expandir jedi_library/log.py com JsonFormatter e setup_logging(); adotar jd-tasks como consumidor"
tags: [tarefa, python, log, json-formatter, logging]
---

# Tarefa — Expansão de `jedi_library.log`

## Contexto

`jedi_library/log.py` existe como port magro do `jediLog` GAS. Nunca foi adotado por nenhum projeto — `jedi-etl/scripts/` usa `jedi_logger` local divergente, e `jd-tasks` tem `logging_config.py` com `JsonFormatter` próprio.

Esta tarefa expande `log.py` para absorver o `JsonFormatter` do `jd-tasks` e adiciona `setup_logging()` como função de configuração canônica.

## Entregáveis

### `jedi_library/log.py` — expansão

```python
import logging
import json
import sys
from datetime import datetime, UTC

class JsonFormatter(logging.Formatter):
    """Formata log como JSON de uma linha em stdout."""
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
        }, ensure_ascii=False)

def setup_logging(level: str = "INFO", *, as_json: bool = True) -> None:
    """Configura o root logger. Chame uma vez no entry-point."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if as_json else logging.Formatter())
    logging.basicConfig(level=getattr(logging, level.upper()), handlers=[handler], force=True)
```

### Testes

- `test/python/test_log.py` — cobrir: JSON válido no output, campo `ts` presente, `as_json=False` usa formatter padrão, `setup_logging` idempotente (segunda chamada não adiciona handler).

### Migração do `jd-tasks`

- Substituir `jd-tasks/api/logging_config.py` (`JsonFormatter` local) por `from jedi_library.log import setup_logging`.
- Tarefa de migração é responsabilidade do repo `jd-tasks` — abrir tarefa lá.

## Critérios de conclusão

- [ ] `JsonFormatter` em `log.py`.
- [ ] `setup_logging(level, as_json)` em `log.py`.
- [ ] Testes passando.
- [ ] `__init__.py` exporta `log`.
- [ ] PR referencia inventário `jedi-library/docs/11-tarefas/20260612-incremento-ondas-1-2-jedi-library-python.md`.

## Referências

- Fonte: `jd-tasks/api/logging_config.py`.
- Plano de ondas: `jedi-library/docs/11-tarefas/20260612-incremento-ondas-1-2-jedi-library-python.md`.
