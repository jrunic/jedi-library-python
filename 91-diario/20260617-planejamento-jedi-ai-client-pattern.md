---
id: 202606171800
projeto: jedi-library-python
tipo: diario
status: concluido
escopo: repo:jedi-library-python
plataforma: local-macbook-jedi-labs
dominios: [tecnologia]
tags: [diario, planejamento, ai, vertex, client-pattern, spec, plano]
---

# Diário — Planejamento: redesign de jedi_library.ai para Client object pattern

## Contexto

Sessão de planejamento motivada pelo diagnóstico de que `jedi_library.ai` funciona "por sorte" — auth opaca via ADC residual, impossibilidade de multi-tenant no mesmo processo, `COST_SHEET_ID` baked-in na lib, `log_usage()` acoplado ao Sheets. A decisão de redesenho surgiu em sessão de 2026-06-16 (não visível aqui).

## O Que Foi Feito

- **Spec escrita** (`20260617-spec-jedi-ai-client-pattern.md`): problema em 5 pontos, solução com Client object pattern, 8 histórias de usuário, 21 critérios de sucesso, decisões de implementação completas (classe `JediAI`, factories `from_service_account_file`/`from_env`, schema de `usage`, remoções definitivas).
- **Plano escrito** (`20260617-plano-jedi-ai-client-pattern.md`): 8 tasks TDD com código completo, comandos exatos e contagem de testes acumulada por task (82 → 89 → 93 → 99 → 104 → 110 → 116 → 116 final). Auto-revisão com mapa de cobertura spec↔task.
- **CONTEXTO.md atualizado** (externamente): seção Autenticação reescrita para refletir `JediAI` e credenciais explícitas; `utils.py` adicionado à estrutura do package; restrições atualizadas.
- **USUARIO.md atualizado** (externamente): dois novos traços do Orlando registrados — exigência de verificação empírica antes de decisão de design; princípio "lib não decide o que o chamador deveria decidir".
- **jd-tasks #240 criada**: "ADR conceitual: client object pattern para libs AI (agnóstico de linguagem)" em projeto `jedi-library`.
- **Diário de push** (`20260613-push-producao-onda1.md`) commitado junto (estava pendente).

## Decisões Tomadas

- **Credenciais explícitas obrigatórias no construtor** — sem fallback ADC implícito. Raiz: multi-tenant em um processo exige um `JediAI` por tenant com credenciais distintas. `from_env()` é conveniência single-tenant, não caminho primário.
- **`usage_handler` injetado pelo caller** — lib não conhece mais Sheets. Caller passa handler que grava onde quiser.
- **`cost_context` removido** — parâmetro obrigatório sem valor; substituído por `execution_id` direto nos métodos e `project` já disponível na instância.
- **`prepare_prompt` para `jedi_library.utils`** — função pura de string sem relação com auth/Vertex.
- **Token counts zero em erro de rede/auth** — padrão da indústria para aggregation-safe em handlers de custo.
- **Breaking change intencional** — sem backward compat; consumidores migram em tarefas separadas.

## Padrões Definidos

Já no CONTEXTO.md:
- Auth via `JediAI` com credenciais explícitas — `from_service_account_file` como primário, `from_env` como conveniência.
- `utils.py` como módulo de funções puras de string.

## Pendências

- **Execução** via `dev-04-desenvolve-com-tdd`: 8 tasks prontas no plano. ⚠️ Considere Opus para execução.
- **jd-tasks #240**: ADR conceitual em `jedi-library` (repo agnóstico).
- **Migração de consumidores** (jedi-etl, tili): tarefas separadas nesses repos após implementação.
- **Bump de versão** em `pyproject.toml` e `uv lock --upgrade` nos consumidores: após execução.

## Voz do Usuário

*(Sessão de planejamento — mensagens do Orlando não capturadas neste turno de contexto. Spec e plano refletem decisões articuladas na sessão de 2026-06-16 e nesta sessão.)*
