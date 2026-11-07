#!/bin/bash
# Publica um DTB compilado como base64 em comentarios da issue de
# relatorio do CI.
#
# Motivo: os artefatos do Actions ficam no blob storage do GitHub
# (productionresultssa*.blob.core.windows.net). De alguns ambientes esse
# host e' inalcancavel - no sandbox do projeto o download do zip do
# artefato morre com EOF - enquanto api.github.com responde. O corpo de
# um comentario de issue cabe folgado: o DTB do topaz tem algumas dezenas
# de KB, ~1/3 a mais em base64, ou seja dois ou tres comentarios.
#
# Cada comentario comeca com um marcador de uma linha, para o coletor
# (tools/fetch_dtb.py) saber a que rodada/arquivo/parte ele pertence:
#
#   <!-- dtb-b64 v1 run=<id> sha=<sha> part=<i>/<n> file=<nome> sha256=<hex> -->
#
# Uso: ci_publish_dtb.sh <titulo-da-issue> <label> <arquivo.dtb>
#
# Requer GH_TOKEN e GITHUB_REPOSITORY; GITHUB_RUN_ID/GITHUB_SHA vem do CI
# (fora dele cai em "local"/HEAD). Sem issue existente o script sai 0:
# publicar DTB e' conveniencia, nunca pode derrubar o build.
set -uo pipefail

TITLE=${1:?uso: ci_publish_dtb.sh <titulo> <label> <arquivo.dtb>}
LABEL=${2:?uso: ci_publish_dtb.sh <titulo> <label> <arquivo.dtb>}
DTB=${3:?uso: ci_publish_dtb.sh <titulo> <label> <arquivo.dtb>}

if [ ! -f "$DTB" ]; then
    echo "ci_publish_dtb: $DTB nao existe; nada a publicar"
    exit 0
fi

CHUNK=${DTB_CHUNK:-50000}
RUN=${GITHUB_RUN_ID:-local}
SHA=${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null | cut -c1-12)}
NAME=$(basename "$DTB")
SUM=$(sha256sum "$DTB" | cut -d' ' -f1)
B64=$(base64 -w0 "$DTB")
SIZE=${#B64}
NPARTS=$(( (SIZE + CHUNK - 1) / CHUNK ))

EXISTING=$(gh issue list --label "$LABEL" --state open --limit 50 \
             --json number,title \
             --jq ".[] | select(.title == \"$TITLE\") | .number" 2>/dev/null | head -1)
if [ -z "${EXISTING:-}" ] || [ "$EXISTING" = "null" ]; then
    echo "ci_publish_dtb: issue \"$TITLE\" nao encontrada; nada a publicar"
    exit 0
fi

echo "ci_publish_dtb: $NAME ($SIZE bytes base64, $NPARTS parte(s)) -> issue #$EXISTING"

BODY=$(mktemp)
i=1
while [ -n "$B64" ]; do
    PART=${B64:0:$CHUNK}
    B64=${B64:$CHUNK}
    {
        echo "<!-- dtb-b64 v1 run=$RUN sha=$SHA part=$i/$NPARTS file=$NAME sha256=$SUM -->"
        echo
        echo '```'
        echo "$PART"
        echo '```'
    } > "$BODY"
    if ! gh issue comment "$EXISTING" --body-file "$BODY" >/dev/null; then
        echo "ci_publish_dtb: falhou ao comentar a parte $i" >&2
        rm -f "$BODY"
        exit 0
    fi
    i=$((i + 1))
done

rm -f "$BODY"
echo "ci_publish_dtb: ok"
