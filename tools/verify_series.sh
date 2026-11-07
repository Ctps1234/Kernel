#!/usr/bin/env bash
# Verifica que a serie patches-6.18 aplica limpa sobre a base fixada.
#
# E' o gate "rebase-cost" do CI, rodando local: baixa a base ACK
# (filtro blob:none + sparse checkout apenas dos arquivos que a serie
# toca) e aplica os patches em ordem com `git am --keep-cr`.
#
# Existe porque o CI nao e' acionavel de dentro do sandbox (o token do
# agente nao tem permissao de workflow_dispatch) e o build completo de
# kernel nao cabe no sandbox (2 nucleos). Aplicar a serie, que e' o que
# quebra com mais frequencia quando se edita um patch, cabe folgado.
#
# Uso:
#   tools/verify_series.sh                # baixa a base em /tmp e valida
#   tools/verify_series.sh --work-dir DIR # reaproveita uma base ja baixada
#   tools/verify_series.sh --keep         # nao apaga a base no fim
#
# Saida: relatorio por patch; exit 1 no primeiro que falhar.

set -u

BASE_REPO=${BASE_REPO:-https://github.com/aosp-mirror/kernel_common}
BASE_COMMIT=${BASE_COMMIT:-1afe39edbe66c201d26f23f2e3396583238f6842}
AQUI=$(cd "$(dirname "$0")/.." && pwd)
SERIE="$AQUI/patches-6.18"

WORK=""
MANTER=0
while [ $# -gt 0 ]; do
	case "$1" in
	--work-dir) WORK=$2; shift 2 ;;
	--keep) MANTER=1; shift ;;
	-h|--help) sed -n '2,20p' "$0"; exit 0 ;;
	*) echo "argumento desconhecido: $1" >&2; exit 2 ;;
	esac
done

if [ ! -d "$SERIE" ]; then
	echo "sem $SERIE" >&2
	exit 2
fi

PATCHES=$(ls "$SERIE"/*.patch | sort)
TOTAL=$(echo "$PATCHES" | wc -l | tr -d ' ')
echo "serie: $TOTAL patches em $SERIE"
echo "base:  $BASE_REPO @ ${BASE_COMMIT:0:12}"

# 1. caminhos que a serie toca
LISTA=$(mktemp)
for p in $PATCHES; do
	sed -n 's|^diff --git a/\([^ ]*\) b/.*|\1|p' "$p"
done | sort -u > "$LISTA"
echo "arquivos tocados: $(wc -l < "$LISTA" | tr -d ' ')"

# 2. base esparsa (sem historico, sem blobs desnecessarios)
if [ -z "$WORK" ]; then
	WORK=$(mktemp -d /tmp/kernel-verify.XXXXXX)
	NOVO=1
else
	NOVO=0
fi

if [ ! -d "$WORK/.git" ]; then
	echo "== baixando a base (isso leva alguns minutos)"
	git init -q "$WORK"
	git -C "$WORK" remote add origin "$BASE_REPO"
	git -C "$WORK" fetch -q --depth 1 --filter=blob:none origin "$BASE_COMMIT"
	git -C "$WORK" checkout -q FETCH_HEAD
	git -C "$WORK" sparse-checkout init --no-cone
	git -C "$WORK" sparse-checkout set --no-cone --stdin < "$LISTA"
fi

if [ -n "$(git -C "$WORK" status --porcelain)" ]; then
	echo "== a base em $WORK tem alteracoes; use um diretorio limpo" >&2
	exit 2
fi

# 3. aplica a serie
cd "$WORK" || exit 2
git config user.name "verify_series"
git config user.email "verify@local"
FALHOU=0
N=0
for p in $PATCHES; do
	N=$((N + 1))
	nome=$(basename "$p")
	if saida=$(git am --keep-cr "$p" 2>&1); then
		:
	else
		echo "FALHOU [$N/$TOTAL] $nome"
		echo "$saida" | sed 's/^/    /' | head -20
		git am --abort 2>/dev/null
		FALHOU=1
		break
	fi
done

cd "$AQUI" || exit 2

if [ "$FALHOU" -eq 0 ]; then
	echo "OK: $N/$N patches aplicaram limpo"
	echo "tip: $(git -C "$WORK" log --oneline -1)"
else
	echo "serie quebrada no patch $N" >&2
fi

if [ "$MANTER" -eq 1 ]; then
	echo "arvore: $WORK"
fi
if [ "$MANTER" -eq 0 ] && [ "$NOVO" -eq 1 ]; then
	echo "(apagando $WORK; use --keep para preservar)"
	rm -rf "$WORK"
fi
rm -f "$LISTA"
exit "$FALHOU"
