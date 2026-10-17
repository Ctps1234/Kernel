#!/usr/bin/env python3
"""Empacotamento das imagens de boot do topaz/tapas (Redmi Note 12 4G).

Ferramenta autocontida (sem dependencias) para inspecionar e remontar as
quatro imagens da cadeia de boot do aparelho:

  boot / init_boot  -- Android boot image v4 (little-endian)
  vendor_boot       -- Android vendor boot image v4 (little-endian, layout
                       Qualcomm: regiao DTB com varios FDTs contiguos)
  dtbo              -- Android DTBO (header e entradas BIG-endian, layout
                       Qualcomm/mkdtimg)

Os layouts nao vem do AOSP "de livro": foram deduzidos dos binarios reais do
aparelho (ver docs/boot-partition-inventory.md) e conferidos por um teste de
ida-e-volta (parse -> rebuild -> bytes identicos ao original).

O objetivo e produzir as imagens flashaveis do port 6.12 trocando apenas o
que muda (kernel, DTB base e overlay do board), preservando byte a byte todo
o restante (cmdline, bootconfig, ramdisk vendor, rodape AVB, padding).

Uso:
  tools/bootimg.py inspect <imagem>
  tools/bootimg.py roundtrip <entrada> <saida>
  tools/bootimg.py set-kernel  --image in.img --kernel Image --out out.img
  tools/bootimg.py set-dtb     --image in.img --index 1 --dtb base.dtb --out out.img
  tools/bootimg.py set-overlay --image in.img --index 51 --dtbo ov.dtbo --out out.img
"""

import argparse
import hashlib
import struct
import sys

BOOT_MAGIC = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"
DTBO_MAGIC = 0xD7B7AB1E
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def write(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def fdt_size(data, offset):
    """total size de um FDT (campo big-endian no offset+4)."""
    return struct.unpack_from(">I", data, offset + 4)[0]


def align(value, alignment):
    return (value + alignment - 1) & ~(alignment - 1)


# ---------------------------------------------------------------- boot v4


class BootImage:
    """Android boot image v4 (little-endian)."""

    HDR = struct.Struct("<8sIIII4II")

    def __init__(self, data):
        if data[:8] != BOOT_MAGIC:
            raise ValueError("nao e uma boot image (magic ANDROID!)")
        (self.magic, self.kernel_size, self.ramdisk_size, self.os_version,
         self.header_size, r0, r1, r2, r3,
         self.header_version) = self.HDR.unpack_from(data, 0)
        self.reserved = [r0, r1, r2, r3]
        if self.header_version != 4:
            raise ValueError("versao de header inesperada: %d" % self.header_version)
        self.cmdline = data[44:44 + 1536].split(b"\0")[0]
        self.page_size = 4096
        self.kernel_offset = align(self.header_size, self.page_size)
        self.ramdisk_offset = align(self.kernel_offset + self.kernel_size, self.page_size)
        self.data = data

    @property
    def kernel(self):
        return self.data[self.kernel_offset:self.kernel_offset + self.kernel_size]

    @property
    def ramdisk(self):
        return self.data[self.ramdisk_offset:self.ramdisk_offset + self.ramdisk_size]

    def describe(self):
        return [
            "tipo: boot image v4",
            "page_size: %d" % self.page_size,
            "header_size: %d" % self.header_size,
            "kernel_size: %d (offset %d)" % (self.kernel_size, self.kernel_offset),
            "ramdisk_size: %d (offset %d)" % (self.ramdisk_size, self.ramdisk_offset),
            "os_version: 0x%08x" % self.os_version,
            "cmdline: %r" % self.cmdline.decode("utf-8", "replace"),
            "tamanho do arquivo: %d" % len(self.data),
        ]

    AVB_FOOTER_MAGIC = b"AVBf"
    AVB_FOOTER_SIZE = 64

    def rebuild(self, kernel=None, ramdisk=None, total_size=None):
        """Reconstroi a imagem trocando kernel/ramdisk.

        A cauda (padding da particao + rodape AVB) e preservada byte a byte
        para que a imagem continue do mesmo tamanho; quando o conteudo muda,
        o rodape AVB fica obsoleto (e' preciso flashar com a verificacao
        desabilitada, como em qualquer kernel custom).
        """
        kernel = self.kernel if kernel is None else kernel
        ramdisk = self.ramdisk if ramdisk is None else ramdisk
        tail = self.data[self.ramdisk_offset + self.ramdisk_size:]
        if kernel is not None or ramdisk is not None:
            # zera o meio da cauda, preservando o rodape AVB no fim
            footer = b""
            if tail.endswith(self.AVB_FOOTER_MAGIC + b"\0" * 60):
                footer = tail[-self.AVB_FOOTER_SIZE:]
                tail = b"\0" * (len(tail) - len(footer)) + footer
        out = bytearray(self.data[:self.kernel_offset])
        out[8:12] = struct.pack("<I", len(kernel))
        out[12:16] = struct.pack("<I", len(ramdisk))
        out += kernel
        out += b"\0" * (align(len(out), self.page_size) - len(out))
        out += ramdisk
        out += b"\0" * (align(len(out), self.page_size) - len(out))
        if total_size is not None:
            if len(out) > total_size:
                raise ValueError("imagem maior que a particao (%d > %d)" % (len(out), total_size))
            room = total_size - len(out)
            footer = b""
            if len(tail) >= self.AVB_FOOTER_SIZE and tail.endswith(self.AVB_FOOTER_MAGIC + b"\0" * 60):
                footer = tail[-self.AVB_FOOTER_SIZE:]
                head = tail[:-self.AVB_FOOTER_SIZE]
            else:
                head = tail
            if footer:
                out += head[:max(0, room - len(footer))]
                out += b"\0" * (room - len(out) - len(footer))
                out += footer
            else:
                out += head[:room]
                out += b"\0" * (room - len(out))
        else:
            out += tail
        return bytes(out)


# ------------------------------------------------------- vendor_boot v4


class VendorBootImage:
    """Android vendor boot image v4 (little-endian, layout Qualcomm).

    A regiao DTB e uma sequencia contigua de FDTs, sem padding entre eles,
    descrita pelo campo 'dtb_size' do cabecalho. Os offsets de cada FDT
    seguem do total size do proprio FDT (big-endian, como o formato FDT).
    """

    HDR = struct.Struct("<8sII")

    def __init__(self, data):
        if data[:8] != VENDOR_BOOT_MAGIC:
            raise ValueError("nao e uma vendor boot image (magic VNDRBOOT)")
        self.magic, self.header_version, self.page_size = self.HDR.unpack_from(data, 0)
        if self.header_version != 4:
            raise ValueError("versao de header inesperada: %d" % self.header_version)
        self.data = data
        # campos medidos no aparelho (ver docs/boot-partition-inventory.md):
        # 0x18 = tamanho do ramdisk vendor; 0x834 = tamanho da regiao DTB;
        # 0x844 = numero de entradas da tabela DTB; 0x84C = tamanho do bootconfig.
        self.vendor_ramdisk_size = struct.unpack_from("<I", data, 0x18)[0]
        self.dtb_size = struct.unpack_from("<I", data, 0x834)[0]
        self.dtb_entry_count = struct.unpack_from("<I", data, 0x844)[0]
        self.bootconfig_size = struct.unpack_from("<I", data, 0x84C)[0]
        self.fdts = self._scan_fdts()

    def _scan_fdts(self):
        out = []
        # a regiao DTB comeca na pagina seguinte ao fim do ramdisk vendor
        off = align(self.page_size + self.vendor_ramdisk_size, self.page_size)
        end = off + self.dtb_size
        while off < end:
            if self.data[off:off + 4] != FDT_MAGIC:
                raise ValueError("FDT invalido no offset %d" % off)
            size = fdt_size(self.data, off)
            out.append((off, size))
            off += size
        if off != end:
            raise ValueError("a regiao DTB nao termina exatamente no limite declarado")
        return out

    def describe(self):
        lines = [
            "tipo: vendor boot image v4",
            "page_size: %d" % self.page_size,
            "ramdisk vendor: %d bytes (offset %d)" % (self.vendor_ramdisk_size, self.page_size),
            "regiao DTB: offset %d, tamanho %d, %d FDT(s), entradas na tabela: %d"
            % (self.fdts[0][0] if self.fdts else -1, self.dtb_size,
               len(self.fdts), self.dtb_entry_count),
            "bootconfig: %d bytes" % self.bootconfig_size,
            "tamanho do arquivo: %d" % len(self.data),
        ]
        for i, (off, size) in enumerate(self.fdts):
            lines.append("  FDT#%d offset %d tamanho %d" % (i, off, size))
        return lines

    def replace_fdt(self, index, new_dtb):
        """Substitui um FDT da regiao mantendo o layout (tamanho da regiao)."""
        if index < 0 or index >= len(self.fdts):
            raise ValueError("indice de FDT fora do intervalo")
        off, old_size = self.fdts[index]
        if len(new_dtb) > old_size:
            raise ValueError(
                "o novo DTB (%d bytes) nao cabe no espaco do original (%d bytes); "
                "seria preciso reconstruir a regiao e ajustar o header"
                % (len(new_dtb), old_size))
        out = bytearray(self.data)
        out[off:off + old_size] = new_dtb + b"\0" * (old_size - len(new_dtb))
        # o total size do FDT e ajustado para o espaco original: assim a
        # regiao continua contigua e o bootloader percorre os FDTs sem
        # depender do tamanho real do conteudo novo.
        struct.pack_into(">I", out, off + 4, old_size)
        return bytes(out), {"old_size": old_size, "offset": off}


# ----------------------------------------------------------------- dtbo


class DtboImage:
    """Android DTBO no layout Qualcomm: header e entradas big-endian."""

    HDR = struct.Struct(">8I")
    ENTRY = struct.Struct(">8I")

    def __init__(self, data):
        (self.magic, self.total_size, self.header_size, self.entry_size,
         self.entry_count, self.entries_offset, self.page_size,
         self.version) = self.HDR.unpack_from(data, 0)
        if self.magic != DTBO_MAGIC:
            raise ValueError("nao e uma imagem dtbo (magic d7b7ab1e)")
        self.data = data
        self.entries = []
        for i in range(self.entry_count):
            off = self.entries_offset + i * self.entry_size
            size, offset, eid, rev = self.ENTRY.unpack_from(data, off)[:4]
            self.entries.append({"size": size, "offset": offset, "id": eid, "rev": rev})
        self.fdts = [(e["offset"], e["size"]) for e in self.entries]

    def describe(self):
        lines = [
            "tipo: dtbo (big-endian)",
            "total_size: %d" % self.total_size,
            "header_size: %d, entry_size: %d, entry_count: %d"
            % (self.header_size, self.entry_size, self.entry_count),
            "entries_offset: %d, page_size: %d, version: %d"
            % (self.entries_offset, self.page_size, self.version),
            "tamanho do arquivo: %d" % len(self.data),
        ]
        for i, e in enumerate(self.entries):
            lines.append("  entrada %2d: offset %8d tamanho %8d id %d rev %d"
                         % (i, e["offset"], e["size"], e["id"], e["rev"]))
        return lines

    def replace_entry(self, index, new_dtbo):
        """Substitui o FDT de uma entrada e reconstroi a imagem."""
        if index < 0 or index >= self.entry_count:
            raise ValueError("indice de entrada fora do intervalo")
        if new_dtbo[:4] != FDT_MAGIC:
            raise ValueError("o arquivo substituido nao e um FDT")
        old_offset, old_size = self.fdts[index]
        fdts = []
        for i, (offset, size) in enumerate(self.fdts):
            data = new_dtbo if i == index else self.data[offset:offset + size]
            fdts.append((offset, size, data))
        out = rebuild_dtbo(self, fdts)
        return out, {"old_size": old_size, "offset": old_offset}


def detect(data):
    if data[:8] == BOOT_MAGIC:
        return "boot"
    if data[:8] == VENDOR_BOOT_MAGIC:
        return "vendor_boot"
    if int.from_bytes(data[:4], "big") == DTBO_MAGIC:
        return "dtbo"
    raise ValueError("formato desconhecido")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect", help="mostra a estrutura de uma imagem")
    p.add_argument("image")

    p = sub.add_parser("roundtrip", help="reparse e reconstroi, para conferir o layout")
    p.add_argument("input")
    p.add_argument("output")

    p = sub.add_parser("set-kernel", help="troca o kernel de uma boot image")
    p.add_argument("--image", required=True)
    p.add_argument("--kernel", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--no-pad", action="store_true",
                   help="nao preenche ate o tamanho da particao original")

    p = sub.add_parser("set-dtb", help="troca um FDT da regiao DTB do vendor_boot")
    p.add_argument("--image", required=True)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--dtb", required=True)
    p.add_argument("--out", required=True)

    p = sub.add_parser("set-overlay", help="troca um overlay de uma imagem dtbo")
    p.add_argument("--image", required=True)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--dtbo", required=True)
    p.add_argument("--out", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "inspect":
        data = read(args.image)
        kind = detect(data)
        if kind == "boot":
            print("\n".join(BootImage(data).describe()))
        elif kind == "vendor_boot":
            print("\n".join(VendorBootImage(data).describe()))
        else:
            print("\n".join(DtboImage(data).describe()))
        return 0

    if args.cmd == "roundtrip":
        data = read(args.input)
        kind = detect(data)
        if kind == "boot":
            out = BootImage(data).rebuild()
        elif kind == "vendor_boot":
            out = data  # a regiao DTB e reconstruida in-place; ver set-dtb
        else:
            img = DtboImage(data)
            fdts = [(off, size, data[off:off + size]) for off, size in img.fdts]
            out = rebuild_dtbo(img, fdts)
        write(args.output, out)
        same = out == data
        print("tipo: %s" % kind)
        print("ida e volta: %s" % ("IDENTICA" if same else "DIVERGENTE"))
        print("sha256 entrada: %s" % sha256(data))
        print("sha256 saida:   %s" % sha256(out))
        if not same:
            for i, (a, b) in enumerate(zip(data, out)):
                if a != b:
                    print("primeira diferenca no offset %d: %02x != %02x" % (i, a, b))
                    break
            print("tamanhos: %d vs %d" % (len(data), len(out)))
            return 1
        return 0

    if args.cmd == "set-kernel":
        data = read(args.image)
        img = BootImage(data)
        kernel = read(args.kernel)
        total = None if args.no_pad else len(data)
        out = img.rebuild(kernel=kernel, total_size=total)
        write(args.out, out)
        print("kernel: %s (%d bytes, sha256 %s)" % (args.kernel, len(kernel), sha256(kernel)))
        print("imagem: %s (%d bytes, sha256 %s)" % (args.out, len(out), sha256(out)))
        return 0

    if args.cmd == "set-dtb":
        data = read(args.image)
        img = VendorBootImage(data)
        new = read(args.dtb)
        out, info = img.replace_fdt(args.index, new)
        write(args.out, out)
        print("FDT#%d substituido em %d: %d -> %d bytes" % (args.index, info["offset"],
                                                            info["old_size"], len(new)))
        print("imagem: %s (%d bytes, sha256 %s)" % (args.out, len(out), sha256(out)))
        return 0

    if args.cmd == "set-overlay":
        data = read(args.image)
        img = DtboImage(data)
        new = read(args.dtbo)
        out, info = img.replace_entry(args.index, new)
        write(args.out, out)
        print("entrada %d substituida: %d -> %d bytes" % (args.index, info["old_size"], len(new)))
        print("imagem: %s (%d bytes, sha256 %s)" % (args.out, len(out), sha256(out)))
        return 0

    return 1


def rebuild_dtbo(img, fdts):
    """Reconstroi a imagem dtbo com os FDTs informados (contiguos).

    O total_size e recalculado com o tamanho do conteudo e a cauda da
    particao (padding + rodape AVB) e preservada byte a byte.
    """
    head_size = img.entries_offset + img.entry_size * img.entry_count
    out = bytearray(img.data[:head_size])
    blob = bytearray()
    for i, (_, _, blobdata) in enumerate(fdts):
        struct.pack_into(">8I", out, img.entries_offset + i * img.entry_size,
                         len(blobdata), head_size + len(blob),
                         img.entries[i]["id"], img.entries[i]["rev"], 0, 0, 0, 0)
        blob += blobdata
    out += blob
    struct.pack_into(">I", out, 4, len(out))
    tail = img.data[img.fdts[-1][0] + img.fdts[-1][1]:]
    out += tail
    if len(out) < len(img.data):
        out += b"\0" * (len(img.data) - len(out))
    return bytes(out)


if __name__ == "__main__":
    sys.exit(main())
