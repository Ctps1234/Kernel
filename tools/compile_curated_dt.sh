#!/usr/bin/env bash
# Gera a DT curada do topaz, confere se bate com os arquivos versionados e compila.
#
# Uso: tools/compile_curated_dt.sh OUT_DIR
#   1. roda tools/curate_dt.py em OUT_DIR/curated (inclui a verificacao contra o FDT ativo);
#   2. exige que khaje.dtsi e topaz.dts gerados sejam identicos aos versionados em
#      device-tree/topaz (a geracao e deterministica);
#   3. pre-processa topaz.dts com cpp (o include "khaje.dtsi") e compila com dtc.
#
# Saida: OUT_DIR/curated/topaz-curated.dtb. Requer cpp e dtc.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?OUT_DIR}/curated"
mkdir -p "$OUT"

python3 "$ROOT/tools/curate_dt.py" --out-dir "$OUT"

for f in khaje.dtsi topaz.dts excluidos.txt; do
    if ! cmp -s "$OUT/$f" "$ROOT/device-tree/topaz/$f"; then
        echo "::error::device-tree/topaz/$f diverge da saida de tools/curate_dt.py." >&2
        echo "Regenere com: python3 tools/curate_dt.py --out-dir device-tree/topaz" >&2
        diff -u "$ROOT/device-tree/topaz/$f" "$OUT/$f" | head -n 80 >&2 || true
        exit 1
    fi
done

cpp -nostdinc -undef -x assembler-with-cpp -I "$OUT" "$OUT/topaz.dts" > "$OUT/topaz-pre.dts"
dtc -I dts -O dtb -o "$OUT/topaz-curated.dtb" "$OUT/topaz-pre.dts" 2> "$OUT/dtc.log"
echo "DTB curado: $OUT/topaz-curated.dtb ($(stat -c %s "$OUT/topaz-curated.dtb") bytes)"
if [ -s "$OUT/dtc.log" ]; then
    echo "avisos do dtc ($(wc -l < "$OUT/dtc.log") linhas), inicio:"
    head -n 40 "$OUT/dtc.log"
fi
