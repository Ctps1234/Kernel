#!/usr/bin/env python3
"""Match and optionally extract a Qualcomm base DTB and Android DTBO overlay.

The input image data is never copied into the repository unless the caller
explicitly chooses an output directory there. The default mode only prints
metadata for the requested Qualcomm MSM/board IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from fdt_inventory import FDT_MAGIC, parse_fdt

DTBO_MAGIC = 0xD7B7AB1E
VENDOR_BOOT_MAGIC = b"VNDRBOOT"
VENDOR_BOOT_V4_HEADER_SIZE = 2128


def align(value: int, multiple: int) -> int:
    return ((value + multiple - 1) // multiple) * multiple


def read_vendor_boot(path: Path) -> tuple[bytes, list[dict[str, object]]]:
    image = path.read_bytes()
    if len(image) < VENDOR_BOOT_V4_HEADER_SIZE or image[:8] != VENDOR_BOOT_MAGIC:
        raise ValueError("not an Android vendor_boot image")
    version = struct.unpack_from("<I", image, 8)[0]
    page_size = struct.unpack_from("<I", image, 12)[0]
    ramdisk_size = struct.unpack_from("<I", image, 24)[0]
    if version != 4:
        raise ValueError(f"expected vendor_boot v4, found version {version}")
    if page_size < 512 or page_size & (page_size - 1):
        raise ValueError(f"invalid vendor_boot page size {page_size}")
    header_size = struct.unpack_from("<I", image, 2096)[0]
    dtb_size = struct.unpack_from("<I", image, 2100)[0]
    if header_size < VENDOR_BOOT_V4_HEADER_SIZE:
        raise ValueError(f"vendor_boot v4 header is too short: {header_size}")
    dtb_offset = page_size + align(ramdisk_size, page_size)
    if dtb_offset + dtb_size > len(image):
        raise ValueError("vendor_boot DTB area extends past end of image")
    area = image[dtb_offset:dtb_offset + dtb_size]

    dtbs: list[dict[str, object]] = []
    pos = 0
    while pos < len(area):
        if pos + 8 > len(area) or struct.unpack_from(">I", area, pos)[0] != FDT_MAGIC:
            raise ValueError(f"expected concatenated FDT at vendor_boot DTB offset 0x{pos:x}")
        total_size = struct.unpack_from(">I", area, pos + 4)[0]
        if total_size < 40 or pos + total_size > len(area):
            raise ValueError(f"invalid FDT size {total_size} at vendor_boot DTB offset 0x{pos:x}")
        blob = area[pos:pos + total_size]
        root, meta = parse_fdt(blob)
        msm_id = root.words("qcom,msm-id")
        board_id = root.words("qcom,board-id")
        dtbs.append({
            "index": len(dtbs),
            "offset": dtb_offset + pos,
            "size": total_size,
            "model": root.strings("model"),
            "compatible": root.strings("compatible"),
            "msm_id": msm_id[0] if msm_id else None,
            "msm_subtype": msm_id[1] if len(msm_id) > 1 else None,
            "board_id": board_id[0] if board_id else None,
            "blob": blob,
            "fdt_meta": meta,
        })
        pos += total_size
    return image, dtbs


def read_dtbo(path: Path) -> tuple[bytes, list[dict[str, object]]]:
    image = path.read_bytes()
    if len(image) < 32:
        raise ValueError("DTBO image is too small to contain its table header")
    magic, total_size, header_size, entry_size, count, entries_offset, page_size, version = struct.unpack_from(">8I", image, 0)
    if magic != DTBO_MAGIC:
        raise ValueError(f"bad DTBO table magic 0x{magic:08x}")
    if header_size < 32 or entry_size < 32:
        raise ValueError("DTBO header or entry size is too small")
    if total_size > len(image) or entries_offset + entry_size * count > total_size:
        raise ValueError("DTBO table extends past the declared image size")

    overlays: list[dict[str, object]] = []
    for index in range(count):
        entry_off = entries_offset + index * entry_size
        dt_size, dt_offset, table_id, rev, *_custom = struct.unpack_from(">8I", image, entry_off)
        if dt_offset + dt_size > total_size or dt_size < 40:
            raise ValueError(f"invalid DTBO entry {index} range")
        blob = image[dt_offset:dt_offset + dt_size]
        if struct.unpack_from(">I", blob, 0)[0] != FDT_MAGIC:
            raise ValueError(f"DTBO entry {index} does not begin with an FDT")
        root, meta = parse_fdt(blob)
        msm_id = root.words("qcom,msm-id")
        board_id = root.words("qcom,board-id")
        overlays.append({
            "index": index,
            "offset": dt_offset,
            "size": dt_size,
            "table_id": table_id,
            "revision": rev,
            "model": root.strings("model"),
            "compatible": root.strings("compatible"),
            "msm_id": msm_id[0] if msm_id else None,
            "msm_subtype": msm_id[1] if len(msm_id) > 1 else None,
            "board_id": board_id[0] if board_id else None,
            "blob": blob,
            "fdt_meta": meta,
        })
    return image, overlays


def describe(item: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in item.items() if key not in ("blob", "fdt_meta")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendor_boot", type=Path, help="Android vendor_boot v4 image")
    parser.add_argument("dtbo", type=Path, help="Android DTBO table image")
    parser.add_argument("--msm-id", type=lambda x: int(x, 0), required=True, help="Qualcomm MSM ID, e.g. 0x206")
    parser.add_argument("--board-id", type=lambda x: int(x, 0), required=True, help="Qualcomm board ID, e.g. 0x30022")
    parser.add_argument("--out-dir", type=Path, help="optional destination for the matching base DTB and overlay")
    args = parser.parse_args()

    try:
        _vendor_image, dtbs = read_vendor_boot(args.vendor_boot)
        _dtbo_image, overlays = read_dtbo(args.dtbo)
        base_matches = [x for x in dtbs if x["msm_id"] == args.msm_id]
        overlay_matches = [x for x in overlays if x["msm_id"] == args.msm_id and x["board_id"] == args.board_id]
        report: dict[str, object] = {
            "requested": {"msm_id": f"0x{args.msm_id:08x}", "board_id": f"0x{args.board_id:08x}"},
            "base_candidates": [describe(x) for x in base_matches],
            "overlay_candidates": [describe(x) for x in overlay_matches],
        }
        if not base_matches or not overlay_matches:
            raise ValueError(f"no matching pair found (base matches={len(base_matches)}, overlay matches={len(overlay_matches)})")
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            extracted = []
            for base in base_matches:
                name = f"base-dtb-{base['index']}.dtb"
                target = args.out_dir / name
                target.write_bytes(base["blob"])
                extracted.append({"path": str(target), "sha256": hashlib.sha256(base["blob"]).hexdigest()})
            for overlay in overlay_matches:
                name = f"overlay-entry-{overlay['index']}.dtbo"
                target = args.out_dir / name
                target.write_bytes(overlay["blob"])
                extracted.append({"path": str(target), "sha256": hashlib.sha256(overlay["blob"]).hexdigest()})
            report["extracted"] = extracted
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        print()
    except (OSError, ValueError, struct.error) as exc:
        print(f"extract_android_dt: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
