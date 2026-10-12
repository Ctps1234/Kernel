#!/usr/bin/env bash
# Verifica o fragmento de defconfig do topaz contra o Kconfig da base 6.12.
#
# Uso: tools/check_defconfig.sh <arvore-kernel> <fragmento> <dir-saida>
#
# Passos (somente configuracao; nada e compilado):
#   1. make ARCH=arm64 gki_defconfig
#   2. merge_config.sh -m com o fragmento
#   3. make ARCH=arm64 olddefconfig
#   4. compara cada CONFIG pedido com o .config final e grava o relatorio
#
# Saida: dir-saida/defconfig-report.txt. Codigo 1 se algum simbolo nao ficou
# como pedido. Os passos 1 a 3 exigem Kconfig e scripts/kconfig da arvore.
#
# Diferenca importante: o olddefconfig omite do .config os simbolos cujas
# dependencias nao sao atendidas. Por isso o relatorio separa:
#   - "nao definido": nenhum "config SIMBOLO" nos Kconfig da arvore (nome errado);
#   - "omitido por dependencia": definido, mas nao habilitavel; mostra o depends.
set -uo pipefail

KDIR="${1:?uso: check_defconfig.sh <arvore> <fragmento> <saida>}"
FRAG="${2:?fragmento}"
OUT="${3:?dir de saida}"
FRAG_ABS="$(readlink -f "$FRAG")"

mkdir -p "$OUT"
cd "$KDIR" || { echo "arvore nao encontrada: $KDIR" >&2; exit 2; }
KDIR_ABS="$(pwd)"
export ARCH=arm64

run() {  # run <nome> <comando...>: falha se o comando falhar
    local name="$1"; shift
    if ! "$@" > "$OUT/$name.log" 2>&1; then
        echo "::error::passo '$name' falhou (log: $OUT/$name.log)" >&2
        tail -40 "$OUT/$name.log" >&2
        return 1
    fi
}

run gki_defconfig make gki_defconfig || exit 1
cp .config "$OUT/gki.config"
run merge scripts/kconfig/merge_config.sh -m -O . .config "$FRAG_ABS" || exit 1
cp .config "$OUT/merged.config"
run olddefconfig make olddefconfig || exit 1
cp .config "$OUT/final.config"

python3 - "$FRAG_ABS" "$OUT/final.config" "$OUT/defconfig-report.txt" "$KDIR_ABS" <<'PY'
import os, re, sys

frag_path, final_path, report_path, kdir = sys.argv[1:5]

def parse_fragment(path):
    want = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^(CONFIG_\w+)=(\S+?)\s*(#.*)?$", line.strip())
        if m:
            want[m.group(1)] = m.group(2)
    return want

def parse_final(path):
    got = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"^(CONFIG_\w+)=(\S+)$", line)
        if m:
            got[m.group(1)] = m.group(2)
            continue
        m = re.match(r"^# (CONFIG_\w+) is not set$", line)
        if m:
            got[m.group(1)] = "n"
    return got

def find_definitions(sym):
    """Retorna [(arquivo, [linhas depends/select/prompt])] para 'config SYM'."""
    hits = []
    target = f"config {sym}"
    for root, dirs, files in os.walk(kdir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if not f.startswith("Kconfig"):
                continue
            path = os.path.join(root, f)
            try:
                lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            for i, l in enumerate(lines):
                if l.strip() == target:
                    keep = []
                    for j in range(i + 1, min(i + 15, len(lines))):
                        s = lines[j].strip()
                        if s.startswith(("config ", "menuconfig ", "choice", "endchoice")):
                            break
                        if s.startswith(("depends", "select", "bool", "tristate", "prompt", "def_")):
                            keep.append(s)
                    hits.append((os.path.relpath(path, kdir), keep))
    return hits

want = parse_fragment(frag_path)
got = parse_final(final_path)
ok, undefined, disabled, changed = [], [], [], []
for sym, val in want.items():
    if sym not in got:
        (disabled if find_definitions(sym[len("CONFIG_"):]) else undefined).append(sym)
    elif got[sym] == val:
        ok.append(sym)
    elif got[sym] == "n":
        disabled.append(sym)
    else:
        changed.append((sym, val, got[sym]))

lines = [
    f"fragmento: {len(want)} simbolos pedidos",
    f"  mantidos como pedidos: {len(ok)}",
    f"  nao definidos em nenhum Kconfig (nome errado): {len(undefined)}",
    f"  desativados ou omitidos por dependencia: {len(disabled)}",
    f"  valor diferente (pedido -> final): {len(changed)}",
]
if undefined:
    lines += ["", "nao definidos (corrigir nome ou remover):"] + [f"  {s}" for s in undefined]
if disabled:
    lines += ["", "desativados ou omitidos por dependencia (arquivo e linhas do Kconfig):"]
    for s in disabled:
        hits = find_definitions(s[len("CONFIG_"):])
        if not hits:
            lines.append(f"  {s}: definicao nao encontrada")
        for path, keep in hits:
            lines.append(f"  {s} em {path}")
            lines += [f"      {k}" for k in keep[:6]]
if changed:
    lines += ["", "valor diferente:"] + [f"  {s}: {v} -> {g}" for s, v, g in changed]
report = "\n".join(lines) + "\n"
open(report_path, "w", encoding="utf-8").write(report)
print(report, end="")
sys.exit(0 if not (undefined or disabled or changed) else 1)
PY
