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
4. Só depois de build verde: discutir aposentar a trilha 6.12 e
   promover esta série a `patches/` principal.

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
  (mesmo comportamento da lista compartilhada antiga) porque os
  maximos `vdda-phy`/`vdda-pll` do Khaje ainda nao foram comprovados;
  preencher quando houver dado de FDT/downstream confiavel. Relatorio
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
