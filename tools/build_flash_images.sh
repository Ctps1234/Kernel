#!/bin/sh
# Monta as imagens flashaveis do port 6.12 (topaz/tapas) a partir das
# imagens originais do aparelho e dos artefatos do CI.
#
# Entradas (fora do Git):
#   google_drive/boot_b.img         boot original (particao boot, slot B)
#   google_drive/vendor_boot_b.img  vendor_boot original
#   google_drive/dtbo_b.img         dtbo original
#   <ci-artifacts>/Image-khaje      kernel 6.12 compilado no CI
#   <ci-artifacts>/dtbs/.../khaje-idp-nopmi.dtb
#   <ci-artifacts>/dtbs/.../topaz-khaje-idp-nopmi-overlay.dtbo
#   <ci-artifacts>/initramfs/initramfs.cpio  (job initramfs do CI)
#
# Saidas: google_drive/out/*.img
#
# Uso: tools/build_flash_images.sh [dir-ci-artifacts]
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
CI_ART=${1:-${CI_ARTIFACTS_DIR:-$REPO/ci-artifacts}}
BLOBS=$REPO/google_drive
OUT=$BLOBS/out
DTBS=$CI_ART/dtbs/arch/arm64/boot/dts/qcom/khaje

for f in "$BLOBS/boot_b.img" "$BLOBS/vendor_boot_b.img" "$BLOBS/dtbo_b.img" \
         "$BLOBS/init_boot_b.img" \
         "$CI_ART/Image-khaje" "$DTBS/khaje-idp-nopmi.dtb" \
         "$DTBS/topaz-khaje-idp-nopmi-overlay.dtbo" \
         "$CI_ART/initramfs/initramfs.cpio"; do
    [ -f "$f" ] || { echo "faltando: $f" >&2; exit 1; }
done

mkdir -p "$OUT"
cd "$REPO"

echo "== conferindo os originais (ida e volta) =="
python3 tools/bootimg.py roundtrip "$BLOBS/boot_b.img" /tmp/rt-boot.img
python3 tools/bootimg.py roundtrip "$BLOBS/vendor_boot_b.img" /tmp/rt-vendor-boot.img
python3 tools/bootimg.py roundtrip "$BLOBS/dtbo_b.img" /tmp/rt-dtbo.img
python3 tools/bootimg.py roundtrip "$BLOBS/init_boot_b.img" /tmp/rt-init-boot.img
rm -f /tmp/rt-boot.img /tmp/rt-vendor-boot.img /tmp/rt-dtbo.img /tmp/rt-init-boot.img

echo "== boot: kernel 6.12 =="
python3 tools/bootimg.py set-kernel --image "$BLOBS/boot_b.img" \
    --kernel "$CI_ART/Image-khaje" --out "$OUT/boot_b-khaje-6.12.img"

echo "== vendor_boot: DTB base Khaje 6.12 (FDT#1, msm-id 0x206) =="
python3 tools/bootimg.py set-dtb --image "$BLOBS/vendor_boot_b.img" --index 1 \
    --dtb "$DTBS/khaje-idp-nopmi.dtb" --out "$OUT/vendor_boot_b-khaje-6.12.img"

echo "== dtbo: overlay topaz (entrada 51) =="
python3 tools/bootimg.py set-overlay --image "$BLOBS/dtbo_b.img" --index 51 \
    --dtbo "$DTBS/topaz-khaje-idp-nopmi-overlay.dtbo" --out "$OUT/dtbo_b-khaje-6.12.img"

echo "== init_boot: ramdisk minima (init + busybox) =="
python3 tools/bootimg.py set-ramdisk --image "$BLOBS/init_boot_b.img" \
    --ramdisk "$CI_ART/initramfs/initramfs.cpio" \
    --out "$OUT/init_boot_b-khaje-minimal.img"

echo "== manifesto =="
( cd "$OUT" && sha256sum ./*.img ) | tee "$OUT/SHA256SUMS"

echo
echo "ATENCAO: as imagens ainda nao estao assinadas. O rodape AVB das"
echo "particoes originais fica obsoleto apos a troca de conteudo; e preciso"
echo "flashear com verificacao desabilitada (vbmeta com --disable-verity"
echo "--disable-verification) e com o bootloader desbloqueado."
