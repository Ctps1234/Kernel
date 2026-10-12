#!/usr/bin/env python3
"""Converte um overlay decompilado (saida de tools/decompile_fdt.py --plugin)
em um .dtso com referencias simbolicas, sem adivinhar quais celulas sao phandles.

Usa apenas as tabelas que o proprio dtc gera para plugins:

* ``__fixups__``: label externo (definido na base) -> ``caminho:propriedade:offset``
  em bytes. Cada celula apontada, que hoje vale 0xffffffff, vira ``&label``.
* ``__local_fixups__``: caminho/propriedade -> indices de celula que contem um
  phandle local ao overlay. O valor da celula e resolvido pelo ``phandle`` do no
  correspondente e, quando existe, pelo label de ``__symbols__`` do overlay.
  Sem label, usa-se referencia por caminho ``&{/...}``.

Os nos ``__symbols__``, ``__fixups__`` e ``__local_fixups__`` sao removidos e os
``phandle`` literais tambem, pois o dtc os regenera ao compilar com ``-@``.

Uso:
    python3 tools/symbolize_overlay.py INPUT.dtso --output OUTPUT.dtso

A validacao (dtc, fdtoverlay, comparacao com o FDT ativo) acontece no workflow
de GitHub Actions; este script nao depende de dtc.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

NODE_OPEN = re.compile(r"^\s*([^\s=;{}]+)\s*\{\s*$")
NODE_CLOSE = re.compile(r"^\s*\};\s*$")
PROP_VALUE = re.compile(r"^\s*([^\s=;{}]+)\s*=\s*(.*?);\s*$")
PROP_FLAG = re.compile(r"^\s*([^\s=;{}]+);\s*$")
CELL_GROUP = re.compile(r"<([^<>]*)>")
INTERNAL_NODES = {"__symbols__", "__fixups__", "__local_fixups__"}


@dataclass
class Prop:
    name: str
    value: str | None  # None para propriedade vazia


@dataclass
class Node:
    name: str
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    label: str | None = None  # label definido para referencias locais do overlay

    def child(self, name: str) -> "Node | None":
        for c in self.children:
            if c.name == name:
                return c
        return None

    def prop(self, name: str) -> Prop | None:
        for p in self.props:
            if p.name == name:
                return p
        return None

    def path(self) -> str:
        if self.parent is None:
            return "/"
        parts = []
        n: Node | None = self
        while n is not None and n.parent is not None:
            parts.append(n.name)
            n = n.parent
        return "/" + "/".join(reversed(parts))


def parse(text: str) -> Node:
    root = Node("/")
    stack = [root]
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith(("/*", "*", "//", "/dts-v1/", "/plugin/")):
            continue
        m = NODE_OPEN.match(line)
        if m and m.group(1) == "/" and len(stack) == 1:
            # O "/ {" de topo e a propria raiz sintetica.
            stack.append(root)
            continue
        if m:
            node = Node(m.group(1), parent=stack[-1])
            stack[-1].children.append(node)
            stack.append(node)
            continue
        if NODE_CLOSE.match(line):
            stack.pop()
            continue
        m = PROP_VALUE.match(line)
        if m:
            stack[-1].props.append(Prop(m.group(1), m.group(2)))
            continue
        m = PROP_FLAG.match(line)
        if m:
            stack[-1].props.append(Prop(m.group(1), None))
            continue
        raise ValueError(f"linha nao reconhecida: {raw!r}")
    if len(stack) != 1:
        raise ValueError("chaves desbalanceadas no DTS de entrada")
    return root


def cells_of(value: str) -> list[str]:
    """Achata grupos <...> em uma lista de celulas (strings)."""
    cells: list[str] = []
    for group in CELL_GROUP.findall(value):
        cells.extend(group.split())
    return cells


def render_cells(original: str, cells: list[str]) -> str:
    """Remonta o valor preservando a divisao em grupos <...>."""
    out = []
    idx = 0
    for group in CELL_GROUP.findall(original):
        n = len(group.split())
        out.append("<" + " ".join(cells[idx : idx + n]) + ">")
        idx += n
    if idx != len(cells):
        raise ValueError("contagem de celulas inconsistente")
    return ", ".join(out)


def resolve_path(root: Node, path: str) -> Node:
    node = root
    for part in path.strip("/").split("/"):
        if not part:
            continue
        nxt = node.child(part)
        if nxt is None:
            raise KeyError(f"no nao encontrado: {path}")
        node = nxt
    return node


def parse_string_list(value: str) -> list[str]:
    return re.findall(r'"([^"]*)"', value)


def convert(text: str) -> str:
    root = parse(text)

    fixups_node = root.child("__fixups__")
    local_node = root.child("__local_fixups__")
    symbols_node = root.child("__symbols__")
    if fixups_node is None or local_node is None or symbols_node is None:
        raise ValueError("overlay sem __symbols__/__fixups__/__local_fixups__")

    # label -> caminho (overlay)
    overlay_symbols: dict[str, str] = {}
    for p in symbols_node.props:
        for s in parse_string_list(p.value or ""):
            overlay_symbols[p.name] = s
    path_to_label = {v: k for k, v in overlay_symbols.items()}

    # 1) Referencias externas: __fixups__
    external_hits = 0
    for p in fixups_node.props:
        label = p.name
        for entry in parse_string_list(p.value or ""):
            path, prop_name, offset = entry.rsplit(":", 2)
            target = resolve_path(root, path)
            prop = target.prop(prop_name)
            if prop is None or prop.value is None:
                raise ValueError(f"propriedade ausente em fixup: {entry}")
            cells = cells_of(prop.value)
            idx = int(offset) // 4
            if cells[idx].lower() != "0xffffffff":
                raise ValueError(f"fixup em celula que nao e 0xffffffff: {entry} = {cells[idx]}")
            cells[idx] = f"&{label}"
            prop.value = render_cells(prop.value, cells)
            external_hits += 1

    # Mapa phandle -> no (somente nos do proprio overlay)
    phandle_map: dict[int, Node] = {}

    def collect(node: Node) -> None:
        for p in node.props:
            if p.name == "phandle" and p.value:
                phandle_map[int(cells_of(p.value)[0], 0)] = node
        for c in node.children:
            collect(c)

    collect(root)

    # 2) Referencias internas: __local_fixups__
    local_hits = 0
    local_by_label = 0
    local_by_path = 0

    def walk_local(lnode: Node, prefix: list[str]) -> None:
        nonlocal local_hits, local_by_label, local_by_path
        for p in lnode.props:
            if p.value is None:
                continue
            target_node = resolve_path(root, "/" + "/".join(prefix)) if prefix else root
            prop = target_node.prop(p.name)
            if prop is None or prop.value is None:
                raise ValueError(f"propriedade local ausente: /{'/'.join(prefix)}:{p.name}")
            cells = cells_of(prop.value)
            for off_str in cells_of(p.value):
                # __local_fixups__ guarda offsets em bytes dentro da propriedade.
                idx = int(off_str, 0) // 4
                ref = int(cells[idx], 0)
                node = phandle_map.get(ref)
                if node is None:
                    raise ValueError(f"phandle local {ref} sem no em /{'/'.join(prefix)}:{p.name}")
                label = path_to_label.get(node.path())
                if label is not None:
                    # Sem definir o label no no alvo, o dtc trataria &label como
                    # referencia externa (base), e o overlay nao aplicaria.
                    node.label = label
                    cells[idx] = f"&{label}"
                    local_by_label += 1
                else:
                    cells[idx] = f"&{{{node.path()}}}"
                    local_by_path += 1
                local_hits += 1
            prop.value = render_cells(prop.value, cells)
        for c in lnode.children:
            walk_local(c, prefix + [c.name])

    walk_local(local_node, [])

    # 3) Remove nos gerados e phandles literais.
    root.children = [c for c in root.children if c.name not in INTERNAL_NODES]

    def strip_phandles(node: Node) -> None:
        node.props = [p for p in node.props if p.name != "phandle"]
        for c in node.children:
            strip_phandles(c)

    strip_phandles(root)

    source_sha = hashlib.sha256(text.encode()).hexdigest()
    header = [
        "/dts-v1/;",
        "/plugin/;",
        "/*",
        " * Gerado por tools/symbolize_overlay.py a partir de um overlay decompilado.",
        f" * Entrada SHA-256 (texto): {source_sha}",
        f" * Referencias externas convertidas: {external_hits}; internas: {local_hits}",
        f" * (label: {local_by_label}, caminho: {local_by_path}).",
        " * Nao revisado por upstream; validar com dtc -@ e fdtoverlay antes de qualquer uso.",
        " */",
        "",
    ]
    body: list[str] = []

    def emit(node: Node, depth: int) -> None:
        ind = "    " * depth
        lbl = f"{node.label}: " if node.label else ""
        if node.parent is None:
            body.append("/ {")
        else:
            body.append(f"{ind}{lbl}{node.name} {{")
        for p in node.props:
            if p.value is None:
                body.append(f"{ind}    {p.name};")
            else:
                body.append(f"{ind}    {p.name} = {p.value};")
        for c in node.children:
            emit(c, depth + 1)
        body.append(f"{ind}}};")

    emit(root, 0)
    return "\n".join(header + body) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    text = args.input.read_text(encoding="utf-8")
    out = convert(text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(out, encoding="utf-8")
    print(f"ok: {args.output} ({out.count(chr(10))} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
