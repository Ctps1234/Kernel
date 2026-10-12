#!/usr/bin/env bash
# Valida a DT topaz: compila base e overlay com dtc, aplica o overlay com
# fdtoverlay e compara o resultado com o FDT ativo de referencia.
#
# Uso: tools/validate_dt.sh [DIR_SAIDA]
#   DIR_SAIDA padrao: ${TMPDIR:-/tmp}/topaz-dt-validate (fora do repositorio).
#
# Requer: dtc e fdtoverlay (pacote device-tree-compiler).
# Falha (exit != 0) em erro de compilacao, de referencia nao resolvida ou de
# aplicacao do overlay. A diferenca com o FDT ativo e apenas informativa: o
# FDT ativo ja esta mesclado em runtime e contem nos/propriedades do bootloader.
#
# Em GitHub Actions, o stderr de cada etapa tambem vai para GITHUB_STEP_SUMMARY.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-${TMPDIR:-/tmp}/topaz-dt-validate}"
BASE="$ROOT/device-tree/reference/khaje-base-reference.dts"
LIVE="$ROOT/device-tree/reference/topaz-live-reference.dts"
OVL="$ROOT/device-tree/topaz/topaz-overlay.dtso"
FAILED=0

summary() {
    # Anexa texto ao resumo do job (visivel na pagina do run, quando disponivel).
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        printf '%s\n' "$@" >> "$GITHUB_STEP_SUMMARY"
    fi
}

# step NOME CMD... : roda CMD, guarda stdout/stderr em $OUT/NOME.log e registra o resultado.
step() {
    local name="$1"; shift
    local log="$OUT/$name.log"
    echo "== $name"
    "$@" >"$log" 2>&1
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "   ok ($(wc -l <"$log") linhas de log)"
        return 0
    fi
    echo "   FALHOU (rc=$rc); log: $log" >&2
    head -n 80 "$log" >&2
    summary "### FALHA: $name (rc=$rc)" '```' "$(head -n 120 "$log")" '```'
    FAILED=1
    return "$rc"
}

for tool in dtc fdtoverlay python3; do
    command -v "$tool" >/dev/null || { echo "ERRO: falta '$tool'" >&2; exit 2; }
done

mkdir -p "$OUT"
summary "## Validacao DT topaz"

step "gen-overlay" python3 "$ROOT/tools/symbolize_overlay.py" \
    "$ROOT/device-tree/reference/topaz-overlay-51-reference.dtso" \
    --output "$OUT/topaz-overlay.generated.dtso" || exit 1

if ! diff -q "$OUT/topaz-overlay.generated.dtso" "$OVL" >/dev/null; then
    echo "ERRO: $OVL esta fora de sincronia com tools/symbolize_overlay.py" >&2
    echo "      regenere com: python3 tools/symbolize_overlay.py device-tree/reference/topaz-overlay-51-reference.dtso --output device-tree/topaz/topaz-overlay.dtso" >&2
    summary "ERRO: overlay versionado fora de sincronia com o gerador."
    exit 1
fi

# Base: sem -@ (o __symbols__ ja e literal na referencia).
step "dtc-base" dtc -I dts -O dtb -o "$OUT/base.dtb" "$BASE" || exit 1

# Overlay: plugin com -@ gera __fixups__/__local_fixups__.
step "dtc-overlay" dtc -@ -I dts -O dtb -o "$OUT/overlay.dtbo" "$OVL" || exit 1

step "fdtoverlay" fdtoverlay -i "$OUT/base.dtb" -o "$OUT/merged.dtb" "$OUT/overlay.dtbo" || exit 1

# Comparacao informativa com o FDT ativo; falha aqui nao bloqueia.
step "dtc-live" dtc -I dts -O dtb -o "$OUT/live.dtb" "$LIVE" || true
dtc -q -I dtb -O dts -o "$OUT/merged.dts" "$OUT/merged.dtb" 2>>"$OUT/dtc-decompile.log" || true
dtc -q -I dtb -O dts -o "$OUT/live.dts" "$OUT/live.dtb" 2>>"$OUT/dtc-decompile.log" || true
diff -u "$OUT/live.dts" "$OUT/merged.dts" > "$OUT/live-vs-merged.diff" 2>/dev/null || true
DIFFLINES=$(grep -c '^[-+][^-+]' "$OUT/live-vs-merged.diff" 2>/dev/null || true)
echo "linhas de diff com o FDT ativo (informativo): ${DIFFLINES:-0}"
summary "- diff informativo com o FDT ativo: ${DIFFLINES:-0} linhas"

if [ "$FAILED" -ne 0 ]; then
    echo "FALHA: veja os logs em $OUT" >&2
    exit 1
fi
echo "OK: artefatos em $OUT"
