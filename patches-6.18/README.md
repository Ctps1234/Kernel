# Série sobre o ACK da Google (`android17-6.18`)

Rebase da série local (`../patches/`, base Android Common 6.12) sobre a
árvore oficial da Google, fixada em:

- repo: `https://github.com/aosp-mirror/kernel_common`
- branch: `android17-6.18`
- commit: `1afe39edbe66c201d26f23f2e3396583238f6842` (Linux 6.18-rc6)

Decisão e plano completos em
[`../docs/google-mainline-vendor-plan.md`](../docs/google-mainline-vendor-plan.md).
Os nomes de arquivo são idênticos aos da série 6.12 para manter o mapa
1:1 entre as duas. As mensagens de commit são as originais (mencionam a
árvore 6.12); o conteúdo é o mesmo, com os ajustes de contexto abaixo.
Atualizacao (2026-10-30): a serie completa (32 patches, 0001-0033
sem o 0029) **compila e linka** nesta base — `Image` verde no CI
(run 40983813425; detalhes em "Rodadas de build" abaixo). Boot e
hardware seguem sem nenhuma evidencia: falta DT upstream-style do
SM6225/topaz e teste no aparelho. O texto historico abaixo e
mantido como registro das fatias do rebase.

Atualizacao (2026-10-30, fatia S1 da DT): entra o **0034** —
`sm6225.dtsi` minimo (CPUs/PSCI/timer/GIC, GCC+RPMCC, TLMM,
UART de console, interconnect Bengal, votos CX/MX via SMD-RPM) e
`sm6225-xiaomi-topaz.dts` (memoria, reserved-memory com o
`ramoops@5d000000` do FDT vivo, stdout-path no UART), mais os
compatibles de suporte (`qcom,sm6225` em qcom.yaml/UBWC,
`qcom,rpm-sm6225`, `qcom,sm6225-rpm-proc`,
`qcom,sm6225-apcs-hmss-global`). O fragmento de config sobe
`PSTORE`/`PSTORE_RAM`/`PSTORE_CONSOLE` para built-in e o job de
build ganha o gate `CHECK_DTBS=1` (dtbs_check) sobre o DTB novo.
Primeira run do gate (41052634674, verde em Image) achou 7 erros
de schema reais no binding TLMM do 0001 (patternProperties
pega-tudo avaliava ate `compatible`/`reg` contra o schema de
pin-node) — e ensinou que `make CHECK_DTBS=1` retorna 0 mesmo com
erro do dt-validate; o passo agora grepa o log e falha. Correcao
do binding no **0035** (molde do `qcom,sm6115-tlmm` upstream).
Serie agora com **34 patches** (0001-0035 sem o 0029). O **0088** torna o **NFC** (ST21NFCC no
I2C SE4) alcancavel: pinctrl corrigido p/ GPIO96/97 e
driver ST_NCI_I2C built-in. Os **0089-0090** adicionam o **IR blaster**
(ir-spi-led no SPI SE0). Serie com **89 patches**
(0001-0090 sem o 0029). Escopo,
fontes de cada dado e o que ficou para as fatias S2-S6:
`docs/dt-upstream-sm6225-plan.md`. Veredito: run
[`41056142520`](https://github.com/Ctps1234/Kernel/actions/runs/41056142520)
verde nos dois jobs — serie aplica, `Image` linka e o DTB do
topaz passa `dtbs_check` sem nenhum reporte do `dt-validate`
(S1 concluida no sentido CI). Continua sendo so CI: nada disto e
evidencia de boot.

Atualizacao (2026-10-30, fatia S2): entra o **0036** — UFS host
(`qcom,sm6225-ufshc`, novo no binding no grupo de 9 clocks) +
QMP PHY no formato do 0005, os trilhos fisicos PM6125
L4/L11/L18/L24 como recursos RPM-SMD (janelas de tensao finais do
FDT vivo) e a fiação de placa (vcc/vccq2 a 800 mA, supplies da
PHY, reset no gpio113). Serie com **35 patches** (0001-0036 sem o
0029). Sem `iommus` (apps_smmu ainda nao existe) — divida
documentada no plano de DT.

Errata da S2 (mesmo dia): a primeira run do gate (41101955941)
reprovou o 0036 — o binding da PHY do 0005 exigia 9 clocks com
teto-base 3 (insatisfazivel) e o binding upstream exige
`power-domains` na PHY, mas o gcc-khaje nao registrava GDSCs.
Entra o **0037**: teto do binding corrigido, os 9 GDSCs do GCC
registrados (offsets do bengal-gdsc.dtsi = upstream SM6115) e
`power-domains`/`vdd-hba` ligados na DT. Serie com **36 patches**
(0001-0037 sem o 0029). Veredito: run
[`41106546373`](https://github.com/Ctps1234/Kernel/actions/runs/41106546373)
verde — serie aplica 36/36, `Image` linka com os GDSCs e o DTB
(S1+S2) passa `dtbs_check` sem reportes. S2 concluida no sentido
CI; boot continua sem evidencia.

Atualizacao (2026-10-30, fatia S3): entra o **0038** — MDSS
(DPU/DSI/PHY-7nm), dispcc/gpucc no SoC e o painel M7
(`xiaomi,m7-38-0c-0a`) com reset/enable/TE e o trilho
`pm6125_l9` na placa. Serie com **37 patches** (0001-0038 sem o
0029). Dividas pendentes (`iommus`/SMMU, OPP do MDP, no da GPU),
documentadas no plano de DT. Aguardando veredito do CI.

Errata/veredito da S3 (mesmo dia): a run `41146627214` reprovou o
`dtbs_check` com 2 reportes — os bindings `qcom,khaje-mdss` e
`qcom,khaje-dpu` exigem `iommus` e `operating-points-v2`. Entra o
**0039**: `apps_smmu@c600000` (identico ao sm6115/FDT), `iommus`
do MDSS e retroativo do UFS (SID 0x100 — divida da S2 encerrada),
OPPs do MDP (rates do dispcc-khaje) e matches no arm-smmu-qcom.
Serie com **38 patches** (0001-0039 sem o 0029). Veredito: run
[`41149442110`](https://github.com/Ctps1234/Kernel/actions/runs/41149442110)
verde — apply 38/38, `Image` linka e o DTB (S1+S2+S3) passa
`dtbs_check` sem reportes. S3 concluida no sentido CI; boot
continua sem evidencia. `required-opps` (rpmpd) e no da GPU
seguem pendentes.

Atualizacao (2026-10-30, pos-S3): entram o **0040** (rpmpd
`qcom,sm6225-rpmpd` no driver/binding/header + no sob
`rpm_requests` + `required-opps` do MDP com os corners do
`dispcc-khaje`) e o **0041** (GPU Adreno 610.0 GMU-less +
`gmu`-wrapper + `adreno_smmu` + `qfprom`/speed-bin, com a
tabela de OPPs fundida das tabelas de pwrlevel por speed-bin
do downstream). Serie com **40 patches** (0001-0041 sem o
0029). Vereditos: runs
[`41156489474`](https://github.com/Ctps1234/Kernel/actions/runs/41156489474)
e
[`41158774144`](https://github.com/Ctps1234/Kernel/actions/runs/41158774144)
verdes — apply limpo, `Image` linka e `dtbs_check` sem
reportes. Firmware zap fora da serie; boot sem evidencia.

Atualizacao (2026-10-31, fatia S4): entram **0042–0047** —
ADSP (smp2p, trilhos LPI rwlc/rwlm, PAS@ab00000), servicos
**AudioReach** (GPR q6apm/q6prm; correcao do Elite), LPASS
(LPI pinctrl, macros VA/RX/TX, SoundWire 1.6.0), codec
WCD937x e sndcard `qcom,sm6225-sndcard`. Duas correcoes de
binding latente no caminho (VA-macro autocontraditorio e ref
do wcd937x — padrao dos 0035/0037). Serie com **46 patches**
(0001-0047 sem o 0029). Vereditos: runs `41176222778`,
`41178236139`, `41181229514`, `41184273173` verdes —
`dtbs_check` sem reportes. Alto-falante (SIA81xx, sem driver
upstream), pinos SWR e MBHC pendentes; firmware ADSP fora da
serie; boot sem evidencia.

Atualizacao (2026-10-31, **S5 placa**): entram **0048-0052** —
SPMI + PM6125 (`pm6125.dtsi` upstream: PON/teclas/RTC/
temp-alarm/ADC), TSENS `qcom,sm6225-tsens` + 16 zonas,
I2C SE2/SE4 com touch e NFC **ST21NFC**, vibrador no PMIC
GPIO8 — e a **correcao do console: SE3** (`uart3@4a8c000`,
alias `hsuart0` do FDT; o SE4 da S1 e o barramento do NFC).
O **0053** corrigiu a identificacao do touch: e o
**FT3519T** (firmware `..._samsung_ft3519t.bin` no vendor
do aparelho), nao FT5452 — e o driver ja existia na serie
(0022, edt-ft5x06 `focaltech,ft3519`, 15-bit, `=y`); o no
foi reescrito para o binding edt sem importar driver
vendor. O **0054** fecha a fatia de **CPU**: cpufreq-hw
(`qcom,sm6225-cpufreq-hw`, LUT de hardware), CPUs
`qcom,kryo260` e PSCI/OSI com os idle-states do FDT
(+ config `ARM_QCOM_CPUFREQ_HW=y`). O **0055** abre a
**S6 (cameras, rota CAMSS upstream)**: CCI
`cci@5c1b000` com clocks/GDSC do GCC (bengal nao tem
CAMCC separado — o GCC khaje ja trazia todos os
`GCC_CAMSS_*`) + `I2C_QCOM_CCI=y`. O **0056** traz o
**nucleo CAMSS**: binding `qcom,sm6225-camss`, recursos
no driver (geracoes do `CAMSS_2290` em 3 unidades) e
`camss@5c6e000` desabilitado, com os supplies do CSIPHY
(L18/L4) na placa. O **0057** traz o primeiro sensor, a
frontal **OV08D10**: o driver upstream (ACPI-only) ganhou
match OF, binding novo e sequenciamento de probe opcional
(reset/supplies), e o no (CCI1 @0x36, MCLK1, 2 lanes ->
CSIPHY2) habilita o CAMSS. O **0058** importa o driver
mainline do **S5KJN1** (50 MP, traseiro principal,
mergeado upstream depois do corte da base) com binding,
e o no (CCI0 @0x2d, MCLK0 24 MHz, 4 lanes 700 MHz ->
CSIPHY0). O **0063** adiciona o barramento GENI I2C da
QUP SE1 e descreve dois dispositivos downstream nele: o
PMIC de camera **WL2866D** @0x28 (ainda pelo driver misc
do 0033, saidas desligadas apos o probe) e o controlador
USB-C/PD **RT1711H** @0x4e, cujo interrupt ativo-baixo e
o CHG_PD_INT_N no **GPIO93** do topaz. O **0064** expoe as
quatro saidas do WL2866D como reguladores (DVDD1 com
1,05/1,2 V; DVDD2 1,05 V; AVDDx 2,8 V), mantendo o helper
downstream e o misc device; os sensores continuam sem
supplies porque o mapeamento saida->sensor era decisao do
userspace downstream e nao consta em nenhuma fonte de
kernel acessivel. Os **0065-0068** trazem o USB primario
em HS: bindings (`qcom,sm6225-dwc3`, PHY Femto), DWC3
(0x4e00000, glue 0x4ef8800) + PHY Femto (0x1613000) no
SoC com os LDOs L12/L15, correcao de tags ICC (o binding
bengal da arvore fixa 1 celula; o CAMSS usava tags de
2 celulas) e a placa em dual-role com o endpoint
DWC3<->RT1711H. Os **0069-0071** trazem o **microSD
(SDHCI2)**: binding `qcom,sm6225-sdhci`, host 0x4784000
com DLL/DDR e OPP downstream + LDOs L5/L22, CD no
GPIO88 ativo-alto (camada Xiaomi) e SDR104. Serie com
**70 patches** (0001-0071 sem o 0029). O **0072** adiciona
o **MPM** (agregador de wakeup, mapa Khaje do driver
downstream) e cabeca SPMI/USB nele. Serie com **71
patches** (0001-0072 sem o 0029). Os **0073-0074** trazem
o **Bluetooth WCN3990** no HS UART da SE3 (hsuart0 do
FDT vivo), com L16/L17/L23 e o GPIO87 SW_CTRL; a SE3
sai de console (o console downstream e a SE4, que na
topaz vira o I2C do NFC — debug fica no ramoops). Serie
com **73 patches** (0001-0074 sem o 0029). O **0075**
descreve o **Wi-Fi WCN3990** (ath10k SNOC @0xc800000,
IRQ 358-369, SID 0x1a0): a regiao MSA ja existente na
placa ganha rotulo e o no fica habilitado; runtime
ainda depende do PAS do modem (PD de WLAN). Os **0076-0077** descrevem o **crypto** (QCE + BAM) e
os **0078-0080** trazem o **modem PAS**
(remoteproc@6080000; hospeda o PD de WLAN do ath10k)
e os **0081-0083** fecham o trio de DSPs com o
**CDSP PAS**; os **0084-0085** adicionam a **IMEM**.
O **0086** e higiene (Signed-off-by/SPDX da auditoria
checkpatch) e o **0087** traz o **PRNG**
(rng@1b53000). Serie com **86 patches** (0001-0087
sem o 0029). Vereditos: runs
`41226732607`, `41228370915`, `41231928129`,
`41233199069`, `41243173565`, `41250221213`,
`41322986183`, `41328560854`, `41337536375`,
`41346999641`, `41349310964`, `41351366980`,
`41514847959`, `41518607602`, `41522071688`,
`41526973371`, `41530367079`, `41535011077`,
`41538846766`, `41544358036`, `41546822966` e
**`41553988909`** (serie inteira, 89 patches) verdes no workflow 6.18 — `dtbs_check` sem
reportes. Correcao de registro: os runs `41247264596`,
`41258294792` e `41296845168`, citados como verdes dos
marcos 0054/0056/0057, eram na verdade do workflow 6.12
congelado; no workflow 6.18 esses marcos quebravam (API de
regulator inexistente no ov08d10, include rpm-icc faltando
no CAMSS, listas do binding truncadas) e so ficaram
verdes com os fixes 0059-0062, validados pelo run
`41322986183`. Dividas:
identify/resume do edt no FT3519T e rail IOVCC sem
confirmacao, clock/clkreq do NFC fora do binding, I2C sem
GPI DMA (modo FIFO), `dynamic-power-coefficient`
estimado; identidade de registradores CAMSS vs qcm2290
presumida; trilhos dos sensores via WL2866D agora
descrito na SE1, mas ainda sem modelo de regulador, e
endereco I2C do OV08D10 por confirmar; S5KJN1 com MCLK
reprogramado p/ 24 MHz e endereco por confirmar;
GC02M1 e o flash I2C (IC ainda nao identificado)
pendentes; RT1711H sem DWC3/PHY, FSA4480 ou VBUS
modelados, e PM8008/carregadores da SE1 pendentes;
boot sem evidencia.

## Estado (2026-10-29)

Rebaseados e verificados aplicando limpos, em ordem, sobre o commit
fixado: **0001–0011** (fundação de SoC: pinctrl, RPMCC, PHY UFS,
interconnect Bengal, reguladores RPM-SMD, votos de tensão/debug de
clock e os controladores GCC/DISPCC/GPUCC/debugcc Khaje). Evidência:
run [`40970905805`](https://github.com/Ctps1234/Kernel/actions/runs/40970905805)
do workflow `google-mainline.yml` verde sobre o commit `14b9d20`, e
reprodução local idêntica (árvore resultante byte a byte igual à
branch de rebase). Errata do mesmo dia: a primeira exportação do 0010
saiu incompleta (edições paralelas no mesmo arquivo se sobrescreveram
e só um dos três trechos de `common.c` sobreviveu — aplicava limpo,
mas não compilaria); corrigida e re-verificada no commit `14b9d20`.
Lição registrada: edições no mesmo arquivo, sempre sequenciais e
conferidas por grep de conteúdo, não só por aplicação limpa.

Sete entraram sem nenhum ajuste (0001, 0002, 0003, 0006, 0007, 0008,
0009). Quatro exigiram hunks manuais, todos conferidos por
comportamento contra o código 6.18:

- **0004** (`clk-smd-rpm.c`): include `<linux/clk.h>` recolocado após a
  entrada nova `<linux/cleanup.h>`; em `clk_smd_rpm_set_rate()`, a
  atribuição `r->rate = rate` no caminho de clock desabilitado foi
  portada para o novo formato upstream (`guard(mutex)` + `return 0`,
  sem o `goto out` do 6.12).
- **0005** (binding QMP UFS): `qcom,sm6225-qmp-ufs-phy` inserido na
  posição alfabética atual da lista (entre sm6125 e sm6350); o bloco
  `allOf` de clocks entrou sem ajuste.
- **0010** (votos de tensão): os quatro callbacks
  prepare/unprepare/pre/post_rate_change adicionados a
  `clk_rcg2_floor_ops` (o hunk gêmeo em `clk_rcg2_ops` entrou limpo);
  `struct qcom_cc_regmap_update` e os campos `clk_regulators`/
  `num_clk_regulators`/`pre_probe` de `qcom_cc_desc` recolocados em
  `common.h`; em `common.c`, includes e os helpers de
  deinit/unvote recolocados, o bloco de init de reguladores +
  `pre_probe` posicionado logo após a alocação de `cc` (antes do
  attach de power domains e da configuração de PLLs, preservando a
  semântica 6.12) e a chamada `qcom_cc_enable_critical_clocks()`
  adaptada ao novo caminho de erro `goto put_rpm`.
- **0011** (controladores Khaje): apenas o `Makefile` — as linhas
  `debugcc-khaje.o`/`dispcc-khaje.o` recolocadas em volta da entrada
  nova upstream `camcc-milos.o`. Os quatro drivers novos
  (gcc/dispcc/gpucc/debugcc) entraram sem ajuste.

`checkpatch.pl --strict` nos quatro patches manuais: mesmo resultado
das contrapartes 6.12 (único ERROR pré-existente da série inteira:
falta de `Signed-off-by`); nenhum achado novo introduzido pelo rebase.

Segunda fatia (2026-10-29): **0012–0015** rebaseados. 0012, 0013 e
0015 limpos; o 0014 (vendor-prefixes) foi recortado — `synaptics` já
existe upstream e ficou de fora — e seis entradas foram reinseridas à
mão nas posições alfabéticas atuais (fpc, nopmi, pd, signal, sm,
tcpc-dual), com o YAML validado e cada prefixo presente exatamente
uma vez. Série exportada reaplicada do zero: 15/15 limpos, árvore
idêntica à branch de trabalho. Gate verde na run `40977113902`.

Terceira fatia (2026-10-29): **0016–0025** (display/GPU/touch). O
0016 só precisou da linha de match no `dpu_kms.c`. O 0017 foi
re-desenhado para a arquitetura 6.18: a config UBWC saiu do
`msm_mdss.c` para a estrutura compartilhada `qcom_ubwc_cfg_data`
(`drivers/soc/qcom/ubwc_config.c`, chaveada pelo compatible da raiz),
então o `khaje_data` mora lá (match `qcom,khaje`), com dois campos
novos na estrutura — `ubwc_dec_version_from_reg` e `ubwc_static`. O
valor vendor `0x11f` foi decodificado contra os bitfields de
`UBWC_STATIC` (swizzle 7, bank spread, HBB 1, MIN_ACC_LEN 1): o
caminho por campos do dec_30 produziria `0x111`, perdendo os bits
1–3, por isso o valor cru continua sendo OR-ed no dec_30 (zero para
todas as plataformas upstream, sem mudança de comportamento);
`highest_bank_bit` convertido de 1 para 14 na nova codificação
absoluta, como nos irmãos SM6115/SM6125. No `msm_mdss.c` sobraram o
match `qcom,khaje-mdss` (reusando `data_76k8`, os mesmos 76800 de
`reg_bus_bw`), a leitura runtime da versão do decoder e a passagem
dela ao dec_40. 0018/0019/0023 entraram limpos (cascatas do 0011
resolvidas), 0020 ganhou as entradas nos grupos atuais dos bindings,
0021 só contexto de Kconfig/Makefile (driver já usa a API `_multi`,
todos os símbolos presentes no 6.18), 0022/0024 limpos, 0025 com a
terceira lista do binding reinserida à mão. Verificação do zero:
25/25 limpos, árvore idêntica. Gate verde na run `40978017904`.

Quarta fatia (2026-10-29): **0026–0033 — série completa**
(32 patches; o 0029 foi descartado de propósito). 0026 adaptado ao
driver renomeado (`qcom_pas_data`, `qcom_pas_init_regulator`),
incluindo o fallback de supply "mx"; 0027 limpo; 0028 com o helper
de tensão mínima portado e os campos `cx/px_supply_min_uV` sobre o
recurso novo; 0030 recortado (TX SM6115 já upstream — ficou só o
grupo fallback SM6225; VA/RX SM6115 + fallbacks SM6225 adicionados,
com o bloco de clocks do VA mantendo os `items` explícitos
mclk/dcodec/npl); 0031 limpo; 0032 só a linha de match; 0033 só o
`Makefile`. Verificação do zero: 32/32 limpos, árvore idêntica.

## Próximos passos (rebase concluído)

1. **Build de imagem nesta base — FEITO**: o job `kernel-build` do
   `google-mainline.yml` produz `Image` verde (run 40983813425:
   vmlinux linkado, `OBJCOPY arch/arm64/boot/Image`). Quatro rodadas
   de correções de API/schema foram necessárias (ver "Rodadas de
   build" abaixo) — aplicação limpa não pega quebra de API.
   Compilar/linkar não é boot: ainda falta DT upstream-style do
   SM6225/topaz nesta base e qualquer teste em hardware.
2. ~~Fragmento de config próprio para o 6.18~~: resolvido mantendo o
   fragmento compartilhado — a auditoria de símbolos passou nas duas
   bases e a única lacuna real (`CONFIG_SOUND=y`) era do fragmento
   em si. Criar fragmento 6.18-específico só se surgir divergência
   real entre as trilhas.
3. Itens novos já identificados e ainda não endereçados: auditoria do
   `PLL_FSM_LEGACY_MODE` no caminho Trion/Lucid (GPLL10/11), GENI I2C
   upstream, decisão CAMSS vs Spectra (SM6225/S5KJN1 ausentes no ACK;
   `sm6225-mainline`/`pmos-tapas` como referência), e o match UBWC
   `qcom,sm6225` quando existir DTS upstream-style (hoje só
   `qcom,khaje`, que é o que o FDT vendor declara).
4. ~~Discutir promover esta série~~: **decidido pelo dono —
   prosseguir com a 6.18 como trilha principal.** A série 6.12 em
   `patches/` fica congelada como referência/histórico até uma
   decisão separada sobre removê-la; trabalho novo vai para
   `patches-6.18/`.

## Rodadas de build (CI)

- Run 40979345152: `configure` verde apos `CONFIG_SOUND=y` no
  fragmento (o defconfig arm64 da ACK traz `SOUND=m`, o que limitava
  `SND` e toda a arvore ASoC a modulo; na base 6.12 o defconfig ja
  trazia `SOUND=y` e a lacuna estava mascarada). O `configure_kernel.sh`
  passou a exigir `SOUND` no REQUIRED.
- Mesma run, build: primeiro erro de compilacao em
  `phy-qcom-qmp-ufs.c` — o 0006 referenciava a lista compartilhada
  `qmp_phy_vreg_l`, removida no split por-SoC do driver 6.18. O 0006
  exportado agora define `sm6225_ufsphy_vreg_l` sem `init_load_uA`
  (mesmo comportamento da lista compartilhada antiga). **Errata
  posterior:** os maximos ja estavam no FDT vivo em
  `device-tree/reference/topaz-live-reference.dts`
  (`vdda-phy-max-microamp = 85700`, `vdda-pll-max-microamp = 18300`;
  supplies `pm6125_l4`/`pm6125_l18`), identicos no overlay 51 e no
  `khaje-idp.dtsi`; o 0006 passou a votar essas cargas. Relatorio
  de cada rodada fica na issue rotulada `ci-report` ("build do kernel
  6.18").
- Run 40980614978: proximo erro em `pinctrl-khaje.c` (0002):
  `.remove_new = msm_pinctrl_remove` — no 6.18 o membro voltou a se
  chamar `remove` e o helper `msm_pinctrl_remove` nao existe mais
  (drivers TLMM upstream nao declaram remove). 0002 exportado sem a
  linha; mesma limpeza preventiva no 0007 (`bengal.c`:
  `.remove_new` -> `.remove`, `qnoc_remove` continua existindo). O
  job de build passou a usar `make -k` para reportar todas as
  unidades quebradas por rodada.
- Run 40981633328 (com -k): todos os erros restantes num so arquivo,
  o catalogo DPU do Khaje (0016), cujo schema foi refatorado. O
  catalogo e quase identico ao do QCM2290/SM6115 upstream, o que da
  a traducao direta: mascaras SSPP viram `VIG_SDM845_MASK_NO_SDMA` /
  `DMA_SDM845_MASK_NO_SDMA` (SmartDMA continua nao anunciado, como
  no cabecalho do catalogo), e somem os `features` de ctl/lm/dspp/pp/
  dsc/intf — os enums correspondentes (`DPU_CTL_ACTIVE_CFG`,
  `DPU_DIM_LAYER`, `DPU_MIXER_COMBINED_ALPHA`, `DPU_DSPP_PCC`,
  `PINGPONG_SM8150_MASK`, `DPU_DSC_OUTPUT_CTRL`, `INTF_SC7180_MASK`)
  foram removidos e a semantica migrou para sblks/caps. Atenção em
  hardware: validar TE/modo comando (o sblk de pingpong upstream
  atual so declara dither) e PCC/DSC.
- Run 40983813425: **verde** — vmlinux linkado e
  `arch/arm64/boot/Image` gerada com a série completa (32 patches).
  A run 40981633325 do workflow 6.12 também ficou verde com as
  mudanças compartilhadas (fragmento com `SOUND=y`, REQUIRED com
  `SOUND`), sem regressão na trilha antiga. Com o marco atingido, o
  `make -k` saiu do job e a `Image` entrou no artefato
  `google-kernel-build`.

## Método (para repetir nas próximas fatias)

1. Clone raso da base fixada; branch de trabalho local.
2. `git apply` em ordem; limpos viram commit com a mensagem original
   (os patches 0001–0011 não têm `From:`/`Date:`, então `git am` não
   serve; extrair assunto/corpo parando em `---` **ou** no primeiro
   `diff --git`, senão o diff inteiro vaza para a mensagem — foi o que
   quebrou a primeira exportação do 0008/0009).
3. Falhas: `git apply --reject`, inspecionar cada `.rej` contra o
   código atual, encaixar à mão preservando a semântica, nunca só o
   contexto.
4. `git format-patch` da pilha para este diretório, renomeando para os
   nomes da série 6.12.
5. Verificação do zero: worktree limpo no commit fixado, aplicar a
   série exportada em ordem e conferir `git diff` vazio contra a
   branch de trabalho.
