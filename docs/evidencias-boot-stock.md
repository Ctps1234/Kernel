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

## Painel m7: identificação do IC (investigação de 2026-10-13)

Estado: **IC não identificado.** Nenhuma hipótese foi confirmada.

- **Pista do irmão k7.** O driver MTK `dsi_panel_k7_38_0c_0a_fhdp_video.c` (repositório público
  `agostino64/android_kernel_xiaomi_mtk`) lê o ID com `0x82` e identifica o IC como **ICNL9911C**
  (esperado `0x31 0x41`). É a mesma convenção de nome "38 0c 0a", mas é outro painel.
- **Hipótese descartada 1: ICNL9911C.** A tabela de init do k7 não tem nenhum `0xB6`, e o m7 da stock
  começa com `b6 30 6b 00 06 03 0a 13 1a 6c 18 19 02`. Também usa `f0 5a 59` (k7) contra `f0 5a 5a` (m7).
  Não confirma o mesmo IC.
- **Hipótese descartada 2: NT36672E.** `drivers/gpu/drm/panel/panel-novatek-nt36672e.c` (base 6.12) começa
  com `b0 00` e `c1` com 16 bytes, o que não bate com a sequência do m7. Não é o mesmo IC.
- **Base 6.12:** não há driver upstream `chipone`/`icnl` (busca em `drivers/gpu/drm/panel/`).
- **Dmesg e linha de comando:** nenhum nome de IC ou ID de painel aparece no boot.
- **`lista-vendor-device.txt`:** sem arquivo de painel ou display.

Para fechar a identificação, falta uma destas informações:
1. Nome do IC gravado na etiqueta ou na FPC do painel (foto, sem abrir o aparelho).
2. Leitura do ID do DDIC (comandos DCS `0xDA`/`0xDB`/`0xDC` ou `0x04`) feita pelo driver de stock.
3. Saída de `dumpsys display` no Termux ou em um app de informações de hardware, se o IC aparecer lá.

### Resultado de dumpsys e getprop (2026-10-13)

- `dumpsys display`: painel "Tela integrada", 1080x2400, modos 120/90/60 Hz, `manufacturerPnpId=QCM`.
  **Nome do IC nao aparece.** A configuracao do display e lida de
  `/vendor/etc/displayconfig/display_id_4630946444529356673.xml`. Ainda nao foi lida.
- `getprop`: `ro.vendor.display.type=oled`, o que bate com o painel de video.
- O build em execucao e RisingOS 9 para o codinome `tapas`. Confirmado pelo usuario: `topaz` e `tapas` sao o
  mesmo aparelho e usam o mesmo kernel; so o NFC muda. Logo, essas propriedades valem como evidencia para `topaz`.

## Engenharia reversa do vendor_boot e do dtbo_b (IC do painel m7 continua nao confirmado)

Feita sem tocar no aparelho. Arquivos locais em `google_drive/` (gitignored); extracoes em `/tmp`.

- **vendor_boot_b.img** (`VNDRBOOT` v4). Ramdisk vendor (LZ4 legacy) extraido: 266 arquivos, 258 `.ko`.
- **msm_drm.ko** (driver de display do vendor) tem a logica `mi_disp` de ID de painel: `mi,panel-id`,
  `mi_get_panel_id_by_dsi_panel`, `panel_build_id`, e a mensagem `mi,panel-id not specified`.
  O FDT de referencia **nao define** `mi,panel-id` nem build-id para o `m7`, entao esse caminho nao le o IC.
- **topaz-module-map.txt**: sem modulo de painel separado (so `dispcc-khaje.ko` e `panel_event_notifier.ko`).
  O codigo do `m7` esta dentro do `msm_drm`.
- **dtbo_b.img** (FDT overlay, tabela `d7b7ab1e`, 52 entradas, 4096 bytes de pagina). Os overlays definem
  os paineis `m7 38 0c 0a` e `m7 38 0c 0b` (`qcom,mdss-dsi-panel-name` com texto
  "m7 38 0c 0a video mode fhdp dsi panel"), alem de `nt36672e` (120/90 Hz) e `td4330`.
  Busca por `icnl`, `chipone`, `ilitek`, `hx83`, `ili9`, `panel-id`, `build-id` nos DTBs: **nenhum nome de IC
  para o `m7`**. O `novatek,NVT-ts` aparece junto dos overlays de `nt36672e` (touch do painel novatek, nao o FT5452).
- No FDT de referencia, o trecho do `m7` lido (linhas ~11040-11200) nao tem comando de leitura de ID do DDIC.
  O comando `qcom,mdss-dsi-panel-status-command` so aparece no `td4330`. Nao verificado o bloco inteiro do `m7`.

**Conclusao:** o IC do painel `m7` nao esta codificado em nenhum software extraido (driver, modulos, DTBO).
O nome so pode ser obtido lendo o ID do controlador (via debugfs/DSI em kernel de debug) ou pela etiqueta/FPC do painel.
Pendente para decidir: `dbg-ls` do debugfs, ou abertura do aparelho (sem decisao tomada).

**Atualizacao:** `ls /sys/kernel/debug` no aparelho retornou vazio. Debugfs nao esta montado (ou o kernel de stock nao expoe o no).
Montar debugfs altera o estado do aparelho em execucao (reverte no reboot), por isso nao foi feito sem decisao explicita.
Proximo passo de leitura sem alterar nada: `mount | grep debugfs` e `ls /sys/class/drm/card0-DSI-1`.

**Atualizacao 2:** `/sys/class/drm/card0-DSI-1` aponta para `/sys/devices/platform/soc/5e00000.qcom,mdss_mdp/drm/card0/card0-DSI-1`
(so o link; sem atributo com nome de IC). O `dmesg-boot.txt` confirma `create procfs mipi_rw_prim success!`, entao o caminho de leitura
e `/proc/mipi_rw_prim`, e nao o debugfs. Formato de uso (do `mi_dsi_display_set_mipi_rw`, fonte publica de outro kernel Xiaomi da mesma familia
`mi_disp`, nao verificada no topaz): `<leitura 0/1> <tamanho rx> <LP 00|HS 01> <cabecalho DSI 7 bytes> <payload>`.
Leitura proposta, so comandos DCS de leitura: `0x04` (display ID, 3 bytes), `0xDA`, `0xDB`, `0xDC` (ID1/2/3).
Stock kernel do log: `Linux 5.15.211` (nao 6.12).

**Atualizacao 3:** `su -c "ls -l /proc/mipi_rw_prim"` no aparelho: `No such file or directory`. O no criado no boot do log nao existe no boot atual
(ou foi renomeado/removido). Todas as tentativas de leitura DCS por `/proc` falharam pelo mesmo motivo. Nao houve envio de comando DSI.

**Atualizacao 4:** `/proc/mi_display` existe no aparelho (diretorio). No codigo de referencia as entradas ficam na raiz de `/proc`,
entao no stock elas podem estar dentro desse diretorio. Proximo passo: listar `/proc/mi_display` (somente leitura).
