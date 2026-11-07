#!/usr/bin/env bash
# Roda, em sequencia, todos os gates locais da serie 6.18.
#
# Existe porque o CI nao e' acionavel daqui (workflow_dispatch da 403 e
# os artefatos/logs nao baixam), mas as checagens que pegam os erros de
# verdade cabem no sandbox. O que este script NAO faz: compilar kernel e
# rodar dtbs_check - isso continua so' no CI.
#
#   1. patch_lint.py          contagens de hunk de todo patch
#   2. verify_series.sh       aplica a serie inteira na base fixada
#   3. audit_dts_pairs.py     pares "*-names"/lista e pins->function
#   4. audit_compatibles.py   driver sem no' / tabela de maquina
#   5. audit_regulators.py    min/init/max dos rails contra o FDT real
#
# Uso: tools/check_all.sh [--sem-verify] [--verboso]
#
# Sai 0 so' se tudo passar. A arvore da verificacao fica em /tmp
# (kernel-verify.XXXXXX) para inspecao; o caminho e' impresso no fim.
set -uo pipefail

AQUI=$(cd "$(dirname "$0")/.." && pwd)
SEM_VERIFY=0
VERBOSO=""
for arg in "$@"; do
	case "$arg" in
	--sem-verify) SEM_VERIFY=1 ;;
	--verboso) VERBOSO="--verboso" ;;
	*) echo "argumento desconhecido: $arg" >&2; exit 2 ;;
	esac
done

FALHAS=0
ARVORE=""

passo() { printf '\n== %s\n' "$*"; }
ok()    { printf '   ok: %s\n' "$*"; }
falha() { printf '   FALHOU: %s\n' "$*"; FALHAS=$((FALHAS + 1)); }

passo "patch_lint (contagens de hunk)"
if py=$(python3 "$AQUI/tools/patch_lint.py" 2>&1); then
	ok "$(printf '%s' "$py" | tail -1)"
else
	falha "patch_lint"
	printf '%s\n' "$py" | tail -20
fi

if [ "$SEM_VERIFY" -eq 0 ]; then
	passo "verify_series (aplicacao da serie na base fixada)"
	if saida=$(bash "$AQUI/tools/verify_series.sh" --keep 2>&1); then
		ok "$(printf '%s' "$saida" | grep '^OK:' || true)"
		ok "$(printf '%s' "$saida" | grep '^tip:' || true)"
		ARVORE=$(printf '%s' "$saida" | sed -n 's/^arvore: //p')
	else
		falha "verify_series"
		printf '%s\n' "$saida" | tail -12
	fi
fi

if [ -n "$ARVORE" ] && [ -d "$ARVORE" ]; then
	passo "audit_dts_pairs ($ARVORE)"
	if saida=$(python3 "$AQUI/tools/audit_dts_pairs.py" --dir "$ARVORE" $VERBOSO 2>&1); then
		ok "$(printf '%s' "$saida" | tail -1)"
	else
		falha "audit_dts_pairs"
		printf '%s\n' "$saida" | tail -20
	fi

	passo "audit_compatibles ($ARVORE)"
	if saida=$(python3 "$AQUI/tools/audit_compatibles.py" --tree "$ARVORE" $VERBOSO 2>&1); then
		ok "$(printf '%s' "$saida" | tail -1)"
	else
		falha "audit_compatibles"
		printf '%s\n' "$saida" | tail -20
	fi
fi

passo "audit_regulators (rails contra o FDT do aparelho)"
if saida=$(python3 "$AQUI/tools/audit_regulators.py" $VERBOSO 2>&1); then
	ok "$(printf '%s' "$saida" | tail -1)"
else
	falha "audit_regulators"
	printf '%s\n' "$saida" | tail -20
fi

printf '\n'
if [ "$FALHAS" -eq 0 ]; then
	echo "TUDO OK (gates locais; build e dtbs_check continuam no CI)"
	[ -n "$ARVORE" ] && echo "arvore: $ARVORE"
	exit 0
fi
echo "$FALHAS gate(s) falharam"
[ -n "$ARVORE" ] && echo "arvore: $ARVORE"
exit 1
