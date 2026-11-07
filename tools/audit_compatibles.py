#!/usr/bin/env python3
"""Cruza os compatibles dos drivers da serie com os nos do DTS.

Duas perguntas que nem dtbs_check nem o build respondem:

1. Driver adicionado que nenhum no instancia. Compila, entra no
   Image, e nunca roda - o trabalho de port vira codigo morto. (Nem
   sempre e' erro: driver de subdevice criado por outro driver nao
   tem nó; ver --permitidos.)

2. Entrada de tabela indexada por `of_machine_get_match_data()` ou
   `soc_device_match()` que nao casa com a raiz do DTS. Base do
   problema real do `qcom_ubwc_configs`: a tabela e' consultada com o
   compatible da **raiz**, nao com o do bloco.

Uso:
  tools/audit_compatibles.py
  tools/audit_compatibles.py --tree /tmp/kernel-verify.XXXX --verboso
"""

import argparse
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# drivers que existem sem nó proprio: sao criados por outro driver
# (subdevice) ou casam por tabela de maquina, nao por no de DT.
SEM_NO_PROPRIO = {
    "qcom,khaje-debugcc": "debug clock controller, criado pelo clk driver",
    "qcom,khaje": "chave de tabela de máquina (ubwc_config), não nó",
}


def compatibles_de_drivers(diretorio):
    saida = {}
    for arq in sorted(glob.glob(os.path.join(diretorio, "*.patch"))):
        atual = None
        for linha in open(arq, encoding="utf-8", errors="replace"):
            m = re.match(r"\+\+\+ b/(.*\.c)$", linha.rstrip("\n"))
            if m:
                atual = m.group(1)
                continue
            if not linha.startswith("+") or not atual:
                continue
            for c in re.findall(r'\.compatible\s*=\s*"([^"]+)"', linha):
                saida.setdefault(c, set()).add(
                    (os.path.basename(arq), atual))
    return saida


def compatibles_do_dts(arvore):
    presentes = set()
    raiz = None
    padroes = ["arch/arm64/boot/dts/qcom/*.dts",
               "arch/arm64/boot/dts/qcom/*.dtsi"]
    arquivos = []
    for padrao in padroes:
        arquivos += glob.glob(os.path.join(arvore, padrao))
    for arq in arquivos:
        texto = open(arq, encoding="utf-8", errors="replace").read()
        for grupo in re.findall(r'compatible = ((?:"[^"]+"\s*,?\s*)+);',
                                texto):
            presentes |= set(re.findall(r'"([^"]+)"', grupo))
        if arq.endswith(".dts") and raiz is None:
            m = re.search(r"^\tcompatible = ((?:\"[^\"]+\"\s*,?\s*)+);",
                          texto, re.M)
            if m:
                raiz = (os.path.basename(arq),
                        re.findall(r'"([^"]+)"', m.group(1)))
    return presentes, raiz, arquivos


def entradas_de_tabela_de_maquina(diretorio):
    """compatibles em tabelas que o kernel consulta pela raiz."""
    achados = {}
    for arq in sorted(glob.glob(os.path.join(diretorio, "*.patch"))):
        atual = None
        for linha in open(arq, encoding="utf-8", errors="replace"):
            m = re.match(r"\+\+\+ b/(.*)$", linha.rstrip("\n"))
            if m:
                atual = m.group(1)
                continue
            if not linha.startswith("+") or not atual:
                continue
            # ubwc_config.c e' indexado por of_machine_get_match_data();
            # socinfo/qcom_ubwc sao as tabelas de maquina conhecidas.
            if "ubwc" not in atual and "socinfo" not in atual:
                continue
            for c in re.findall(r'\.compatible\s*=\s*"([^"]+)"', linha):
                achados.setdefault(c, set()).add(os.path.basename(arq))
    return achados


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patches",
                    default=os.path.join(RAIZ, "patches-6.18"))
    ap.add_argument("--tree", default=None,
                    help="arvore com a serie aplicada (default: o repo)")
    ap.add_argument("--verboso", action="store_true")
    args = ap.parse_args(argv)

    arvore = args.tree
    if not arvore:
        # a serie vive em patches; o DTS so' existe na arvore aplicada,
        # que tools/verify_series.sh --keep deixa em /tmp
        candidatos = sorted(glob.glob("/tmp/kernel-verify.*"),
                            key=os.path.getmtime, reverse=True)
        arvore = candidatos[0] if candidatos else RAIZ
        if candidatos:
            print("arvore: %s (use --tree para escolher)" % arvore)
    drivers = compatibles_de_drivers(args.patches)
    presentes, raiz, arquivos = compatibles_do_dts(arvore)
    if not arquivos:
        print("erro: nenhum DTS em %s" % arvore)
        return 2

    problemas = 0

    print("== drivers da serie sem nó no DTS ==")
    for c in sorted(drivers):
        if c in presentes:
            continue
        if c in SEM_NO_PROPRIO:
            if args.verboso:
                print("   [ok] %-30s %s" % (c, SEM_NO_PROPRIO[c]))
            continue
        problemas += 1
        print("   %-30s %s" % (c, sorted(drivers[c])[0][0]))
    if not problemas:
        print("   nenhum")

    print("\n== tabela de maquina (raiz do DTS) ==")
    if not raiz:
        print("   aviso: raiz do DTS nao encontrada")
    else:
        nome_no, lista = raiz
        print("   raiz %s: %s" % (nome_no, ", ".join(lista)))
        entradas = entradas_de_tabela_de_maquina(args.patches)
        if not entradas:
            print("   nenhuma entrada adicionada pela serie")
        else:
            casam = [c for c in entradas if c in lista]
            if casam:
                print("   casa(m): %s" % ", ".join(sorted(casam)))
            else:
                # tabelas costumam ter varias chaves para o mesmo dado
                # (nome interno e nome comercial); basta uma casar
                problemas += 1
                print("   NENHUMA entrada casa com a raiz: %s"
                      % ", ".join("%s (%s)" % (c, ", ".join(sorted(p)))
                                  for c, p in sorted(entradas.items())))

    if problemas:
        print("\n%d problema(s)" % problemas)
        return 1
    print("\nOK: compatibles coerentes entre serie e DTS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
