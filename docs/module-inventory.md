# Inventário de módulos ativos — topaz/tapas

## Fonte

Arquivo recebido: `google_drive/topaz-module-map.txt`. Contém `/proc/modules`, `vendor_dlkm/modules.load`, `vendor_dlkm/modules.dep` e os arquivos equivalentes disponíveis em `system_dlkm`.

## Resumo do estado em execução

- `/proc/modules`: 320 módulos carregados no momento da captura.
- `/vendor_dlkm/lib/modules/modules.load`: 238 entradas.
- `/system_dlkm/lib/modules/5.15.94/modules.load`: 2 entradas (`zsmalloc.ko`, `zram.ko`).
- Os quatro módulos consultados separadamente (`msm_kgsl`, `msm_drm`, `camera`, `qca_cld3_wlan`) reportam `vermagic` `5.15.41 SMP preempt mod_unload modversions aarch64`.
- O arquivo `modules.load` não explica sozinho todos os módulos ativos; os módulos de outros ramdisks/load lists ainda precisam ser mapeados.

## Drivers de dispositivo realmente ativos

| Função | Módulo ativo | Dependências indicadas em `modules.dep` |
|---|---|---|
| GPU | `msm_kgsl` | `msm_performance`, `qcom_va_minidump`, `qcom-dcvs`, `mdt_loader` |
| Display | `msm_drm` | `panel_event_notifier`, `qcom_va_minidump` |
| Câmera | `camera` | `cx_ipeak`, `leds-qti-flash`, `qti_battery_charger`, `panel_event_notifier`, `pmic_glink` |
| Wi‑Fi | `wlan` (arquivo `qca_cld3_wlan.ko`) | `icnss2`, `wlan_firmware_service`, `cnss_prealloc`, `cnss_nl`, `cnss_utils`, `cfg80211`, `qcom_ramdump` |
| Touchscreen | `focaltech_ts_i2c` | `lct_tp`, `nopmi_chg`, `qcom-pmic-voter`, `xiaomi_touch_game`, `panel_event_notifier`, `xm_adapter_class` |
| Vídeo | `msm_video` | `msm-mmrm`, `mdt_loader` |
| Impressão digital | `goodix_fp` | sem dependência mostrada no `modules.dep` |

`goodix_ts_9896` aparece no `modules.load`, mas não em `/proc/modules`; portanto, não estava carregado durante a captura. A FDT descreve nós FocalTech e Goodix, enquanto o driver FocalTech estava efetivamente ativo.

## Prioridade para o port 6.12

1. **Obrigatórios para o caminho Android atual:** GPU (`msm_kgsl`), display (`msm_drm`), câmera (`camera`) e Wi‑Fi (`wlan`/QCACLD), além do stack de touch FocalTech.
2. **Dependências a preservar/portar junto:** `mdt_loader`, `qcom_va_minidump`, `qcom-dcvs`, `icnss2`, `wlan_firmware_service`, `cfg80211`, `panel_event_notifier`, `pmic_glink` e os serviços QMI/QRTR correspondentes.
3. Os módulos são binários 5.15.41; este inventário descreve o que o sistema usa, mas não fornece o source nem torna os `.ko` compatíveis com o KMI 6.12.
