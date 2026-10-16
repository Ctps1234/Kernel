#!/usr/bin/env python3
"""Integra as device trees de topaz/tapas em uma árvore do kernel 6.12.

O staging é determinístico e idempotente: pode ser reexecutado sobre a
mesma árvore sem duplicar conteúdo.

Passos:

1. copia `device-tree/source/qcom/**` para
   `<kernel>/arch/arm64/boot/dts/qcom/khaje/`, preservando a estrutura de
   diretórios (o build do kernel resolve includes com `-i <dir do arquivo>`,
   e cada diretório do conjunto importado é autossuficiente);
2. renomeia os overlays (`/plugin/;`) de `.dts` para `.dtso`, que é a
   extensão que o build do kernel compila em `.dtbo` e combina com a base
   via `fdtoverlay`;
3. copia os Makefiles em estilo kernel de `device-tree/kernel/qcom/khaje/`;
4. registra `subdir-y += khaje` no Makefile de `arch/arm64/boot/dts/qcom/`.

Uso:
    tools/integrate_dts.py --kernel-tree /path/para/basekernel [--check]
"""

import argparse
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DTS_SOURCE = os.path.join(REPO_ROOT, "device-tree", "source", "qcom")
DTS_KERNEL = os.path.join(REPO_ROOT, "device-tree", "kernel", "qcom", "khaje")

KERNEL_DTS_DIR = os.path.join("arch", "arm64", "boot", "dts", "qcom")
SUBDIR_MARKER = "# Khaje (SM6225) topaz/tapas device trees"


def is_overlay(path):
    """Um .dts com /plugin/; é um overlay, não um device tree base."""
    if not path.endswith(".dts"):
        return False
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip().startswith("/plugin/;"):
                return True
            if line.strip().startswith("/dts-v1/;"):
                continue
    return False


def stage_sources(kernel_tree, dry_run=False):
    src_root = DTS_SOURCE
    dst_root = os.path.join(kernel_tree, KERNEL_DTS_DIR, "khaje")
    copied, renamed = [], []

    for dirpath, _dirnames, filenames in os.walk(src_root):
        rel_dir = os.path.relpath(dirpath, src_root)
        for name in sorted(filenames):
            if name == "Makefile":
                # Makefile no estilo vendor: substituido pelos Makefiles
                # em estilo kernel de device-tree/kernel/.
                continue
            if not name.endswith((".dts", ".dtsi", ".dtso")):
                continue

            src = os.path.join(dirpath, name)
            dst_name = name
            if is_overlay(src):
                dst_name = name[:-len(".dts")] + ".dtso"

            dst = os.path.join(dst_root, rel_dir, dst_name)
            if dst_name != name:
                renamed.append((os.path.relpath(src, REPO_ROOT), dst_name))
            copied.append((os.path.relpath(src, REPO_ROOT), os.path.relpath(dst, kernel_tree)))
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)

    return copied, renamed


def stage_makefiles(kernel_tree, dry_run=False):
    dst_root = os.path.join(kernel_tree, KERNEL_DTS_DIR, "khaje")
    copied = []
    for dirpath, _dirnames, filenames in os.walk(DTS_KERNEL):
        rel_dir = os.path.relpath(dirpath, DTS_KERNEL)
        for name in sorted(filenames):
            if name != "Makefile":
                continue
            src = os.path.join(dirpath, name)
            dst = os.path.join(dst_root, rel_dir, name)
            copied.append(os.path.relpath(dst, kernel_tree))
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
    return copied


def register_subdir(kernel_tree, dry_run=False):
    """Adiciona `subdir-y += khaje` ao Makefile de arch/arm64/boot/dts/qcom."""
    makefile = os.path.join(kernel_tree, KERNEL_DTS_DIR, "Makefile")
    if not os.path.isfile(makefile):
        print(f"ERRO: {makefile} nao existe", file=sys.stderr)
        return False

    with open(makefile, "r", encoding="utf-8") as handle:
        content = handle.read()

    if "subdir-y += khaje" in content:
        return False

    addition = f"\n{SUBDIR_MARKER}\nsubdir-y += khaje\n"
    if not dry_run:
        with open(makefile, "a", encoding="utf-8") as handle:
            handle.write(addition)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", required=True,
                        help="raiz da árvore do kernel (após aplicar a série de patches)")
    parser.add_argument("--check", action="store_true",
                        help="apenas relata o que seria feito, sem alterar a árvore")
    args = parser.parse_args()

    kernel_tree = os.path.abspath(args.kernel_tree)
    if not os.path.isdir(kernel_tree):
        print(f"ERRO: arvore de kernel inexistente: {kernel_tree}", file=sys.stderr)
        return 2

    copied, renamed = stage_sources(kernel_tree, args.check)
    makefiles = stage_makefiles(kernel_tree, args.check)
    added = register_subdir(kernel_tree, args.check)

    print(f"fontes DTS copiadas: {len(copied)}")
    for src, dst in copied:
        print(f"  {src} -> {dst}")
    if renamed:
        print("overlays renomeados para .dtso:")
        for src, dst in renamed:
            print(f"  {src} -> {dst}")
    print(f"Makefiles em estilo kernel copiados: {len(makefiles)}")
    for path in makefiles:
        print(f"  {path}")
    print("subdir-y += khaje registrado" if added else "subdir-y += khaje ja presente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
