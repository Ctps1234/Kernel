#!/usr/bin/env python3
"""Verificação estática de includes de Device Tree.

Resolve os `#include "..."` (relativos) e `#include <...>` (caminhos de
include do kernel) de todos os arquivos .dts/.dtsi/.dtso de uma árvore de
device tree e reporta os que não resolvem.

A resolução de includes entrequotedos segue a mesma ordem usada pelo build
do kernel (scripts/Makefile.dtbs):

    dtc -i <dir do arquivo> -i <DTC_INCLUDE...>

ou seja, o diretório do próprio arquivo tem precedência, seguido dos
diretórios de include globais.

Uso:
    tools/check_dts_includes.py --dts-dir device-tree/source/qcom \
        --kernel-tree /path/para/basekernel [--verbose]
"""

import argparse
import os
import re
import sys

INCLUDE_RE = re.compile(r'^\s*#\s*include\s+(?:"([^"]+)"|<([^>]+)>)')

DTS_SUFFIXES = (".dts", ".dtsi", ".dtso")


def collect_dts_files(root):
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if name.endswith(DTS_SUFFIXES):
                files.append(os.path.join(dirpath, name))
    return sorted(files)


def parse_includes(path):
    includes = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = INCLUDE_RE.match(line)
            if match:
                quoted, angled = match.groups()
                includes.append(quoted if quoted else angled)
    return includes


def resolve(include, source_dir, include_dirs, angled):
    """Resolve um include segundo a ordem do build do kernel."""
    if angled:
        # Includes <...> usam apenas os diretórios globais de include.
        for directory in include_dirs:
            candidate = os.path.join(directory, include)
            if os.path.isfile(candidate):
                return candidate
        return None

    # Includes "..." começam pelo diretório do arquivo que os referencia.
    if os.path.isfile(os.path.join(source_dir, include)):
        return os.path.join(source_dir, include)
    for directory in include_dirs:
        candidate = os.path.join(directory, include)
        if os.path.isfile(candidate):
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dts-dir", required=True,
                        help="raiz da árvore de device tree a verificar")
    parser.add_argument("--kernel-tree", default=None,
                        help="árvore do kernel (para includes <dt-bindings/...>)")
    parser.add_argument("--include-dir", action="append", default=[],
                        help="diretório extra de include (repetível)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    dts_dir = os.path.abspath(args.dts_dir)
    if not os.path.isdir(dts_dir):
        print(f"ERRO: diretório inexistente: {dts_dir}", file=sys.stderr)
        return 2

    include_dirs = list(args.include_dir)
    if args.kernel_tree:
        include_dirs.append(os.path.join(args.kernel_tree, "include"))
        include_dirs.append(os.path.join(args.kernel_tree, "include", "dt-bindings"))
        include_dirs.append(os.path.join(args.kernel_tree, "arch", "arm64", "boot", "dts"))

    files = collect_dts_files(dts_dir)
    unresolved = []
    total = 0

    for path in files:
        source_dir = os.path.dirname(path)
        for include in parse_includes(path):
            total += 1
            angled = include.startswith("<")
            target = include.strip("<>")
            resolved = resolve(target, source_dir, include_dirs, angled)
            if resolved is None:
                unresolved.append((os.path.relpath(path, dts_dir), include))
            elif args.verbose:
                print(f"OK   {os.path.relpath(path, dts_dir)} -> {include}")

    print(f"arquivos .dts/.dtsi/.dtso: {len(files)}")
    print(f"includes verificados: {total}")
    if unresolved:
        print(f"includes NAO resolvidos: {len(unresolved)}")
        for path, include in unresolved:
            print(f"  {path}: {include}")
        return 1

    print("todos os includes resolvem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
