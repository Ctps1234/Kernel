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

# Símbolos que precisam estar ativos (y) para o port funcionar.
REQUIRED="ARCH_QCOM QCOM_SMD_RPM COMMON_CLK_QCOM SM_GCC_6225 SM_DISPCC_6225 SM_GPUCC_6225 SM_DEBUGCC_6225 PINCTRL_MSM PINCTRL_KHAJE INTERCONNECT_QCOM INTERCONNECT_QCOM_BENGAL REGULATOR_QCOM_SMD_RPM SCSI_UFS_QCOM BLK_DEV_DM DM_VERITY F2FS_FS EROFS_FS USB_CONFIGFS USB_CONFIGFS_F_FS PSTORE_BLK QCOM_PANEL_EVENT_NOTIFIER DRM DRM_MSM DRM_MSM_DPU DRM_MSM_MDSS"
# Símbolos aceitáveis como módulo (o driver ainda é compilado).
ALLOWED_MOD="PHY_QCOM_QMP_UFS"

cd "$KERNEL_TREE"

# O kconfig e o build precisam saber a arquitetura-alvo.
export ARCH=arm64

# O compilador cruzado só é usado se estiver instalado: o job de device
# trees não precisa dele, e o kconfig aborta se ele não existir.
CROSS=${CROSS_COMPILE:-aarch64-linux-gnu-}
CROSS_ARGS=""
if command -v "${CROSS}gcc" >/dev/null 2>&1; then
    CROSS_ARGS="CROSS_COMPILE=${CROSS}"
    export CROSS_COMPILE="$CROSS"
    echo "usando compilador cruzado: ${CROSS}gcc"
else
    unset CROSS_COMPILE
    echo "compilador cruzado ausente; o kconfig usara o compilador do host"
fi

echo "== defconfig GKI =="
make ARCH=arm64 $CROSS_ARGS defconfig

echo "== mesclando $FRAGMENT =="
# Merge manual: o fragmento vem depois do .config, e no kconfig a última
# ocorrência de um símbolo prevalece (KCONFIG_ALLCONFIG).
MERGED=.merged-khaje.config
cat .config "$FRAGMENT" > "$MERGED"
# KCONFIG_ALLCONFIG só é honrado nos modos all*/alldefconfig; olddefconfig
# ignora o arquivo. O fragmento vem depois do .config e, no kconfig, a
# última ocorrência de um símbolo prevalece.
make ARCH=arm64 $CROSS_ARGS \
     KCONFIG_ALLCONFIG="$MERGED" alldefconfig
rm -f "$MERGED"

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
for sym in $ALLOWED_MOD; do
    if grep -q "^CONFIG_${sym}=y" .config; then
        echo "  ok      CONFIG_${sym}=y"
    elif grep -q "^CONFIG_${sym}=m" .config; then
        echo "  ok      CONFIG_${sym}=m (módulo; ainda compilado)"
    else
        echo "  FALTANDO CONFIG_${sym}" >&2
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    echo "ERRO: o fragmento de configuração não habilitou todos os símbolos do port" >&2
    exit 1
fi

echo "configuração do port concluída"
