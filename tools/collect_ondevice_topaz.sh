#!/system/bin/sh
# collect_ondevice_topaz.sh - coleta no proprio topaz, sem PC/adb.
#
# Uso, num terminal com root (ex. Termux apos conceder root no Magisk):
#   su
#   sh /sdcard/Download/collect_ondevice_topaz.sh
#
# Com dump de leitura da particao recovery do slot ativo:
#   su
#   COLLECT_RECOVERY=1 sh /sdcard/Download/collect_ondevice_topaz.sh
#
# Saida padrao: /sdcard/Download/topaz-info
# Um diretorio diferente pode ser passado como primeiro argumento.
#
# Nao executa reboot, fastboot ou flash e nao escreve em nenhuma
# particao. Ele grava apenas os arquivos de coleta no diretorio de
# saida; no modo COLLECT_RECOVERY=1, tambem grava ali a imagem lida
# da particao recovery.
#
# Privacidade: nao usa getprop em massa; coleta propriedades uma a
# uma, sem serial/IMEI. /proc/bootconfig tem as linhas com
# serial/imei/macaddr removidas. O dmesg pode conter MACs ou
# identificadores de perifericos: revise antes de compartilhar.
set -u
umask 022

PATH="/system/bin:/system/xbin:/vendor/bin:/vendor/xbin:/odm/bin:/sbin:${PATH:-}"
export PATH

OUT=${1:-/sdcard/Download/topaz-info}

command -v getprop >/dev/null 2>&1 || {
    echo "erro: getprop nao encontrado; rode este script no Android." >&2
    exit 1
}

UID_NOW=$(id -u 2>/dev/null || echo desconhecido)
if [ "$UID_NOW" != "0" ]; then
    echo "erro: este script precisa rodar como root (uid atual: $UID_NOW)." >&2
    echo "No Termux ou terminal, rode primeiro: su" >&2
    echo "Depois rode novamente: sh /sdcard/Download/collect_ondevice_topaz.sh" >&2
    exit 1
fi

mkdir -p "$OUT" || {
    echo "erro: nao consegui criar o diretorio $OUT" >&2
    exit 1
}

echo "coletando em $OUT ..."
date > "$OUT/collected-at.txt" 2>&1 || true
id > "$OUT/root.txt" 2>&1 || true

# --- identidade / estado (sem serial/IMEI de proposito) ---
{
    for prop in ro.product.model ro.product.device \
        ro.build.fingerprint ro.vendor.build.fingerprint \
        ro.build.version.release ro.build.version.sdk \
        ro.boot.slot_suffix ro.boot.verifiedbootstate \
        ro.boot.vbmeta.device_state ro.boot.flash.locked \
        ro.boot.hardware ro.board.platform ro.boot.baseband; do
        printf '%s=%s\n' "$prop" "$(getprop "$prop" 2>/dev/null)"
    done
} > "$OUT/props.txt"

uname -a > "$OUT/uname.txt" 2>&1 || true
cat /proc/cmdline 2>/dev/null \
    | sed -e 's/[^ ]*serial[^ ]*/REDACTED/g' -e 's/[^ ]*cpuid[^ ]*/REDACTED/g' > "$OUT/cmdline.txt" || true
if [ -f /proc/bootconfig ]; then
    # bootconfig usa uma atribuicao por linha; remover a linha inteira
    # evita sobrar 'androidboot.serialno = "valor"' so com chave ocultada.
    grep -Evi 'serial|imei|macaddr|cpuid' /proc/bootconfig \
        > "$OUT/bootconfig.txt" || true
else
    : > "$OUT/bootconfig.txt"
fi

# --- particoes / storage ---
{
    echo "== /proc/partitions =="
    cat /proc/partitions 2>/dev/null
    echo
    echo "== /dev/block/by-name =="
    ls -l /dev/block/by-name 2>/dev/null || ls /dev/block/by-name 2>/dev/null
} > "$OUT/partitions.txt" 2>&1 || true
{
    for f in model vendor rev type; do
        printf '%s: ' "$f"
        cat "/sys/block/sda/device/$f" 2>/dev/null
        echo
    done
} > "$OUT/ufs-device.txt" 2>&1 || true

# --- input (touch) ---
{
    getevent -i 2>/dev/null | head -n 200
    echo
    dumpsys input 2>/dev/null | head -n 120
} > "$OUT/input.txt" 2>&1 || true

# --- evidencias de runtime do kernel stock (root) ---
dmesg > "$OUT/dmesg-stock.txt" 2>&1 || true
sha256sum /sys/firmware/fdt > "$OUT/fdt-hash.txt" 2>&1 || true
wc -c /sys/firmware/fdt >> "$OUT/fdt-hash.txt" 2>&1 || true
if [ -f /sys/kernel/debug/regulator/regulator_summary ]; then
    grep -E 'pm6125_l4|pm6125_l18' \
        /sys/kernel/debug/regulator/regulator_summary \
        > "$OUT/regulator-ufs-phy.txt" || true
else
    echo "regulator_summary indisponivel (debugfs nao montado)" \
        > "$OUT/regulator-ufs-phy.txt"
fi
(lsmod 2>/dev/null || cat /proc/modules 2>/dev/null) \
    > "$OUT/lsmod.txt" 2>&1 || true
lpdump 2>/dev/null | head -n 80 > "$OUT/lpdump-head.txt" || true

# --- opcional: dump somente-leitura da recovery do slot ativo ---
if [ "${COLLECT_RECOVERY:-0}" = "1" ]; then
    SLOT=$(getprop ro.boot.slot_suffix 2>/dev/null)
    IMG="recovery${SLOT}.img"
    PART="/dev/block/by-name/recovery${SLOT}"
    echo "lendo $PART para $OUT/$IMG ..."
    if [ -e "$PART" ]; then
        dd if="$PART" of="$OUT/$IMG" bs=4M \
            > "$OUT/recovery-dump.log" 2>&1 || true
        sync
        sha256sum "$OUT/$IMG" > "$OUT/recovery-sha256-device.txt" 2>&1 || true
    else
        echo "particao nao encontrada: $PART" > "$OUT/recovery-dump.log"
    fi
fi

# --- manifesto de hashes dos arquivos coletados ---
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$OUT" && for f in *; do
        [ -f "$f" ] && [ "$f" != "SHA256SUMS" ] && sha256sum "$f"
    done) > "$OUT/SHA256SUMS" || true
fi

chmod 0644 "$OUT"/* 2>/dev/null || true

echo
echo "pronto: $OUT"
ls -l "$OUT" 2>/dev/null || true
echo
echo "Revise antes de compartilhar (dmesg pode ter MACs)."
echo "Arquivos-chave: props.txt, cmdline.txt, bootconfig.txt,"
echo "fdt-hash.txt, dmesg-stock.txt, partitions.txt e lpdump-head.txt"
