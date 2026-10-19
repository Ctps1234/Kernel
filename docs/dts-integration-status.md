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
Último resultado oficial CI: run `39297306053` (commit `a3ba576`), com a série 0001–0018 e as DTS/DTBO atuais; a verificação confirmou 103 includes e todos resolvem:

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

Verificados os compatibles críticos usados pelos DTS importados contra os
drivers portados na série e os match tables/bindings do Android Common 6.12:

| Compatible (DTS) | Driver/patch | Status |
|---|---|---|
| `qcom,khaje-pinctrl` | 0002 | OK |
| `qcom,rpmcc-khaje` | 0004 | OK |
| `qcom,khaje-gcc/dispcc/gpucc/debugcc` | 0011 | OK |
| `qcom,bengal-{system_noc,config_noc,bimc,clk_virt,mmnrt_virt,mmrt_virt}` | 0007 | OK |
| `qcom,rpm-smd-regulator-resource` / `qcom,rpm-smd-regulator` | 0008/0009 | OK |
| GENI/QUP: `qcom,geni-se-qup`, `qcom,geni-i2c`, `qcom,geni-spi`, `qcom,geni-uart` | Drivers/bindings do Android Common 6.12 | Run `39289149697`: controladores e filhos GENI sem diagnósticos nos três DTBs; wrapper 2/2, `reg`/compatibles/clocks e ICC/DMA alinhados. I2C preserva 400 kHz; UART mantém IRQ de wake e estados `default`/`sleep`. O compatible legado do carregador BQ permanece sem match. Sem teste em hardware. |
| `qcom,sm6225-qmp-ufs-phy` + host UFS SM6225 | 0005/0006/0017/0018 | PHY/host sem diagnósticos nos três DTBs; run 39129187629 passou binding/example e compilou a imagem do kernel. Nenhum boot ou teste em hardware |
| `qcom,khaje` (SoC) | common kernel | OK |

Nenhuma divergência restante nos compatibles críticos de fundação de boot; o nó legado BQ, fora dessa fundação, continua sem match 6.12.

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

O baseline anterior ao patch 0015 registrava 3009 erros em 778 assinaturas
(833 no DTB base, contra 1143 no começo da rodada). A run oficial 39067847004,
com o binding 0015 e `gpio-ranges`, confirmou 2791 erros (769 base; 1011 em
cada composto), zero erros de pinctrl Khaje e 664 avisos sem schema; o baseline
versionado foi atualizado. A run 39069450075 encontrou os erros de meta-schema
que levaram ao patch 0016. A run 39071211672 aplicou 0001–0016 e validou
schemas/exemplos, gate `dt-validate` e kernel. A run 39090488896 aplicou
0001–0017, passou `dt_binding_check`/`dt-doc-validate` sem diagnósticos e
compilou DTBs/kernel; `dt-validate` caiu para 2686 erros/695 assinaturas, com
664 avisos. A run `39129187629` aplicou 0018: DTBs, gate de `dt-validate`,
`dt_binding_check` e `dt-doc-validate` passaram. O baseline versionado caiu
para 2632 erros/679 assinaturas/664 avisos, sem diagnósticos do host UFS nos
três DTBs; o job separado compilou a imagem do kernel. A run `39289149697`
revalidou a integração GENI: DTBs, gate, `dt_binding_check`,
`dt-doc-validate` e build do kernel passaram. A medição dessa run foi 2487
erros/643 assinaturas/640 avisos, abaixo do baseline, que não foi regravado;
GENI e UFS não têm diagnósticos nos três DTBs. A run `39297306053` também
passou após a correção do nó DWC3, medindo 2418 erros/631 assinaturas/640
avisos sem schema, abaixo do baseline 2632/679/664; o gate não detectou
regressão e o log não contém diagnósticos DWC3. O backlog restante é
majoritariamente propriedade `qcom,*` do 5.15 sem binding/leitor 6.12.

## Bloqueadores conhecidos para build/DTBS_CHECK

1. ~~Header `qcom,khaje-qmp-usb3.h` ausente (USB)~~ — resolvido (patch 0012).
2. ~~Headers de áudio ausentes~~ — resolvido (patch 0013 + correção de include).
3. ~~Header `msm-camera.h` ausente~~ — resolvido (include removido).
4. ~~Headers RPMh/DMA-heap/thermal/DCC/power-on ausentes~~ — resolvido (patch 0013).
5. ~~DTS/DTBO não versionáveis~~ — resolvido: staging por
   `tools/integrate_dts.py` + Makefiles em `device-tree/kernel/`.
6. ~~Defconfig final~~ — resolvido: `config/topaz-khaje.config` +
   `tools/configure_kernel.sh`, e o build da imagem do kernel passou no CI.
7. A run `39297306053` voltou a validar os schemas selecionados, incluindo
   `qcom,ufs.yaml`; `dt_binding_check` e `dt-doc-validate` passaram. Ver
   [`docs/dt-schema-validation.md`](dt-schema-validation.md).
8. **Host UFS:** `ufs_mem` permanece para MCQ e `ice`/`ice_core_clk` são
   consumidos pelo ICE; sem diagnósticos em nenhum dos três DTBs também na
   run `39297306053`. Gear e sequência elétrica não foram testados em hardware.
9. **GENI/QUP:** alinhamento 6.12 de wrapper, I2C/SPI/UART, ICC, DMA, clocks e
   pinctrl passou o gate na run `39297306053`; a medição global é
   2418/631/640 frente ao baseline versionado 2632/679/664. UART e periféricos
   ainda não foram testados em hardware.

## Recomendação

- Manter a fundação de boot focada em `khaje-idp-nopmi.dts` +
  `topaz-khaje-idp-nopmi-overlay.dtso`, adiando áudio/câmera/display avançado.
- Não reutilizar binários 5.15 no KMI 6.12: os `.ko` do aparelho não são
  compatíveis e ainda não há fonte dos drivers proprietorários.
