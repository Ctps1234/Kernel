# Nova base: ACK da Google (`android17-6.18`) + vendor novo

Registro da decisão de 2026-10-29 e do custo medido de migrar a série local
para a árvore oficial da Google, com a definição do que passa a ser o
"vendor novo" deste projeto. Nada aqui foi testado em hardware; o escopo
desta fatia é decisão + medição, sem alterar a série 0001–0033 nem o CI
atual.

## Decisão

- **Nova base alvo**: `kernel/common` da Google, branch **`android17-6.18`**,
  fixada no commit `1afe39edbe66c201d26f23f2e3396583238f6842`
  (2025-11-19, Linux `6.18.0-rc6`), via mirror oficial
  `https://github.com/aosp-mirror/kernel_common`.
- Por que `android17-6.18` e não `android-mainline`: a `android-mainline`
  (no mesmo instante em `9592f280229ade39addedb401857d4593deabd04`,
  também 6.18-rc6) é a branch de desenvolvimento que alimenta as linhas
  GKI, sem qualquer estabilidade de KMI. A `android17-6.18` é a linha GKI
  do Android 17 — nosso alvo de sistema — derivada dela, e é onde um
  vendor de produção se apoia. "Mainline da Google", para este projeto,
  significa ACK oficial em vez de mirror de terceiros.
- **Base antiga congelada, não apagada**: a série 0001–0033 continua verde
  sobre o commit `0efd3abd...` do mirror EdMory (6.12) e o workflow
  `dts-validate.yml` continua sendo o gate até a nova trilha atingir
  paridade de aplicação + build. Só então o default troca.
- O modelo do repositório não muda: série de patches numerada + base
  externa fixada por commit. Repins da base nova serão commits próprios,
  sempre com nova medição de custo (a branch ainda está em `-rc` e anda).

## O que é o "vendor novo"

Não reutilizar os módulos vendor 5.15 da Xiaomi (KMI incompatível e sem
futuro). O vendor passa a ser **nosso**, em duas camadas:

1. **Vendor de kernel (escopo deste repositório)**: a série de patches
   rebaseada sobre o ACK, o fragmento de config e o conjunto DTB/DTBO.
   Na fase de bring-up tudo pode ir built-in na imagem; a separação em
   módulos vendor sob a KMI do GKI (`vendor_boot`/`vendor_dlkm`, lista
   `modules.load`) é uma etapa posterior, quando houver boot para
   validar ordem de carga.
2. **Vendor de userspace Android (fora deste repositório, mas acoplado)**:
   cada escolha de driver no kernel fixa a HAL correspondente. A tabela
   abaixo é o contrato que a série de kernel deve respeitar; construir
   a imagem vendor em si é trabalho de árvore de device Android, não
   deste repo.

| Subsistema | Lado kernel (série nova) | Implicação no userspace |
|---|---|---|
| Display/GPU | DRM/MSM + DPU/DSI upstream, painel M7 | composer/gralloc sobre DRM e dma-buf heaps; KGSL e blobs Adreno ficam de fora |
| Touch | `edt-ft5x06` + FT3519 (0022) | input genérico, sem HAL proprietária |
| Áudio | ASoC/QDSP6 + AudioReach (`q6apm`/`q6prm`), macros/WCD upstream | policy/topologia AudioReach novas; firmware ADSP continua sendo blob |
| Câmera | **decisão pendente** (Spectra mantém HAL Xiaomi possível; CAMSS exige HAL nova) | maior item em aberto; ver `docs/camera-port-audit.md` |
| Wi‑Fi | **decisão pendente** (`ath11k` vs QCACLD+ICNSS2) | ver `docs/wifi-port-audit.md` |
| Sensores/fingerprint/carregador | sem fonte neste port até aqui | continuam bloqueados, independem da base |

Firmware blobs (ADSP, modem, etc.) continuam necessários em qualquer
cenário; "vendor novo" não promete um sistema 100% aberto.

## Custo medido do rebase (2026-10-29)

Método: clone `--depth 1` da branch `android17-6.18` no commit fixado e
`git apply --check` sequencial dos patches 0001–0033, aplicando os que
passam e registrando os que falham (sem `patch -f` nem 3-way: o clone
raso não tem os blobs da base antiga). Resultado: **15 aplicam limpos,
18 falham**. O mesmo loop está versionado em
`.github/workflows/google-mainline.yml` (somente `workflow_dispatch`)
para reproduzir a medição a cada repin.

### Aplicam limpos (manter como estão)

0001, 0002 (pinctrl Khaje), 0003 (binding RPMCC), 0006 (PHY UFS),
0007 (interconnect Bengal), 0008/0009 (reguladores RPM-SMD),
0012/0013 (headers dt-bindings), 0015 (panel notifier),
0018 (bindings MDSS/DPU), 0022 (FT3519 — confirmado **ausente** no
HEAD 6.18, continua nosso), 0024 (speed-bins A610),
0027 (loader ADSP), 0031 (LPI SM6225).

### Falham — disposição por patch

| Patch | Causa | Disposição |
|---|---|---|
| 0004 clk-rpmcc | contexto em `clk-smd-rpm.c` (includes/structs) | rebase |
| 0005 binding QMP-UFS | contexto da lista de compatibles; `sm6225` ausente upstream | rebase trivial |
| 0010 vdd-class | deriva em `clk-rcg2.c`/`common.c` | rebase |
| 0011 clock controllers | contexto do `Makefile` de `clk/qcom` | rebase; **bloqueia 0019/0023** |
| 0014 vendor-prefixes | contexto da lista alfabética | rebase/recortar (rechecar prefixo a prefixo) |
| 0016 catálogo DPU | refatoração em `dpu_kms.c` | rebase com revisão |
| 0017 MDSS/UBWC | `msm_mdss.h` deixou de existir | rebase com revisão |
| 0019 GDSC dispcc | cascata do 0011 (arquivos não criados) | reavaliar após 0011 |
| 0020 compatibles DSI | contexto dos bindings; `sm6225` ausente upstream | rebase trivial |
| 0021 painel M7 | contexto de `Kconfig`/`Makefile` (driver é arquivo novo) | rebase trivial |
| 0023 GDSCs gpucc | cascata do 0011 + contexto de `Kconfig` | reavaliar após 0011 |
| 0025 binding arm,smmu | contexto; `sm6225` ausente upstream | rebase trivial |
| 0026 PAS ADSP SM6225 | deriva na tabela de match (`sm6115` presente como âncora) | rebase |
| 0028 votos PAS | depende do 0026 | rebase |
| 0029 resets LPASSCC SM6115 | **já upstream**: `lpasscc-sm6115.c` no 6.18 já traz os dois mapas de reset e o binding existe | **descartar** |
| 0030 macros LPASS | TX SM6115 já upstream (binding + driver); VA/RX e matches SM6225 continuam nossos | recortar + rebase |
| 0032 máquina sc8280xp | deriva no driver de máquina | rebase |
| 0033 WL2866D | contexto do `drivers/misc/Makefile` | rebase trivial |

### Fatos da base nova que mudam o desenho

- **SM6225 continua sem suporte upstream** no ACK 6.18: não há
  `sm6225.dtsi`, `gcc-sm6225.c` nem `pinctrl-sm6225.c`; o irmão SM6115
  está presente (`sm6115.dtsi`, GCC, pinctrl, LPASSCC). A série Khaje
  continua necessária — a base nova não aposenta o grosso do port.
- **CAMSS não tem recursos SM6115/SM6225** na base nova, e o sensor
  S5KJN1 não está na árvore (OV08D10 está). Câmera segue dependendo de
  port próprio; a referência `sm6225-mainline`/`pmos-tapas` continua
  válida para identificação de sensores e fiação.
- O gap de clock encontrado via `pmos-tapas` persiste no 6.18:
  `PLL_FSM_LEGACY_MODE` só é setado em `clk_fabia_pll_configure()`,
  não no caminho Trion/Lucid usado por GPLL10/GPLL11. Vira candidato
  a patch novo na série rebaseada, após auditoria contra o downstream.
- GENI I2C e CCI upstream estão presentes, como já estavam no 6.12.

## Sequência de migração proposta

1. Rebasear em fatias pequenas, na ordem da série, começando pelos
   triviais (0005, 0020, 0021, 0025, 0033) e pelo desbloqueador 0011;
   descartar o 0029 e recortar 0014/0030 no caminho. Cada fatia fecha
   com aplicação limpa na base nova medida pelo workflow manual.
2. Quando a série inteira aplicar, ligar build de imagem + `dtbs` no
   workflow novo (mesmos gates do atual) e só então promover
   `google-mainline.yml` a gate de push e aposentar a base 6.12.
3. Manter a DTS downstream atual durante o rebase (identidade da
   série). A migração para DTS upstream-style (`sm6225.dtsi` próprio,
   espelhando o SM6115) é decisão separada, por subsistema, depois da
   paridade — não misturar os dois movimentos.
4. Câmera e Wi‑Fi continuam com decisão arquitetural pendente; o
   rebase não as resolve e não deve fingir que resolve.

## Riscos assumidos

- Base em `-rc`: repins frequentes até o 6.18 estabilizar; mitigado
  pelo pin por commit + workflow de custo.
- KMI do `android17-6.18` ainda não congelada: irrelevante enquanto
  kernel e módulos nascem juntos da mesma série; vira restrição real
  na fase de módulos vendor separados.
- A base antiga (mirror EdMory, linhagem CLO) pode conter deltas
  Qualcomm que o ACK puro não tem; a medição de aplicação não detecta
  dependência semântica. Cada patch rebaseado deve ser conferido pelo
  comportamento, não só pelo contexto.
- Nenhuma das duas bases foi testada em hardware. A troca de base não
  altera esse fato nem autoriza flash.

## Progresso

- **2026-10-29**: primeira fatia executada — patches **0001–0011**
  rebaseados para `patches-6.18/` (sete sem ajuste; 0004, 0005, 0010 e
  0011 com hunks manuais conferidos por comportamento), verificados
  aplicando limpos do zero sobre o commit fixado, com a árvore final
  idêntica à branch de trabalho. O workflow `google-mainline.yml`
  virou gate de push para `patches-6.18/**` e fechou verde na run
  [`40970905805`](https://github.com/Ctps1234/Kernel/actions/runs/40970905805)
  (commit `14b9d20`, que também corrige uma exportação incompleta do
  0010 causada por edições paralelas no mesmo arquivo; detalhes no
  README da série). Detalhes, método e
  fila restante em `patches-6.18/README.md`. Próxima fatia natural:
  0012–0015 + 0018 (limpos ou quase) ou o desbloqueio de display
  0016/0017; build de imagem nesta base continua pendente.
- **2026-10-29 (continuação)**: rebase **concluído** — 0012–0015
  (run `40977113902`), 0016–0025 (run `40978017904`; destaque para o
  0017 re-desenhado sobre o `qcom_ubwc_cfg_data` compartilhado) e
  0026–0033 (run `40978442794`), totalizando 32 patches com o 0029
  descartado por já estar upstream. Todas as fatias verificadas do
  zero (aplicação limpa + árvore idêntica) e verdes no gate
  `google-mainline.yml`. Próximo marco: job de build de imagem no
  mesmo workflow (auditoria prévia: todos os 57 símbolos do fragmento
  e os símbolos obrigatórios do `configure_kernel.sh` ainda têm
  definição Kconfig na árvore 6.18+série).
