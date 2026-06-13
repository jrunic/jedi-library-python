---
id: 202606122220
projeto: jedi-library-python
tipo: plano
status: rascunho
escopo: repo:jedi-library-python
plataforma: "*"
dominios: [tecnologia]
descricao: "Plano — implementar jedi_library.assets com read_text() e list_files() sobre importlib.resources"
tags: [plano-execucao, python, assets, importlib, resources]
spec: docs/11-tarefas/20260612-spec-jedi-assets.md
---

# jedi_library.assets — Plano de Implementação

**Objetivo:** Criar módulo com read_text() e list_files() sobre importlib.resources; fixture interna para testes autocontidos.
**Arquitetura:** Wrapper sobre files(package).joinpath(); fixture dentro de jedi_library/_fixtures/ para testar sem paths externos.
**Pilha técnica:** Python 3.12, stdlib (importlib.resources, fnmatch)

## Nota sobre packaging

O `pyproject.toml` usa `[tool.uv] package = true` com hatchling como backend padrão. O hatchling inclui automaticamente todos os arquivos dentro do diretório do package — os arquivos em `jedi_library/_fixtures/` serão incluídos em editable install e wheel sem configuração adicional neste repo. Consumidores que empacotam seus próprios recursos (ex: arquivos `.sql` de migration) precisam declarar `package-data` no seu próprio `pyproject.toml` (ver CONTEXTO.md).

---

## Task 1 — Cria fixture interna de teste

**Arquivos:** `jedi_library/_fixtures/__init__.py`, `jedi_library/_fixtures/textos.txt`, `jedi_library/_fixtures/sql/__init__.py`, `jedi_library/_fixtures/sql/V001__criar_tabela.sql`, `jedi_library/_fixtures/sql/V002__adicionar_coluna.sql`, `jedi_library/_fixtures/sql/nota.txt`

**Steps:**

1. Cria `jedi_library/_fixtures/__init__.py` (arquivo vazio — torna o diretório um package Python, necessário para `importlib.resources.files("jedi_library._fixtures")`)

2. Cria `jedi_library/_fixtures/textos.txt` com conteúdo:
   ```
   Olá, mundo com acentos: ã, é, ô
   ```

3. Cria `jedi_library/_fixtures/sql/__init__.py` (arquivo vazio — torna o subdiretório um subpackage)

4. Cria `jedi_library/_fixtures/sql/V001__criar_tabela.sql` com:
   ```sql
   CREATE TABLE items (id INTEGER PRIMARY KEY);
   ```

5. Cria `jedi_library/_fixtures/sql/V002__adicionar_coluna.sql` com:
   ```sql
   ALTER TABLE items ADD COLUMN nome TEXT;
   ```

6. Cria `jedi_library/_fixtures/sql/nota.txt` com:
   ```
   este arquivo nao eh SQL
   ```

7. Verifica que os recursos são acessíveis via importlib:
   ```bash
   uv run python -c "from importlib.resources import files; print(list(files('jedi_library._fixtures').iterdir()))"
   ```
   Output esperado: lista contendo entradas para `textos.txt` e `sql`

8. Commit:
   ```
   feat(assets): fixture interna _fixtures para testes de importlib.resources
   ```

---

## Task 2 — assets.py e testes (TDD)

**Arquivos:** criar `jedi_library/assets.py`, criar `tests/test_assets.py`

**Steps:**

1. Escreve `tests/test_assets.py` completo (fase vermelha):
   ```python
   from jedi_library import assets


   def test_read_text_retorna_conteudo():
       content = assets.read_text("jedi_library._fixtures", "textos.txt")
       assert "Olá" in content


   def test_read_text_utf8_acentos():
       content = assets.read_text("jedi_library._fixtures", "textos.txt")
       assert "ã" in content


   def test_list_files_retorna_ordenado_lexicograficamente():
       result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
       names = [f.name for f in result]
       assert names == sorted(names)


   def test_list_files_filtra_por_padrao_sql():
       result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
       for f in result:
           assert f.name.endswith(".sql")


   def test_list_files_exclui_nao_casados():
       all_files = assets.list_files("jedi_library._fixtures", "sql", "*")
       sql_files = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
       all_names = {f.name for f in all_files}
       sql_names = {f.name for f in sql_files}
       assert "nota.txt" in all_names
       assert "nota.txt" not in sql_names


   def test_list_files_conteudo_legivel():
       result = assets.list_files("jedi_library._fixtures", "sql", "*.sql")
       assert len(result) == 2
       content = result[0].read_text(encoding="utf-8")
       assert "CREATE TABLE" in content
   ```

2. Roda os testes (fase vermelha — deve falhar com ImportError/AttributeError):
   ```bash
   uv run pytest tests/test_assets.py -v
   ```
   Output esperado: `FAILED` (6 falhas — `assets` não existe ainda)

3. Cria `jedi_library/assets.py`:
   ```python
   """Acesso a recursos empacotados via importlib.resources."""
   import fnmatch
   from importlib.resources import files
   from importlib.resources.abc import Traversable


   def read_text(package: str, resource: str, encoding: str = "utf-8") -> str:
       """Lê conteúdo de recurso empacotado."""
       return files(package).joinpath(resource).read_text(encoding=encoding)


   def list_files(package: str, subdir: str, pattern: str = "*") -> list[Traversable]:
       """Lista arquivos de subdiretório em ordem lexicográfica, filtrados por padrão fnmatch."""
       container = files(package).joinpath(subdir)
       items = [
           item for item in container.iterdir()
           if item.is_file() and fnmatch.fnmatch(item.name, pattern)
       ]
       return sorted(items, key=lambda f: f.name)
   ```

4. Roda os testes (fase verde — deve passar):
   ```bash
   uv run pytest tests/test_assets.py -v
   ```
   Output esperado: `6 passed`

5. Commit:
   ```
   feat(assets): jedi_library.assets com read_text() e list_files() — 6 testes passando
   ```

---

## Task 3 — Re-exporta em __init__.py

**Arquivos:** modificar `jedi_library/__init__.py`

**Steps:**

1. Atualiza `jedi_library/__init__.py` (adicionar `assets`):
   ```python
   from jedi_library import log, ai, assets

   __all__ = ["log", "ai", "assets"]
   ```

2. Verifica que o módulo é acessível via import canônico:
   ```bash
   uv run python -c "from jedi_library import assets; print(assets.read_text('jedi_library._fixtures', 'textos.txt'))"
   ```
   Output esperado:
   ```
   Olá, mundo com acentos: ã, é, ô
   ```

3. Roda suite completa para garantir que nenhum módulo existente quebrou:
   ```bash
   uv run pytest tests/ -v
   ```
   Output esperado: todos os testes existentes + 6 novos passando

4. Commit:
   ```
   feat(assets): re-exporta assets em jedi_library.__init__
   ```

---

## Auto-revisão

Critérios da spec cobertos:

- [x] `read_text(package, resource)` retorna conteúdo correto incluindo UTF-8 com acentos — coberto por `test_read_text_retorna_conteudo` e `test_read_text_utf8_acentos`
- [x] `list_files(package, subdir, pattern)` retorna lista ordenada lexicograficamente — coberto por `test_list_files_retorna_ordenado_lexicograficamente`
- [x] Filtro por padrão glob inclui apenas arquivos que casam — coberto por `test_list_files_filtra_por_padrao_sql` e `test_list_files_exclui_nao_casados`
- [x] Funções operam sobre fixture interna (sem dependência de paths externos) — fixture em `jedi_library/_fixtures/` acessível via `importlib.resources.files("jedi_library._fixtures")`
- [x] Tipo de retorno `list[Traversable]` permite `.read_text()` nos itens — coberto por `test_list_files_conteudo_legivel`
- [x] Sem dependências externas — apenas `importlib.resources` e `fnmatch` da stdlib
- [x] Módulo re-exportado em `__init__.py` — Task 3
- [x] Sem placeholders — todos os steps têm código completo e output esperado
- [x] Consistência de nomes — `test/` (não `tests/`) alinhado com estrutura existente do repo; `uv run` em todos os comandos de verificação

Critério fora do escopo deste plano (documentado na tarefa, não na spec técnica):

- [ ] CONTEXTO.md do repo ganha seção sobre `package-data` para consumidores — task separada, não incluída aqui
