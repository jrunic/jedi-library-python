#!/bin/bash
# O QUE: Remove diretório test/python/ (contém apenas __pycache__) e
#        diretório src/ (já esvaziado — src/python/jedi_log.py já foi deletado).
#
# POR QUE: Esses diretórios são resquício do monorepo jedi-library (antes
#           do split em jedi-library-python / jedi-library-gas). O prefixo
#           python/ dentro de src/ e test/ não faz sentido num repo Python puro.
#           src/python/jedi_log.py e test/python/test_log.py já foram deletados
#           nesta sessão. Resta apenas o __pycache__ em test/python/.
#
# IMPACTOS:
#   - test/python/__pycache__/ será apagado (cache de bytecode — regenerado
#     automaticamente pelo pytest na próxima execução).
#   - src/ será apagado (já vazio).
#   - Nenhum arquivo de código fonte ou teste é perdido.
#   - git status mostrará apenas as remoções já staged (jedi_log.py e
#     test_log.py) — __pycache__ é gitignored.
#
# COMO REVERTER: Não há nada a reverter. __pycache__ é regenerado
#                automaticamente. Se necessário: mkdir -p test/python src/python
#
# REPO: jedi-library-python

set -e

REPO="/Users/jedi/jedi-brain/15-repositorios/jedi-library-python"

echo "Removendo test/python/ (contém apenas __pycache__)..."
rm -rf "$REPO/test/python"

echo "Removendo src/ (diretório vazio)..."
rmdir "$REPO/src" 2>/dev/null && echo "src/ removido." || echo "src/ não estava vazio ou não existe — ignorado."

echo "Pronto."
