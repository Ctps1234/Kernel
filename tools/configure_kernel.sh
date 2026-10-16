#!/bin/sh
# Configura a árvore do kernel com o fragmento de configuração do port
# Khaje/topaz (config/topaz-khaje.config) sobre o defconfig GKI.
#
# Uso:
#   tools/configure_kernel.sh /path/para/basekernel [config/fragmento.config]
set -eu

KERNEL_TREE=${1:?uso: configure_kernel.sh <kernel-tree> [fragmento.config]}
FRAGMENT=${2:-"$(dirname "$0")/../config/topaz-khaje.config"}

cd "$KERNEL_TREE"

echo "== defconfig GKI =="
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig

echo "== mesclando $FRAGMENT =="
./scripts/kconfig/merge_config.sh -O . .config "$(cd "$(dirname "$FRAGMENT")" && pwd)/$(basename "$FRAGMENT")"

echo "== olddefconfig =="
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig

echo "== símbolos do port Khaje =="
grep -E "^CONFIG_(ARCH_QCOM|PINCTRL_KHAJE|SM_(GCC|DISPCC|GPUCC|DEBUGCC)_6225|INTERCONNECT_QCOM_BENGAL|REGULATOR_QCOM_SMD_RPM|PHY_QCOM_QMP_UFS|COMMON_CLK_RPMCC)=y" .config \
    || echo "ATENCAO: algum simbolo do port nao ficou habilitado"
