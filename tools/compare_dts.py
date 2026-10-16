#!/usr/bin/env python3
"""Compara a estrutura de duas device trees (nós e propriedades).

serve para confrontar o DTB compilado a partir das DTS do projeto com a
referência extraída do aparelho (`device-tree/reference/*.dts`), medindo
quanto da descrição de hardware do FDT real está coberta.

Uso:
    tools/compare_dts.py REFERENCIA.dts NOSSO.dts [--dtc /caminho/dtc]
    tools/compare_dts.py REFERENCIA.dts NOSSO.dtb --dtc /caminho/dtc
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

NODE_RE = re.compile(r"^\s*(&?[A-Za-z0-9,_@.\-+#/]+)\s*\{")
PROP_RE = re.compile(r"^\s*([A-Za-z0-9,_@.\-+#]+)\s*=")
LABEL_RE = re.compile(r"^\s*([A-Za-z0-9,_@.\-+#]+)\s*:\s*[A-Za-z0-9,_@.\-+#]+\s*;")

# Subtrees artificiais gerados ao compilar overlays.
SKIP_NODES = ("__fixups__", "__local_fixups__", "__symbols__", "__overrides__",
              "__dtbo__", "fragment@")


def decompile(path, dtc):
    """Converte um .dtb em texto DTS usando o dtc informado."""
    if not path.endswith(".dtb"):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    with tempfile.NamedTemporaryFile(suffix=".dts", delete=False) as tmp:
        out = tmp.name
    try:
        subprocess.run([dtc, "-I", "dtb", "-O", "dts", "-o", out, path],
                       check=True, capture_output=True)
        with open(out, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    finally:
        os.unlink(out)


def parse(text):
    """Extrai o conjunto de caminhos de nós e suas propriedades."""
    nodes = {}
    stack = []  # (indentacao, nome)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("/*", "//", "#")):
            continue

        match = NODE_RE.match(line)
        if match:
            indent = len(line) - len(line.lstrip())
            while stack and stack[-1][0] >= indent:
                stack.pop()
            name = match.group(1)
            if any(name == skip or name.startswith(skip) for skip in SKIP_NODES):
                # subtree ignorado: mantem a indentacao para nao embaralhar
                stack.append((indent, None))
                continue
            path = "/" + "/".join([n for _i, n in stack if n] + [name])
            nodes.setdefault(path, set())
            stack.append((indent, name))
            continue

        match = PROP_RE.match(line) or LABEL_RE.match(line)
        if match and stack:
            indent = len(line) - len(line.lstrip())
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack and stack[-1][1]:
                path = "/" + "/".join(n for _i, n in stack if n)
                nodes.setdefault(path, set()).add(match.group(1))

    return nodes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", help="DTS de referência")
    parser.add_argument("target", help="DTS ou DTB a comparar")
    parser.add_argument("--dtc", default=os.environ.get("DTC", "dtc"),
                        help="binario dtc (necessario para .dtb)")
    parser.add_argument("--properties", action="store_true",
                        help="compara também as propriedades de cada nó")
    parser.add_argument("--max-report", type=int, default=40)
    args = parser.parse_args()

    reference = parse(decompile(args.reference, args.dtc))
    target = parse(decompile(args.target, args.dtc))

    ref_nodes = set(reference)
    our_nodes = set(target)

    only_ref = sorted(ref_nodes - our_nodes)
    only_our = sorted(our_nodes - ref_nodes)
    common = ref_nodes & our_nodes

    print(f"referencia: {len(ref_nodes)} nos")
    print(f"nosso DTB : {len(our_nodes)} nos")
    print(f"cobertos  : {len(common)} "
          f"({100.0 * len(common) / max(len(ref_nodes), 1):.1f}% da referencia)")

    if only_ref:
        print(f"\nnos da referencia ausentes no nosso DTB ({len(only_ref)}):")
        for path in only_ref[:args.max_report]:
            print(f"  {path}")
        if len(only_ref) > args.max_report:
            print(f"  ... e mais {len(only_ref) - args.max_report}")

    if only_our:
        print(f"\nnos do nosso DTB ausentes na referencia ({len(only_our)}):")
        for path in only_our[:args.max_report]:
            print(f"  {path}")
        if len(only_our) > args.max_report:
            print(f"  ... e mais {len(only_our) - args.max_report}")

    if args.properties:
        diffs = 0
        for path in sorted(common):
            missing = reference[path] - target[path]
            if missing:
                diffs += 1
                if diffs <= args.max_report:
                    print(f"  props ausentes em {path}: "
                          f"{', '.join(sorted(missing))}")
        print(f"\nnos com propriedades ausentes: {diffs}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
