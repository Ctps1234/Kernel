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
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-${TMPDIR:-/tmp}/topaz-dt-validate}"
BASE="$ROOT/device-tree/reference/khaje-base-reference.dts"
LIVE="$ROOT/device-tree/reference/topaz-live-reference.dts"
OVL="$ROOT/device-tree/topaz/topaz-overlay.dtso"

for tool in dtc fdtoverlay python3; do
    command -v "$tool" >/dev/null || { echo "ERRO: falta '$tool'" >&2; exit 2; }
done

mkdir -p "$OUT"
echo "== 1. Gerar overlay simbolico a partir da referencia e comparar com o versionado"
python3 "$ROOT/tools/symbolize_overlay.py" \
    "$ROOT/device-tree/reference/topaz-overlay-51-reference.dtso" \
    --output "$OUT/topaz-overlay.generated.dtso" >/dev/null
if ! diff -q "$OUT/topaz-overlay.generated.dtso" "$OVL" >/dev/null; then
    echo "ERRO: $OVL esta fora de sincronia com tools/symbolize_overlay.py" >&2
    echo "      regenere com: python3 tools/symbolize_overlay.py device-tree/reference/topaz-overlay-51-reference.dtso --output device-tree/topaz/topaz-overlay.dtso" >&2
    exit 1
fi

echo "== 2. Compilar base (sem -@; __symbols__ ja e literal na referencia)"
dtc -q -I dts -O dtb -o "$OUT/base.dtb" "$BASE"

echo "== 3. Compilar overlay como plugin (-@ gera __fixups__/__local_fixups__)"
dtc -q -@ -I dts -O dtb -o "$OUT/overlay.dtbo" "$OVL"
fixups=$(dtc -q -I dtb -O dts "$OUT/overlay.dtbo" | grep -c '=.*"/' || true)
echo "   entradas de __fixups__/__symbols__ com caminho: $fixups"

echo "== 4. Aplicar overlay na base com fdtoverlay"
fdtoverlay -i "$OUT/base.dtb" -o "$OUT/merged.dtb" "$OUT/overlay.dtbo"

echo "== 5. Comparar com o FDT ativo de referencia (informativo)"
dtc -q -I dts -O dtb -o "$OUT/live.dtb" "$LIVE"
dtc -q -I dtb -O dts -o "$OUT/merged.dts" "$OUT/merged.dtb"
dtc -q -I dtb -O dts -o "$OUT/live.dts" "$OUT/live.dtb"
diff -u "$OUT/live.dts" "$OUT/merged.dts" > "$OUT/live-vs-merged.diff" || true
echo "   linhas de diff: $(grep -c '^[-+][^-+]' "$OUT/live-vs-merged.diff" || true)"
echo "   relatorio: $OUT/live-vs-merged.diff"

echo "OK: artefatos em $OUT"
