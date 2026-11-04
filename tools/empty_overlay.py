#!/usr/bin/env python3
"""Neutraliza uma entrada de overlay do dtbo com um FDT vazio.

Uso no port 6.18: o bootloader (ABL) aplica a entrada indicada por
`androidboot.dtbo_idx` (51 no topaz) sobre o FDT base escolhido por
`dtb_idx` (1). Como o nosso DTB mainline ja e o board completo
(SoC + placa num FDT so), o overlay downstream -- cheio de fragmentos
que referenciam labels do DT vendor -- nao pode ser aplicado sobre
ele. Esta ferramenta substitui o FDT da entrada por um FDT minimo
bem-formado que preserva apenas as propriedades da raiz do overlay
original (model/compatible/qcom,msm-id/qcom,board-id, usadas pelo
bootloader para selecionar a entrada) e nao tem nenhum fragmento:
aplicar esse overlay e um no-op.

Uso:
  tools/empty_overlay.py --dtbo dtbo_b.img --index 51 --out dtbo-vazio.img
  tools/empty_overlay.py --dtbo dtbo_b.img --index 51 --out-fdt vazio.dtbo
     (so emite o FDT sintetizado, sem remontar a imagem)
"""

import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from bootimg import DtboImage, read, write, sha256  # noqa: E402

FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9


def _align4(value):
    return (value + 3) & ~3


def fdt_root_props(fdt):
    """Le as propriedades do no raiz de um FDT (lista nome->bytes)."""
    if struct.unpack_from(">I", fdt, 0)[0] != 0xD00DFEED:
        raise ValueError("magic FDT invalido")
    off_struct, off_strings = struct.unpack_from(">II", fdt, 8)

    def prop_name(nameoff):
        end = fdt.index(b"\0", off_strings + nameoff)
        return fdt[off_strings + nameoff:end].decode("utf-8", "replace")

    props = []
    pos = off_struct
    depth = 0
    while pos < len(fdt):
        (tok,) = struct.unpack_from(">I", fdt, pos)
        pos += 4
        if tok == FDT_BEGIN_NODE:
            end = fdt.index(b"\0", pos)
            pos = _align4(end + 1)
            depth += 1
            if depth > 1:
                break  # primeiro filho: props da raiz ja foram lidas
        elif tok == FDT_END_NODE:
            depth -= 1
            if depth == 0:
                break
        elif tok == FDT_PROP:
            size, nameoff = struct.unpack_from(">II", fdt, pos)
            pos += 8
            valor = bytes(fdt[pos:pos + size])
            pos = _align4(pos + size)
            if depth == 1:
                props.append((prop_name(nameoff), valor))
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise ValueError("token FDT inesperado: %d" % tok)
    return props


def build_empty_fdt(props):
    """Constroi um FDT (v17) so com o no raiz e as props dadas."""
    strings = b""
    offsets = {}
    for nome, _ in props:
        if nome not in offsets:
            offsets[nome] = len(strings)
            strings += nome.encode("utf-8") + b"\0"

    def pad(data):
        return data + b"\0" * ((-len(data)) % 4)

    struct_blk = struct.pack(">I", FDT_BEGIN_NODE) + pad(b"\0")
    for nome, valor in props:
        struct_blk += struct.pack(">III", FDT_PROP, len(valor), offsets[nome])
        struct_blk += pad(bytes(valor))
    struct_blk += struct.pack(">II", FDT_END_NODE, FDT_END)

    rsvmap = struct.pack(">QQ", 0, 0)
    off_rsvmap = 40
    off_struct = off_rsvmap + len(rsvmap)
    off_strings = off_struct + len(struct_blk)
    total = off_strings + len(strings)
    header = struct.pack(
        ">10I", 0xD00DFEED, total, off_struct, off_strings, off_rsvmap,
        17, 16, 0, len(strings), len(struct_blk))
    return header + rsvmap + struct_blk + strings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dtbo", required=True, help="imagem dtbo original")
    parser.add_argument("--index", type=int, required=True,
                        help="entrada a neutralizar (51 no topaz)")
    parser.add_argument("--out", help="imagem dtbo de saida")
    parser.add_argument("--out-fdt", help="so grava o FDT sintetizado")
    args = parser.parse_args(argv)
    if not args.out and not args.out_fdt:
        parser.error("informe --out e/ou --out-fdt")

    data = read(args.dtbo)
    img = DtboImage(data)
    if args.index < 0 or args.index >= img.entry_count:
        raise ValueError("indice fora do intervalo")
    off, size = img.fdts[args.index]
    props = fdt_root_props(data[off:off + size])
    sintetizado = build_empty_fdt(props)

    # auto-conferencia: o FDT sintetizado tem as mesmas props da raiz
    if fdt_root_props(sintetizado) != props:
        raise ValueError("FDT sintetizado nao reproduz as props da raiz")

    print("entrada %d: FDT original de %d bytes; props da raiz preservadas:"
          % (args.index, size))
    for nome, valor in props:
        print("  %s = %r" % (nome, valor[:64]))
    print("FDT vazio sintetizado: %d bytes" % len(sintetizado))

    if args.out_fdt:
        write(args.out_fdt, sintetizado)
        print("fdt: %s (sha256 %s)" % (args.out_fdt, sha256(sintetizado)))
    if args.out:
        out, info = img.replace_entry(args.index, sintetizado)
        write(args.out, out)
        print("imagem: %s (%d bytes, sha256 %s)"
              % (args.out, len(out), sha256(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
