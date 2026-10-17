# Status de integração das fontes DTS/DTBO importadas

## Origem

Fontes importadas de `nodrawAlliance/android_kernel_xiaomi_sm6225-devicetrees`,
branch `lineage-24.0`, commit `7581fa2ee9b8213f8989f329e11b642d17328a39`,
para `device-tree/source/` (54 arquivos, estrutura `qcom/...`). Ver
`device-tree/source/README.md`.

## Escopo

Base Khaje nopmi + overlays topaz/tapas (board IDs `0x30022`/`0x20022`) e
variantes `sm5602`, mais áudio, câmera e display topaz/tapas, além das
dependências SoC (Bengal/Khaje, PM6125, PM8008, SMMU, RDBG, GDSC, qupv3).

## Reconciliação de includes (estática)

A verificação é automatizada por `tools/check_dts_includes.py`, que resolve
`#include "..."` (relativos, na ordem do build: diretório do arquivo e
depois os diretórios globais) e `#include <...>` (caminhos do kernel).
Último resultado sobre a base fixada com a série 0001–0015 aplicada (0015 altera somente o binding pinctrl):

```
arquivos .dts/.dtsi/.dtso: 54
includes verificados: 103
todos os includes resolvem
```

### Includes de sistema

| Include | Disponibilidade |
|---|---|
| `dt-bindings/clock/qcom,{dispcc,gcc,gpucc}-khaje.h` | Fornecido pelo patch 0011 |
| `dt-bindings/clock/qcom,rpmcc.h` | Fornecido pelo patch 0004 (RPMCC) |
| `dt-bindings/interconnect/qcom,bengal.h` | Fornecido pelo patch 0007 |
| `dt-bindings/regulator/qcom,rpm-smd-regulator.h` | Fornecido pelo patch 0008 |
| `dt-bindings/phy/qcom,khaje-qmp-usb3.h` | Fornecido pelo patch 0012 |
| `dt-bindings/regulator/qcom,rpmh-regulator-levels.h` | **Fornecido pelo patch 0013** |
| `dt-bindings/arm/msm/qcom_dma_heap_dt_constants.h` | **Fornecido pelo patch 0013** |
| `dt-bindings/thermal/thermal_qti.h` | **Fornecido pelo patch 0013** |
| `dt-bindings/input/qcom,qpnp-power-on.h` | **Fornecido pelo patch 0013** |
| `dt-bindings/soc/qcom,dcc_v2.h` | **Fornecido pelo patch 0013** |
| `dt-bindings/audio-codec-port-types.h`, `dt-bindings/qcom,audio-ext-clk.h`, `dt-bindings/qcom,bolero-clk-rsc.h` | **Fornecidos pelo patch 0013** (a base 6.12 não traz nenhum dos três) |
| demais (`gpio.h`, `spmi.h`, `thermal/thermal.h`, `arm-gic.h`, `input.h`, `iio/qcom,spmi-vadc.h`, `interrupt-controller/irq.h`) | Presentes na base fixada |

Correção aplicada nas fontes: `audio/bengal-audio-overlay.dtsi` usava
`<bindings/...>`; passou a usar `<dt-bindings/...>`, que é o caminho
resolvido pelo build do kernel (`scripts/dtc/include-prefixes/dt-bindings`).

### Includes entre arquivos

Os 54 arquivos são agrupados em diretórios autossuficientes (raiz,
`audio/`, `camera/`, `display/display/`): a varredura não encontrou nenhum
include que dependa de outro diretório, então o `-i <dir do arquivo>` que
o build do kernel usa resolve tudo sem mexer em `DTC_INCLUDE`.

## Staging no kernel (reprodutível)

`tools/integrate_dts.py` faz o staging de forma determinística e idempotente:

1. copia `device-tree/source/qcom/**` para
   `arch/arm64/boot/dts/qcom/khaje/` (diretório próprio para não colidir
   com `pm6125.dtsi`/`pm8008.dtsi` que já existem na base 6.12);
2. renomeia os overlays (`/plugin/;`) de `.dts` para `.dtso`, que é a
   extensão que o build compila em `.dtbo` e combina com a base via
   `fdtoverlay`;
3. copia os Makefiles em estilo kernel de `device-tree/kernel/qcom/khaje/`
   (base, overlays de board e subdirs `audio/`, `camera/`, `display/`);
4. registra `subdir-y += khaje` em `arch/arm64/boot/dts/qcom/Makefile`.

Alvos gerados (mecanismo de multi-dtb do kernel):

| Artefato | Conteúdo |
|---|---|
| `khaje-idp-nopmi.dtb` | base Khaje (board id `0x10022`), compilada com `-@` |
| `khaje-idp-nopmi-topaz.dtb` | base + `topaz-khaje-idp-nopmi-overlay.dtbo` (board id `0x30022`) |
| `khaje-idp-nopmi-tapas.dtb` | base + `tapas-khaje-idp-nopmi-overlay.dtbo` (board id `0x20022`) |
| `audio/topaz-sm6225-audio-overlay.dtbo` | overlay de áudio topaz |
| `camera/topaz-camera-sensor-idp-overlay.dtbo` | overlay de câmera topaz |
| `display/display/topaz-sde-display-idp-nopmi-overlay.dtbo` | overlay de display topaz |

`tools/build_dts.py` reproduz localmente a mesma invocação do kernel
(`cpp` + `dtc` + `fdtoverlay`), sem exigir build completo.

## Reconciliação de compatibles (estática)

Verificados os compatibles SoC críticos usados pelos DTS importados contra
os drivers portados na série 0001–0014:

| Compatible (DTS) | Driver/patch | Status |
|---|---|---|
| `qcom,khaje-pinctrl` | 0002 | OK |
| `qcom,rpmcc-khaje` | 0004 | OK |
| `qcom,khaje-gcc/dispcc/gpucc/debugcc` | 0011 | OK |
| `qcom,bengal-{system_noc,config_noc,bimc,clk_virt,mmnrt_virt,mmrt_virt}` | 0007 | OK |
| `qcom,rpm-smd-regulator-resource` / `qcom,rpm-smd-regulator` | 0008/0009 | OK |
| `qcom,sm6225-qmp-ufs-phy` | 0005/0006 | OK (DTS corrigido de `qcom,ufs-phy-qmp-v4-khaje`) |
| `qcom,khaje` (SoC) | common kernel | OK |

Nenhuma divergência restante nos compatibles de fundação de boot.

## Validação com dtc

- A compilação local mais recente usou `tools/build_dts.py`, dtc 1.7 e
  `fdtoverlay`; base e overlays topaz/tapas foram reconstruídos das fontes
  staged e compostos com sucesso. Permanecem avisos preexistentes de DT
  vendor (`reg_format`, `ranges_format`, `unit_address_format`, etc.).
- Os overlays usam a sintaxe `&label { ... }` de topo, que exige dtc 1.5+;
  a validação autoritativa continua sendo o CI com dtc 1.7.0 da árvore base
  em `scripts/dtc`.
- CI (`.github/workflows/dts-validate.yml`): job `dts-validate` compila os
  DTBs/DTBOs, roda `dt-validate` (DT-schema) e `dt_binding_check`; job
  `kernel-build` compila a imagem do kernel para validar o port dos
  drivers.

## Validação DT-schema (dt-validate)

O job *Device trees* do CI roda o `dt-validate` sobre os três DTBs (base
Khaje e compostos topaz/tapas) e um gate de regressão
(`tools/dt_validate_report.py` + `docs/dt-validate-baseline.json`) que falha
quando aparece uma assinatura de erro nova ou quando alguma contagem
cresce. Detalhes, medição e backlog por schema em
[`docs/dt-schema-validation.md`](dt-schema-validation.md).

O último baseline oficial (antes do patch 0015) registrava 3009 erros em
778 assinaturas (833 no DTB base, contra 1143 no começo da rodada). A
validação local posterior, com o binding 0015 e `gpio-ranges`, reduziu o total
a 2791 (769 base; 1011 em cada composto), com zero erros de pinctrl Khaje e
664 avisos sem schema. O CI ainda deve confirmar essa redução; o backlog
restante é majoritariamente propriedade `qcom,*` do 5.15 sem binding 6.12.

## Bloqueadores conhecidos para build/DTBS_CHECK

1. ~~Header `qcom,khaje-qmp-usb3.h` ausente (USB)~~ — resolvido (patch 0012).
2. ~~Headers de áudio ausentes~~ — resolvido (patch 0013 + correção de include).
3. ~~Header `msm-camera.h` ausente~~ — resolvido (include removido).
4. ~~Headers RPMh/DMA-heap/thermal/DCC/power-on ausentes~~ — resolvido (patch 0013).
5. ~~DTS/DTBO não versionáveis~~ — resolvido: staging por
   `tools/integrate_dts.py` + Makefiles em `device-tree/kernel/`.
6. ~~Defconfig final~~ — resolvido: `config/topaz-khaje.config` +
   `tools/configure_kernel.sh`, e o build da imagem do kernel passou no CI.
7. Reduzir erros de `dt-validate` — em andamento: o patch pinctrl 0015 e o
   `gpio-ranges` zeram localmente os erros do binding nos três DTBs; o total
   caiu para 769 no base e 1011 em cada composto. A confirmação oficial e a
   atualização do baseline ainda dependem do CI (ver
   [`docs/dt-schema-validation.md`](dt-schema-validation.md)).

## Recomendação

- Manter a fundação de boot focada em `khaje-idp-nopmi.dts` +
  `topaz-khaje-idp-nopmi-overlay.dtso`, adiando áudio/câmera/display avançado.
- Não reutilizar binários 5.15 no KMI 6.12: os `.ko` do aparelho não são
  compatíveis e ainda não há fonte dos drivers proprietorários.
