---
id: 202606122110
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — implementar jedi_library.slug com normalize(), unique_slug() e normalize_unique()"
tags: [spec, python, slug, normalize, unicode]
---

# Spec: `jedi_library.slug` — Normalização e Unicidade de Slugs

> Task de implementação: [[20260612-jedi-slug]]

## Problema

Dois repos mantêm implementações independentes de normalização de texto para slugs e tags. Apesar de servirem o mesmo propósito, divergiram em detalhes (separador, tratamento de caracteres especiais). Qualquer novo repo que precise de slug copia ou depende de um deles. Não há ponto canônico.

## Solução

Módulo `slug` com três funções que cobrem os dois casos de uso: normalização simples (URLs, nomes de arquivo), unicidade com sufixo numérico (evitar colisões em coleções), e normalização de lista com deduplicação (tags). Stdlib-only.

## Histórias de Usuário

1. Como endpoint que gera slug de conteúdo, quero normalizar títulos com acentos e espaços para URLs limpas e consistentes.
2. Como criador de tarefas com título duplicado, quero obter um slug único com sufixo numérico para evitar colisão de IDs.
3. Como importador de tags, quero normalizar uma lista descartando duplicatas de caixa, sem alterar a ordem das primeiras ocorrências.
4. Como consumidor passando input degenerado (caracteres sem equivalente ASCII, string vazia, só espaços), quero receber string vazia de volta sem exceção.
5. Como consumidor com restrição de comprimento, quero truncar o slug no último hífen antes do limite, nunca no meio de uma palavra.

## Critérios de Sucesso

- `normalize("Ação Rápida")` → `"acao-rapida"` (NFKD → ASCII → lower → kebab)
- `normalize("  olá, mundo!  ")` → `"ola-mundo"` (strip, colapso de separadores)
- Input degenerado → `""` sem raise
- `normalize(text, max_len=20)` trunca no último hífen antes do limite
- `unique_slug("tarefa", {"tarefa"})` → `"tarefa-2"`; com `{"tarefa", "tarefa-2"}` → `"tarefa-3"`
- `unique_slug` com input degenerado → `""` sem raise
- `normalize_unique(["Financeiro", "FINANCEIRO", "Farmácia", "financeiro"])` → `["financeiro", "farmacia"]` (deduplicado, ordem preservada)
- `normalize_unique` descarta silenciosamente entradas que normalizam para `""`
- Todas as 91 tags de produção do `jd-tasks` passam por `normalize(tag) == tag` (idempotência em dados reais)

## Decisões de Implementação

- Novo módulo `slug`, sem dependências externas (stdlib pura)
- Pipeline de normalização: decomposição NFKD → encoding ASCII ignorando não-mapeáveis → lower → strip → substituição de não-alfanuméricos por hífen → colapso de hífens → strip de hífens nas pontas
- `max_len`: trunca e busca ponto de corte no último hífen; se não encontrar, usa o trecho bruto
- `unique_slug`: normaliza a base e itera sufixo numérico a partir de 2 até encontrar slug não-presente
- `normalize_unique`: itera, normaliza cada item, descarta vazio e já-visto, preserva primeira ocorrência
- Módulo re-exportado em `__init__.py`

## Decisões de Teste

- Testes puramente funcionais: entrada → saída esperada, sem mocks
- Cobrir: acentos PT-BR comuns, maiúsculas, espaços múltiplos, caracteres especiais, input vazio, input degenerado, max_len com e sem hífen no ponto de corte, colisão simples e encadeada, deduplicação com variações de caixa
- Verificar idempotência contra as 91 tags reais antes de declarar concluído

## Fora de Escopo

- Slugs com separador diferente de hífen
- Transliteração além de NFKD para ASCII (sem mapeamento manual de caracteres especiais)
- Persistência de slugs gerados
- Verificação de unicidade em banco de dados (consumidor mantém o set de existentes)

## Assumptions

1. Python 3.12, stdlib suficiente
2. pytest como runner
3. Fusão kebab (espaço → hífen) é não-breaking para os 91 slugs de produção verificados

## Notas

- ADR `20260612-jedi-slug-criacao.md` no repo agnóstico define o contrato.
- Fontes doadoras: módulos de slug do `tili` e de tag utils do `jd-tasks` — verificar edge cases antes de escrever.
