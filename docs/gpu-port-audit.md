# Auditoria de port de GPU Topaz — Adreno 610 (A610)

## Resultado resumido

A rota de GPU adotada neste passo é **DRM/MSM A6xx upstream**, não um
forward-port do KGSL downstream. O resultado é deliberadamente limitado a
suporte de compilação/schema e a um protótipo DTS desabilitado:

- o patch [`0023-clk-qcom-gpucc-khaje-gdscs.patch`](../patches/0023-clk-qcom-gpucc-khaje-gdscs.patch)
  registra os GDSCs CX/GX no `gpucc-khaje` e exporta `GPU_CX_GDSC` /
  `GPU_GX_GDSC`;
- o patch [`0024-drm-msm-adreno-a610-khaje-speedbins.patch`](../patches/0024-drm-msm-adreno-a610-khaje-speedbins.patch)
  acrescenta as codificações Khaje 235 e 216 à tabela de speed-bins da A610;
- o patch [`0025-dt-bindings-iommu-arm-smmu-sm6225.patch`](../patches/0025-dt-bindings-iommu-arm-smmu-sm6225.patch)
  adiciona `qcom,sm6225-smmu-500` ao binding ARM SMMU, sem criar novo match
  de driver;
- [`device-tree/test/khaje-gpu-upstream.dtsi`](../device-tree/test/khaje-gpu-upstream.dtsi)
  materializa GPU, GMU-wrapper, Adreno SMMU, zap-shader e OPP-table no molde
  SM6115, com os recursos reais reconciliados do FDT Topaz e todos os nós em
  `status = "disabled"`;
- o nó `gpucc` da DTS fonte recebeu `#power-domain-cells = <1>`, mas a DTS de
  produção continua usando a hierarquia vendor/KGSL.

Nada disso é evidência de probe, boot, renderização ou paridade com o HAL
gráfico Android. Nenhum hardware foi exercitado.

## Por que DRM/MSM, e não importar o KGSL agora

O kernel 6.12 alvo já contém o driver DRM/MSM A6xx e uma entrada de catálogo
para a Adreno 610 (`chip-id 0x06010000`, GMU-wrapper e
`zapfw = "a610_zap.mdt"`). O SM6115/Bengal upstream fornece um molde completo
de nós GPU/GMU-wrapper/Adreno-SMMU nos mesmos endereços de topo. Portar o
KGSL 5.15 inteiro significaria importar uma pilha downstream grande, seu
contrato com userspace proprietário e dependências de power/ICC/IOMMU
anteriores ao modelo upstream; além disso, ele colidiria conceitualmente com
os providers Khaje já portados nesta série.

Isso não decide a paridade Android: o userspace gráfico atual do aparelho
fala KGSL (`/dev/kgsl-3d0`), enquanto o DRM/MSM expõe `/dev/dri/*` para
Mesa/freedreno. O objetivo deste passo é deixar o caminho upstream descrito e
compilável, sem apresentá-lo como substituto validado da pilha vendor.

## Mapeamento de recursos

A referência autoritativa de hardware é o FDT ativo em
[`device-tree/reference/topaz-live-reference.dts`](../device-tree/reference/topaz-live-reference.dts),
cruzado com o SM6115 upstream da base fixada.

| Recurso | FDT/vendor Khaje | Protótipo upstream |
|---|---|---|
| GPU | `qcom,kgsl-3d0@5900000`, janela principal `0x5900000/0x90000`, segunda janela `0x5961000/0x800`, IRQ GIC SPI 177 | `qcom,adreno-610.0`; split do SM6115: `kgsl_3d0_reg_memory=0x5900000/0x40000`, `cx_mem=0x599e000/0x1000`, `cx_dbgc=0x5961000/0x800`; IRQ 177 |
| GMU | sem firmware GMU completa; operação por wrapper | `qcom,adreno-gmu-wrapper` em `0x596a000/0x30000`, referenciado por `qcom,gmu` |
| SMMU | `kgsl-smmu@59a0000`, global SPI 163, contextos SPI 167–174 | `qcom,sm6225-smmu-500`, `qcom,adreno-smmu`, `qcom,smmu-500`, `arm,mmu-500`; mesmos endereço e IRQs |
| ICC | BIMC master 4 → slave 512 | `&bimc MASTER_GRAPHICS_3D &bimc SLAVE_EBI_CH0`, nome `gfx-mem` |
| Speed-bin | `gpu_speed_bin@6006`, `reg=<0x6006 0x2>`, `bits=<5 8>` | `nvmem-cells = <&gpu_speed_bin>`, nome `speed_bin` |
| Zap | região ativa `gpu_region@55b15000/0x2000` | filho `zap-shader` com `memory-region = <&pil_gpu_mem>` |

A janela `cx_mem` não é confirmada diretamente pelo FDT vendor: ele usa uma
janela principal única de `0x90000`. O split em três regiões é o formato do
molde SM6115 e permite descrever separadamente o bloco GMU-wrapper; essa
diferença permanece registrada como item de ativação, não como fato lido do
FDT.

### Clocks da GPU

Os seis clocks exigidos para `qcom,adreno-610.0` têm correspondência direta
nos IDs do FDT:

| Nome upstream | Provider/ID Khaje | Nome/papel vendor |
|---|---|---|
| `core` | `&gpucc GPU_CC_GX_GFX3D_CLK` (10) | `gfx3d_clk` |
| `iface` | `&gpucc GPU_CC_AHB_CLK` (0) | `iface_clk` |
| `mem_iface` | `&gcc GCC_BIMC_GPU_AXI_CLK` (3) | `mem_iface_clk` |
| `alt_mem_iface` | `&gcc GCC_GPU_MEMNOC_GFX_CLK` (76) | `mem_clk` |
| `gmu` | `&gpucc GPU_CC_CX_GMU_CLK` (4) | `gmu_clk` |
| `xo` | `&gpucc GPU_CC_CXO_CLK` (7) | `rbbmtimer_clk` no vendor |

Para a SMMU, o contrato `mem`/`hlos`/`iface` usa GCC 76, GPUCC
`GPU_CC_HLOS1_VOTE_GPU_SMMU_CLK` (12) e GCC 77. O FDT também lista o AHB do
GPUCC no `kgsl-smmu`; ele foi omitido para seguir o contrato de clocks da
implementação upstream compartilhada por QCM2290/SM6115/SM6125.

## GDSCs CX e GX (patch 0023)

O driver original do patch 0011 só registrava clocks e resets. O patch 0023
adiciona, nos offsets do bloco GPUCC:

| Domínio | GDSCR | Registros auxiliares | Flags upstream |
|---|---:|---|---|
| CX (`GPU_CX_GDSC=0`) | `0x106c` | HW control `0x1540` | `PWRSTS_OFF_ON`, `VOTABLE` |
| GX (`GPU_GX_GDSC=1`) | `0x100c` | GX BCR/SW reset `0x1008`, clamp/IO `0x1508` | `PWRSTS_OFF_ON`, `CLAMP_IO \| SW_RESET \| VOTABLE`, pai CX |

Os offsets foram confirmados pelos nós/syscons do FDT
(`0x5991008`, `0x5991508`, `0x5991540`) e coincidem com o `gpucc-sm6115`.
Os parâmetros vendor `qcom,no-status-check-on-disable`, timeout GDS 500 e
`clk-dis-wait=8` no CX não têm equivalente direto nas structs copiadas; os
waits/flags resultantes são, portanto, herdados do SM6115 e seguem sem
validação em hardware. `SM_GPUCC_6225` também passou a selecionar
`QCOM_GDSC`, porque `SM_GCC_6225` não faz essa seleção e o caminho precisa
funcionar sem depender de outro driver de clocks Qualcomm estar habilitado.

## Speed-bins, OPPs e o risco do fallback

O FDT lista cinco conjuntos `qcom,gpu-pwrlevels-*`, em ordem decrescente de
desempenho. Interpretando o sufixo como índice upstream do speed-bin, as
frequências e os `qcom,level` são:

| Fuse | Índice | Frequências vendor (MHz) |
|---:|---:|---|
| 0 | 0 | 1260, 1114.8, 1025, 785, 600, 465, 320 |
| 235 | 1 | 1114.8, 1025, 785, 600, 465, 320 |
| 216 | 2 | 1025, 785, 600, 465, 320 |
| 157 | 3 | 745, 600, 465, 320 |
| 127 | 4 | 600, 465, 320 |

Os `qcom,level` correspondentes são 64 (320 MHz), 128 (465), 192 (600), 256
(745/785), 384 (1025) e 416 (1114.8/1260). Daí saem as máscaras
`opp-supported-hw` do protótipo: `0x1f` para 320/465/600 MHz, `0x08` para
745 MHz, `0x07` para 785/1025 MHz, `0x03` para 1114.8 MHz e `0x01` para
1260 MHz.

A tabela upstream anterior só conhecia os fuses Bengal 206→1 e 200→2 (além
de 0, 157 e 127 compartilhados). Sem o patch 0024, uma unidade Khaje com
fuse 235 ou 216 não casaria com nenhuma entrada; o chamador usa então
`BIT(0)`, justamente o bin mais rápido. As máscaras, sozinhas, não seriam
uma proteção. O patch adiciona 235→1 e 216→2 nos mesmos slots dos bins
Bengal equivalentes.

A inferência sufixo→índice continua sendo uma hipótese de ativação: o fuse
da unidade capturada não foi lido, e a associação precisa ser confirmada por
leitura do QFPROM ou pelo código downstream antes de expor DVFS real.

### Corner sem RPMPD

O molde SM6115 coloca `power-domains = <&rpmpd ...>` na GPU e
`required-opps` em cada OPP. Esta árvore Khaje não tem nó RPMPD upstream; o
voto CX vendor passa pelos reguladores/votos RPM-SMD e pelo
`clk-vdd-class` dos patches 0009–0011. Por isso o protótipo omite tanto
`power-domains` na GPU quanto `required-opps` nas OPPs, em vez de inventar um
mapeamento dos `qcom,level` para estados genpd inexistentes. Fechar esse
contrato é pré-condição para qualquer ativação com DVFS.

Não foram adicionados `opp-peak-kBps`: o caminho ICC está descrito, mas os
valores vendor de barramento/DDR ainda não foram reconciliados com a
semântica de bandwidth do framework upstream.

## Chip-id 0x06010001 versus catálogo 0x06010000

O FDT declara `qcom,chipid = <0x06010001>` e modelo `Adreno610v2`. O driver
upstream, porém, deriva o chip-id do compatible `qcom,adreno-610.0`, gerando
`0x06010000` e selecionando a entrada A610 existente. Usar um compatible
`.1` inventado não ajudaria: não há entrada de binding/catálogo para ele.

Portanto, o protótipo segue o molde upstream, mas não prova que a revisão v2
dispensa quirks próprios. Diferenças de patch level, feature bits ou errata
só podem ser resolvidas com leitura de registradores no hardware ou fonte
confiável da revisão.

## SMMU Adreno (patch 0025)

O patch só altera o binding. Isso é intencional: em
`arm-smmu-qcom.c`, o match genérico `qcom,smmu-500` já seleciona
`qcom_smmu_500_impl0_data`, e o comentário do driver pede para não crescer a
lista por SoC quando esse caminho cobre o hardware. O compatible específico
`qcom,sm6225-smmu-500` descreve corretamente o silício sem fingir que ele é
SM6115 e cai na constraint de clocks `mem`/`hlos`/`iface` compartilhada.

O FDT também expõe região TCU e um TBU com seu próprio endereço/clock. O nó
do molde upstream descreve apenas a região principal `0x59a0000/0x10000`;
se o caminho de TBU precisar de descrição separada numa ativação Khaje, isso
terá de ser reconciliado então.

## Validação executada neste passo

- Os patches 0023–0025 foram gerados como commits separados sobre a base
  fixada já contendo 0001–0022 e exportados para `patches/`. Checkpatch:
  0 erros nos três; o 0023 mantém apenas avisos genéricos de separar
  bindings/includes e de linha de commit iniciada por `#`.
- A DTS fonte foi encenada com `tools/integrate_dts.py` numa árvore com a
  série aplicada. Um wrapper de teste incluiu `khaje.dtsi`,
  `khaje-idp-nopmi.dtsi` e os três fragmentos de `device-tree/test/`
  (MDSS, touch e GPU).
- Como não há `dtc` local, a validação local foi CPP igual ao do kernel +
  parse com `dtlib`: 1377 nós; GPU/GMU/SMMU encontrados, todos `disabled`;
  phandles e células conferidos explicitamente para clocks, IOMMU
  (`SID=0`, mask/flag `1`), ICC (4→512), OPPs/máscaras, GDSCs CX/GX
  (0/1) e `#power-domain-cells=1` no GPUCC.
- Isso valida includes, sintaxe, labels e specifiers do protótipo, mas,
  isoladamente, não substitui o build completo nem teste de probe.
  O `qcom,khaje-gpucc.yaml` já estava no `DT_SCHEMA_FILES` do CI; este passo
  acrescenta `arm,smmu.yaml` ao mesmo escopo.
- A run de CI [`40194361059`](https://github.com/Ctps1234/Kernel/actions/runs/40194361059), sobre o commit `bbfcecf`, terminou
  com os jobs *Kernel build (port dos drivers)* e *Device trees (dtbs +
  dt-schema)* em sucesso. Os artefatos mostram `gpucc-khaje.o`,
  `a6xx_catalog.o` e `arm-smmu-qcom.o` compilados, seguidos de `LD vmlinux`
  e `OBJCOPY arch/arm64/boot/Image`; o `System.map` contém
  `gpu_cc_khaje_gdscs`, `gpu_cc_khaje_desc` e `a6xx_gpus`, e a configuração
  efetiva tem `CONFIG_DRM_MSM=y`, `CONFIG_SM_GPUCC_6225=y`,
  `CONFIG_QCOM_GDSC=y`, `CONFIG_ARM_SMMU=y` e `CONFIG_ARM_SMMU_QCOM=y`.
  As strings `a610_zap.mdt`, `gpu_cx_gdsc` e `gpu_gx_gdsc` estão no
  `Image-khaje`.
- O sucesso do CI continua sendo evidência de aplicação, compilação/link e
  dos gates de DT do workflow. Não é evidência de probe da GPU/SMMU/GMU,
  carregamento do zap, DVFS seguro, renderização ou compatibilidade com o
  userspace Android.

## Bloqueios de ativação

1. **Coexistência com a descrição vendor.** A DTS de produção ainda contém
   `msm_gpu`/`qcom,kgsl-3d0`, `kgsl-smmu` e os GDSCs vendor. Ativar a
   hierarquia upstream exige remover/substituir esses nós, não apenas mudar
   `status` no protótipo.
2. **Status dos nós auxiliares.** GPU, GMU-wrapper e SMMU estão todos
   desabilitados neste protótipo. A forma final de habilitar GMU/SMMU deve
   seguir o contrato do driver e ser testada; a intenção aqui é impedir
   probe acidental.
3. **Corner de tensão.** Sem decisão RPMPD versus votos RPM-SMD/
   `clk-vdd-class`, as OPPs não têm `required-opps` e não devem dirigir DVFS
   real.
4. **Speed-bin real não lido.** O mapa 235→1/216→2 e a ordem dos bins
   precisam de confirmação no silício/fonte downstream.
5. **Revisão A610 v2.** O `0x06010001` pode precisar de quirks que o
   catálogo `0x06010000` não expressa.
6. **Zap e firmware.** A fonte usa `pil_gpu_mem` em `0x55615000`, enquanto o
   FDT ativo coloca a região em `0x55b15000`. Endereço, disponibilidade de
   `a610_zap.mdt`/SQE no vendor e o handshake com TrustZone/PIL não foram
   exercitados.
7. **Userspace Android.** DRM/MSM não é substituto drop-in do KGSL para o
   HAL/userspace vendor. Uma pilha gráfica Android funcional continua sendo
   uma decisão separada.
8. **Bandwidth e TBU.** Falta traduzir votos de barramento do vendor para
   `opp-peak-kBps` e decidir se TCU/TBU exigem descrição além do nó SMMU do
   molde.

## Arquivos deste passo

- [`patches/0023-clk-qcom-gpucc-khaje-gdscs.patch`](../patches/0023-clk-qcom-gpucc-khaje-gdscs.patch)
- [`patches/0024-drm-msm-adreno-a610-khaje-speedbins.patch`](../patches/0024-drm-msm-adreno-a610-khaje-speedbins.patch)
- [`patches/0025-dt-bindings-iommu-arm-smmu-sm6225.patch`](../patches/0025-dt-bindings-iommu-arm-smmu-sm6225.patch)
- [`device-tree/test/khaje-gpu-upstream.dtsi`](../device-tree/test/khaje-gpu-upstream.dtsi)
- [`device-tree/source/qcom/khaje.dtsi`](../device-tree/source/qcom/khaje.dtsi)
  — somente `#power-domain-cells = <1>` no `gpucc`
