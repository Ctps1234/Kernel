#!/usr/bin/env python3
"""Confere a contagem dos hunks de cada patch antes do `git am`.

Editar um patch a mao e' facil: some uma linha `+` e esqueca de subir
o `+N` do `@@`, ou o contrario. O `git am` entao falha no meio da
serie, ou - pior - aplica deslocado. Este script recomputa as
contagens do corpo do hunk e compara com o cabecalho, sem precisar de
arvore de kernel e sem rede.

Regra de contagem: linha `+` conta so' no lado novo, `-` so' no lado
velho, ` ` (contexto) conta nos dois. Uma linha vazia ("" sem espaco)
marca o fim do hunk; `\\ No newline at end of file` nao conta.

Uso:
  tools/patch_lint.py                     # patches-6.18/*
  tools/patch_lint.py arquivo.patch ...
"""

import argparse
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def confere(caminho):
    problemas = []
    linhas = open(caminho, encoding="utf-8", errors="replace").read().split("\n")
    i = 0
    while i < len(linhas):
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", linhas[i])
        if not m:
            i += 1
            continue
        velho_ini, velho_n, novo_ini, novo_n = (
            int(m.group(1)), int(m.group(2) or 1),
            int(m.group(3)), int(m.group(4) or 1))
        j = i + 1
        v = n = 0
        while j < len(linhas):
            t = linhas[j]
            # fim do hunk: proximo hunk, proximo arquivo, assinatura do
            # format-patch ("-- ") ou linha vazia
            if t.startswith("@@ ") or t.startswith("diff --git") or \
               t.startswith("-- ") or t == "":
                break
            if t.startswith("--- ") and j + 1 < len(linhas) and \
               linhas[j + 1].startswith("+++ "):
                break
            if t.startswith("\\"):
                j += 1
                continue
            if t.startswith("+"):
                n += 1
            elif t.startswith("-"):
                v += 1
            elif t.startswith(" "):
                v += 1
                n += 1
            else:
                problemas.append((i + 1, "linha de hunk invalida: %r" % t[:40]))
                break
            j += 1
        if (v, n) != (velho_n, novo_n):
            problemas.append((i + 1, "cabecalho diz -%d,+%d mas o corpo tem "
                                     "-%d,+%d" % (velho_n, novo_n, v, n)))
        i = j
    return problemas


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="*")
    args = ap.parse_args(argv)
    alvos = args.arquivos or sorted(
        glob.glob(os.path.join(RAIZ, "patches-6.18", "*.patch")))
    if not alvos:
        print("erro: nenhum patch")
        return 2

    total = 0
    for caminho in alvos:
        for linha, msg in confere(caminho):
            total += 1
            print("%s:%d: %s" % (os.path.basename(caminho), linha, msg))
    if total:
        print("\n%d problema(s) em %d arquivo(s)" % (total, len(alvos)))
        return 1
    print("OK: %d patch(es), todas as contagens de hunk conferem"
          % len(alvos))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
