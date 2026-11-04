#!/usr/bin/env python3
"""Injeta qcom,msm-id/qcom,board-id na raiz de um DTB compilado.

O bootloader Qualcomm (ABL) seleciona o FDT base dentro da regiao DTB
do vendor_boot casando `qcom,msm-id` (e `qcom,board-id`) da raiz de
cada FDT com a plataforma. O DTB mainline do topaz nao tem essas
propriedades (e nao deve ter: sao convencao do empacotamento vendor,
nao do device tree upstream), entao o repack as injeta no binario,
copiando os valores exatos do FDT stock substituido.

A cirurgia e minima e verificada: insere os registros PROP logo apos
o nome do no raiz no bloco struct, anexa os nomes que faltarem no
bloco de strings (sem mover os offsets existentes) e recalcula apenas
totalsize/off_dt_strings/size_dt_struct/size_dt_strings do cabecalho.
Ao final, percorre a arvore inteira dos dois FDTs e exige que
caminhos e propriedades sejam identicos, exceto as injetadas.

Uso:
  tools/fdt_inject_ids.py --dtb sm6225-xiaomi-topaz.dtb \
      --vendor-boot vendor_boot_b.img --index 1 --out topaz-ids.dtb
"""

import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from bootimg import VendorBootImage, read, write, sha256  # noqa: E402
from empty_overlay import fdt_root_props  # noqa: E402

FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9

HDR = struct.Struct(">10I")


def _align4(value):
    return (value + 3) & ~3


def walk(fdt):
    """Resumo da arvore: lista (caminho, tuple ordenado de props)."""
    (_magic, _total, off_struct, off_strings, _rsv, _ver, _lcv,
     _cpu, _sstr, _sdt) = HDR.unpack_from(fdt, 0)
    out = []
    path = []
    props = None
    pos = off_struct
    while pos < len(fdt):
        (tok,) = struct.unpack_from(">I", fdt, pos)
        pos += 4
        if tok == FDT_BEGIN_NODE:
            end = fdt.index(b"\0", pos)
            nome = fdt[pos:end].decode("utf-8", "replace")
            pos = _align4(end + 1)
            path.append(nome)
            props = []
            out.append(("/".join(path) or "/", props))
        elif tok == FDT_END_NODE:
            path.pop()
            props = None
        elif tok == FDT_PROP:
            size, nameoff = struct.unpack_from(">II", fdt, pos)
            pos += 8
            end = fdt.index(b"\0", off_strings + nameoff)
            nome = fdt[off_strings + nameoff:end].decode("utf-8", "replace")
            valor = bytes(fdt[pos:pos + size])
            pos = _align4(pos + size)
            if props is not None:
                props.append((nome, valor))
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise ValueError("token FDT inesperado: %d" % tok)
    return [(caminho, tuple(lista)) for caminho, lista in out]


def inject(fdt, novas):
    """novas: lista [(nome, bytes)] a inserir na raiz (se ausente)."""
    (magic, _total, off_struct, off_strings, off_rsv, ver, lcv, cpu,
     size_strings, size_struct) = HDR.unpack_from(fdt, 0)
    if magic != 0xD00DFEED:
        raise ValueError("magic FDT invalido")
    existentes = {nome for nome, _ in fdt_root_props(fdt)}
    novas = [(n, v) for n, v in novas if n not in existentes]
    if not novas:
        return fdt, []

    struct_blk = bytearray(fdt[off_struct:off_struct + size_struct])
    strings_blk = bytearray(fdt[off_strings:off_strings + size_strings])

    # ponto de insercao: logo apos BEGIN_NODE da raiz + nome (alinhado)
    (tok,) = struct.unpack_from(">I", struct_blk, 0)
    if tok != FDT_BEGIN_NODE:
        raise ValueError("bloco struct nao comeca com o no raiz")
    end = struct_blk.index(b"\0", 4)
    pos = _align4(end + 1)

    insercao = bytearray()
    for nome, valor in novas:
        nome_b = nome.encode("utf-8") + b"\0"
        nameoff = strings_blk.find(nome_b)
        # so aceita match no inicio de uma string do bloco
        while nameoff > 0 and strings_blk[nameoff - 1] != 0:
            nameoff = strings_blk.find(nome_b, nameoff + 1)
        if nameoff < 0:
            nameoff = len(strings_blk)
            strings_blk += nome_b
        insercao += struct.pack(">III", FDT_PROP, len(valor), nameoff)
        insercao += bytes(valor) + b"\0" * ((-len(valor)) % 4)

    struct_blk[pos:pos] = insercao
    new_off_strings = off_struct + len(struct_blk)
    total = new_off_strings + len(strings_blk)
    header = HDR.pack(magic, total, off_struct, new_off_strings, off_rsv,
                      ver, lcv, cpu, len(strings_blk), len(struct_blk))
    meio = fdt[40:off_struct]  # rsvmap e padding, preservados
    return header + meio + bytes(struct_blk) + bytes(strings_blk), novas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dtb", required=True, help="nosso DTB compilado")
    parser.add_argument("--vendor-boot", required=True,
                        help="vendor_boot original (fonte dos IDs stock)")
    parser.add_argument("--index", type=int, default=1,
                        help="FDT fonte dos IDs (padrao 1, dtb_idx do topaz)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    vb = VendorBootImage(read(args.vendor_boot))
    off, size = vb.fdts[args.index]
    stock = dict(fdt_root_props(vb.data[off:off + size]))
    ids = []
    for nome in ("qcom,msm-id", "qcom,board-id"):
        if nome not in stock:
            raise ValueError("FDT stock sem %s na raiz" % nome)
        ids.append((nome, stock[nome]))

    original = read(args.dtb)
    resultado, injetadas = inject(original, ids)

    # verificacao: arvore identica, exceto as props injetadas na raiz
    arv_o = dict(walk(original))
    arv_n = dict(walk(resultado))
    if set(arv_o) != set(arv_n):
        raise ValueError("conjunto de nos mudou")
    for caminho in arv_o:
        po = list(dict(arv_o[caminho]).items())
        pn = list(dict(arv_n[caminho]).items())
        if caminho == "/":
            pn = [(n, v) for n, v in pn if n not in dict(injetadas)]
        if po != pn:
            raise ValueError("props divergem em %s" % caminho)

    write(args.out, resultado)
    print("injetadas na raiz: %s"
          % ", ".join("%s=%s" % (n, v.hex()) for n, v in injetadas))
    print("dtb: %s (%d -> %d bytes, sha256 %s)"
          % (args.out, len(original), len(resultado), sha256(resultado)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
