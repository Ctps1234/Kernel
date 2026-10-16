#!/bin/sh
# Configura a árvore do kernel com o fragmento de configuração do port
# Khaje/topaz (config/topaz-khaje.config) sobre o defconfig GKI.
#
# Falha (exit != 0) se algum símbolo do port não ficar habilitado no .config
# final, o que normalmente significa dependência não satisfeita na base 6.12.
#
# Uso:
#   tools/configure_kernel.sh /path/para/basekernel [config/fragmento.config]
set -eu

KERNEL_TREE=${1:?uso: configure_kernel.sh <kernel-tree> [fragmento.config]}
FRAGMENT=${2:-"$(dirname "$0")/../config/topaz-khaje.config"}
FRAGMENT=$(cd "$(dirname "$FRAGMENT")" && pwd)/$(basename "$FRAGMENT")

# Símbolos que precisam estar ativos para o port funcionar.
REQUIRED="ARCH_QCOM QCOM_SMD_RPM COMMON_CLK_QCOM SM_GCC_6225 SM_DISPCC_6225 SM_GPUCC_6225 SM_DEBUGCC_6225 PINCTRL_MSM PINCTRL_KHAJE INTERCONNECT_QCOM INTERCONNECT_QCOM_BENGAL REGULATOR_QCOM_SMD_RPM PHY_QCOM_QMP_UFS"

cd "$KERNEL_TREE"

# O merge_config.sh chama `make` internamente; sem ARCH/CROSS_COMPILE no
# ambiente ele configuraria para a arquitetura do host e perderia todos os
# símbolos arm64 do port.
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-

echo "== defconfig GKI =="
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig

echo "== mesclando $FRAGMENT =="
if ! ./scripts/kconfig/merge_config.sh -O . .config "$FRAGMENT"; then
    echo "AVISO: merge_config.sh reportou problemas (ver mensagens acima)" >&2
fi

echo "== olddefconfig =="
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig

echo "== conference dos símbolos do port Khaje =="
missing=0
for sym in $REQUIRED; do
    if grep -q "^CONFIG_${sym}=y" .config; then
        echo "  ok      CONFIG_${sym}=y"
    else
        echo "  FALTANDO CONFIG_${sym} (dependência não satisfeita?)" >&2
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    echo "ERRO: o fragmento de configuração não habilitou todos os símbolos do port" >&2
    exit 1
fi

echo "configuração do port concluída"
