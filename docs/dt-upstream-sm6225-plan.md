# Plano: DT upstream-style do SM6225/topaz para a base ACK 6.18

## Por que este documento

A série `patches-6.18/` compila e linka a `Image` na ACK
`android17-6.18` (run `40983813425`), mas a imagem ainda não tem
**DTB da placa** nesta base: a ACK não traz `sm6225.dtsi` e as DTS
do projeto (`device-tree/source/`) estão no formato vendor
(downstream), incompatível com os drivers/bindings upstream que a
série habilita. Este plano mapeia como construir `sm6225.dtsi` +
`sm6225-xiaomi-topaz.dts` no estilo upstream, em fatias validáveis,
sem inventar dados de hardware.

Estratégia de boot continua a híbrida já decidida
(`docs/boot-dependency-analysis.md`): primeiro marco = console
serial mínimo, sem stack vendor. Este documento cobre só a parte
Device Tree desse caminho na trilha 6.18.

## Âncoras e evidências disponíveis

| Fonte | Uso |
|---|---|
| `sm6115.dtsi` upstream (ACK 6.18, 3464 linhas) + placas `sm6115-fxtec-pro1x`, `sm6115p-lenovo-j606f` | **Modelo estrutural**: mesmo SoC-class Bengal; copiar a organização e trocar apenas o que o Khaje tiver de diferente comprovado. |
| `device-tree/reference/topaz-live-reference.dts` (13978 linhas, FDT vivo do aparelho) | **Fonte primária de dados**: endereços, IRQs, clocks, reguladores, reserved-memory, pinos. |
| `device-tree/source/` (54 arquivos vendor importados) | Tradução nó-a-nó vendor→upstream já praticada na trilha 6.12; ver `docs/dts-integration-status.md`, `docs/dts-fidelity-report.md`, `docs/device-tree-inventory.md`. |
| `pmos-tapas` / `sm6225-mainline` (referências externas registradas) | Mapa de hardware e prova de que o SM6225 sobe com kernel mainline; **não** é drop-in (drivers/DT próprios, outra base). |
| Bindings da própria série (patches 0001/0003/0005/0008/0011/0014/0030/0031/0032/0033) | Contrato que os nós precisam satisfazer (`dtbs_check` é o juiz). |

## Compatibles que a DT precisa declarar (estado atual da série)

Do SoC (drivers da série ou matches adicionados sobre upstream):

- `qcom,khaje-gcc`, `qcom,khaje-dispcc`, `qcom,khaje-gpucc` (+ debugcc)
  — clocks próprios do patch 0010; o SM6115 upstream usa outros
  compatibles, então os nós de clock **não** podem ser cópia direta.
- `qcom,khaje-pinctrl` — TLMM (0001/0002).
- `qcom,khaje-mdss`, `qcom,khaje-dpu`, `qcom,khaje` (match UBWC do
  0017 — é o compat de SoC que o FDT vendor declara na raiz; decidir
  o compat de raiz upstream aqui: provável `qcom,sm6225` novo, o que
  obriga a adicionar match UBWC para ele — item já anotado no
  README da série).
- `qcom,sm6225-dsi-phy-7nm` — DSI PHY (série).
- `qcom,sm6225-qmp-ufs-phy` (0005/0006) + host UFS — PHY em
  `0x4807000`, host em `0x4804000` (ver `docs/ufs-qmp-phy-port.md`);
  supplies `vdda-phy`/`vdda-pll` precisam de providers topaz
  reais comprovados no FDT, não os labels do IDP.
- `qcom,bengal-bimc` — interconnect (0007). **Pergunta aberta**:
  o driver declara um único compatible; confirmar se
  system_noc/config_noc entram como nós adicionais com dados
  próprios ou se o modelo é outro (rotas FDT conhecidas:
  system_noc → bimc → config_noc).
- RPM SMD (0008/0009): reguladores são descritos como recursos
  aninhados, não no formato upstream clássico — a DT deve seguir a
  *nossa* binding, com os trilhos do FDT (PM6125 etc.).
- `qcom,sm6225-adsp-pas` — PAS/ADSP (0026/0027/0028).
- `qcom,sm6225-sndcard` (0032) + macros LPASS com fallback
  SM6225→SM6115 (0030) + LPI pinctrl (0031): nós RX/TX/VA/SWD
  com os clocks do binding (VA: `mclk`, `dcodec`, `npl`).

Da placa topaz:

- Painel `xiaomi,m7-38-0c-0a` (0014) atrás do DSI, com o
  panel-event-notifier (0015) se o binding pedir.
- Touchscreen FT3519: **não há driver upstream** na base; o config
  exige `TOUCHSCREEN_EDT_FT5X06` por herança da 6.12. DT não deve
  declarar nó que nenhum driver casa — pendência de driver,
  não de DT.
- `ovti,wl2866d-i2c` (0033) no barramento I2C da câmera; sensores
  (S5KJN1 sem driver upstream, OV08D10 presente) dependem da
  decisão CAMSS vs Spectra, fora deste plano.

## Diferenças SM6225 × SM6115 a comprovar no FDT (não presumir)

1. **CPUs/clusters e OPPs** (Kryo 260: prime/cluster diferente do
   SM6115), `capacity-dmips-mhz`, idle states, cpufreq-hw/EPSS.
2. **Clock IDs e resets**: os headers `dt-bindings/clock` do SM6115
   upstream não servem para os controladores Khaje (0010) — a DT
   usa os IDs definidos pelos patches 0003/0010.
3. **MDSS 6.10 × 6.3**: base/len/IRQ do MDSS, DSI e PHY; catálogo
   já casado por compatible, mas o nó precisa dos recursos certos.
4. **QUP/GENI**: quantidade e endereços das instâncias SE
   (UART de console é o primeiro consumidor — marco serial).
5. **Interconnect**: conjunto de NoCs e larguras (ver pergunta
   aberta acima) e `interconnects` dos consumidores (UFS, MDSS...).
6. **Reserved-memory**: regiões do FDT vivo (rmtfs, modem, adsp,
   cdsp, cont-framebuffer etc.) copiadas com endereços reais.
7. **SMMU/apps_smmu, tsens, SCM, SEE, RPM glink** — presentes no
   SM6115; conferir compat/endpoints no FDT.

## Fatias propostas (cada uma = patch novo na série + gate CI)

Numeração continua a partir de 0034 em `patches-6.18/`.

- **S1 – SoC mínimo com console UART descrito** *(CONCLUÍDA em
  30/out/2026: patch 0034 + correção 0035 do binding TLMM;
  run `41056142520` verde com `Image`, DTB e `dtbs_check` sem
  nenhum reporte — ver a nota sobre o gate abaixo; segue sem
  qualquer evidência de boot)*: `sm6225.dtsi`
  com CPUs/PSCI/timer/GIC, `gcc`, `rpmcc`, TLMM, QUP+UART do
  console, interconnect mínimo, `smd-rpm`/reguladores base;
  `sm6225-xiaomi-topaz.dts` só com `chosen` (stdout-path),
  `memory`, reserved-memory e o UART. Incluir também o nó
  `ramoops@5d000000` do FDT vivo e, no fragmento, subir
  `CONFIG_PSTORE_RAM=y` + `CONFIG_PSTORE_CONSOLE=y` — hoje o dono
  não tem conversor UART, então `pstore` é o canal de log
  desenhado para um eventual primeiro teste físico, não o prompt
  serial.
  Gate: `dtbs` compila + `dtbs_check` dos arquivos novos no CI.
  Este marco é **somente CI** por enquanto: o único topaz
  disponível é o aparelho principal e não pode parar; qualquer
  teste nele continua bloqueado pelos pré-requisitos de backup,
  fallback e método reversível em
  `docs/hardware-info-needed.md`.
- **S2 – Storage** *(CONCLUÍDA em 30/out/2026: patches 0036 +
  0037; run `41106546373` verde com `Image` e `dtbs_check` sem
  reportes)*: UFS host+PHY com supplies/ICC
  reais; gate `dtbs_check`. (Cargas `vdda-*` comprovadas no FDT
  vivo: 85700/18300 µA sobre `pm6125_l4`/`pm6125_l18` — ver 0006.)
  Puxou da S5 os trilhos físicos L4/L11/L18/L24 do PM6125.
  Primeira run do gate (41101955941) reprovou a fatia por dois
  defeitos da própria série: o binding da PHY (0005) pedia 9
  clocks com teto-base 3, e `power-domains` é obrigatório no
  binding upstream enquanto o `gcc-khaje` não registrava GDSC
  nenhum. Correção no **0037**: teto do binding a 9 + os 9 GDSCs
  do GCC registrados no driver (offsets do `bengal-gdsc.dtsi`,
  idênticos aos do upstream SM6115) + `power-domains`/`vdd-hba`
  na DT. **Dívidas restantes da fatia**: (a) `iommus` ausente até
  existir o nó `apps_smmu` (SID do UFS no FDT: 0x100);
  (b) o teto HS-G3 downstream não é expressível no binding
  upstream (o device UFS 2.2 de 2 vias negocia G3 sozinho);
  (c) os stubs de clock-símbolo da PHY como parents do GCC
  continuam (como downstream); trocar pelos clocks reais da PHY
  é limpeza posterior.
- **S3 – Display**: CONCLUÍDA (CI) em 2026-10-30 — **0038** +
  **0039**, run `41149442110` verde (apply 38/38, `Image` linka,
  `dtbs_check` sem reportes). Conteúdo: gpucc@5990000 +
  dispcc@5f00000 (parents e `vdd_cx`/`vdd_mx` dos bindings khaje),
  MDSS@5e00000/DPU@5e01000/DSI@5e94000/PHY-7nm@5e94400
  (endereços/IRQ 186 do `khaje-sde-common.dtsi`; clocks dos
  bindings khaje-mdss/dpu), painel M7 0a (`vddio`=l9, recurso RPM
  `ldoa9`; reset gpio82; enable LCM gpio54; TE gpio81) e
  supplies DSI/PHY (l18/l4). A primeira rodada reprovou com 2
  reportes (`iommus` e `operating-points-v2` obrigatórios pelos
  bindings); o **0039** puxou o `apps_smmu@c600000` para esta
  fatia e ligou `iommus` de MDSS e, retroativamente, do UFS
  (dívida da S2 encerrada), tabela de OPPs do MDP (rates do
  dispcc-khaje) e os matches `qcom,sm6225-smmu-500`/
  `qcom,khaje-mdss` no arm-smmu-qcom. **Dívidas restantes**:
  ~~`required-opps`/corners (rpmpd)~~ e ~~nó da GPU~~ — ambas
  encerradas nas fatias intermediárias 0040/0041 abaixo; resta
  validar TE/modo-comando do 0016 quando houver hardware.
- **Fatias intermediárias (pós-S3, CI-verdes)**:
  - **rpmpd (0040)**, run `41156489474`: `qcom,sm6225-rpmpd`
    (driver/binding/header; conjunto de PDs do sm6115 sobre os
    recursos rwcx/rwmx) + nó sob `rpm_requests` + `required-opps`
    do MDP com o mapa de corners do próprio `dispcc-khaje`
    (LOW_SVS@200M, SVS@300M, SVS_PLUS@383M, NOM@470M,
    TURBO@560M). Encerrou a dívida de corners da S3.
  - **GPU (0041)**, run `41158774144`: `gpu@5900000` Adreno
    610.0 (chipid `0x06010001`, GMU-less), `gmu@596a000`
    (gmu-wrapper nos GDSCs CX/GX do gpucc),
    `adreno_smmu@59a0000`, `qfprom@1b40000` com a célula
    `gpu_speed_bin@6006` e a tabela de OPPs fundida das 5
    tabelas de pwrlevel downstream (bins 0..4 via fuses
    0/235/216/157/127, corners RPM 64..416 como
    `required-opps`, `opp-supported-hw` por bin). Firmware zap
    não faz parte da série.
- **S4 – Áudio/ADSP**: lado DT completo (2026-10-31) em 6
  patches CI-verdes (runs `41176222778`, `41178236139`,
  `41181229514`, `41184273173`):
  - 0042: smp2p-adsp + trilhos LPI (rwlc/rwlm) +
    `remoteproc@ab00000` (PAS do 0026) com glink/APR+FastRPC.
  - 0043 (correção): o firmware khaje é **AudioReach/SPF** —
    serviços Elite substituídos por `gpr{q6apm,q6prm}`;
    `lpass_tlmm@a7c0000`.
  - 0044: macros VA/RX/TX (bolero) + SoundWire v1.6.0
    (@a610000/@a740000), clocks PRM.
  - 0045 (correção de CI): binding VA autocontraditório no
    `clock-names` posicional (defeito latente); attrs de
    porta SWR exigidos pelo binding.
  - 0046: codec **WCD937x** (slaves SWR dev 0xa, supplies
    l14/l9, micbias 2,7 V, reset gpio92) + sndcard
    `qcom,sm6225-sndcard` (links WCD Playback/Capture + VA
    Capture).
  - 0047 (correção de CI): refs do binding `wcd937x` sem
    fragmento vazio + `micbias4` obrigatório.
  **Dívidas**: alto-falante (amplificador SIA81xx **sem driver
  upstream** — caminho não descrito), estados de pinos SWR no
  LPI, parâmetros MBHC (jack), variante 9370 vs 9375 por
  confirmar em hardware, e o mapeamento de portas/canais do
  codec ficou nos defaults do driver (downstream usa outra
  codificação).
- **S5 – Placa**: lado DT completo (2026-10-31) em 5 patches
  CI-verdes (runs `41226732607`, `41228370915`,
  `41231928129`, `41233199069`):
  - 0048: `spmi@1c40000` + placa inclui o `pm6125.dtsi`
    upstream (PON power/resin→volume−, temp-alarm+zona,
    ADC5/ADC-TM, RTC, gpios PMIC) + volume+ no PMIC GPIO5.
  - 0049: TSENS `qcom,sm6225-tsens` (16 sensores, IRQs
    275/190) + 16 zonas térmicas (índices conferem 1:1 com
    o mapa downstream bengal; sem cooling-maps ainda).
  - 0050: QUP `i2c2@4a88000`/`i2c4@4a90000` +
    `uart3@4a8c000` — **correção: o console khaje é SE3**
    (alias `hsuart0` do FDT); a S1 usava SE4, que é o I2C
    do NFC. Touch **FocalTech FT5452** (@0x38, irq 80,
    reset 86, avdd 36; clock SE fixado em 19,2 MHz) e NFC
    **ST21NFC** (`st,st21nfcc-i2c` @0x08, irq 70, reset 69).
  - 0051: `input-enable` removido dos estados do touch
    (TLMM não aceita a propriedade).
  - 0052: vibrador `gpio-vibrator` no PM6125 GPIO8.
  **Correção pós-S5 (0053, run `41243173565`)**: o touch
  não é FT5452 — é o **FT3519T** (evidência de runtime:
  `focaltech_ts_fw_samsung_ft3519t.bin`; os chip IDs
  0x54/0x52 enganam). O driver já estava na série
  (0022: edt-ft5x06 `focaltech,ft3519`, coordenadas
  15-bit, `=y`); o nó da S5c (`focaltech,fts`+binding
  mínimo) foi reescrito para o binding edt
  (AVDD=GPIO36 fixo, IOVCC=L9 por confirmar) — **nenhum
  driver vendor precisou ser importado**.
  **Dívidas**: identify()/resume do edt no FT3519T e rail
  IOVCC não verificados; clkreq/clock de RF do NFC fora
  do binding upstream; GPI DMA não descrito (I2C em modo
  FIFO); flash LED ficou com a fatia de câmeras;
  calibração TSENS opera no modo "calibrationless"
  (como o sm6115 upstream).
- **CPU – cpufreq/idle**: completo no lado DT (2026-10-31,
  patch 0054, run `41247264596`): `cpufreq@f521000`
  (`qcom,sm6225-cpufreq-hw`, OPPs da LUT do hardware como
  upstream), CPUs `qcom,kryo260` com clocks/freq-domain, e
  PSCI em modo **OSI** com a hierarquia de domínios e os
  idle-states copiados do FDT vivo (params khaje diferem do
  sm6115: cluster PC `0x41000043`, níveis CCI/sistema).
  Cooling-map da GPU restaurado; CPU sem cooling-maps como
  upstream. Driver embutido via fragmento
  (`ARM_QCOM_CPUFREQ_HW`, erro de nome corrigido no caminho).
  **Dívidas**: `dynamic-power-coefficient` herdado do sm6115
  (estimativa), sem verificação de DVFS/idle em hardware.
- **S6 – Câmeras** (em curso; decisão: **CAMSS upstream**,
  sem vendor Spectra): levantamento 2026-10-31 mostrou que
  (a) não há CAMCC separado no bengal — os clocks e o GDSC
  TOP de câmera saem do GCC khaje já portado (0011);
  (b) o `qcom,qcm2290-camss` (mesmo IP-base `0x5c6e000`) é
  o molde na base; (c) `ov08d10` existe upstream, `s5kjn1`
  e `gc02m1` não; (d) a árvore mainline SM6225 de
  referência **não tem câmeras** — caminho novo.
  - **S6a (0055)**, run `41250221213`: CCI
    (`cci@5c1b000`, 2 mestres, IRQ 206, clocks/GDSC do
    GCC) + `I2C_QCOM_CCI=y`.
  - **S6b (0056)**, validado de fato no run
    `41322986183` (ver "Fechamento da S6" abaixo): binding
    `qcom,sm6225-camss` + recursos no driver (tabelas
    `csiphy/csid/vfe_res_6225`: gerações do `CAMSS_2290`
    — csiphy-3ph-1.0/csid-340/vfe-340 — estendidas a
    **3 unidades**, versão mantida `CAMSS_2290`) + nó
    `camss@5c6e000` (10 janelas/9 IRQs/20 clocks GCC,
    ICC bengal, SIDs 0x400/0x800) **desabilitado**;
    supplies CSIPHY na placa (L18/L4). **Premissa não
    verificada**: identidade de registradores com o
    qcm2290 (CSIPHY downstream é "v1.2.1").
  - **S6c sensores (em curso)**:
    - **S6c-1 (0057)**, validado de fato no run
      `41322986183` (idem): **OV08D10**
      frontal — o driver upstream era ACPI-only; ganhou
      match OF + binding novo (`ovti,ov08d10.yaml`) +
      sequenciamento de probe opcional (reset/supplies),
      sem tocar o caminho ACPI. Nó no CCI1 @0x36
      (endereço = default de datasheet, sem XML p/
      confirmar), MCLK1 19,2 MHz (gpio21), reset gpio24,
      2 lanes @720 Mbps → **CSIPHY2/port@2**; CAMSS
      habilitado. **Dívidas**: trilhos do sensor são do
      WL2866D (hoje só API misc, sem reguladores);
      endereço I2C e o power-on real não verificados.
    - **S6c-2 (0058+0060)**: **S5KJN1** (principal,
      50 MP) — descoberto que o driver foi mergeado no
      mainline (Linaro, 2025) depois do corte da base;
      importado com o binding (`samsung,s5kjn1`) e
      adaptado p/ a API 6.18 no 0060 (master ja usa
      `v4l2_subdev_client_info` nas pad ops). No no CCI0
      @0x2d (datasheet), MCLK0 **24 MHz** (exigencia do
      driver; downstream usa 19,2 MHz), reset gpio18,
      4 lanes @700 MHz -> **CSIPHY0/port@0**. GC02M1
      (macro) e o flash I2C continuam pendentes: o
      downstream declara `CAM_FLASH_TYPE_I2C` via CCI,
      nao o periferico flash SPMI do PM6125, e o IC
      externo ainda nao foi identificado.
    - **Fechamento da S6 (0059-0062)**, run
      **`41322986183`** (serie inteira, 61 patches,
      0 reportes): correcoes que a S6 arrastava sem
      ninguem ver — os runs citados nos marcos 0056/0057
      (e no 0054) eram do **workflow 6.12**, nao do 6.18
      (licao: sempre filtrar por nome do workflow). No
      6.18 quebravam: `devm_regulator_bulk_get_optional`
      inexistente no ov08d10 (0059), include
      `qcom,rpm-icc.h` faltando p/ os ICC do CAMSS
      (0061) e listas do binding CAMSS truncadas na
      3a unidade (0062). O laudo `falhas.txt` tinha um
      bug de clobber (grep codigo 2 c/ log faltante)
      que escondia os diagnosticos — corrigido no
      workflow. **Dividas S6 restantes**: GC02M1 sem
      driver, flash I2C com IC nao identificado,
      sensores sem supplies do WL2866D no DT (reguladores
      expostos no 0064, mas o mapeamento saida->sensor
      era do userspace downstream),
      enderecos I2C dos sensores por datasheet, MCLK
      24 MHz do S5KJN1 nao verificado no GCC,
      identidade de registradores CAMSS=qcm2290
      presumida.
- **Barramento SE1 / USB-C (0063)**, run
  **`41328560854`** (serie inteira, 62 patches,
  0 reportes): QUPV3 SE1 (`i2c@4a84000`, GPIO4/5,
  GIC SPI 328) habilitado a 400 kHz. Nele entram o
  WL2866D `pmic@28` (EN no GPIO26; driver misc atual
  desliga as saidas apos o probe) e o RT1711H @0x4e.
  O **GPIO93 do topaz e o CHG_PD_INT_N ativo-baixo do
  RT1711H**, com pull-up/drive 2; os estados genericos
  downstream `cam_flash_tx_*` que reaproveitam o mesmo
  pino nao sao a ligacao desta placa. Os PDOs fixos de
  5 V (fonte 0,5 A, dreno 2 A) espelham o downstream.
  **Dividas**: DWC3/PHY, FSA4480, VBUS, PM8008 e os
  carregadores da SE1 ainda nao modelados; conector
  sem endpoints ate o USB existir na DT.
- **WL2866D regulador (0064)**, run **`41337536375`**
  (serie inteira, 63 patches, 0 reportes): as quatro
  saidas viram reguladores (`dvdd1`/`dvdd2`/`avdd1`/
  `avdd2`), com a sequencia de enable downstream
  (descarga, seletor de tensao, bit de enable) e a
  tensao selecionada lembrada entre enables. DVDD1
  aceita 1,05/1,2 V; DVDD2 fixo 1,05 V; AVDD fixos
  2,8 V. Binding ganha os nos filhos; sensors seguem
  sem supplies por falta de evidencia do mapeamento
  (o helper `wl2866d_camera_power_control` nao tem
  chamadores de kernel downstream e o DT de camera so
  lista `cam_clk`/`cam_vio`).
- **USB HS (0065-0068)**, run **`41346999641`** (serie
  inteira, 67 patches, 0 reportes): DWC3 primario (core
  0x4e00000 IRQ255, glue 0x4ef8800 pwr_event IRQ302,
  SID 0x120) + PHY SNPS Femto 0x1613000, teto
  high-speed, dual-role com endpoint p/ o RT1711H;
  PHY alimentada por L4/L12/L15 do PM6125. De quebra:
  as tags RPM de 2 celulas do CAMSS foram removidas
  (o binding bengal da arvore fixa 1 celula) e o
  binding do CAMSS corrigido p/ 3 interconnects.
  **Dividas USB**: QMP combo USB3/DP (SuperSpeed),
  FSA4480/SBU, VBUS (charger), wakeups DP/DM via MPM
  (sem no MPM/IPCC ainda), tensao inicial dos LDOs da
  PHY e rates fora do downstream.
- **microSD/SDHCI2 (0069-0071)**, run **`41349310964`**
  (serie inteira, 70 patches, 0 reportes): host
  0x4784000 (IRQ350/353, SID 0xa0, clocks/reset SDCC2),
  DLL/DDR das listas downstream, OPP 100/202 MHz +
  CX do rpmpd, estados SDC2; placa com L22 (vmmc),
  L5 (vqmmc), CD GPIO88 ativo-alto, SDR104. O trilho
  io-bias L7 ficou fora de proposito (sem consumidor
  upstream). **Dividas**: taxas/polaridades nao
  verificadas em hardware; io-bias e DLL fino.
- **MPM (0072)**, run **`41351366980`** (serie inteira,
  71 patches, 0 reportes): agregador de wakeup como
  filho do remoteproc RPM, apss_mpm na rpm_msg_ram
  (mmio-sram), mailbox apcs_glb canal 1, GIC 197.
  Mapa khaje do `qcom-mpm.c` downstream
  (SPMI 86->183, USB dp 91->184/dm 90->188/ss 12->422,
  lpass 5->296, lpi 24->79, pino 2->190 sem rotulo).
  SPMI e DWC3 migrados p/ interrupts-extended via MPM.
  Fecha a divida "wakeups DP/DM via MPM" do USB.

## Gate de CI a adicionar (junto da S1)

*Status: implementado junto do 0034 e endurecido após a primeira
rodada — o passo "DTB + dtbs_check" roda `make CHECK_DTBS=1
qcom/sm6225-xiaomi-topaz.dtb` (validação contra todos os schemas,
só para o DTB novo) e, como o `make` retorna 0 mesmo com erro do
`dt-validate`, grepa o log pelas linhas de reporte para o nosso
DTB e falha se houver alguma. A primeira rodada achou 7 erros
reais no binding `qcom,khaje-pinctrl` do 0001 (corrigidos no
0035); a rodada `41056142520` fechou com zero reportes.*

No job `kernel-build` do `google-mainline.yml`, após o `Image`:
`make ARCH=arm64 ... dtbs` (ao menos o DTB novo) e
`make dtbs_check DT_SCHEMA_FILES=<bindings/nós novos>` em passo
separado reportando na mesma issue `ci-report`. `dt-doc-validate`
completo das bindings modificadas pela série inteira é desejável,
mas como passo próprio (pode ser ruidoso no início; começar pelos
arquivos novos da S1).

## Fora de escopo / decisões pendentes do dono

- ~~Promover a série 6.18 a principal~~ — **decidido pelo dono:
  prosseguir com a 6.18.** Destino final da trilha 6.12 (congelar
  vs. remover) é decisão separada, sem pressa.
- ~~Valores `init_load_uA` da PHY UFS e providers de
  `vdda-phy`/`vdda-pll`~~ — resolvido do FDT vivo (85700/18300 µA,
  `pm6125_l4`/`pm6125_l18`); falta só a *tradução* dos nós para a
  binding upstream na S2 e, um dia, a confirmação em runtime.
- Informações do aparelho ainda necessárias (confirmações de
  estado atual, backups de segurança e canal de log de boot):
  ver `docs/hardware-info-needed.md`.
- Touch FT3519 e câmera S5KJN1/CAMSS: frentes de driver próprias.

## Disciplina (a mesma das fatias anteriores)

Nenhum endereço, IRQ, clock ou trilho entra na DT sem fonte
citável (FDT vivo, DTS vendor importado ou binding). Onde o SM6115
e o FDT divergirem, vence o FDT; onde o FDT for vendor-format, o
nó é *traduzido* para o binding upstream, nunca colado. Cada fatia
só é dada como pronta com `dtbs`/`dtbs_check` verdes no CI — e
isso continua não sendo evidência de boot.
