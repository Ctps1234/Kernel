#!/usr/bin/env python3
"""Confere os rails RPM-SMD da serie contra o FDT do aparelho.

O `qcom,init-voltage` de um rail e' o que o RPM aplica no boot, e a
maioria dos drivers (PHY USB, codec, BT, SD) so' faz enable/disable -
ninguem chama `regulator_set_voltage()` em runtime. Errar esse valor
no DTS nao gera erro, log nem deferral: o periferico simplesmente
recebe a tensao errada. Por isso a comparacao e' contra o FDT do
aparelho, nunca contra o downstream de outro SoC da familia.

Le dois DTS de referencia (default: as duas referencias do repo) e a
serie de patches, e compara min/init/max de cada rail.

Uso:
  tools/audit_regulators.py
  tools/audit_regulators.py --referencia a.dts --referencia b.dts
  tools/audit_regulators.py --verboso        # lista rail por rail
"""

import argparse
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_PADRAO = [
    "device-tree/reference/topaz-live-reference.dts",
    "device-tree/reference/khaje-base-reference.dts",
]
PROPS = ("regulator-min-microvolt", "qcom,init-voltage",
         "regulator-max-microvolt")


def _inteiro(texto):
    return int(texto, 16) if texto.startswith("0x") else int(texto)


def le_dts(caminho):
    """rail -> (min, init, max) a partir de um DTS/DTSI textual."""
    texto = open(caminho, encoding="utf-8", errors="replace").read()
    saida = {}
    for m in re.finditer(r"\n\s*regulator-(l\d+|s\d+|bob|vs\d) \{\n(.*?)\n\s*\};",
                         texto, re.S):
        nome, corpo = m.group(1), m.group(2)
        valores = []
        for prop in PROPS:
            mm = re.search(prop + r"\s*=\s*<(0x[0-9a-fA-F]+|\d+)>", corpo)
            valores.append(_inteiro(mm.group(1)) if mm else None)
        saida[nome] = tuple(valores)
    return saida


def le_serie(diretorio):
    """rail -> lista de (min, init, max, arquivo) dos patches."""
    saida = {}
    for arq in sorted(glob.glob(os.path.join(diretorio, "*.patch"))):
        # patches de binding trazem exemplos de YAML com rails que nao
        # existem no DTS de producao; comparar so' confunde a auditoria
        if "dt-bindings" in os.path.basename(arq):
            continue
        linhas = open(arq, encoding="utf-8", errors="replace").read().split("\n")
        for i, linha in enumerate(linhas):
            m = re.match(r"\+.*?\bregulator-(l\d+|s\d+|bob) \{\s*$", linha)
            if not m:
                continue
            corpo = []
            for k in range(i + 1, min(len(linhas), i + 45)):
                if re.match(r"\+\s*\};", linhas[k]):
                    break
                corpo.append(linhas[k].lstrip("+"))
            corpo = "\n".join(corpo)
            # so' nos interessa o rail RPM-SMD (o binding tem exemplos)
            if "rpm-smd-regulator" not in corpo:
                continue
            valores = []
            for prop in PROPS:
                mm = re.search(prop + r"\s*=\s*<(\d+)>", corpo)
                valores.append(int(mm.group(1)) if mm else None)
            saida.setdefault(m.group(1), []).append(
                tuple(valores) + (os.path.basename(arq),))
    return saida


def formata(trio):
    return "/".join("-" if v is None else str(v) for v in trio)


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--referencia", action="append", default=None,
                    help="DTS do aparelho (pode repetir; default: as duas "
                         "referencias do repo)")
    ap.add_argument("--patches", default=os.path.join(RAIZ, "patches-6.18"))
    ap.add_argument("--verboso", action="store_true",
                    help="mostra todos os rails, nao so' os divergentes")
    args = ap.parse_args(argv)

    refs = args.referencia or [os.path.join(RAIZ, p) for p in REF_PADRAO]
    fontes = []
    for caminho in refs:
        if not os.path.exists(caminho):
            print("aviso: referencia ausente: %s" % caminho)
            continue
        fontes.append((os.path.basename(caminho), le_dts(caminho)))
    if not fontes:
        print("erro: nenhuma referencia legivel")
        return 2

    serie = le_serie(args.patches)
    if not serie:
        print("erro: nenhum rail RPM-SMD encontrado em %s" % args.patches)
        return 2

    problemas = 0
    declarados = set()
    for rail in sorted(serie, key=lambda x: (x[0], int(x[1:]))):
        for entrada in serie[rail]:
            trio, arquivo = entrada[:3], entrada[3]
            declarados.add(rail)
            diverge = []
            for nome, tabela in fontes:
                esperado = tabela.get(rail)
                if esperado is None:
                    continue
                if esperado != trio:
                    diverge.append("%s %s" % (nome, formata(esperado)))
            if diverge:
                problemas += 1
                print("%-5s serie %-26s != %s" % (rail, formata(trio),
                                                  ' ; '.join(diverge)))
                print("      arquivo: %s" % arquivo)
            elif args.verboso:
                print("%-5s %-26s identico (%s)" % (rail, formata(trio),
                                                    ", ".join(n for n, _ in fontes)))

    # rails que o aparelho usa e a serie nao declara
    for nome, tabela in fontes:
        ausentes = sorted(set(tabela) - declarados)
        if ausentes:
            print("\nso' em %s (sem consumidor na serie): %s"
                  % (nome, ", ".join(ausentes)))

    if problemas:
        print("\nFALHA: %d rail(s) divergente(s)" % problemas)
        return 1
    print("\nOK: %d rail(s) conferido(s), todos iguais ao FDT do aparelho"
          % sum(len(v) for v in serie.values()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
