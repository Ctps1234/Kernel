#!/usr/bin/env python3
"""Compara dois DTS decompilados por conteudo, nao por linha.

Cada propriedade e identificada por (caminho do no, nome). Valores numericos que
coincidem com um phandle de algum no da arvore sao trocados pelo caminho desse
no, de modo que renumeracao de phandles nao aparece como diferenca. A ordem dos
nos e das propriedades tambem nao importa.

Uso: dts_semantic_diff.py ATIVO.dts MESCLADO.dts [--top N]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __import__("os").path.dirname(__file__))
import symbolize_overlay as s  # noqa: E402  (parser de DTS decompilado)

INTERNAL = {"__symbols__", "__fixups__", "__local_fixups__"}
PHANDLE_PROPS = {"phandle", "linux,phandle"}


def canon_value(raw: str | None, phandles: dict[int, str]) -> str:
    if raw is None:
        return "<flag>"
    out = []
    # Preserva strings e bytes literais; achata celulas numericas.
    for chunk in re.findall(r'"[^"]*"|<[^<>]*>|\[[^\]]*\]|[^,\s][^,]*', raw):
        chunk = chunk.strip()
        if chunk.startswith("<"):
            cells = []
            for tok in chunk[1:-1].split():
                if re.fullmatch(r"0x[0-9a-fA-F]+|\d+", tok):
                    v = int(tok, 0)
                    cells.append(f"&{phandles[v]}" if v in phandles and v != 0 else f"{v:#x}")
                else:
                    cells.append(tok)
            out.append("<" + " ".join(cells) + ">")
        else:
            out.append(chunk)
    return ", ".join(out)


def index(path: str):
    root = s.parse(open(path, encoding="utf-8").read())
    phandles: dict[int, str] = {}

    def collect(n):
        for p in n.props:
            if p.name in PHANDLE_PROPS and p.value:
                phandles[int(s.cells_of(p.value)[0], 0)] = n.path()
        for c in n.children:
            collect(c)

    collect(root)
    nodes: set[str] = set()
    props: dict[tuple[str, str], str] = {}

    def walk(n, skip):
        if n.parent is not None:
            nodes.add(n.path())
        for p in n.props:
            if p.name in PHANDLE_PROPS:
                continue
            props[(n.path(), p.name)] = canon_value(p.value, phandles)
        for c in n.children:
            if c.name in INTERNAL or (skip and c.name == "chosen"):
                continue
            walk(c, skip)

    walk(root, skip=False)
    return nodes, props


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)

    na, pa = index(args.a)
    nb, pb = index(args.b)
    only_a_nodes = sorted(na - nb)
    only_b_nodes = sorted(nb - na)
    only_a = sorted(set(pa) - set(pb))
    only_b = sorted(set(pb) - set(pa))
    changed = sorted(k for k in set(pa) & set(pb) if pa[k] != pb[k])

    print(f"nos: ativo={len(na)} mesclado={len(nb)} "
          f"somente_ativo={len(only_a_nodes)} somente_mesclado={len(only_b_nodes)}")
    print(f"propriedades: somente_ativo={len(only_a)} somente_mesclado={len(only_b)} "
          f"valor_diferente={len(changed)}")

    def show(title, items, fmt):
        if not items:
            return
        print(title)
        for it in items[: args.top]:
            print("  " + fmt(it))

    show("nos somente no ativo (amostra):", only_a_nodes, str)
    show("nos somente no mesclado (amostra):", only_b_nodes, str)
    show("propriedades somente no ativo (amostra):", only_a,
         lambda k: f"{k[0]} :: {k[1]}")
    show("propriedades somente no mesclado (amostra):", only_b,
         lambda k: f"{k[0]} :: {k[1]}")
    show("valor diferente (amostra):", changed,
         lambda k: f"{k[0]} :: {k[1]}\n      ativo:    {pa[k][:160]}\n      mesclado: {pb[k][:160]}")

    by_prop = Counter(k[1] for k in only_a + only_b + changed)
    print("nomes de propriedade mais afetados:")
    for name, c in by_prop.most_common(args.top):
        print(f"  {c:5d}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
