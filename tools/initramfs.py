#!/usr/bin/env python3
"""Build a deterministic, uncompressed cpio-newc initramfs from a directory.

The kernel can consume an uncompressed newc archive directly as the init_boot
ramdisk. File contents and names are preserved; ownership and mtimes are
normalized to root and zero. Character/block devices retain their rdev fields.

Usage:
  tools/initramfs.py <root-directory> <output.cpio> [--gzip]
"""

import argparse
import gzip
import os
import stat
import sys

TRAILER = "TRAILER!!!"


def align4(value):
    return (value + 3) & ~3


def newc_header(ino, mode, uid, gid, nlink, mtime, filesize, devmajor,
                devminor, rdevmajor, rdevminor, namesize, check=0):
    fields = (ino, mode, uid, gid, nlink, mtime, filesize, devmajor,
              devminor, rdevmajor, rdevminor, namesize, check)
    if any(value < 0 or value > 0xFFFFFFFF for value in fields):
        raise ValueError("campo cpio newc fora do intervalo de 32 bits")
    return b"070701" + b"".join(b"%08X" % value for value in fields)


def append_entry(out, ino, name, mode, data=b"", nlink=1,
                 rdevmajor=0, rdevminor=0):
    name = os.fsencode(name)
    out += newc_header(ino, mode, 0, 0, nlink, 0, len(data), 0, 0,
                       rdevmajor, rdevminor, len(name) + 1)
    out += name + b"\0"
    out += b"\0" * (align4(len(out)) - len(out))
    out += data
    out += b"\0" * (align4(len(out)) - len(out))


def build(root):
    root = os.path.abspath(root)
    entries = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
                raise ValueError("caminho fora da raiz: %r" % rel)
            entries.append((rel, full))
    entries.sort(key=lambda item: os.fsencode(item[0]))

    out = bytearray()
    for ino, (rel, full) in enumerate(entries, 1):
        st = os.lstat(full)
        perms = stat.S_IMODE(st.st_mode)
        if stat.S_ISLNK(st.st_mode):
            data = os.fsencode(os.readlink(full))
            append_entry(out, ino, rel, stat.S_IFLNK | perms, data)
        elif stat.S_ISDIR(st.st_mode):
            append_entry(out, ino, rel, stat.S_IFDIR | perms, nlink=2)
        elif stat.S_ISREG(st.st_mode):
            with open(full, "rb") as handle:
                data = handle.read()
            append_entry(out, ino, rel, stat.S_IFREG | perms, data)
        elif stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
            kind = stat.S_IFCHR if stat.S_ISCHR(st.st_mode) else stat.S_IFBLK
            append_entry(out, ino, rel, kind | perms, rdevmajor=os.major(st.st_rdev),
                         rdevminor=os.minor(st.st_rdev))
        elif stat.S_ISFIFO(st.st_mode):
            append_entry(out, ino, rel, stat.S_IFIFO | perms)
        else:
            raise ValueError("tipo de arquivo nao suportado: %s" % rel)

    append_entry(out, 0, TRAILER, 0)
    return bytes(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="diretorio com o conteudo da ramdisk")
    parser.add_argument("output", help="arquivo cpio newc de saida")
    parser.add_argument("--gzip", action="store_true", help="comprime com gzip")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.root):
        print("diretorio inexistente: %s" % args.root, file=sys.stderr)
        return 1

    try:
        blob = build(args.root)
    except (OSError, ValueError) as exc:
        print("erro ao montar initramfs: %s" % exc, file=sys.stderr)
        return 1
    if args.gzip:
        blob = gzip.compress(blob, mtime=0)
    try:
        with open(args.output, "wb") as handle:
            handle.write(blob)
    except OSError as exc:
        print("nao foi possivel gravar %s: %s" % (args.output, exc), file=sys.stderr)
        return 1
    print("%s: %d bytes" % (args.output, len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
