import os
import stat
import struct
import tempfile
import unittest

from tools import check_initramfs, initramfs


def fake_static_aarch64_elf():
    """Minimal ELF64/AArch64 ET_EXEC header with no dynamic interpreter."""
    ident = b"\x7fELF" + bytes((2, 1, 1, 0)) + b"\0" * 8
    header = struct.pack(
        "<HHIQQQIHHHHHH",
        2,       # ET_EXEC
        183,     # EM_AARCH64
        1,       # EV_CURRENT
        0,       # e_entry
        64,      # e_phoff
        0,       # e_shoff
        0,       # e_flags
        64,      # e_ehsize
        56,      # e_phentsize
        0,       # e_phnum
        0,       # e_shentsize
        0,       # e_shnum
        0,       # e_shstrndx
    )
    return ident + header


class InitramfsTests(unittest.TestCase):
    def test_build_is_deterministic_and_preserves_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "bin"))
            with open(os.path.join(root, "bin", "busybox"), "wb") as handle:
                handle.write(b"test-binary")
            os.chmod(os.path.join(root, "bin", "busybox"), 0o755)
            os.symlink("busybox", os.path.join(root, "bin", "sh"))

            first = initramfs.build(root)
            os.utime(os.path.join(root, "bin", "busybox"), (123, 456))
            second = initramfs.build(root)
            self.assertEqual(first, second)

            entries = check_initramfs.parse_newc(first)
            self.assertEqual(entries["bin/busybox"]["data"], b"test-binary")
            self.assertTrue(stat.S_ISLNK(entries["bin/sh"]["mode"]))
            self.assertEqual(entries["bin/sh"]["data"], b"busybox")

    def test_newc_device_numbers_and_minimal_root_validation(self):
        elf = fake_static_aarch64_elf()
        archive = bytearray()
        entries = [
            ("bin", stat.S_IFDIR | 0o755, b"", 0, 0),
            ("bin/busybox", stat.S_IFREG | 0o755, elf, 0, 0),
            ("bin/sh", stat.S_IFLNK | 0o777, b"busybox", 0, 0),
            ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
            ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
            ("dev/null", stat.S_IFCHR | 0o666, b"", 1, 3),
            ("init", stat.S_IFREG | 0o755, elf, 0, 0),
            ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
            ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
            ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ]
        for ino, (name, mode, data, major, minor) in enumerate(entries, 1):
            initramfs.append_entry(archive, ino, name, mode, data,
                                   rdevmajor=major, rdevminor=minor)
        initramfs.append_entry(archive, 0, initramfs.TRAILER, 0)

        parsed = check_initramfs.parse_newc(bytes(archive))
        self.assertEqual((parsed["dev/console"]["rdevmajor"],
                          parsed["dev/console"]["rdevminor"]), (5, 1))
        self.assertEqual((parsed["dev/null"]["rdevmajor"],
                          parsed["dev/null"]["rdevminor"]), (1, 3))
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(archive)
            handle.flush()
            self.assertEqual(check_initramfs.validate(handle.name), 0)

    def test_rejects_path_traversal(self):
        archive = bytearray()
        initramfs.append_entry(archive, 1, "../outside", stat.S_IFREG | 0o644, b"")
        initramfs.append_entry(archive, 0, initramfs.TRAILER, 0)
        with self.assertRaises(check_initramfs.CpioError):
            check_initramfs.parse_newc(bytes(archive))


if __name__ == "__main__":
    unittest.main()
