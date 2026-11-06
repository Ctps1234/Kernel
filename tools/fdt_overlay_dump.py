#!/usr/bin/env python3
"""Decompila um overlay (.dtbo) mostrando os phandles por nome.

Um dtbo sozinho e ilegivel: `target = <0xffffffff>` e
`gpios = <0xffffffff 0x18 0x0>` nao dizem nada. O libfdt resolve isso
com `__fixups__`, onde cada simbolo externo lista as posicoes
(`/fragment@12:target:0`) em que seu phandle foi deixado como
placeholder. Este script faz o mesmo caminho: troca cada celula
marcada por `&simbolo`, usando o `__symbols__` do DT base para saber
para onde o simbolo aponta.

Nao aplica o overlay (nao gera um dtb mesclado): so torna o conteudo
legivel, que e o que interessa para conferir hardware.

Uso:
  tools/fdt_overlay_dump.py board.dtb --base soc.dtb        # DTS anotado
  tools/fdt_overlay_dump.py board.dtb --base soc.dtb --grep touch
"""

import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fdt_dump import parse, percorrer  # noqa: E402


def _achar(raiz, caminho):
    """Navega por um caminho de nomes de no (sem o no raiz)."""
    no = raiz
    for parte in caminho.strip("/").split("/"):
        if not parte:
            continue
        for filho in no.children:
            if filho.name == parte:
                no = filho
                break
        else:
            return None
    return no


def _props(no):
    return {nome: valor for nome, valor in no.props}


def mapa_simbolos(base):
    """nome do simbolo -> caminho no DT base (via __symbols__)."""
    no = _achar(base, "__symbols__")
    if no is None:
        return {}
    saida = {}
    for nome, valor in no.props:
        caminho = valor.rstrip(b"\0").decode("utf-8", "replace")
        saida[nome] = caminho
    return saida


def mapa_fixups(overlay):
    """(caminho, prop, indice) -> nome do simbolo."""
    no = _achar(overlay, "__fixups__")
    if no is None:
        return {}
    saida = {}
    for simbolo, valor in no.props:
        for item in valor.rstrip(b"\0").split(b"\0"):
            if not item:
                continue
            texto = item.decode("utf-8", "replace")
            # formato: "/fragment@12/__overlay__/no:propriedade:indice"
            partes = texto.rsplit(":", 2)
            if len(partes) != 3:
                continue
            caminho, prop, indice = partes
            saida[(caminho, prop, int(indice))] = simbolo
    return saida


def mapa_phandles(overlay):
    """phandle local -> nome do no (para referencias internas)."""
    saida = {}
    for no in percorrer(overlay):
        props = _props(no)
        for chave in ("phandle", "linux,phandle"):
            if chave in props:
                (valor,) = struct.unpack(">I", props[chave][:4])
                saida[valor] = no.name.split("@")[0]
    return saida


def fmt_prop(nome, valor, caminho_no, fixups, phandles, simbolos):
    """Como fdt_dump.fmt_valor, mas resolvendo phandles por nome."""
    from fdt_dump import _e_texto
    texto = _e_texto(valor)
    if texto is not None:
        partes = [t for t in texto.split("\0") if t]
        return ", ".join('"%s"' % t for t in partes) if partes else '""'

    if len(valor) % 4 != 0 or not valor:
        return "[%s]" % " ".join("%02x" % b for b in valor)

    celulas = list(struct.unpack(">%dI" % (len(valor) // 4), valor))
    pedacos = []
    for i, celula in enumerate(celulas):
        simbolo = fixups.get((caminho_no, nome, i))
        if simbolo:
            destino = simbolos.get(simbolo)
            pedacos.append("&%s" % simbolo if destino is None
                           else "&%s /* %s */" % (simbolo, destino))
        elif celula in phandles and celula > 0x100:
            pedacos.append("&%s" % phandles[celula])
        else:
            pedacos.append("0x%x" % celula)
    return "<%s>" % " ".join(pedacos)


def dump(no, caminho, saida, nivel, fixups, phandles, simbolos):
    indent = "\t" * nivel
    if no.parent is None:
        saida.write("/dts-v1/;\n/plugin/;\n\n/ {\n")
    else:
        caminho = (caminho + "/" + no.name) if caminho else "/" + no.name
        saida.write("%s%s {\n" % (indent, no.name))
    for nome, valor in no.props:
        if nivel == 0 and nome.startswith("qcom,") and "id" in nome:
            pass
        saida.write("%s\t%s = %s;\n"
                    % (indent, nome,
                       fmt_prop(nome, valor, caminho or "/", fixups,
                                phandles, simbolos)))
    for filho in no.children:
        if nivel == 0 and filho.name in ("__symbols__", "__fixups__",
                                        "__local_fixups__"):
            continue
        saida.write("\n")
        dump(filho, caminho, saida, nivel + 1, fixups, phandles, simbolos)
    saida.write("%s};\n" % indent)


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("overlay")
    ap.add_argument("--base", default=None,
                    help="DTB base, para resolver os simbolos")
    ap.add_argument("--grep", default=None,
                    help="so nos cujo caminho casa com a substring")
    ap.add_argument("--list", action="store_true",
                    help="lista os fragmentos e seus alvos")
    args = ap.parse_args(argv)

    raiz = parse(open(args.overlay, "rb").read())
    simbolos = {}
    if args.base:
        base = parse(open(args.base, "rb").read())
        simbolos = mapa_simbolos(base)
    fixups = mapa_fixups(raiz)
    phandles = mapa_phandles(raiz)

    if args.list:
        alvos = {}
        for (caminho, prop, _i), simbolo in fixups.items():
            if prop == "target":
                alvos[caminho] = simbolo
        for filho in raiz.children:
            if not filho.name.startswith("fragment"):
                continue
            caminho = "/" + filho.name
            props = _props(filho)
            simbolo = alvos.get(caminho)
            if simbolo is None and "target-path" in props:
                simbolo = props["target-path"].rstrip(b"\0").decode()
            destino = simbolos.get(simbolo, simbolo) if simbolo else "?"
            overlay = _achar(filho, "__overlay__")
            nos = ", ".join(c.name for c in overlay.children) \
                if overlay is not None else ""
            print("%-14s -> %-55s %s" % (filho.name, destino, nos[:70]))
        return 0

    if args.grep:
        alvo = args.grep.lower()
        alvos = {}
        for (caminho, prop, _i), simbolo in fixups.items():
            if prop == "target":
                alvos[caminho] = simbolo
        for filho in raiz.children:
            overlay = _achar(filho, "__overlay__")
            if overlay is None:
                continue
            destino = simbolos.get(alvos.get("/" + filho.name, ""), "?")
            for no in percorrer(overlay):
                if alvo not in no.name.lower() and alvo not in destino.lower():
                    continue
                print("@ %s  (fragmento %s -> %s)"
                      % (no.name, filho.name, destino))
                for nome, valor in no.props:
                    print("    %s = %s;" % (nome, fmt_prop(
                        nome, valor, "/" + filho.name + "/__overlay__",
                        fixups, phandles, simbolos)))
                print()
        return 0

    dump(raiz, "", sys.stdout, 0, fixups, phandles, simbolos)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
