#!/bin/sh
# collect_topaz_info.sh - coleta do topaz via adb sem tocar particoes.
#
# Uso:
#   tools/collect_topaz_info.sh [diretorio-de-saida]
#   COLLECT_RECOVERY=1 tools/collect_topaz_info.sh [diretorio]
#       (opcional; com root, tambem despeja recovery_<slot>.img
#        para /sdcard/Download do aparelho e faz pull dele)
#
# Nao executa fastboot, reboot, flash nem escreve em particao.
# A unica escrita possivel no aparelho e o arquivo temporario
# em /sdcard/Download quando COLLECT_RECOVERY=1 e explicitado.
# Sem root coleta o essencial; com root (Magisk) coleta tambem
# dmesg, hash do FDT ativo e regulator_summary.
#
# Privacidade: props sao coletadas uma a uma (sem getprop em
# massa) e cmdline/bootconfig passam por filtro de serial.
# O dmesg pode conter MACs/seriais de perifericos: revise os
# arquivos antes de compartilhar. Nada sai desta maquina.
set -u

OUT=${1:-./topaz-info}
mkdir -p "$OUT"

command -v adb >/dev/null 2>&1 || {
    echo "erro: adb nao encontrado no PATH" >&2
    exit 1
}
adb get-state >/dev/null 2>&1 || {
    echo "erro: nenhum aparelho autorizado via adb (adb devices)" >&2
    exit 1
}

echo "coletando em $OUT ..."

# --- identidade / estado (sem serial/IMEI de proposito) ---
{
    for prop in ro.product.model ro.product.device \
        ro.build.fingerprint ro.vendor.build.fingerprint \
        ro.build.version.release ro.build.version.sdk \
        ro.boot.slot_suffix ro.boot.verifiedbootstate \
        ro.boot.vbmeta.device_state ro.boot.flash.locked \
        ro.boot.hardware ro.board.platform ro.boot.baseband; do
        val=$(adb shell getprop "$prop" 2>/dev/null | tr -d '\r')
        printf '%s=%s\n' "$prop" "$val"
    done
} > "$OUT/props.txt"

adb shell uname -a > "$OUT/uname.txt" 2>&1 || true
adb shell cat /proc/cmdline 2>/dev/null \
    | sed -e 's/[^ ]*serial[^ ]*/REDACTED/g' > "$OUT/cmdline.txt" || true
# bootconfig usa uma atribuicao por linha; remover a linha inteira
# evita sobrar "androidboot.serialno = \"valor\"" so com chave ocultada.
adb shell cat /proc/bootconfig 2>/dev/null \
    | grep -Evi 'serial|imei|macaddr' > "$OUT/bootconfig.txt" || true

# --- particoes / storage ---
{
    echo "== /proc/partitions =="
    adb shell cat /proc/partitions 2>/dev/null
    echo
    echo "== /dev/block/by-name =="
    adb shell ls /dev/block/by-name 2>/dev/null
} > "$OUT/partitions.txt" 2>&1 || true
{
    for f in model vendor rev type; do
        printf '%s: ' "$f"
        adb shell cat "/sys/block/sda/device/$f" 2>/dev/null | tr -d '\r'
        echo
    done
} > "$OUT/ufs-device.txt" 2>&1 || true

# --- input (touch) ---
{
    adb shell getevent -i 2>/dev/null | head -n 200
    echo
    adb shell dumpsys input 2>/dev/null | head -n 120
} > "$OUT/input.txt" 2>&1 || true

# --- root: evidencias de runtime do kernel stock ---
ROOT=0
if adb shell su -c id 2>/dev/null | grep -q 'uid=0'; then
    ROOT=1
fi
echo "root=$ROOT" > "$OUT/root.txt"

if [ "$ROOT" = "1" ]; then
    adb shell su -c dmesg > "$OUT/dmesg-stock.txt" 2>&1 || true
    adb shell "su -c 'sha256sum /sys/firmware/fdt'" \
        > "$OUT/fdt-hash.txt" 2>&1 || true
    adb shell "su -c 'wc -c /sys/firmware/fdt'" \
        >> "$OUT/fdt-hash.txt" 2>&1 || true
    adb shell "su -c 'cat /sys/kernel/debug/regulator/regulator_summary'" \
        2>/dev/null | grep -E 'pm6125_l4|pm6125_l18' \
        > "$OUT/regulator-ufs-phy.txt" || true
    adb shell su -c lsmod > "$OUT/lsmod.txt" 2>&1 || true
    adb shell su -c lpdump 2>/dev/null | head -n 80 \
        > "$OUT/lpdump-head.txt" || true

    if [ "${COLLECT_RECOVERY:-0}" = "1" ]; then
        SLOT=$(adb shell getprop ro.boot.slot_suffix | tr -d '\r\n')
        IMG="recovery${SLOT}.img"
        echo "despejando $IMG (leitura da particao) ..."
        adb shell "su -c 'dd if=/dev/block/by-name/recovery${SLOT} of=/sdcard/Download/${IMG} bs=4M'" \
            > "$OUT/recovery-dump.log" 2>&1 || true
        adb shell "su -c 'sha256sum /sdcard/Download/${IMG}'" \
            > "$OUT/recovery-sha256-device.txt" 2>&1 || true
        adb pull "/sdcard/Download/${IMG}" "$OUT/${IMG}" >> "$OUT/recovery-dump.log" 2>&1 || true
        echo "copia tambem ficou no aparelho: /sdcard/Download/${IMG}"
    fi
else
    echo "sem root: dmesg/FDT/reguladores pulados (coleta basica ok)"
fi

# --- manifesto de hashes dos arquivos coletados ---
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$OUT" && for f in *; do
        [ -f "$f" ] && [ "$f" != "SHA256SUMS" ] && sha256sum "$f"
    done) > "$OUT/SHA256SUMS" || true
fi

echo "pronto. Revise $OUT antes de compartilhar (dmesg pode ter MACs)."
echo "Para o projeto, os arquivos-chave sao: props.txt, cmdline.txt,"
echo "bootconfig.txt, fdt-hash.txt, dmesg-stock.txt, partitions.txt"
