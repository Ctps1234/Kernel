#!/bin/sh
# Monta as imagens de teste do port 6.18 (topaz) a partir das imagens
# da ROM atual do aparelho (Lunaris OS, dumps de 2026-11-04) e dos
# artefatos do CI (run google-kernel-build).
#
# Entradas (fora do Git):
#   google_drive/dump-lineage/boot_b.img         boot da Lunaris (slot B)
#   google_drive/dump-lineage/vendor_boot_b.img  vendor_boot da Lunaris
#   google_drive/dump-lineage/dtbo_b.img         dtbo da Lunaris
#   google_drive/dump-lineage/init_boot_b.img    init_boot da Lunaris
#   <ci-artifacts>/.../Image                     kernel 6.18 do CI
#   <ci-artifacts>/.../sm6225-xiaomi-topaz.dtb   nosso DTB (SoC+board)
#
# Saidas: google_drive/out-618/*.img
#   boot_b-618.img        kernel trocado pelo 6.18
#   vendor_boot_b-618.img FDT#1 (dtb_idx) trocado pelo nosso DTB e
#                         bootconfig usbcontroller=4e00000.usb
#                         (nosso core DWC3 chama-se usb@4e00000)
#   dtbo_b-618.img        entrada 51 (dtbo_idx) neutralizada com FDT
#                         vazio (o overlay downstream nao pode ser
#                         aplicado sobre o DTB mainline)
#   init_boot_b-618.img   copia identica: no Nivel 0 Android mantemos
#                         a ramdisk generica da ROM
#
# Uso: tools/build_flash_images_618.sh [dir-ci-artifacts]
#
# NAO GRAVAR sem autorizacao explicita e sem fechar o checklist de
# seguranca de docs/aosp16-lineage-crossref.md (Nivel 0).
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
CI_ART=${1:-${CI_ARTIFACTS_DIR:-$REPO/ci-artifacts-618}}
BLOBS=$REPO/google_drive/dump-lineage
OUT=$REPO/google_drive/out-618

IMAGE=$(find "$CI_ART" -name Image -type f | head -n1)
DTB=$(find "$CI_ART" -name sm6225-xiaomi-topaz.dtb -type f | head -n1)

for f in "$BLOBS/boot_b.img" "$BLOBS/vendor_boot_b.img" "$BLOBS/dtbo_b.img" \
         "$BLOBS/init_boot_b.img" "$IMAGE" "$DTB"; do
    [ -n "$f" ] && [ -f "$f" ] || { echo "faltando: $f" >&2; exit 1; }
done

mkdir -p "$OUT"
cd "$REPO"

echo "kernel 6.18: $IMAGE"
echo "dtb topaz:   $DTB"

echo "== conferindo os originais (ida e volta) =="
for img in boot_b vendor_boot_b dtbo_b init_boot_b; do
    python3 tools/bootimg.py roundtrip "$BLOBS/$img.img" /tmp/rt-$img.img
    rm -f /tmp/rt-$img.img
done

echo "== boot: kernel 6.18 =="
python3 tools/bootimg.py set-kernel --image "$BLOBS/boot_b.img" \
    --kernel "$IMAGE" --out "$OUT/boot_b-618.img"

echo "== dtb: injeta qcom,msm-id/board-id (selecao de FDT do ABL) =="
python3 tools/fdt_inject_ids.py --dtb "$DTB" \
    --vendor-boot "$BLOBS/vendor_boot_b.img" --index 1 \
    --out /tmp/topaz-618-ids.dtb

echo "== vendor_boot: nosso DTB no FDT#1 (msm-id 0x206) =="
python3 tools/bootimg.py set-dtb --image "$BLOBS/vendor_boot_b.img" --index 1 \
    --dtb /tmp/topaz-618-ids.dtb --out /tmp/vendor_boot_b-618-dtb.img
rm -f /tmp/topaz-618-ids.dtb

echo "== vendor_boot: bootconfig usbcontroller=4e00000.usb =="
python3 tools/bootimg.py set-bootconfig --image /tmp/vendor_boot_b-618-dtb.img \
    --key androidboot.usbcontroller --value 4e00000.usb \
    --out "$OUT/vendor_boot_b-618.img"
rm -f /tmp/vendor_boot_b-618-dtb.img

echo "== dtbo: entrada 51 neutralizada (overlay vazio) =="
python3 tools/empty_overlay.py --dtbo "$BLOBS/dtbo_b.img" --index 51 \
    --out "$OUT/dtbo_b-618.img"

echo "== init_boot: copia identica da ROM =="
cp "$BLOBS/init_boot_b.img" "$OUT/init_boot_b-618.img"

echo "== manifesto =="
( cd "$OUT" && sha256sum ./*.img ) | tee "$OUT/SHA256SUMS"

echo
echo "ATENCAO: imagens de TESTE, geradas sem nenhuma validacao em hardware."
echo "O vbmeta da Lunaris usa flags=3 (AVB desligado), mas NAO grave antes"
echo "de fechar o checklist do Nivel 0 (backups, /data wrappedkey, plano"
echo "de retorno) e sem autorizacao explicita do dono do aparelho."
