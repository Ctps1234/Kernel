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
| Display | `msm_drm` | `panel_event_notifier` (helper portado em 0015; sem produtor DSI/DPU) e `qcom_va_minidump` (pendente) |
| Câmera | `camera` | `cx_ipeak`, `leds-qti-flash`, `qti_battery_charger`, `panel_event_notifier`, `pmic_glink` |
| Wi‑Fi | `wlan` (arquivo `qca_cld3_wlan.ko`) | `icnss2`, `wlan_firmware_service`, `cnss_prealloc`, `cnss_nl`, `cnss_utils`, `cfg80211`, `qcom_ramdump` |
| Touchscreen | `focaltech_ts_i2c` | `lct_tp`, `nopmi_chg`, `qcom-pmic-voter`, `xiaomi_touch_game`, `panel_event_notifier`, `xm_adapter_class` |
| Vídeo | `msm_video` | `msm-mmrm`, `mdt_loader` |
| Impressão digital | `goodix_fp` | sem dependência mostrada no `modules.dep` |

A comparação do módulo `camera` carregado com a fonte Spectra e o alvo 6.12 está em [`camera-port-audit.md`](camera-port-audit.md). A comparação da pilha WLAN carregada com a fonte QCACLD/ICNSS2 e o alvo 6.12 está em [`wifi-port-audit.md`](wifi-port-audit.md).

`goodix_ts_9896` aparece no `modules.load`, mas não em `/proc/modules`; portanto, não estava carregado durante a captura. A FDT descreve nós FocalTech e Goodix, enquanto o driver FocalTech estava efetivamente ativo.

### Áudio e ADSP observados na captura

O `/proc/modules` do arquivo recebido mostra carregados os componentes de áudio/ADSP abaixo:

- **Máquina, macros, codec e transporte:** `machine_dlkm`, `rx_macro_dlkm`, `tx_macro_dlkm`, `va_macro_dlkm`, `bolero_cdc_dlkm`, `wcd937x_dlkm`, `wcd937x_slave_dlkm`, `wcd9xxx_dlkm`, `wcd_core_dlkm`, `mbhc_dlkm`, `swr_ctrl_dlkm`, `swr_dlkm`, `snd_event_dlkm` e `pinctrl_lpi_dlkm`.
- **DSP/QDSP6:** `audio_pkt_dlkm`, `audio_prm_dlkm`, `spf_core_dlkm`, `gpr_dlkm`, `adsp_loader_dlkm`, `audpkt_ion_dlkm`, `q6_dlkm`, `q6_notifier_dlkm`, `q6_pdr_dlkm`, `qcom_q6v5_pas` e `qcom_q6v5`.
- **Amplificadores:** `fs1815_dlkm`, `aw87xxx_dlkm` e `sipa_dlkm`.
- **WSA881x:** `wsa881x_analog_dlkm` também está carregado. O `modules.dep` registra esse módulo como dependência de `wcd_core_dlkm`; isso pode explicar seu carregamento mesmo sem instância de hardware. No FDT Topaz examinado, os nós WSA881x estão desabilitados e `qcom,wsa-max-devs` é zero.

A presença em `/proc/modules` prova que o módulo foi carregado, não que um dispositivo correspondente tenha associado/probado nem que tenha sido usado por uma rota ALSA. Para isso, cruzar o FDT ativo com `sysfs`/logs de probe e estado do card. A comparação dos contratos de áudio está em [`audio-port-audit.md`](audio-port-audit.md).

## Prioridade para o port 6.12

1. **Obrigatórios para o caminho Android atual:** GPU (`msm_kgsl`), display (`msm_drm`), câmera (`camera`) e Wi‑Fi (`wlan`/QCACLD), além do stack de touch FocalTech.
2. **Dependências a preservar/portar junto:** `mdt_loader`, `qcom_va_minidump`, `qcom-dcvs`, `icnss2`, `wlan_firmware_service`, `cfg80211`, `panel_event_notifier` (API portado em 0015, sem produtor), `pmic_glink` e os serviços QMI/QRTR correspondentes.
3. Os módulos são binários 5.15.41; este inventário descreve o que o sistema usa, mas não fornece o source nem torna os `.ko` compatíveis com o KMI 6.12.
