#!/usr/bin/env bash
# Traz para o sandbox o que o CI publicou no branch ci-artifacts-6.18:
# Image, sm6225-xiaomi-topaz.dtb, .config e os logs da rodada.
#
# Por que existe: o zip de artefato do Actions mora em
# productionresultssa*.blob.core.windows.net, host que nao e' alcancavel
# daqui (a API responde 302 e o download morre com EOF). Um branch do
# proprio repositorio sai por github.com, entao `git clone` funciona e o
# build_flash_images_618.sh consegue montar as imagens.
#
# Uso: tools/fetch_ci_artifacts.sh [destino] [branch]
#   destino  default: ci-artifacts-618/ na raiz do repositorio
#   branch   default: ci-artifacts-6.18
#
# Sai 1 se o branch ainda nao existe (nenhuma run publicou).
set -euo pipefail

AQUI=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-$AQUI/ci-artifacts-618}
BRANCH=${2:-ci-artifacts-6.18}
URL=${CI_REPO_URL:-$(git -C "$AQUI" remote get-url origin)}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if ! git clone -q --depth 1 --branch "$BRANCH" "$URL" "$TMP/b" 2>/dev/null; then
	echo "fetch_ci_artifacts: branch $BRANCH ainda nao existe" >&2
	echo "  (ele nasce na primeira run do workflow que chegar ao build)" >&2
	exit 1
fi

mkdir -p "$DEST"
( cd "$TMP/b" && tar -c --exclude=.git . ) | ( cd "$DEST" && tar -x )

echo "artefatos em $DEST"
if [ -f "$DEST/RUN" ]; then
	echo "  publicado por: $(cat "$DEST/RUN")"
fi
for f in Image sm6225-xiaomi-topaz.dtb config-6.18.config; do
	[ -f "$DEST/$f" ] && echo "  $f: $(stat -c %s "$DEST/$f") bytes"
done
if [ -d "$DEST/logs" ]; then
	echo "  logs: $(ls "$DEST/logs" | tr '\n' ' ')"
fi
