#!/usr/bin/env python3
"""Resume um diff entre dois DTS decompilados (saida de `dtc -I dtb -O dts`).

Separa diferencas que sao so renumeracao de valores hexadecimais (tipicamente
phandles locais ao overlay, reatribuidos por dtc/fdtoverlay) das diferencas
reais de conteudo, e lista as propriedades mais afetadas.

Uso: dts_diff_summary.py A.dts B.dts [--top N]
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import Counter

HEX = re.compile(r"0x[0-9a-fA-F]+")


def norm(line: str) -> str:
    return HEX.sub("N", line.strip())


def prop_name(line: str) -> str:
    s = line.strip()
    m = re.match(r"([^\s=;{}]+)\s*(=|;|$)", s)
    return m.group(1) if m else s[:40]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)

    a = open(args.a, encoding="utf-8").read().splitlines()
    b = open(args.b, encoding="utf-8").read().splitlines()

    raw = [l for l in difflib.unified_diff(a, b, lineterm="", n=0)
           if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    na = [norm(l) for l in a]
    nb = [norm(l) for l in b]
    norm_raw = [l for l in difflib.unified_diff(na, nb, lineterm="", n=0)
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]

    print(f"linhas de diff brutas: {len(raw)}")
    print(f"linhas de diff apos normalizar hex: {len(norm_raw)}")
    if norm_raw:
        names = Counter(prop_name(l[1:]) for l in norm_raw)
        print("propriedades/nos mais afetados (apos normalizar hex):")
        for name, count in names.most_common(args.top):
            print(f"  {count:5d}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
