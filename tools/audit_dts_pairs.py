#!/usr/bin/env python3
"""Checa pares "*-names / lista" nos DTS, onde dtc e dtbs_check nao olham.

Uma DTS pode passar em `dtbs_check` e mesmo assim ter:

  clocks = <&gcc A>, <&gcc B>;
  clock-names = "core";

O driver pede `core` e `iface`; `iface` nao existe no DT, o probe falha
com -ENOENT e o device nunca sobe. O schema nao compara contagem (sao
duas propriedades separadas), e o dtc nao sabe o que o driver vai pedir.
As vezes o driver ate sobe, com o clock errado em cada posicao.

Aqui a regra e' mecanica: para cada par (propriedade, prop-names) numa
mesma node, o numero de nomes tem que bater com o numero de entradas, e
os nomes nao podem repetir. `pinctrl-N` tem tratamento proprio: para
`pinctrl-names` com N nomes, `pinctrl-0`..`pinctrl-(N-1)` precisam
existir.

Uso:
  tools/audit_dts_pairs.py arquivo.dts [arquivo2.dts ...]
  tools/audit_dts_pairs.py --dir /tmp/kernel-verify.XXXX --dts
"""

import argparse
import glob
import os
import re
import sys

# (propriedade com a lista, propriedade com os nomes)
PARES = [
    ("clocks", "clock-names"),
    ("interrupts", "interrupt-names"),
    ("resets", "reset-names"),
    ("dmas", "dma-names"),
    ("power-domains", "power-domain-names"),
    ("iommus", "iommu-names"),
    ("reg", "reg-names"),
    ("interconnect-names", "interconnects"),
]


def divide_lista(valor):
    """'<&a 1>, <&b 2>' -> ['<&a 1>', '<&b 2>'].

    Respeita <...> e ()... para nao quebrar cell lists com virgula
    dentro de parenteses.
    """
    itens, atual, prof = [], [], 0
    for c in valor:
        if c in "<(":
            prof += 1
        elif c in ">)":
            prof -= 1
        if c == "," and prof == 0:
            itens.append("".join(atual).strip())
            atual = []
            continue
        atual.append(c)
    if "".join(atual).strip():
        itens.append("".join(atual).strip())
    return itens


def conta_entradas(prop, valor):
    if prop in ("clocks", "resets", "dmas", "power-domains", "iommus",
                "interconnects", "reg"):
        return len(divide_lista(valor))
    return len(divide_lista(valor))


def nomes(valor):
    return re.findall(r'"([^"]*)"', valor)


def audita(caminho):
    problemas = []
    with open(caminho, encoding="utf-8", errors="replace") as fh:
        linhas = [l.rstrip("\n") for l in fh]

    # pilha por indentacao: guarda (indent, nome, props)
    pilha = [(-1, {"nome": "/", "props": {}, "linha": 0})]
    for numero, linha in enumerate(linhas, 1):
        s = linha.strip()
        if not s or s.startswith("//"):
            continue
        indent = len(linha) - len(linha.lstrip("\t"))
        while len(pilha) > 1 and indent <= pilha[-1][0]:
            fecha = pilha.pop()[1]
            _checa(caminho, fecha, problemas)
        m = re.match(r"^(\S[^=]*?) \{$", s)
        if m:
            pilha.append((indent, {"nome": m.group(1), "props": {},
                                   "linha": numero, "pai": pilha[-1][1]["nome"]}))
            continue
        m = re.match(r"^(\S[^=]*?) = (.+);$", s)
        if m:
            pilha[-1][1]["props"][m.group(1)] = m.group(2)
    while len(pilha) > 1:
        fecha = pilha.pop()[1]
        _checa(caminho, fecha, problemas)

    # pinctrl-N: precisa de todos os indices
    for numero, linha in enumerate(linhas, 1):
        m = re.match(r'^\s*pinctrl-names = (.+);$', linha)
        if not m:
            continue
        total = len(nomes(m.group(1)))
        bloco = "\n".join(linhas[max(0, numero - 80):numero + 80])
        faltando = [i for i in range(total)
                    if not re.search(r"pinctrl-%d\s*=" % i, bloco)]
        if faltando:
            problemas.append((caminho, numero,
                              "pinctrl-names declara %d estado(s), falta(m) "
                              "pinctrl-%s" % (total,
                                              ", ".join(map(str, faltando)))))
    return problemas


def _checa(caminho, no, problemas):
    props = no["props"]

    # qcom,tlmm-common.yaml: quando `pins` lista qualquer "gpioN", o
    # estado tem de declarar `function` (o `if/then` do binding). Foi
    # exatamente isto que reprovou o dtbs_check do topaz em 2026-11-06
    # num cd-pins sem function.
    # nos "&label { ... }" sao overrides: valem so' as propriedades
    # listadas, o resto vem do no' original (que declara function).
    if "pins" in props and not no["nome"].startswith("&"):
        pinos = re.findall(r'"([^"]+)"', props["pins"])
        if any(p.startswith("gpio") for p in pinos) and "function" not in props:
            problemas.append((caminho, no["linha"],
                              "%s [pins]: estado com pinos gpioN exige "
                              "`function` (qcom,tlmm-common.yaml)"
                              % no["nome"]))

    for prop, prop_nomes in PARES:
        if prop not in props or prop_nomes not in props:
            continue
        entradas = conta_entradas(prop, props[prop])
        lista = nomes(props[prop_nomes])
        if len(lista) != entradas:
            problemas.append((caminho, no["linha"],
                              "%s [%s]: %d entrada(s) vs %d nome(s) em %s"
                              % (no["nome"], prop, entradas, len(lista),
                                 prop_nomes)))
        if len(set(lista)) != len(lista):
            problemas.append((caminho, no["linha"],
                              "%s [%s]: nomes repetidos em %s"
                              % (no["nome"], prop, prop_nomes)))
        if len(lista) != len(set(lista)):
            continue


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="*")
    ap.add_argument("--dir", default=None,
                    help="diretorio da arvore aplicada (busca .dts/.dtsi)")
    args = ap.parse_args(argv)

    alvos = list(args.arquivos)
    if args.dir:
        for padrao in ("*.dts", "*.dtsi"):
            alvos += sorted(glob.glob(os.path.join(args.dir, "**", padrao),
                                      recursive=True))
    alvos = sorted({os.path.abspath(a) for a in alvos if os.path.exists(a)})
    if not alvos:
        print("erro: nenhum arquivo")
        return 2

    total = 0
    for caminho in alvos:
        for arq, linha, msg in audita(caminho):
            total += 1
            print("%s:%d: %s" % (os.path.basename(arq), linha, msg))
    if total:
        print("\n%d inconsistencia(s) em %d arquivo(s)" % (total, len(alvos)))
        return 1
    print("OK: %d arquivo(s), nenhuma inconsistencia de pares"
          % len(alvos))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
