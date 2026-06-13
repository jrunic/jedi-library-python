---
id: 202606122140
projeto: jedi-library-python
tipo: spec
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Spec — implementar jedi_library.assets com read_text() e list_files() sobre importlib.resources"
tags: [spec, python, assets, importlib, resources, pipx]
---

# Spec: `jedi_library.assets` — Acesso a Recursos Empacotados

> Task de implementação: [[20260612-jedi-assets]]

## Problema

O `tili` acessa arquivos SQL de migration via path relativo ao módulo. Isso funciona em desenvolvimento mas quebra quando o package é instalado via `pipx` (wheel), onde o código está num zip e caminhos relativos ao sistema de arquivos não existem. Sem um wrapper canônico sobre `importlib.resources`, cada consumidor resolve esse problema de forma diferente — ou não resolve.

## Solução

Módulo `assets` com duas funções sobre a API de recursos da stdlib: leitura de um recurso por nome e listagem de recursos em subdiretório com filtro por padrão glob. Compatível com editable install, wheel e pipx.

## Histórias de Usuário

1. Como `jedi_library.db`, quero listar todos os arquivos de migration de um package em ordem lexicográfica, independente de como o package foi instalado.
2. Como script que lê um template Markdown, quero ler o conteúdo de um recurso empacotado sem construir paths manuais ou depender de `__file__`.
3. Como consumidor que gera wheel ou instala via pipx, quero que as funções funcionem sem alteração de código — apenas com a declaração correta de `package-data` no meu próprio `pyproject.toml`.

## Critérios de Sucesso

- `read_text(package, resource)` retorna o conteúdo correto do arquivo empacotado, incluindo caracteres acentuados (encoding UTF-8).
- `list_files(package, subdir, pattern)` retorna lista ordenada lexicograficamente por nome de arquivo.
- Filtro por padrão glob inclui apenas arquivos que casam; outros são excluídos.
- Funções operam sobre fixture interna à `jedi_library` (sem dependência de paths externos no teste).
- Comportamento idêntico em editable install e wheel.

## Decisões de Implementação

- Novo módulo `assets`, apenas stdlib (`importlib.resources`, `fnmatch`)
- `read_text`: delega para a API de recursos da stdlib com encoding configurável (default UTF-8)
- `list_files`: navega pelo subdiretório do package, filtra por padrão fnmatch, retorna lista ordenada; tipo de retorno permite chamar `.read_text()` diretamente nos itens
- Fixture de teste: arquivo SQL mínimo empacotado dentro do próprio `jedi_library` para autocontenção dos testes
- `CONTEXTO.md` do repo ganha seção documentando que consumidores precisam declarar `package-data` para que arquivos SQL e templates sejam incluídos em wheels e pipx
- Módulo re-exportado em `__init__.py`

## Decisões de Teste

- Usar fixture real dentro do package (não mock de `importlib.resources`) — o valor do módulo é funcionar com o mecanismo real
- Cobrir: leitura de conteúdo, acentos, listagem ordenada, filtro por padrão glob, encoding

## Fora de Escopo

- Acesso a recursos binários (imagens, fontes)
- Escrita de recursos em tempo de execução
- Cache de recursos lidos

## Assumptions

1. Python 3.12 com `importlib.resources` na stdlib
2. pytest como runner
3. `jedi_library.db` é o principal consumidor downstream — `assets` deve existir antes de `db`
4. Consumidor é responsável por declarar `package-data` no seu próprio `pyproject.toml`

## Notas

- ADR `20260612-jedi-assets-criacao.md` no repo agnóstico define o contrato.
- A cicatriz do `tili` Fase 2 (path relativo via `__file__`) motivou esta spec — não repetir no `db`.
