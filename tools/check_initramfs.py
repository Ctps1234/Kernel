#!/usr/bin/env python3
"""Validate the minimal initramfs archive and its AArch64 static binaries."""

import os
import stat
import struct
import sys


class CpioError(ValueError):
    pass


def parse_newc(data):
    entries = {}
    offset = 0
    while offset + 110 <= len(data):
        if data[offset:offset + 6] != b"070701":
            raise CpioError("magic newc invalido no offset %d" % offset)
        try:
            fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                      for i in range(13)]
        except ValueError as exc:
            raise CpioError("campo newc invalido no offset %d" % offset) from exc
        (ino, mode, uid, gid, nlink, mtime, filesize, devmajor, devminor,
         rdevmajor, rdevminor, namesize, check) = fields
        if not namesize:
            raise CpioError("namesize zero no offset %d" % offset)
        name_start = offset + 110
        name_end = name_start + namesize
        if name_end > len(data) or data[name_end - 1] != 0:
            raise CpioError("nome truncado/sem NUL no offset %d" % offset)
        name = data[name_start:name_end - 1].decode("utf-8", "surrogateescape")
        data_start = (name_end + 3) & ~3
        data_end = data_start + filesize
        if data_end > len(data):
            raise CpioError("conteudo truncado para %r" % name)
        next_offset = (data_end + 3) & ~3
        if name == "TRAILER!!!":
            if filesize != 0:
                raise CpioError("TRAILER!!! deve ser vazio")
            if next_offset != len(data):
                raise CpioError("bytes excedentes apos TRAILER!!!")
            return entries
        if name.startswith("/") or name == ".." or name.startswith("../") or "/../" in name:
            raise CpioError("caminho inseguro no cpio: %r" % name)
        if name in entries:
            raise CpioError("entrada cpio duplicada: %r" % name)
        entries[name] = {
            "ino": ino, "mode": mode, "uid": uid, "gid": gid, "nlink": nlink,
            "mtime": mtime, "filesize": filesize, "devmajor": devmajor,
            "devminor": devminor, "rdevmajor": rdevmajor,
            "rdevminor": rdevminor, "data": data[data_start:data_end],
        }
        offset = next_offset
    raise CpioError("TRAILER!!! ausente ou arquivo truncado")


def assert_static_aarch64_elf(name, data):
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise CpioError("%s nao e ELF64" % name)
    if data[4] != 2 or data[5] != 1:
        raise CpioError("%s nao e ELF64 little-endian" % name)
    machine = struct.unpack_from("<H", data, 18)[0]
    if machine != 183:
        raise CpioError("%s e_machine=%d, esperado AArch64 (183)" % (name, machine))
    elf_type = struct.unpack_from("<H", data, 16)[0]
    if elf_type not in (2, 3):
        raise CpioError("%s tem tipo ELF inesperado: %d" % (name, elf_type))
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]
    if phentsize < 56 or phoff + phentsize * phnum > len(data):
        raise CpioError("tabela de program headers invalida em %s" % name)
    for i in range(phnum):
        p_type = struct.unpack_from("<I", data, phoff + i * phentsize)[0]
        if p_type == 3:  # PT_INTERP: dynamic loader required
            raise CpioError("%s tem PT_INTERP; o binario nao e estatico" % name)


def validate(path):
    with open(path, "rb") as handle:
        data = handle.read()
    entries = parse_newc(data)
    required = ("init", "bin", "bin/busybox", "bin/sh", "dev", "dev/console",
                "dev/null", "proc", "sys", "tmp")
    missing = [name for name in required if name not in entries]
    if missing:
        raise CpioError("faltam entradas obrigatorias: %s" % ", ".join(missing))

    init = entries["init"]
    if not stat.S_ISREG(init["mode"]) or not (init["mode"] & 0o111):
        raise CpioError("/init nao e um arquivo executavel")
    assert_static_aarch64_elf("/init", init["data"])

    busybox = entries["bin/busybox"]
    if not stat.S_ISREG(busybox["mode"]) or not (busybox["mode"] & 0o111):
        raise CpioError("/bin/busybox nao e um arquivo executavel")
    assert_static_aarch64_elf("/bin/busybox", busybox["data"])

    shell = entries["bin/sh"]
    if not stat.S_ISLNK(shell["mode"]) or shell["data"] != b"busybox":
        raise CpioError("/bin/sh deve ser um link simbolico para busybox")

    console = entries["dev/console"]
    if not stat.S_ISCHR(console["mode"]) or (console["rdevmajor"], console["rdevminor"]) != (5, 1):
        raise CpioError("/dev/console deve ser char 5:1")
    null = entries["dev/null"]
    if not stat.S_ISCHR(null["mode"]) or (null["rdevmajor"], null["rdevminor"]) != (1, 3):
        raise CpioError("/dev/null deve ser char 1:3")

    if len(data) > 16 * 1024 * 1024:
        raise CpioError("ramdisk inesperadamente grande: %d bytes" % len(data))
    print("initramfs validada: %d bytes, %d entradas" % (len(data), len(entries)))
    print("  /init: ELF AArch64 estatico (%d bytes)" % init["filesize"])
    print("  /bin/busybox: ELF AArch64 estatico (%d bytes)" % busybox["filesize"])
    print("  /dev/console: char 5:1; /dev/null: char 1:3")
    return 0


def main(argv=None):
    path = argv[1] if argv and len(argv) > 1 else None
    if path is None:
        print("uso: %s initramfs.cpio" % os.path.basename(sys.argv[0]), file=sys.stderr)
        return 2
    try:
        return validate(path)
    except (OSError, CpioError) as exc:
        print("initramfs invalida: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
