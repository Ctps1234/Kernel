#!/usr/bin/env python3
"""Decompile an FDT to a DTS reference using only the Python standard library.

The generated source is a hardware snapshot, not a reviewed upstream DTS. By
default, volatile /chosen boot properties and properties with common per-device
identity names are omitted. Review the output before sharing or attempting to
boot it.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path

from fdt_inventory import FDT_MAGIC, Node, parse_fdt

VOLATILE_CHOSEN = {
    "bootargs",
    "kaslr-seed",
    "rng-seed",
    "linux,initrd-start",
    "linux,initrd-end",
}
SENSITIVE_PROPERTY_NAMES = {
    "serial-number",
    "serial_number",
    "serialno",
    "mac-address",
    "local-mac-address",
    "wifi-mac-address",
    "wlan-mac-address",
    "bluetooth-mac-address",
    "imei",
}


def memreserve_entries(blob: bytes) -> list[tuple[int, int]]:
    if len(blob) < 40:
        return []
    header = struct.unpack_from(">10I", blob, 0)
    magic, total_size, _off_struct, _off_strings, off_reserve = header[:5]
    if magic != FDT_MAGIC or off_reserve + 16 > min(total_size, len(blob)):
        return []

    result: list[tuple[int, int]] = []
    offset = off_reserve
    while offset + 16 <= min(total_size, len(blob)):
        address, size = struct.unpack_from(">QQ", blob, offset)
        offset += 16
        if address == 0 and size == 0:
            break
        result.append((address, size))
    return result


def quote_dts_string(raw: bytes) -> str:
    value = raw.decode("utf-8", "replace")
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{value}"'


def property_value(raw: bytes) -> str:
    if not raw:
        return ""

    # Preserve FDT string lists as DTS strings where practical. Numeric cells
    # and arbitrary binary properties retain the same bytes when emitted below.
    if raw.endswith(b"\0"):
        parts = raw[:-1].split(b"\0")
        try:
            decoded = [part.decode("utf-8") for part in parts]
        except UnicodeDecodeError:
            decoded = []
        if decoded and all(part and all(char.isprintable() or char == "\t" for char in part)
                           for part in decoded):
            return ", ".join(quote_dts_string(part.encode("utf-8")) for part in decoded)

    if len(raw) % 4 == 0:
        cells = struct.unpack(f">{len(raw) // 4}I", raw)
        return "<" + " ".join(f"0x{cell:08x}" for cell in cells) + ">"

    return "[" + " ".join(f"{byte:02x}" for byte in raw) + "]"


def sanitize(root: Node) -> list[tuple[str, str]]:
    removed: list[tuple[str, str]] = []
    for node in root.walk():
        for name in list(node.props):
            lower = name.lower()
            is_dynamic = node.path == "/chosen" and name in VOLATILE_CHOSEN
            if is_dynamic or lower in SENSITIVE_PROPERTY_NAMES:
                del node.props[name]
                removed.append((node.path, name))
    return removed


def emit_node(node: Node, depth: int = 0) -> list[str]:
    indent = "    " * depth
    name = node.name if node.parent is not None else "/"
    lines = [f"{indent}{name} {{"]
    child_indent = "    " * (depth + 1)

    for prop_name, raw in node.props.items():
        value = property_value(raw)
        if value:
            lines.append(f"{child_indent}{prop_name} = {value};")
        else:
            lines.append(f"{child_indent}{prop_name};")

    for child in node.children:
        lines.extend(emit_node(child, depth + 1))

    lines.append(f"{indent}}};")
    return lines


def render(root: Node, reservations: list[tuple[int, int]], source_hash: str,
           stripped: list[tuple[str, str]], plugin: bool) -> str:
    lines = ["/dts-v1/;"]
    if plugin:
        lines.append("/plugin/;")
    lines.extend([
        "/*",
        " * Generated FDT snapshot for reference; not an upstream-reviewed DTS.",
        f" * Source SHA-256: {source_hash}",
        " * Volatile /chosen and common identity properties were filtered.",
        " * Validate bindings and hardware data before any boot use.",
        f" * Filtered properties: {len(stripped)}.",
        " */",
        "",
    ])
    for address, size in reservations:
        lines.append(f"/memreserve/ 0x{address:x} 0x{size:x};")
    if reservations:
        lines.append("")
    lines.extend(emit_node(root))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dtb", type=Path, help="input raw flattened device tree")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output DTS reference")
    parser.add_argument("--plugin", action="store_true",
                        help="include the /plugin/; directive for an overlay reference")
    args = parser.parse_args()

    try:
        blob = args.dtb.read_bytes()
        root, _meta = parse_fdt(blob)
        reservations = memreserve_entries(blob)
        source_hash = hashlib.sha256(blob).hexdigest()
        stripped = sanitize(root)
        text = render(root, reservations, source_hash, stripped, args.plugin)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    except (OSError, ValueError, struct.error) as exc:
        print(f"decompile_fdt: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {args.output} ({len(text)} bytes); filtered {len(stripped)} properties")
    for path, name in stripped:
        print(f"  filtered {path}:{name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
