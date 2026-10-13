#!/usr/bin/env python3
"""Gera a DT curada do topaz a partir da conversao mecanica (fase 2).

Entradas (versionadas em device-tree/reference e device-tree/topaz):
  * khaje-base-reference.dts  base decompilada; ``__symbols__`` dá os labels;
  * topaz-overlay.dtso        overlay simbolizado (fragments com ``target = <&label>``);
  * topaz-live-reference.dts  FDT ativo, usado so para verificacao.

Saidas (em --out-dir):
  * khaje.dtsi  subconjunto da base: nos referenciados pelo overlay, mais o fecho
                transitivo por phandles, ancestrais, /cpus, /psci, /reserved-memory,
                /firmware, /chosen e os alvos de /aliases. Phandles viram &label
                quando o no alvo tem label. Sem /memory (fica na placa).
  * topaz.dts   /dts-v1/; #include "khaje.dtsi"; propriedades de raiz do overlay
                (o fdtoverlay nao as aplicava na fase 1); /memory com os valores
                do ativo; cada fragment do overlay vira um bloco &label { ... }.

Verificacao (--check): reanalisa o topaz.dts resolvendo o include, os blocos &label
e os labels, e compara com o FDT ativo por caminho de no e valor (phandles
normalizados para caminhos). Divergencias conhecidas estao em EXPECTED, com motivo.
Qualquer outra divergencia, nó extra, label inexistente ou phandle pendurado
faz o script sair com codigo 1.

A comparacao e local e nao depende de dtc. A compilacao real (dtc, dt-validate)
acontece no workflow de GitHub Actions.

Uso:
    python3 tools/curate_dt.py --out-dir device-tree/topaz          # gera
    python3 tools/curate_dt.py --out-dir device-tree/topaz --check  # verifica
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
REF = REPO / "device-tree" / "reference"
BASE_PATH = REF / "khaje-base-reference.dts"
LIVE_PATH = REF / "topaz-live-reference.dts"
OVERLAY_PATH = REPO / "device-tree" / "topaz" / "topaz-overlay.dtso"

LABEL_OK = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NODE_OPEN = re.compile(r"^\s*((?:[A-Za-z_]\w*:\s*)*)([^\s=;{}]+)\s*\{\s*$")
NODE_CLOSE = re.compile(r"^\s*\};\s*$")
PROP_VALUE = re.compile(r"^\s*([^\s=;{}]+)\s*=\s*(.*?);\s*$")
PROP_FLAG = re.compile(r"^\s*([^\s=;{}]+);\s*$")
CELL_GROUP = re.compile(r"<([^<>]*)>")
TOKEN = re.compile(r'"[^"]*"|<[^<>]*>|\[[^\]]*\]|[^,\s][^,]*')

# Propriedades cujo valor e uma lista de phandles, cada um seguido de N celulas
# definidas pelo no provedor (#...-cells). Mapeia nome -> propriedade de celulas.
CELLS_PROP = {
    "clocks": "#clock-cells",
    "resets": "#reset-cells",
    "power-domains": "#power-domain-cells",
    "interrupts-extended": "#interrupt-cells",
    "phys": "#phy-cells",
    "dmas": "#dma-cells",
    "interconnects": "#interconnect-cells",
    "iommus": "#iommu-cells",
    "mboxes": "#mbox-cells",
    "qcom,freq-domain": "#freq-domain-cells",
    "cooling-device": "#cooling-cells",
    "thermal-sensors": "#thermal-sensor-cells",
    "pwms": "#pwm-cells",
    "sound-dai": "#sound-dai-cells",
}
# Propriedades com um unico phandle e nenhuma celula extra.
SINGLE_PHANDLE = {"interrupt-parent", "phy-handle", "trip", "next-level-cache",
                  "memory-region", "operating-points-v2", "qcom,lmh-dcvs"}
SINGLE_PATTERNS = [re.compile(r".*-supply$")]
GPIO_PATTERN = re.compile(r".*-gpios?$")  # usa #gpio-cells

# Nos da raiz da base que nao entram na DT da SoC.
EXCLUDE_ROOT = {"memory", "__symbols__", "__fixups__", "__local_fixups__"}
# Escopo C (reduzida ao port 6.12): subsistemas fora do port inicial. Um no (base ou
# overlay) cujo `compatible` casa com esta regex sai da DT curada e de topaz.dts, junto
# com seus filhos. Os nos excluidos ficam listados em excluidos.txt (trilha de auditoria).
EXCLUDE_COMPAT = re.compile("|".join([
    # display (MDSS/DSI/SDE e painel)
    r"qcom,sde", r"qcom,mdss", r"qcom,dsi", r"dsi-phy", r"qcom,smmu_sde",
    # camera (CCI, CSI, CPAS, TFE/IFE, OPE, sensores, EEPROM)
    r"qcom,cam", r"qcom,cci", r"qcom,csi", r"qcom,csid", r"qcom,tfe", r"qcom,ope", r"qcom,ppi",
    r"qcom,tpg", r"qcom,cpas", r"qcom,eeprom", r"qcom,msm-cam", r"qcom,icp", r"wl2866d",
    # carregador e Type-C (I2C)
    r"nopmi-chg", r"bq2589x", r"sc8551", r"sm5602", r"ln8000", r"rt1711h", r"rt-pd-manager",
    r"cp_manager", r"onewire", r"ds28e16",
    # toque e impressao digital (dependem do painel ou nao sao do port inicial)
    r"touch", r"synaptics", r"focaltech", r"novatek", r"goodix", r"fpc,",
    # audio (LPASS/SPF, codecs, SoundWire, Bolero)
    r"qcom,spf", r"qcom,bengal-asoc", r"qcom,audio", r"qcom,swr", r"qcom,wcd9", r"qcom,msm-cdc",
    r"qcom,msm-stub-codec", r"qcom,bolero", r"qcom,lpass", r"qcom,codec", r"qcom,adsp-loader",
    r"wsa8", r"qcom,wsa", r"si,sia81xx",
    # USB (DWC3, PHY HS/SS)
    r"dwc-usb3", r"usb-nop", r"qcom,usb-",
    # SD/eMMC (mmc0/mmc1 e sdhc_1/sdhc_2 do overlay)
    r"sdhci-msm",
    # depuracao (CoreSight, JTAG, EUD)
    r"coresight", r"arm,primecell", r"jtagv8", r"qcom,msm-eud",
    # DSP, modem, Wi-Fi/BT, IPA, TrustZone e criptografia
    r"adsp", r"cdsp", r"modem", r"-pas", r"fastrpc", r"glinkpkt", r"ipa", r"icnss", r"wcn",
    r"qseecom", r"smcinvoke", r"qcedev", r"qcrypto", r"qrng", r"msm_fastrpc",
    # NFC, amplificadores de audio, adaptador PD, vibrador e SIM tray (sem uso no bring-up)
    r"st,st21nfc", r"awinic", r"foursemi", r"xiaomi,pd_adapter", r"qcom,qpnp-vibrator",
    r"xiaomi,simtray", r"qcom,msm-notifier",
]))


# No sem compatible que sai da curada (pelo caminho completo, em qualquer nivel).
EXCLUDE_PATHS = [
    "/soc/thermal-screen",
    # Subsistemas fora do port inicial sem compatible proprio (vendor): antena/ant-check,
    # PD/USB-SS, camera (VAF), painel DSI (pll codes e fonte do painel), notificacao de termica.
    "/soc/ant_check", "/soc/ant_check_div", "/soc/cam-vaf", "/soc/vdda_usb_ss_dp_core",
    "/soc/dsi_pll_codes", "/soc/dsi_panel_pwr_supply_no_labibb", "/soc/thermal-message",
    "/soc/pinctrl@400000/ant-check-pin", "/soc/pinctrl@400000/ant-check-div-pin",
    "/soc/thermal-zones/rf-pa1-therm-usr",
]

# Port 6.12 do toque: excecao controlada ao escopo C. O no de vendor
# `focaltech@38` (compatible "focaltech,fts", FT5452 em I2C 0x38) sai do overlay e
# e substituido pelo no upstream TOUCH_PORT_BLOCK (edt-ft5x06, focaltech,ft5452),
# emitido em topaz.dts. As propriedades vendor do barramento saem. Os nos goodix e
# synaptics continuam excluidos por EXCLUDE_COMPAT.
TOUCH_BUS_LABEL = "qupv3_se2_i2c"
TOUCH_NODE_NAME = "focaltech@38"
TOUCH_BUS_VENDOR_PROPS = {"qcom,touch-active", "qcom,i2c-touch-active"}
# Valores da stock (FDT de referencia, no focaltech@38 do barramento i2c-1):
#   irq-gpio   <&tlmm 0x50 0x02>  -> GPIO 80, borda de descida (IRQ_TYPE_EDGE_FALLING)
#   reset-gpio <&tlmm 0x56 0x01>  -> GPIO 86, active low (flag 1 do vendor)
#   avdd-gpio  <&tlmm 0x24 0x00>  -> GPIO 36, active high; ligado como regulador fixo
#   display-coords 0x2a2f 0x5dbf  -> 10799 x 23999
# Pendencias (nao confirmadas em hardware): pinctrl do touch (ts_int_active etc.
# do vendor nao entram aqui), polaridade do reset e o uso do avdd como regulador.
TOUCH_PORT_BLOCK = [
    "/ {",
    "\ttouch_avdd: regulator-touch-avdd {",
    "\t\tcompatible = \"regulator-fixed\";",
    "\t\tregulator-name = \"touch_avdd\";",
    "\t\tgpio = <&tlmm 0x24 0x00>;",
    "\t\tenable-active-high;",
    "\t};",
    "};",
    "",
    "&tlmm {",
    "\tts_int_active: ts-int-active-state {",
    "\t\tpins = \"gpio80\";",
    "\t\tfunction = \"gpio\";",
    "\t\tdrive-strength = <8>;",
    "\t\tbias-pull-up;",
    "\t};",
    "\tts_reset_active: ts-reset-active-state {",
    "\t\tpins = \"gpio86\";",
    "\t\tfunction = \"gpio\";",
    "\t\tdrive-strength = <8>;",
    "\t\tbias-pull-up;",
    "\t};",
    "};",
    "",
    "&qupv3_se2_i2c {",
    "\ttouchscreen@38 {",
    "\t\tcompatible = \"focaltech,ft5452\";",
    "\t\treg = <0x38>;",
    "\t\tinterrupt-parent = <&tlmm>;",
    "\t\tinterrupts = <0x50 0x02>;",
    "\t\treset-gpios = <&tlmm 0x56 0x01>;",
    "\t\tpinctrl-names = \"default\";",
    "\t\tpinctrl-0 = <&ts_int_active &ts_reset_active>;",
    "\t\tvcc-supply = <&touch_avdd>;",
    "\t\ttouchscreen-size-x = <10799>;",
    "\t\ttouchscreen-size-y = <23999>;",
    "\t\tstatus = \"okay\";",
    "\t};",
    "};",
    "",
]


# compatible por caminho, do FDT ativo. A base de referencia nao traz compatible em
# alguns nos (ex.: touch sob i2c); o ativo e a fonte para decidir o corte.
LIVE_COMPAT: dict[str, str] = {}


def node_compat(node: "Node") -> str | None:
    return node.props.get("compatible") or LIVE_COMPAT.get(path_key(node))


def is_dropped(compat: str | None, path: str | None = None) -> bool:
    if compat and EXCLUDE_COMPAT.search(compat):
        return True
    return bool(path) and any(path == p or path.startswith(p + "/") for p in EXCLUDE_PATHS)


# Subarvores inteiras mantidas (fecho minimo de infraestrutura de boot).
ESSENTIAL_SUBTREES = ["/cpus", "/psci", "/reserved-memory", "/firmware", "/chosen"]

# Divergencias conhecidas entre a DT curada e o FDT ativo. Cada chave e
# (caminho normalizado, propriedade); o valor explica a origem.
EXPECTED = {
    ("/aliases", "mmc0"): "escopo C: sdhci (SD/eMMC) fora do port inicial; alias sai com o no",
    ("/aliases", "mmc1"): "escopo C: sdhci (SD/eMMC) fora do port inicial; alias sai com o no",
    ("/aliases", "swr0"): "escopo C: SoundWire/audio fora do port inicial; alias sai com o no",
    ("/aliases", "swr1"): "escopo C: SoundWire/audio fora do port inicial; alias sai com o no",
    ("/firmware/android/fstab/vendor", "status"):
        "fase 1: base 'ok', ativo 'disabled' (runtime); o overlay nao altera o no",
    ("/memory", "ddr_manufacturer_id"): "injetada pelo bootloader; nao e DT da placa",
    ("/memory", "ddr_size"): "injetada pelo bootloader; nao e DT da placa",
    ("/soc/qcom,qupv3_0_geni_se@4ac0000/i2c@4a88000", "qcom,touch-active"):
        "port 6.12 do toque: propriedade vendor do barramento removida (TOUCH_BUS_VENDOR_PROPS)",
    ("/soc/qcom,qupv3_0_geni_se@4ac0000/i2c@4a88000", "qcom,i2c-touch-active"):
        "port 6.12 do toque: propriedade vendor do barramento removida (TOUCH_BUS_VENDOR_PROPS)",
}
# Nos novos da curada que nao existem no FDT ativo, de proposito (TOUCH_PORT_BLOCK).
EXPECTED_EXTRA_NODES = {
    "/regulator-touch-avdd": "port 6.12 do toque: regulador fixo do AVDD (GPIO 36) da stock",
    "/soc/qcom,qupv3_0_geni_se@4ac0000/i2c@4a88000/touchscreen@38":
        "port 6.12 do toque: no edt-ft5x06 / focaltech,ft5452 (substitui focaltech@38 de vendor)",
    "/soc/pinctrl@400000/ts-int-active-state":
        "port 6.12 do toque: pinctrl do INT (GPIO 80) copiado da stock (pmx_ts_int_active), flat no tlmm",
    "/soc/pinctrl@400000/ts-reset-active-state":
        "port 6.12 do toque: pinctrl do reset (GPIO 86) copiado da stock (pmx_ts_reset_active), flat no tlmm",
}
# Propriedades que o gerador normaliza de forma intencional.
NORMALIZED_FLAGS = {"bias-disable"}
# Valores de status normalizados: "ok" (legado, aceito pelo Linux) vira "okay" (o unico
# que o dt-schema aceita). Mesma semantica; a comparacao com o ativo trata os dois iguais.
NORMALIZED_STATUS = {'"ok"': '"okay"', '"OK"': '"okay"'}


def norm_value(prop: str, value: str) -> str:
    """Valor a escrever no DTS: aplica a normalizacao de status."""
    if prop == "status":
        return NORMALIZED_STATUS.get(value, value)
    return value


@dataclass
class Node:
    name: str
    parent: "Node | None" = None
    labels: list[str] = field(default_factory=list)
    props: dict[str, str | None] = field(default_factory=dict)
    children: dict[str, "Node"] = field(default_factory=dict)

    def path(self) -> str:
        if self.parent is None:
            return "/"
        parts = []
        n: Node | None = self
        while n is not None and n.parent is not None:
            parts.append(n.name)
            n = n.parent
        return "/" + "/".join(reversed(parts))


def parse(text: str) -> tuple[Node, list[Node]]:
    """Le DTS decompilado (com ou sem labels). Retorna (raiz, blocos &label)."""
    root = Node("/")
    overrides: list[Node] = []
    stack = [root]
    for raw in text.splitlines():
        line = raw.rstrip()
        st = line.strip()
        if not st or st.startswith(("/*", "*", "//", "/dts-v1/", "/plugin/", "#include")):
            continue
        m = NODE_OPEN.match(line)
        if m:
            labels = re.findall(r"([A-Za-z_]\w*):", m.group(1))
            name = m.group(2)
            if name == "/" and len(stack) == 1:
                node = root
            elif name.startswith("&") and len(stack) == 1:
                node = Node(name)
                overrides.append(node)
            else:
                if name in stack[-1].children:
                    raise ValueError(f"no duplicado: {stack[-1].path()}/{name}")
                node = Node(name, parent=stack[-1], labels=labels)
                stack[-1].children[name] = node
            if node is root or node.parent is None:
                node.labels = node.labels + labels  # raiz ou bloco &label
            stack.append(node)
            continue
        if NODE_CLOSE.match(line):
            stack.pop()
            continue
        m = PROP_VALUE.match(line)
        if m:
            stack[-1].props[m.group(1)] = m.group(2)
            continue
        m = PROP_FLAG.match(line)
        if m:
            stack[-1].props[m.group(1)] = None
            continue
        raise ValueError(f"linha nao reconhecida: {raw!r}")
    if len(stack) != 1:
        raise ValueError("chaves desbalanceadas")
    return root, overrides


def walk(node: Node):
    yield node
    for c in node.children.values():
        yield from walk(c)


def resolve_path(root: Node, path: str) -> Node:
    node = root
    for part in path.strip("/").split("/"):
        if part:
            if part not in node.children:
                raise KeyError(f"no nao encontrado: {path}")
            node = node.children[part]
    return node


def cells(value: str | None) -> list[str]:
    if value is None:
        return []
    out: list[str] = []
    for g in CELL_GROUP.findall(value):
        out.extend(g.split())
    return out


def render_cells(original: str, new_cells: list[str]) -> str:
    out = []
    idx = 0
    for g in CELL_GROUP.findall(original):
        n = len(g.split())
        out.append("<" + " ".join(new_cells[idx: idx + n]) + ">")
        idx += n
    if idx != len(new_cells):
        raise ValueError("contagem de celulas inconsistente")
    return ", ".join(out)


def num(tok: str) -> int | None:
    if re.fullmatch(r"0x[0-9a-fA-F]+|\d+", tok):
        return int(tok, 0)
    return None


class Tree:
    """Indices de uma arvore: labels, phandles e a decodificacao de phandles."""

    def __init__(self, root: Node, overrides: list[Node] | None = None):
        self.root = root
        self.labels: dict[str, Node] = {}
        for n in walk(root):
            for lb in n.labels:
                if lb in self.labels:
                    raise ValueError(f"label duplicado: {lb}")
                self.labels[lb] = n
        for ovr in overrides or []:
            target = self.labels.get(ovr.name[1:])
            if target is None:
                raise ValueError(f"label de override inexistente: {ovr.name}")
            merge_into(target, ovr)
        self.labels = {}
        for n in walk(root):
            for lb in n.labels:
                if lb in self.labels:
                    raise ValueError(f"label duplicado: {lb}")
                self.labels[lb] = n
        self.phandles: dict[int, Node] = {}
        for n in walk(root):
            ph = n.props.get("phandle") or n.props.get("linux,phandle")
            if ph:
                self.phandles[int(cells(ph)[0], 0)] = n

    def cells_needed(self, provider: Node | None, prop: str) -> int:
        if provider is None:
            return 0
        cp = CELLS_PROP.get(prop) or ("#gpio-cells" if GPIO_PATTERN.match(prop) else None)
        if cp is None:
            return 0
        v = provider.props.get(cp)
        return int(cells(v)[0], 0) if v else 0

    def decode(self, node: Node, prop: str, value: str | None):
        """Retorna lista de (indice, token, alvo) dos phandles da propriedade, ou None.

        None significa que a propriedade nao e uma lista de phandles conhecida
        ou que a decodificacao nao fecha exatamente (contagem de celulas).
        """
        if value is None:
            return None
        toks = cells(value)
        if prop in SINGLE_PHANDLE or any(p.match(prop) for p in SINGLE_PATTERNS):
            if len(toks) != 1:
                return None
            tgt = self.target_of(toks[0])
            return [(0, toks[0], tgt)] if tgt is not None else None
        if prop not in CELLS_PROP and not GPIO_PATTERN.match(prop):
            return None
        out = []
        i = 0
        while i < len(toks):
            tgt = self.target_of(toks[i])
            if tgt is None:
                return None
            out.append((i, toks[i], tgt))
            i += 1 + self.cells_needed(tgt, prop)
        return out if i == len(toks) else None

    def target_of(self, tok: str) -> "Node | None":
        if tok.startswith("&"):
            return self.labels.get(tok[1:])
        v = num(tok)
        return self.phandles.get(v) if v else None


def merge_into(target: Node, ovr: Node) -> None:
    for k, v in ovr.props.items():
        target.props[k] = v
    for name, child in ovr.children.items():
        if name in target.children:
            merge_into(target.children[name], child)
        else:
            child.parent = target
            target.children[name] = child


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- geracao


def base_symbols(base: Node) -> dict[str, list[str]]:
    """Caminho -> labels validos, a partir de __symbols__ da base."""
    by_path: dict[str, list[str]] = {}
    sym = base.children.get("__symbols__")
    if sym is None:
        raise ValueError("base sem __symbols__")
    for label, value in sym.props.items():
        path = re.findall(r'"([^"]*)"', value or "")[0]
        if LABEL_OK.match(label):
            by_path.setdefault(path, []).append(label)
    return by_path


def overlay_refs(text: str) -> tuple[set[str], set[str]]:
    """(labels referenciados, labels definidos) no overlay simbolizado."""
    refs = set(re.findall(r"&([A-Za-z_]\w*)", text))
    defs = set(re.findall(r"(?m)^\s*([A-Za-z_]\w*):\s", text))
    return refs - defs, defs


class Closure:
    def __init__(self, base: Tree):
        self.t = base
        self.keep: set[int] = set()  # id(Node)
        self.kept: list[Node] = []
        self.ambiguous: list[tuple[str, str, str]] = []  # (no, prop, alvo) nao decodificado
        self.work: list[Node] = []

    def add(self, node: Node) -> None:
        if id(node) in self.keep:
            return
        if node.parent is not None and node.parent.parent is None and node.name in EXCLUDE_ROOT:
            return
        if is_dropped(node_compat(node), node.path()):
            return
        self.keep.add(id(node))
        self.kept.append(node)
        self.work.append(node)
        if node.parent is not None:
            self.add(node.parent)

    def add_subtree(self, node: Node) -> None:
        self.add(node)
        for c in node.children.values():
            self.add_subtree(c)

    def run(self, roots: list[Node]) -> None:
        for r in roots:
            self.add(r)
        self.add(self.t.root)
        while self.work:
            node = self.work.pop()
            for prop, value in node.props.items():
                if prop in ("phandle", "linux,phandle"):
                    continue
                dec = self.t.decode(node, prop, value)
                if dec is not None:
                    for _, _, tgt in dec:
                        self.add(tgt)
                    continue
                # Valor que nao decodificamos: se algum numero casar com phandle,
                # registramos para revisao (nao puxa o no automaticamente).
                for tok in cells(value):
                    v = num(tok)
                    if v and v in self.t.phandles and self.t.phandles[v] is not node:
                        self.ambiguous.append((node.path(), prop, self.t.phandles[v].path()))


def render_value(t: Tree, node: Node, prop: str, value: str | None, kept: set[int],
                 sym: dict[str, list[str]]) -> str:
    if value is None:
        return f"{prop};"
    if value is not None and prop == "status":
        return f"{prop} = {norm_value(prop, value)};"
    if prop in NORMALIZED_FLAGS and cells(value) in (["0x0"], ["0x00000000"], ["0"]):
        return f"{prop};"
    dec = t.decode(node, prop, value)
    if dec is None:
        return f"{prop} = {value};"
    toks = cells(value)
    changed = False
    for idx, tok, tgt in dec:
        lbl = next((lb for lb in sym.get(tgt.path(), []) if id(tgt) in kept), None)
        if lbl is not None:
            toks[idx] = f"&{lbl}"
            changed = True
    if not changed:
        return f"{prop} = {value};"
    return f"{prop} = {render_cells(value, toks)};"


def render_node(t: Tree, node: Node, kept: set[int], sym: dict[str, list[str]],
                depth: int, skip_props: set[str] = frozenset()) -> list[str]:
    ind = "\t" * depth
    labels = "".join(f"{lb}: " for lb in sym.get(node.path(), []) if lb)
    head = f"{ind}{labels}{node.name} {{"
    lines = [head]
    for prop, value in node.props.items():
        if prop in skip_props:
            continue
        lines.append(f"{ind}\t{render_value(t, node, prop, value, kept, sym)}")
    for child in node.children.values():
        if id(child) in kept:
            lines.extend(render_node(t, child, kept, sym, depth + 1))
    lines.append(f"{ind}}};")
    return lines


def render_overlay_body(node: Node, depth: int) -> list[str]:
    ind = "\t" * depth
    lines = []
    for prop, value in node.props.items():
        lines.append(f"{ind}{prop};" if value is None else f"{ind}{prop} = {norm_value(prop, value)};")
    for child in node.children.values():
        labels = "".join(f"{lb}: " for lb in child.labels)
        lines.append(f"{ind}{labels}{child.name} {{")
        lines.extend(render_overlay_body(child, depth + 1))
        lines.append(f"{ind}}};")
    return lines


def generate(out_dir: Path) -> None:
    base_root, _ = parse(BASE_PATH.read_text(encoding="utf-8"))
    base_sym = base_symbols(base_root)
    bt = Tree(base_root)
    # A base decompilada nao tem labels nos nos: eles vem de __symbols__.
    bt.labels = {}
    for path, labels in base_sym.items():
        for lb in labels:
            bt.labels[lb] = resolve_path(base_root, path)
    overlay_text = OVERLAY_PATH.read_text(encoding="utf-8")
    ov_root, _ = parse(overlay_text)
    live_root, _ = parse(LIVE_PATH.read_text(encoding="utf-8"))
    LIVE_COMPAT.clear()
    LIVE_COMPAT.update({path_key(n): n.props["compatible"] for n in walk(live_root)
                        if n.parent is not None and n.props.get("compatible")})

    refs, defs = overlay_refs(overlay_text)
    missing = [r for r in refs if r not in bt.labels]
    if missing:
        raise SystemExit(f"overlay referencia labels ausentes na base: {sorted(missing)}")

    # Escopo C: fragmentos cujo alvo e excluido saem; filhos excluidos do overlay mantido
    # saem de dentro dele (in place). Excluidos sao registrados em excluidos.txt.
    kept_frags: list[tuple[Node, Node]] = []
    dropped_log: list[str] = []
    for frag in ov_root.children.values():
        if not frag.name.startswith("fragment@"):
            raise SystemExit(f"no inesperado no overlay: {frag.name}")
        m = re.fullmatch(r"<&([A-Za-z_]\w*)>", (frag.props.get("target") or "").strip())
        if not m or "__overlay__" not in frag.children:
            raise SystemExit(f"fragmento sem target simbolico ou sem __overlay__: {frag.name}")
        tgt = bt.labels[m.group(1)]
        if is_dropped(node_compat(tgt), tgt.path()):
            dropped_log.append(f"{frag.name} (alvo &{m.group(1)}, {tgt.props.get('compatible')})")
            continue
        kept_frags.append((frag, tgt))

    def prune(target: Node, ov: Node, path: str) -> None:
        for name in list(ov.children):
            child = ov.children[name]
            base_child = target.children.get(name)
            comp = child.props.get("compatible") or (node_compat(base_child) if base_child else None) \
                or LIVE_COMPAT.get(f"{path}/{name}")
            if is_dropped(comp, f"{path}/{name}"):
                dropped_log.append(f"{path}/{name} (compatible {comp})")
                del ov.children[name]
            elif base_child is not None:
                prune(base_child, child, f"{path}/{name}")

    for frag, tgt in kept_frags:
        if tgt is bt.labels[TOUCH_BUS_LABEL]:
            ov = frag.children["__overlay__"]
            for prop in TOUCH_BUS_VENDOR_PROPS:
                ov.props.pop(prop, None)
            if TOUCH_NODE_NAME in ov.children:
                dropped_log.append(f"{tgt.path()}/{TOUCH_NODE_NAME} (substituido pelo no upstream de toque, TOUCH_PORT_BLOCK)")
                del ov.children[TOUCH_NODE_NAME]
        prune(tgt, frag.children["__overlay__"], tgt.path())

    # Estados de pinctrl definidos no overlay (filhos com label do tlmm) so sao mantidos
    # se algum no mantido os referencia. Os que so serviam a no excluido saem.
    tlmm_node = bt.labels["tlmm"]
    used_outside: set[str] = set()
    for frag, tgt in kept_frags:
        for name, child in frag.children["__overlay__"].children.items():
            if tgt is tlmm_node and child.labels:
                continue
            for node in [child, *walk(child)]:
                for v in node.props.values():
                    if v:
                        used_outside.update(re.findall(r"&([A-Za-z_]\w*)", v))
        for v in frag.children["__overlay__"].props.values():
            if v:
                used_outside.update(re.findall(r"&([A-Za-z_]\w*)", v))
    for frag, tgt in kept_frags:
        if tgt is not tlmm_node:
            continue
        ov = frag.children["__overlay__"]
        for name in list(ov.children):
            child = ov.children[name]
            if child.labels and not (set(child.labels) & used_outside):
                dropped_log.append(f"{tgt.path()}/{name} (estado de pinctrl sem uso na DT curada)")
                del ov.children[name]

    kept_text: set[str] = set()

    def collect_refs(node: Node) -> None:
        for v in node.props.values():
            if v:
                kept_text.update(re.findall(r"&([A-Za-z_]\w*)", v))
        for c in node.children.values():
            collect_refs(c)

    for frag, _ in kept_frags:
        collect_refs(frag.children["__overlay__"])
    kept_refs = kept_text - defs
    dangling = sorted(r for r in kept_refs
                      if is_dropped(node_compat(bt.labels[r]), bt.labels[r].path()))
    if dangling:
        raise SystemExit("overlay mantido referencia nos excluidos: " + ", ".join(dangling)
                         + " (ajuste EXCLUDE_COMPAT ou o overlay)")
    roots = [bt.labels[r] for r in sorted(kept_refs)] + [tgt for _, tgt in kept_frags]

    # Filhos do overlay que tem o mesmo nome de um no da base sao mesclados por dtc
    # com esse no. O no da base precisa estar na DT curada, senao o overlay cria um
    # no parcial no lugar dele.
    def overlay_children_roots(target: Node, ov: Node) -> None:
        for name, child in ov.children.items():
            if name in target.children:
                roots.append(target.children[name])
                overlay_children_roots(target.children[name], child)

    for frag, tgt in kept_frags:
        overlay_children_roots(tgt, frag.children["__overlay__"])
    # Alvos de aliases e de chosen/stdout-path entram como raizes.
    aliases = base_root.children.get("aliases")
    if aliases is not None:
        for prop, value in aliases.props.items():
            if prop == "phandle" or value is None:
                continue
            p = re.findall(r'"([^"]*)"', value)
            if p:
                try:
                    roots.append(resolve_path(base_root, p[0]))
                except KeyError:
                    pass
    for ess in ESSENTIAL_SUBTREES:
        try:
            roots.append(resolve_path(base_root, ess))
        except KeyError:
            pass

    cl = Closure(bt)
    if aliases is not None:
        cl.add(aliases)  # o proprio no /aliases; seus alvos ja sao raizes acima
    for ess in ESSENTIAL_SUBTREES:
        try:
            cl.add_subtree(resolve_path(base_root, ess))
        except KeyError:
            pass
    cl.run(roots)
    kept = {id(n) for n in cl.kept}

    # ---------------- khaje.dtsi
    dtsi: list[str] = []
    dtsi.append("/*")
    dtsi.append(" * DT da SoC Khaje (subconjunto curado) gerada por tools/curate_dt.py.")
    dtsi.append(" * Fonte: khaje-base-reference.dts, sha256 "
                f"{sha256(BASE_PATH)[:16]}...")
    dtsi.append(" * Nao revisado por upstream nem validado em hardware. Nao flashar.")
    dtsi.append(" * Licenca: a definir antes de submissao (base Qualcomm, revisar).")
    dtsi.append(" */")
    dtsi.append("")
    body = []
    # Raiz: propriedades da base e filhos mantidos (sem memory, sem tabelas __*).
    body.append("/ {")
    for prop, value in base_root.props.items():
        if prop in ("phandle",):
            continue
        body.append("\t" + render_value(bt, base_root, prop, value, kept, base_sym))
    for child in base_root.children.values():
        if child.name in EXCLUDE_ROOT or id(child) not in kept:
            continue
        if child.name == "aliases":
            body.extend(render_aliases(bt, child, kept, base_sym, base_root))
            continue
        body.extend(render_node(bt, child, kept, base_sym, 1))
    body.append("};")
    dtsi.extend(body)
    (out_dir / "khaje.dtsi").write_text("\n".join(dtsi) + "\n", encoding="utf-8")

    # ---------------- topaz.dts
    topaz: list[str] = []
    topaz.append("/dts-v1/;")
    topaz.append("")
    topaz.append("/*")
    topaz.append(" * DT da placa topaz (Redmi Note 12 4G), gerada por tools/curate_dt.py.")
    topaz.append(" * Fontes: topaz-overlay.dtso (sha256 " f"{sha256(OVERLAY_PATH)[:16]}...) e")
    topaz.append(" * topaz-live-reference.dts (memory). Nao revisado por upstream.")
    topaz.append(" * Nao flashar. A memoria e preenchida pelo bootloader.")
    topaz.append(" */")
    topaz.append("")
    topaz.append('#include "khaje.dtsi"')
    topaz.append("")
    topaz.append("/ {")
    for prop, value in ov_root.props.items():
        topaz.append(f"\t{prop};" if value is None else f"\t{prop} = {norm_value(prop, value)};")
    topaz.append("};")
    topaz.append("")
    live_mem = live_root.children["memory"]
    topaz.append("/ {")
    topaz.append("\tmemory@40000000 {")
    topaz.append('\t\tdevice_type = "memory";')
    topaz.append(f"\t\treg = {live_mem.props['reg']};")
    topaz.append("\t};")
    topaz.append("};")
    topaz.append("")
    for frag, tgt in kept_frags:
        m = re.fullmatch(r"<&([A-Za-z_]\w*)>", (frag.props.get("target") or "").strip())
        ovl = frag.children["__overlay__"]
        topaz.append(f"&{m.group(1)} {{")
        topaz.extend(render_overlay_body(ovl, 1))
        topaz.append("};")
        topaz.append("")
    topaz.extend(TOUCH_PORT_BLOCK)
    (out_dir / "topaz.dts").write_text("\n".join(topaz), encoding="utf-8")
    excl = [
        "Nos excluidos da DT curada (escopo C: subsistemas fora do port 6.12).",
        "Regex: EXCLUDE_COMPAT em tools/curate_dt.py. Fragmentos e filhos do overlay removidos:",
        "",
    ] + [f"- {x}" for x in dict.fromkeys(dropped_log)]
    (out_dir / "excluidos.txt").write_text("\n".join(excl) + "\n", encoding="utf-8")

    print(f"khaje.dtsi: {len(kept)} nos mantidos de {sum(1 for _ in walk(base_root))}")
    print(f"raizes do overlay: {len(kept_refs)} labels; ambiguos (nao puxados): {len(cl.ambiguous)}")
    print(f"excluidos do overlay (escopo C): {len(set(dropped_log))} (lista em excluidos.txt)")


def render_aliases(t: Tree, aliases: Node, kept: set[int], sym, base_root: Node) -> list[str]:
    lines = ["\taliases {"]
    for prop, value in aliases.props.items():
        if prop == "phandle":
            continue
        paths = re.findall(r'"([^"]*)"', value or "")
        try:
            tgt = resolve_path(base_root, paths[0])
        except (KeyError, IndexError):
            continue
        if id(tgt) in kept:
            lines.append(f"\t\t{prop} = {norm_value(prop, value)};")
    lines.append("\t};")
    return lines


# --------------------------------------------------------------------------- verificacao


def is_phandle_prop(prop: str) -> bool:
    return prop in CELLS_PROP or prop in SINGLE_PHANDLE or bool(GPIO_PATTERN.match(prop)) \
        or any(p.match(prop) for p in SINGLE_PATTERNS)


def canon_value(labels: dict[str, "Node"], pmap: dict[int, "Node"], prop: str,
                value: str | None) -> str:
    """Valor canonico para comparacao: &label e numero de phandle viram caminho de no.

    ``pmap`` e sempre a tabela de phandles do FDT ativo, nos dois lados, para que
    um mesmo numero seja tratado da mesma forma. Numeros que coincidem com um
    phandle do ativo e nao sao referencias ficam iguais nos dois lados.
    """
    if value is None:
        return "<0x0>" if prop in NORMALIZED_FLAGS else "<flag>"
    value = norm_value(prop, value)
    out = []
    for chunk in TOKEN.findall(value):
        chunk = chunk.strip()
        if not chunk.startswith("<"):
            out.append(chunk)
            continue
        toks = []
        for tok in chunk[1:-1].split():
            if tok.startswith("&"):
                node = labels.get(tok[1:])
                toks.append("@" + path_key(node) if node is not None else f"?{tok}")
                continue
            v = num(tok)
            if v and v in pmap:
                toks.append("@" + path_key(pmap[v]))
            else:
                toks.append(f"{v:#x}" if v is not None else tok)
        out.append("<" + " ".join(toks) + ">")
    s = ", ".join(out)
    if prop in NORMALIZED_FLAGS and s == "<0x0>":
        return "<0x0>"
    return s


def path_key(node: Node) -> str:
    """Caminho normalizado: /memory@X e tratado como /memory (a placa tem o endereco)."""
    p = node.path()
    return re.sub(r"^/memory@[0-9a-fA-F]+$", "/memory", p)


def check(out_dir: Path) -> int:
    board_text = (out_dir / "topaz.dts").read_text(encoding="utf-8")
    dtsi_text = (out_dir / "khaje.dtsi").read_text(encoding="utf-8")
    combined = board_text.replace('#include "khaje.dtsi"', dtsi_text)
    cur_root, cur_ovr = parse(combined)
    cur = Tree(cur_root, cur_ovr)
    live_root, _ = parse(LIVE_PATH.read_text(encoding="utf-8"))
    live = Tree(live_root)

    errors: list[str] = []
    notes: list[str] = []
    cur_nodes = {path_key(n): n for n in walk(cur_root) if n.parent is not None}
    live_nodes = {path_key(n): n for n in walk(live_root) if n.parent is not None}

    extra = sorted(set(cur_nodes) - set(live_nodes) - set(EXPECTED_EXTRA_NODES))
    for k in EXPECTED_EXTRA_NODES:
        if k not in cur_nodes:
            notes.append(f"excecao de no sem no correspondente na curada (revisar EXPECTED_EXTRA_NODES): {k}")
    if extra:
        errors.append(f"nos extras na DT curada (ausentes no ativo): {extra[:20]}")
    removed = len(set(live_nodes) - set(cur_nodes))
    notes.append(f"nos: curada={len(cur_nodes)} ativo={len(live_nodes)} removidos={removed}")

    # Labels usados em referencias dentro da curada devem existir.
    for n in walk(cur_root):
        for prop, value in n.props.items():
            for lb in re.findall(r"&([A-Za-z_]\w*)", value or ""):
                if lb not in cur.labels:
                    errors.append(f"label inexistente {lb} em {n.path()}:{prop}")

    value_diffs = []
    for key, cn in cur_nodes.items():
        ln = live_nodes.get(key)
        if ln is None:
            continue
        for prop, value in cn.props.items():
            if prop in ("phandle", "linux,phandle"):
                continue
            lv = ln.props.get(prop, "__ausente__")
            if lv == "__ausente__":
                value_diffs.append((key, prop, "so na curada"))
                continue
            if canon_value(cur.labels, live.phandles, prop, value) != canon_value(live.labels, live.phandles, prop, lv):
                value_diffs.append((key, prop,
                                    f"curada={canon_value(cur.labels, live.phandles, prop, value)} "
                                    f"ativo={canon_value(live.labels, live.phandles, prop, lv)}"))
        for prop in ln.props:
            if prop in ("phandle", "linux,phandle"):
                continue
            if prop not in cn.props:
                value_diffs.append((key, prop, "so no ativo"))

    unexpected = []
    expected_hits = set()
    for key, prop, why in value_diffs:
        if (key, prop) in EXPECTED:
            expected_hits.add((key, prop))
        else:
            unexpected.append((key, prop, why))
    for k in EXPECTED:
        if k not in expected_hits:
            notes.append(f"excecao sem divergencia (revisar lista EXPECTED): {k}")
    for key, prop, why in unexpected:
        errors.append(f"divergencia inesperada em {key}:{prop}: {why}")

    # Phandles pendurados: as posicoes de phandle sao decodificadas no ativo (referencia
    # completa); cada alvo precisa existir na curada, com o mesmo caminho.
    dangling = []
    indeterminate = 0
    for key, ln in live_nodes.items():
        cn = cur_nodes.get(key)
        if cn is None:
            continue
        for prop, lv in ln.props.items():
            if not is_phandle_prop(prop) or lv is None:
                continue
            dec = live.decode(ln, prop, lv)
            if dec is None:
                indeterminate += 1
                continue
            for _, _, tgt in dec:
                if path_key(tgt) not in cur_nodes:
                    dangling.append(f"{key}:{prop} -> {path_key(tgt)}")
    if dangling:
        errors.append(f"phandles sem no correspondente na curada: {dangling[:20]} ({len(dangling)})")
    notes.append(f"propriedades de phandle nao decodificadas no ativo (ignoradas): {indeterminate}")

    # /aliases: todo alias do ativo (exceto o phandle, removido de proposito) precisa existir
    # na curada com o mesmo caminho. Sem isto, perder o no inteiro passaria despercebido.
    live_al = live_nodes.get("/aliases")
    cur_al = cur_nodes.get("/aliases")
    if live_al is not None:
        if cur_al is None:
            errors.append("no /aliases ausente na curada")
        else:
            for prop, lv in live_al.props.items():
                if prop == "phandle" or ("/aliases", prop) in EXPECTED:
                    continue
                cv = cur_al.props.get(prop)
                if cv != lv:
                    errors.append(f"alias {prop}: curada={cv} ativo={lv}")
            notes.append(f"aliases: {len(cur_al.props)} na curada, "
                         f"{len([p for p in live_al.props if p != 'phandle'])} no ativo")

    # Fragments mantidos em topaz.dts: cada label referenciado precisa existir na curada.
    # (O overlay de origem tem fragmentos excluidos no escopo C; eles nao entram aqui.)
    refs, _ = overlay_refs(board_text)
    for r in refs:
        if r not in cur.labels:
            errors.append(f"label do overlay ausente na curada: {r}")

    print("== verificacao da DT curada contra o FDT ativo")
    for n in notes:
        print("  " + n)
    print(f"  divergencias de valor: {len(value_diffs)} "
          f"(esperadas: {len(expected_hits)}, inesperadas: {len(unexpected)})")
    for key, prop, why in value_diffs:
        tag = "esperada" if (key, prop) in EXPECTED else "INESPERADA"
        print(f"    [{tag}] {key}:{prop}: {why[:160]}")
    if errors:
        print("== ERROS")
        for e in errors:
            print("  - " + e)
        return 1
    print("== ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--check", action="store_true", help="verifica em vez de gerar")
    args = ap.parse_args()
    if args.check:
        return check(args.out_dir)
    generate(args.out_dir)
    return check(args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
