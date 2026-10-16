# Fontes de Device Tree para topaz/tapas (SM6225/Khaje)

Estas fontes foram importadas do repositório público

- `nodrawAlliance/android_kernel_xiaomi_sm6225-devicetrees`, branch `lineage-24.0`, commit `7581fa2ee9b8213f8989f329e11b642d17328a39` (atualizado em 2026-10-05).

O repositório é derivado da árvore de device tree Qualcomm R47 (`platform/vendor/qcom-opensource/devicetree`, commit `66167e56588bd7c0c9ec91e1e5c464512f6c4db6`) com overlays Xiaomi para `topaz`/`tapas` (Redmi Note 12 4G, board IDs `0x30022`/`0x20022`), o que coincide com o par FDT/DTBO confirmado neste projeto.

## Escopo importado

Apenas os arquivos necessários para a fundação de boot e periféricos de `topaz`/`tapas` foram copiados, preservando a estrutura `qcom/...`:

- base: `khaje.dtsi`, `khaje-idp.dtsi`, `khaje-idp-nopmi.dts`/`.dtsi`, `khaje-pinctrl.dtsi`, `khaje-regulator.dtsi`, `khaje-usb.dtsi`, `khaje-dma-heaps.dtsi`;
- overlays: `topaz-khaje-idp-nopmi-overlay.dts`, `tapas-khaje-idp-nopmi-overlay.dts`, variantes `sm5602`;
- dtsi topaz: `topaz-khaje-idp-nopmi.dtsi`, `topaz-pinctrl.dtsi`;
- SoC Bengal/Khaje: `bengal-*.dtsi`, `msm-arm-smmu-bengal.dtsi`, `msm-rdbg.dtsi`, `pm6125*.dtsi`, `pm8008.dtsi`;
- periféricos: `audio/`, `camera/`, `display/display/` (topaz/tapas);
- comum Xiaomi: `xiaomi-sm6225-common.dtsi` (raiz e subpastas).

## Adaptações já aplicadas

- Corrigida a referência de include em `display/display/topaz-sde-display-idp-nopmi.dtsi`: `dsi-panel-m7_...` → `dsi_panel_m7_...`, para corresponder aos nomes reais dos arquivos presentes.

## Ressalvas

- Estas fontes vêm de uma árvore de device tree Qualcomm R67, não do commit Android Common 6.12 fixado (`0efd3abd...`). Bindings, headers e compatíveis devem ser reconciliados com a série local 0001–0011 e validados com `dtc`/`dtbs_check` antes de build/boot.
- O overlay de display referencia painéis `m7_38_...` cujos arquivos existem, mas outros painéis alternativos (NT36672E etc.) podem não ser usados no aparelho; revisar.
- Drivers proprietários (KGSL, câmera vendor, QCACLD, FocalTech/Goodix) não são resolvidos por esta DT.
- Não compilar, flashar ou testar boot a partir destas fontes sem concluir a integração e a configuração GKI/defconfig.
- Manter os blobs privados em `google_drive/` fora do Git; estas fontes são públicas e podem ser versionadas.