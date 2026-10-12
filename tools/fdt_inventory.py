#!/usr/bin/env python3
"""Print a privacy-conscious inventory of a flattened device tree (DTB).

Only node paths, compatibles, status and the root board IDs are emitted; raw
register values, serials, MAC addresses, calibration blobs and other property
payloads are deliberately omitted.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9

# Keep the default report focused on the device-specific/bring-up interfaces.
INTERESTING = (
    "khaje",
    "bengal",
    "ufshc",
    "ufs-phy",
    "kgsl",
    "sde",
    "dsi",
    "mdss",
    "cam-",
    "cci",
    "vidc",
    "venus",
    "focaltech",
    "goodix",
    "synaptics",
    "novatek",
    "fpc,",
    "xiaomi-touch",
    "pinctrl",
    "interconnect",
)


@dataclass
class Node:
    name: str
    parent: Node | None = None
    props: dict[str, bytes] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)

    @property
    def path(self) -> str:
        if self.parent is None:
            return "/"
        prefix = self.parent.path.rstrip("/")
        return f"{prefix}/{self.name}"

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children:
            yield from child.walk()

    def strings(self, key: str) -> list[str]:
        raw = self.props.get(key)
        if raw is None:
            return []
        return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]

    def words(self, key: str) -> list[int]:
        raw = self.props.get(key)
        if raw is None or len(raw) % 4:
            return []
        return list(struct.unpack(f">{len(raw) // 4}I", raw))


def align4(value: int) -> int:
    return (value + 3) & ~3


def parse_fdt(blob: bytes) -> tuple[Node, dict[str, int]]:
    if len(blob) < 40:
        raise ValueError("input is too small to contain an FDT header")
    header = struct.unpack_from(">10I", blob, 0)
    (magic, total_size, off_struct, off_strings, _off_mem_rsvmap, version,
     last_comp_version, _boot_cpuid_phys, size_strings, size_struct) = header
    if magic != FDT_MAGIC:
        raise ValueError(f"bad FDT magic 0x{magic:08x}")
    if total_size > len(blob) or total_size < 40:
        raise ValueError(f"invalid FDT totalsize {total_size} for {len(blob)} input bytes")
    if version < 16 or last_comp_version > version:
        raise ValueError(f"unsupported FDT version tuple {version}/{last_comp_version}")
    if off_struct + size_struct > total_size or off_strings + size_strings > total_size:
        raise ValueError("FDT structure or strings block extends past totalsize")

    strings = blob[off_strings:off_strings + size_strings]
    struct_end = off_struct + size_struct
    pos = off_struct
    stack: list[Node] = []
    root: Node | None = None

    def read_cstring(start: int, limit: int) -> tuple[bytes, int]:
        end = blob.find(b"\0", start, limit)
        if end < 0:
            raise ValueError("unterminated string in FDT structure block")
        return blob[start:end], end + 1

    while pos + 4 <= struct_end:
        token = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if token == FDT_BEGIN_NODE:
            name_raw, pos = read_cstring(pos, struct_end)
            pos = align4(pos)
            parent = stack[-1] if stack else None
            node = Node(name_raw.decode("utf-8", "replace"), parent)
            if parent is None:
                if root is not None:
                    raise ValueError("FDT contains more than one root node")
                root = node
            else:
                parent.children.append(node)
            stack.append(node)
        elif token == FDT_END_NODE:
            if not stack:
                raise ValueError("unbalanced FDT_END_NODE")
            stack.pop()
        elif token == FDT_PROP:
            if not stack or pos + 8 > struct_end:
                raise ValueError("property token outside a node or truncated")
            length, name_offset = struct.unpack_from(">II", blob, pos)
            pos += 8
            if name_offset >= len(strings):
                raise ValueError(f"property name offset {name_offset} is out of range")
            name_raw, _ = read_cstring(off_strings + name_offset, off_strings + size_strings)
            if pos + length > struct_end:
                raise ValueError("property value extends past the FDT structure block")
            stack[-1].props[name_raw.decode("utf-8", "replace")] = blob[pos:pos + length]
            pos = align4(pos + length)
        elif token == FDT_NOP:
            continue
        elif token == FDT_END:
            break
        else:
            raise ValueError(f"unknown FDT structure token 0x{token:08x} at 0x{pos - 4:x}")

    if root is None or stack:
        raise ValueError("FDT structure block ended with an incomplete tree")
    return root, {
        "totalsize": total_size,
        "version": version,
        "last_comp_version": last_comp_version,
        "node_count": sum(1 for node in root.walk()),
    }


def summarize(root: Node, meta: dict[str, int], show_all: bool) -> dict[str, object]:
    selected: list[dict[str, object]] = []
    for node in root.walk():
        compatible = node.strings("compatible")
        if not compatible:
            continue
        joined = " ".join(compatible).lower()
        if not show_all and not any(term in (joined + " " + node.path.lower()) for term in INTERESTING):
            continue
        status_values = node.strings("status")
        selected.append({
            "path": node.path,
            "compatible": compatible,
            "status": status_values[0] if status_values else "(implicit)",
        })

    return {
        "fdt": meta,
        "root": {
            "model": root.strings("model"),
            "compatible": root.strings("compatible"),
            "qcom_msm_id": [f"0x{x:08x}" for x in root.words("qcom,msm-id")],
            "qcom_board_id": [f"0x{x:08x}" for x in root.words("qcom,board-id")],
        },
        "compatible_nodes": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dtb", type=Path, help="path to a raw flattened device tree blob")
    parser.add_argument("--all", action="store_true", help="show every node with a compatible property")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a compact text report")
    args = parser.parse_args()

    try:
        blob = args.dtb.read_bytes()
        root, meta = parse_fdt(blob)
        result = summarize(root, meta, args.all)
    except (OSError, ValueError) as exc:
        print(f"fdt_inventory: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    print(f"FDT v{meta['version']} | {meta['totalsize']} bytes | {meta['node_count']} nodes")
    print("Model: " + (", ".join(result["root"]["model"]) or "(none)"))
    print("Compatible: " + (", ".join(result["root"]["compatible"]) or "(none)"))
    for key in ("qcom_msm_id", "qcom_board_id"):
        values = result["root"][key]
        if values:
            print(f"{key}: " + " ".join(values))
    print("\nSelected compatible nodes:")
    for item in result["compatible_nodes"]:
        print(f"- {item['path']} [{item['status']}]")
        print("  " + ", ".join(item["compatible"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
