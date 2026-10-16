# SPDX-License-Identifier: GPL-2.0
#
# Khaje (Qualcomm SM6225) — Redmi Note 12 4G (topaz) / Redmi Note 13 4G (tapas)
#
# Par confirmado no aparelho: base Khaje (board id 0x10022) + overlay de
# board topaz (board id 0x30022) ou tapas (0x20022).

dtb-y += khaje-idp-nopmi.dtb

# DTBs compostos: base Khaje + overlay de board.
khaje-idp-nopmi-topaz-dtbs := khaje-idp-nopmi.dtb topaz-khaje-idp-nopmi-overlay.dtbo
dtb-y += khaje-idp-nopmi-topaz.dtb

khaje-idp-nopmi-tapas-dtbs := khaje-idp-nopmi.dtb tapas-khaje-idp-nopmi-overlay.dtbo
dtb-y += khaje-idp-nopmi-tapas.dtb

# Variantes sm5602 (board ids 0x3002f/0x2002f) mantidas para referência.
khaje-idp-nopmi-topaz-sm5602-dtbs := khaje-idp-nopmi.dtb topaz-sm5602-khaje-idp-nopmi-overlay.dtbo
dtb-y += khaje-idp-nopmi-topaz-sm5602.dtb

khaje-idp-nopmi-tapas-sm5602-dtbs := khaje-idp-nopmi.dtb tapas-sm5602-khaje-idp-nopmi-overlay.dtbo
dtb-y += khaje-idp-nopmi-tapas-sm5602.dtb

subdir-y += audio
subdir-y += camera
subdir-y += display
