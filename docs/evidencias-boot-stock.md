# Evidências do boot de stock (dmesg-boot.txt)

Fonte: `dmesg-boot.txt`, capturado logo após o boot do aparelho com o kernel de stock
(`5.15.211dexter1-g42deba085a84`, Android 13). O log bruto fica em `google_drive/` e **não é versionado**
(ver `.gitignore`). Seriais, MACs e identificadores não são copiados para este documento.

Este documento registra o que o log confirma sobre display, touch e Wi-Fi, e corrige pontos
das notas anteriores.

## Correções às notas anteriores

1. **Touch: o firmware de stock é o que o aparelho usa.** O arquivo
   `focaltech_ts_fw_samsung_ft3519t.bin` está em `/vendor/firmware/` no aparelho
   (`lista-touch-fw.txt`) e é carregado pelo driver de stock no boot. Antes eu tinha tratado o
   arquivo como “de outro aparelho”. Ele é o firmware do controlador.
2. **Touch: ID do chip é `0x5452`**, não só `0x54`. O log tem `verify id:0x5452`.
3. **Display: o PLL do DSI é rotulado `dsi_pll_5nm`.** Isso contradiz o PHY 14nm que está no
   fragmento (`DRM_MSM_DSI_14NM_PHY`). Ver “Pendências”.
4. **Wi-Fi: o caminho de stock é QCACLD-3 `v2.0.9.19I`**, não ath10k. O WLAN FW
   sobe (`icnss2: WLAN FW is ready: 0x587`).

## Display

- Painel ativo: nó `qcom,mdss_dsi_panel_m7_38_0c_0a_fhdp_video` (`m7 38 0c 0a video mode fhdp dsi panel`).
  O driver de stock é `msm_drm` com `mi_disp`. Mesmo com o nome `m7 38 0c 0a`, o IC do
  painel **não aparece no log**. Continua não identificado.
- Modo: 1080x2400, 120 Hz, `dsi_display_set_mode` com `hactive=1080 vactive=2400 fps=120`.
- Notas de DT: `qcom,mdss_dsi_panel_m7_38_0c_0a_fhdp_video` está ligado ao FDT de referência
  `qcom,sde-kms` e `qcom,dsi-phy-v4.1` (formato vendor).
- Mensagens `*ERROR* [msm-dsi-error]` em `dsi_panel_parse_cmd_sets_sub` (tipos 1, 5, 25 a 35):
  são erros de parse de cmd sets opcionais do vendor. Não confirmei impacto. O painel chega
  a bindar e a mudar de modo.
- `fallback to default te-pin-select`: o painel não tem a propriedade de TE. Não confirmado se afeta.
- `OF: graph: no port node found in /soc/qcom,dsi-display-primary`: vendor, sem impacto
  identificado no boot.
- Bootloader: `panel_info=1` na linha de comando.

## Touch

- Driver de stock: `fts_ts` (FocalTech, versão `V3.4 20211214`), I²C `1-0038` (adaptador i2c-1, endereço 0x38).
- `TP info: [Vendor]samsung [IC]ft3519t`, `verify id:0x5452`.
- IRQ GPIO 478, reset GPIO 484 (numeração global). No FDT: `focaltech,irq-gpio = <&tlmm 0x50>`
  (GPIO 80), `reset-gpio = <&tlmm 0x56>` (GPIO 86), `avdd-gpio = <&tlmm 0x24>` (GPIO 36).
  A diferença é constante (398) entre IRQ e reset. Provavelmente é o offset de base do TLMM, não confirmado.
- Tamanho de coordenadas: `display x(0 10799) y(0 23999)`. Confirma que o FDT de referência
  usa `display-coords` `0x2a2f 0x5dbf` (10799 e 23999), com `max-touch-number = 10`.
- Firmware: `fw version in tp:32, host:36`. O driver atualizou o firmware do controlador no boot.
- Não aparece `goodix,gt9896` nem `goodix-sunrise@5d` no log. O Goodix está no FDT, mas não é carregado.
- **Candidato upstream:** `drivers/input/touchscreen/edt-ft5x06.c` (base 6.12) tem a entrada
  `focaltech,ft5452` (`edt_ft5452_data`). Não confirmado: o driver de stock usa a família
  `fts_ts` e o chip é `0x5452`. Testar em hardware antes de adotar.

## Wi-Fi

- Stack de stock: `icnss2 c800000.qcom,icnss` (`Platform driver probed successfully`), PDR `msm/modem/wlan_pd`,
  `wlan: Loading driver v2.0.9.19I` (QCACLD-3), `wlan_hdd_state wlan major(477)`.
- WLAN FW: `Firmware build version : 324bffff`, `Board id: 0`, `Board version: 3a 0 0 0 0`.
- Reserva de memória: `wlan_msa_region@51900000` (1 MiB).
- Sem `ath10k` no log. O caminho upstream exige `ath10k/WCN3990/hw1.0/firmware-5.bin` e um
  board file. Não verifiquei se esses arquivos equivalem aos blobs do vendor (`wlanmdsp.mbn`,
  `bdwlan.*`, que são do QCACLD-3). A hipótese de reaproveitar os blobs do vendor no ath10k
  **não está verificada** e precisa de análise de formato antes de qualquer teste.
- Falhas de firmware opcional (`ipa_fws.*`, `sipa.bin`, `regulatory.db`, `venus.mbn`) são
  `-2` (arquivo ausente). Não são o bloqueio do Wi-Fi.

## Pendências

1. **PHY DSI:** decidir entre o PHY 14nm (upstream `qcom,sm6125-dsi-phy-14nm`, que está no
   fragmento) e o 7nm (`DRM_MSM_DSI_7NM_PHY`, que cobre “7nm/5nm/4nm” no Kconfig da base 6.12
   e tem `qcom,sm6375-dsi-phy-7nm`, `qcom,sm8350-dsi-phy-5nm` e `qcom,sm8450-dsi-phy-5nm`).
   O rótulo `dsi_pll_5nm` sugere o caminho 5nm/7nm, mas o rótulo pode ser só do vendor.
   Precisa de confirmação de SoC e de registros do PHY.
2. **Driver de touch:** `TOUCHSCREEN_EDT_FT5X06` não está no fragmento. Adicionar exige
   autorização do usuário, porque o fragmento foi autorizado só para display.
3. **IC do painel:** identificar pelo registro de ID do painel (leitura via `dsi`) ou pelo
   init do vendor. Até lá, o driver `panel-novatek-nt36672e` é só candidato.
4. **Wi-Fi:** decidir se o caminho é ath10k (exige firmware upstream, que não está no aparelho)
   ou se fica como “não resolvido” até haver fonte do QCACLD.
