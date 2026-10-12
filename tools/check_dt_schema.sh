#!/usr/bin/env bash
# Valida bindings e a DT topaz com dtschema, usando a arvore de kernel fixada
# com a serie local de patches aplicada.
#
# Uso: tools/check_dt_schema.sh KERNEL_DIR PATCHES_DIR MERGED_DTB OUT_DIR [CURATED_DTB]
#   KERNEL_DIR   arvore do commit fixado com os patches ja aplicados
#   PATCHES_DIR  diretorio com os patches locais (para listar bindings alterados)
#   MERGED_DTB   DTB resultante de tools/validate_dt.sh (base + overlay)
#   OUT_DIR      saida (relatorio e schema processado)
#   CURATED_DTB  opcional: DTB da DT curada (khaje.dtsi + topaz.dts); validado com o
#                mesmo schema processado, em log proprio
#
# Requer: dt-doc-validate, dt-mk-schema e dt-validate (pacote dtschema) com libfdt.
# Etapas:
#   1. dt-doc-validate nos bindings alterados pela serie (ainda sem validacao formal);
#   2. dt-mk-schema sobre todos os bindings da arvore;
#   3. dt-validate do MERGED_DTB (e do CURATED_DTB, se dado) contra o schema processado.
# Sai com codigo != 0 se alguma etapa reportar erro.
set -uo pipefail

KDIR="${1:?KERNEL_DIR}"
PATCHES="${2:?PATCHES_DIR}"
DTB="${3:?MERGED_DTB}"
OUT="${4:?OUT_DIR}"
CURATED="${5:-}"
BIND="Documentation/devicetree/bindings"
FAILED=0

summary() {
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        printf '%s\n' "$@" >> "$GITHUB_STEP_SUMMARY"
    fi
}

for tool in dt-doc-validate dt-mk-schema dt-validate; do
    command -v "$tool" >/dev/null || { echo "ERRO: falta '$tool'" >&2; exit 2; }
done
mkdir -p "$OUT"
REPORT="$OUT/dt-schema-report.txt"
: > "$REPORT"

# Bindings criados ou alterados pelos patches locais (caminhos relativos a KDIR).
CHANGED=$(grep -h '^+++ b/Documentation/devicetree/bindings/.*\.yaml$' "$PATCHES"/[0-9][0-9][0-9][0-9]-*.patch \
    | sed 's#^+++ b/##' | sort -u)
echo "bindings da serie: $(echo "$CHANGED" | wc -l)"
echo "bindings da serie: $(echo "$CHANGED" | wc -l)" >> "$REPORT"

echo "== 1. dt-doc-validate nos bindings da serie" | tee -a "$REPORT"
# shellcheck disable=SC2086
if (cd "$KDIR" && dt-doc-validate -u "$BIND" $CHANGED) >"$OUT/doc-validate.log" 2>&1; then
    echo "   ok" | tee -a "$REPORT"
else
    rc=$?
    echo "   FALHOU (rc=$rc); log: $OUT/doc-validate.log" | tee -a "$REPORT"
    FAILED=1
fi
echo "   linhas de saida: $(wc -l < "$OUT/doc-validate.log")" | tee -a "$REPORT"

echo "== 2. dt-mk-schema sobre todos os bindings" | tee -a "$REPORT"
# shellcheck disable=SC2046
if (cd "$KDIR" && dt-mk-schema -j -o "$OUT/processed-schema.json" $(find "$BIND" -name '*.yaml' -not -path '*/examples/*')) \
    >"$OUT/mk-schema.log" 2>&1; then
    echo "   ok ($(wc -c < "$OUT/processed-schema.json") bytes)" | tee -a "$REPORT"
else
    rc=$?
    echo "   FALHOU (rc=$rc); log: $OUT/mk-schema.log" | tee -a "$REPORT"
    FAILED=1
fi

echo "== 3. dt-validate do DTB mesclado" | tee -a "$REPORT"
if [ -s "$OUT/processed-schema.json" ] && dt-validate -s "$OUT/processed-schema.json" "$DTB" \
    >"$OUT/dt-validate.log" 2>&1; then
    echo "   ok" | tee -a "$REPORT"
else
    rc=$?
    echo "   FALHOU (rc=${rc:-?}); log: $OUT/dt-validate.log" | tee -a "$REPORT"
    FAILED=1
fi
echo "   linhas de saida: $(wc -l < "$OUT/dt-validate.log" 2>/dev/null || echo 0)" | tee -a "$REPORT"

if [ -n "$CURATED" ]; then
    echo "== 3b. dt-validate da DT curada" | tee -a "$REPORT"
    if [ -s "$OUT/processed-schema.json" ] && dt-validate -s "$OUT/processed-schema.json" "$CURATED" \
        >"$OUT/dt-validate-curated.log" 2>&1; then
        echo "   ok" | tee -a "$REPORT"
    else
        rc=$?
        echo "   FALHOU (rc=${rc:-?}); log: $OUT/dt-validate-curated.log" | tee -a "$REPORT"
        FAILED=1
    fi
    echo "   linhas de saida: $(wc -l < "$OUT/dt-validate-curated.log" 2>/dev/null || echo 0)" | tee -a "$REPORT"
fi

# Resumo de erros: primeiras linhas de cada log para o relatorio.
for log in doc-validate mk-schema dt-validate dt-validate-curated; do
    if [ -s "$OUT/$log.log" ]; then
        {
            echo ""
            echo "--- $log.log (inicio)"
            head -n 60 "$OUT/$log.log"
        } >> "$REPORT"
    fi
done

# Contagem de erros por propriedade (cada erro do dt-validate tem uma linha "from schema").
# Evita depender do texto truncado das anotacoes do GitHub.
python3 - "$OUT" | tee "$OUT/erros-por-propriedade.txt" >> "$REPORT" <<'PY'
import collections, os, re, sys
out = sys.argv[1]
for log in ("dt-validate", "dt-validate-curated"):
    path = os.path.join(out, log + ".log")
    if not os.path.isfile(path):
        continue
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    cnt = collections.Counter()
    total = 0
    for i, line in enumerate(lines):
        if not line.startswith("from schema"):
            continue
        total += 1
        prev = lines[i - 1] if i > 0 else line
        m = re.search(r"\): ([^:]+):", prev)  # "no (compat): propriedade: mensagem"
        key = m.group(1) if m else re.sub(r"^\S+: ", "", prev)[:80]
        cnt[key] += 1
    print("")
    print(f"--- {log}: {total} erro(s) por propriedade")
    for key, n in cnt.most_common(40):
        print(f"  {n:4d}  {key}")
PY

summary "## dtschema (bindings da serie + DTB mesclado)" '```' "$(cat "$REPORT")" '```'
cat "$REPORT"

# Anotacoes do run (visiveis na pagina do run, sem login): inicio de cada log com falha.
if [ -n "${GITHUB_ACTIONS:-}" ]; then
    for log in doc-validate mk-schema dt-validate dt-validate-curated; do
        if [ -s "$OUT/$log.log" ] && grep -qiE 'error|fail|Traceback|invalid' "$OUT/$log.log"; then
            python3 - "$OUT/$log.log" "$log" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()[:2500]
text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
print(f"::warning title=dtschema {sys.argv[2]}::" + text)
PY
        fi
    done
    if [ -s "$OUT/erros-por-propriedade.txt" ]; then
        python3 - "$OUT/erros-por-propriedade.txt" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()[:2500]
text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
print("::notice title=dtschema erros por propriedade::" + text)
PY
    fi
fi
exit "$FAILED"
