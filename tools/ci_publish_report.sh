#!/bin/bash
# Publica um resumo da validação como issue do repositório.
#
# Os logs completos ficam nos artefatos do Actions; este resumo traz o que
# é necessário para decidir rápido se a rodada passou e onde falhou.
#
# Uso: ci_publish_report.sh <titulo-da-issue> <rotulo> [arquivos de log...]
set -uo pipefail

TITLE=${1:?uso: ci_publish_report.sh <titulo> <label> [logs...]}
LABEL=${2:?uso: ci_publish_report.sh <titulo> <label> [logs...]}
shift 2

RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
BODY=$(mktemp)
{
  echo "### Rodada \`${GITHUB_RUN_ID}\` (${GITHUB_SHA:0:12})"
  echo
  echo "- run: ${RUN_URL}"
  echo "- workflow: ${GITHUB_WORKFLOW}"
  echo "- branch: ${GITHUB_REF_NAME}"
  echo
} >> "$BODY"

for log in "$@"; do
  [ -f "$log" ] || continue
  echo "#### $(basename "$log")" >> "$BODY"
  echo
  echo '```' >> "$BODY"
  # Ultimas linhas: em geral e onde o build falha.
  tail -n 60 "$log" >> "$BODY"
  echo '```' >> "$BODY"
  echo
done

if [ -d arch/arm64/boot/dts/qcom/khaje ]; then
  echo "#### DTBs gerados" >> "$BODY"
  echo
  echo '```' >> "$BODY"
  find arch/arm64/boot/dts/qcom/khaje \( -name '*.dtb' -o -name '*.dtbo' \) \
    -printf '%p %s bytes\n' | sort >> "$BODY"
  echo '```' >> "$BODY"
  echo
fi

# Atualiza a issue deste relatorio se ela ja existir (busca pelo titulo, e
# nao apenas pelo rotulo: as duas jobs do workflow publicam relatorios
# diferentes e nao podem sobrescrever a issue uma da outra).
EXISTING=$(gh issue list --label "$LABEL" --state open --limit 50 \
             --json number,title \
             --jq ".[] | select(.title == \"$TITLE\") | .number" 2>/dev/null | head -1)

if [ -n "${EXISTING:-}" ] && [ "$EXISTING" != "null" ]; then
  gh issue edit "$EXISTING" --title "$TITLE" --body-file "$BODY" >/dev/null
  echo "issue atualizada: #${EXISTING}"
else
  gh issue create --title "$TITLE" --label "$LABEL" --body-file "$BODY" >/dev/null
  echo "issue criada"
fi

rm -f "$BODY"
