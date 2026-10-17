#!/usr/bin/env python3
"""Compila as device trees de topaz/tapas sem build completo do kernel.

Reproduz a invocacao que o build do kernel usa (scripts/Makefile.dtbs):

    $(HOSTCC) -E -nostdinc -I scripts/dtc/include-prefixes -undef \
              -D__DTS__ -x assembler-with-cpp -o <tmp.dts> <fonte>
    $(DTC) -o <alvo> -b 0 -i <dir da fonte> <flags> <tmp.dts>

e depois aplica os overlays com `fdtoverlay`, como faz o mecanismo de
multi-dtb do kernel.

Requer `dtc` (>= 1.5 para overlays com `&label` de topo) e `fdtoverlay`.
Use `--dtc`/`--fdtoverlay` para apontar para binarios especificos.

Uso:
    tools/build_dts.py --kernel-tree /path/para/basekernel \
        [--output DIR] [--dtc PATH] [--fdtoverlay PATH] [alvo...]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DTS_SUBDIR = os.path.join("arch", "arm64", "boot", "dts", "qcom", "khaje")

# Flags usados pelo build do kernel; as checagens antigas do dtc 1.4 sao
# aceitas via --dtc-flags extras quando o dtc local e mais novo.
BASE_DTC_FLAGS = [
    "-Wno-unique_unit_address",
    "-Wno-unit_address_vs_reg",
    "-Wno-avoid_unnecessary_addr_size",
    "-Wno-alias_paths",
    "-Wno-graph_child_address",
    "-Wno-simple_bus_reg",
]


def run(cmd, **kwargs):
    printable = " ".join(cmd)
    print(f"+ {printable}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def preprocess(kernel_tree, source, tmpdir):
    """Passo de pre-processamento (cpp) igual ao do kernel."""
    out = os.path.join(tmpdir, os.path.basename(source) + ".tmp.dts")
    include_prefixes = os.path.join(kernel_tree, "scripts", "dtc", "include-prefixes")
    run([
        os.environ.get("CC", "gcc"), "-E",
        "-nostdinc", "-I", include_prefixes,
        "-undef", "-D__DTS__", "-x", "assembler-with-cpp",
        "-o", out, source,
    ])
    return out


def compile_dts(kernel_tree, source, output, dtc, extra_flags, symbols):
    tmpdir = tempfile.mkdtemp(prefix="dts-")
    try:
        preprocessed = preprocess(kernel_tree, source, tmpdir)
        flags = list(extra_flags)
        while True:
            cmd = [
                dtc, "-o", output, "-b", "0",
                "-i", os.path.dirname(source),
            ] + flags
            if symbols:
                cmd.append("-@")
            cmd.append(preprocessed)
            print(f"+ {' '.join(cmd)}", flush=True)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stderr.splitlines():
                    print(line)
                return
            # dtc mais antigo nao conhece todas as checagens: remove a flag
            # correspondente e tenta de novo.
            unsupported = None
            for line in result.stderr.splitlines():
                if "Unrecognized check name" in line:
                    unsupported = line.split('"')[1]
                    break
            if unsupported is None:
                for line in result.stderr.splitlines():
                    print(line, file=sys.stderr)
                raise subprocess.CalledProcessError(result.returncode, cmd)
            dropped = f"-Wno-{unsupported}"
            if dropped not in flags:
                for line in result.stderr.splitlines():
                    print(line, file=sys.stderr)
                raise subprocess.CalledProcessError(result.returncode, cmd)
            flags.remove(dropped)
            print(f"  (dtc local nao suporta {dropped}; repetindo sem ela)", flush=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def find_sources(kernel_tree):
    """Mapeia os alvos de device tree do projeto Khaje."""
    root = os.path.join(kernel_tree, DTS_SUBDIR)
    targets = []

    base = os.path.join(root, "khaje-idp-nopmi.dts")
    if os.path.isfile(base):
        targets.append(("khaje-idp-nopmi.dtb", base, True))

    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if not name.endswith(".dtso"):
                continue
            source = os.path.join(dirpath, name)
            rel = os.path.relpath(dirpath, root)
            out = name[:-len(".dtso")] + ".dtbo"
            if rel != ".":
                out = os.path.join(rel, out)
            targets.append((out, source, False))
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", required=True,
                        help="arvore do kernel com as DTS ja staged")
    parser.add_argument("--output", default=None,
                        help="diretorio de saida (padrao: <kernel>/khaje-dtb)")
    parser.add_argument("--dtc", default=os.environ.get("DTC", "dtc"))
    parser.add_argument("--fdtoverlay", default=os.environ.get("FDTOVERLAY", "fdtoverlay"))
    parser.add_argument("--dtc-flag", action="append", default=[],
                        help="flag extra do dtc (repetivel)")
    parser.add_argument("--no-symbols", action="store_true",
                        help="nao compila a base com -@ (sem tabela de simbolos)")
    args = parser.parse_args()

    kernel_tree = os.path.abspath(args.kernel_tree)
    if not os.path.isdir(kernel_tree):
        print(f"ERRO: arvore de kernel inexistente: {kernel_tree}", file=sys.stderr)
        return 2

    output = os.path.abspath(args.output or os.path.join(kernel_tree, "khaje-dtb"))
    os.makedirs(output, exist_ok=True)

    flags = list(BASE_DTC_FLAGS) + list(args.dtc_flag)
    targets = find_sources(kernel_tree)
    if not targets:
        print("ERRO: nenhuma DTS de topaz/tapas encontrada; rode tools/integrate_dts.py",
              file=sys.stderr)
        return 2

    built = []
    for name, source, is_base in targets:
        destination = os.path.join(output, name)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        try:
            compile_dts(kernel_tree, source, destination, args.dtc, flags,
                        symbols=is_base and not args.no_symbols)
            built.append(destination)
        except subprocess.CalledProcessError as error:
            print(f"FALHA ao compilar {name} ({error})", file=sys.stderr)
            return 1

    # Composicao base + overlay (mecanismo de multi-dtb do kernel).
    base_dtb = os.path.join(output, "khaje-idp-nopmi.dtb")
    if os.path.isfile(base_dtb):
        for overlay, composite in (
            ("topaz-khaje-idp-nopmi-overlay.dtbo", "khaje-idp-nopmi-topaz.dtb"),
            ("tapas-khaje-idp-nopmi-overlay.dtbo", "khaje-idp-nopmi-tapas.dtb"),
        ):
            overlay_path = os.path.join(output, overlay)
            if not os.path.isfile(overlay_path):
                continue
            destination = os.path.join(output, composite)
            run([args.fdtoverlay, "-o", destination, "-i", base_dtb, overlay_path])
            built.append(destination)

    print("\nartefatos gerados:")
    for path in built:
        print(f"  {os.path.relpath(path, output)} ({os.path.getsize(path)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
