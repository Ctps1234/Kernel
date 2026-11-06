#!/usr/bin/env python3
"""Decompila um FDT (dtb) para texto DTS sem depender do `dtc`.

Usado para ler os DTs aplicados no aparelho (dumps do firmware) e as
entradas do dtbo sem precisar do device-tree-compiler no sandbox. A
saida e proposital e intimamente parecida com `dtc -I dtb -O dts`:
propriedades de texto viram strings, o resto vira celulas hexadecimais
quando o tamanho e multiplo de 4, e bytes crus no formato `[xx yy]`.

Uso:
  tools/fdt_dump.py arquivo.dtb                 # tudo em stdout
  tools/fdt_dump.py arquivo.dtb --grep ufs      # so nos interessantes
  tools/fdt_dump.py arquivo.dtb --list          # so caminhos dos nos
"""

import argparse
import struct
import sys

FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9

HDR = struct.Struct(">10I")


class Node:
    __slots__ = ("name", "props", "children", "parent")

    def __init__(self, name, parent=None):
        self.name = name
        self.props = []
        self.children = []
        self.parent = parent

    def path(self):
        if self.parent is None:
            return "/"
        partes = []
        no = self
        while no.parent is not None:
            partes.append(no.name)
            no = no.parent
        return "/" + "/".join(reversed(partes))


def parse(fdt):
    (_magic, total, off_struct, off_strings, _rsv, _ver, _lcv,
     _cpu, _sstr, _sdt) = HDR.unpack_from(fdt, 0)
    if total > len(fdt):
        raise ValueError("cabecalho diz %d bytes, arquivo tem %d"
                         % (total, len(fdt)))
    pos = off_struct
    raiz = None
    atual = None
    while pos < len(fdt):
        (tok,) = struct.unpack_from(">I", fdt, pos)
        pos += 4
        if tok == FDT_BEGIN_NODE:
            fim = fdt.index(b"\0", pos)
            nome = fdt[pos:fim].decode("utf-8", "replace")
            pos = (fim + 4) & ~3
            no = Node(nome, atual)
            if atual is None:
                raiz = no
            else:
                atual.children.append(no)
            atual = no
        elif tok == FDT_END_NODE:
            atual = atual.parent
        elif tok == FDT_PROP:
            tamanho, nome_off = struct.unpack_from(">II", fdt, pos)
            pos += 8
            valor = bytes(fdt[pos:pos + tamanho])
            pos = (pos + tamanho + 3) & ~3
            # nome da propriedade: buscar na tabela de strings
            inicio = off_strings + nome_off
            fim = fdt.index(b"\0", inicio)
            nome_prop = fdt[inicio:fim].decode("utf-8", "replace")
            atual.props.append((nome_prop, valor))
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise ValueError("token inesperado %d em 0x%x" % (tok, pos - 4))
    return raiz


def _e_texto(valor):
    if not valor or valor[-1] != 0:
        return None
    corpo = valor[:-1]
    if not corpo:
        return ""
    # NUL interno separa strings numa lista ("a", "b")
    if all(b == 0 or 32 <= b < 127 or b in (9, 10) for b in corpo):
        return valor.decode("utf-8", "replace")
    return None


def _ambiguo_como_texto(valor):
    """Valor alinhado a 4 bytes com <= 2 caracteres e' mais util como
    celulas (`qcom,pmic-id = <0x2d 0x0 0x0 0x0>`, nao `"-"`)."""
    if len(valor) % 4 != 0:
        return False
    corpo = valor.rstrip(b"\0")
    return len(corpo) <= 2


def fmt_valor(valor):
    texto = None if _ambiguo_como_texto(valor) else _e_texto(valor)
    if texto is not None:
        # dtc imprime listas de strings como "a", "b"
        partes = [t for t in texto.split("\0") if t]
        if not partes:
            return '""'
        return ", ".join('"%s"' % t.replace('"', '\\"') for t in partes)
    if len(valor) % 4 == 0 and len(valor) > 0:
        celulas = struct.unpack(">%dI" % (len(valor) // 4), valor)
        return "<%s>" % " ".join("0x%x" % c for c in celulas)
    return "[%s]" % " ".join("%02x" % b for b in valor)


def dump(no, saida, nivel=0):
    indent = "\t" * nivel
    if no.parent is None:
        saida.write("/dts-v1/;\n\n")
        cabeca = "/ {"
    else:
        cabeca = "%s%s {" % (indent, no.name)
    saida.write(cabeca + "\n")
    for nome, valor in no.props:
        saida.write("%s\t%s = %s;\n"
                    % (indent, nome, fmt_valor(valor)))
    for filho in no.children:
        saida.write("\n")
        dump(filho, saida, nivel + 1)
    saida.write("%s};\n" % indent)


def percorrer(no):
    yield no
    for filho in no.children:
        yield from percorrer(filho)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dtb")
    ap.add_argument("--grep", default=None,
                    help="so nos cujo caminho casa com esta substring")
    ap.add_argument("--list", action="store_true",
                    help="lista apenas os caminhos dos nos")
    args = ap.parse_args(argv)

    with open(args.dtb, "rb") as fp:
        dados = fp.read()
    raiz = parse(dados)
    if raiz is None:
        print("FDT sem raiz", file=sys.stderr)
        return 1

    if args.list:
        for no in percorrer(raiz):
            print(no.path())
        return 0

    if args.grep:
        alvo = args.grep.lower()
        for no in percorrer(raiz):
            if alvo in no.path().lower():
                print("@ %s (%d props, %d filhos)"
                      % (no.path(), len(no.props), len(no.children)))
                for nome, valor in no.props:
                    print("    %s = %s;" % (nome, fmt_valor(valor)))
                print()
        return 0

    dump(raiz, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:  # ex.: `| head`
        sys.stdout = None
        sys.exit(0)
