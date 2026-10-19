# Validação DT-schema (dt-validate) do port topaz/tapas

Documenta o estado da validação de schema das device trees do Redmi Note 12
4G (topaz/tapas) contra os bindings do upstream 6.12, o gate de regressão
usado no CI e o backlog que falta para zerar o `dt-validate`.

## Como a validação roda

O job *Device trees (dtbs + dt-schema)* do workflow
`.github/workflows/dts-validate.yml` faz, nesta ordem:

1. clone da base fixada (`0efd3abd3c356d644ea49f6ed37e9830b78d34e3`) e
   aplicação da série 0001–0018;
2. staging das DTS de `device-tree/source/` na árvore do kernel
   (`tools/integrate_dts.py`);
3. verificação estática de includes (`tools/check_dts_includes.py`);
4. configuração do kernel (`tools/configure_kernel.sh` + `config/topaz-khaje.config`);
5. build dos DTB/DTBO (`make qcom/khaje/...`): o DTB base primeiro, em um
   `make` separado, porque o sub-make do DTB composto e o do DTB base
   disputam o mesmo arquivo;
6. `make dt_binding_schemas` (schema processada via `dt-mk-schema`);
7. `dt-validate -m` sobre os DTBs já compilados (base, topaz e tapas);
8. gate de regressão: `tools/dt_validate_report.py` compara as assinaturas
   de erro com `docs/dt-validate-baseline.json`;
9. `dt_binding_check` com escopo nos bindings tocados pela série, seguido de
   `dt-doc-validate` direto para garantir que falhas de meta-schema não sejam
   suprimidas pelo Makefile upstream.

### Por que o dt-validate não roda dentro do make

Rodar `make CHECK_DTBS=1 ...` refaz o build dos DTBs com o comando do `dtc`
alterado (o `dt-validate` entra no comando). Com `-j`, os sub-makes do
kernel reconstroem o mesmo DTB base e um apaga o `.dtb.d` que o outro ainda
precisa:

```
fixdep: error opening file: arch/arm64/boot/dts/qcom/khaje/.khaje-idp-nopmi.dtb.d: No such file or directory
make[4]: *** [scripts/Makefile.dtbs:133: arch/arm64/boot/dts/qcom/khaje/khaje-idp-nopmi.dtb] Error 2
```

Por isso o `dt-validate` roda direto sobre os DTBs compilados, que é
equivalente (mesmo `dt-validate`, mesma schema processada, mesmas flags
`-m` do `dtbs_check` do kernel).

## Gate de regressão

`tools/dt_validate_report.py` lê a saída do `dt-validate` e classifica:

- **avisos**: `failed to match any schema with compatible` — nós de
  hardware owner que a árvore 6.12 não descreve; esperados enquanto os
  bindings vendor não são portados;
- **erros**: violações reais de schema (propriedade não permitida, tipo
  errado, nome fora do padrão, `oneOf` não satisfeito, ...).

Cada erro vira uma *assinatura* estável: schema de origem + mensagem com
valores binários e dígitos normalizados. As assinaturas são comparadas com
`docs/dt-validate-baseline.json`:

| Situação | Resultado |
|---|---|
| assinatura nova | **falha** (regressão) |
| contagem maior que a da linha de base | **falha** (regressão) |
| contagem menor | ok (melhora, reportada) |
| assinatura igual | ok |

A linha de base é versionada; reduções de erro exigem regenerá-la
(`python3 tools/dt_validate_report.py --log <log> --update`).

## Estado medido

### Última rodada oficial antes do patch 0015

Rodada `38991765488` (branch `arena/f49f65df-kernel`), três DTBs validados
(base Khaje + compostos topaz e tapas):

| DTB | Erros | Assinaturas | Avisos (sem schema) |
|---|---|---|---|
| `khaje-idp-nopmi.dtb` | 833 | 607 | 210 |
| `khaje-idp-nopmi-topaz.dtb` | 1088 | 774 | 227 |
| `khaje-idp-nopmi-tapas.dtb` | 1088 | 775 | 227 |
| **total** | **3009** | **778** | **664** |

O DTB base tinha 1143 erros no começo da rodada (o mesmo build, com o
`dt-validate` embutido no `make`): as correções de schema e de DTS tiraram
310 erros do DTB base (-27%), e os compostos topaz/tapas caíram de 1354
para 1088. Esses números são a medição oficial anterior à correção de
pinctrl; o baseline foi atualizado posteriormente com o log oficial da run
39067847004.

### Validação local após 0015 (17/10/2026)

O binding Khaje agora descreve explicitamente as propriedades do controlador,
os wrappers/grupos recursivos e os dois tipos de estado: mux (`pins` +
`function`) e pinconf-only (`config`, sem `function`, incluindo
`input-enable`). `device-tree/source/qcom/bengal-pinctrl.dtsi` declara
`gpio-ranges = <&tlmm 0 0 114>;`, alinhado ao `.ngpios = 114` do driver
Khaje. Também foi corrigido `tools/build_dts.py`: os overlays topaz/tapas são
compilados para `.dtbo` antes da composição, em vez de confundir o overlay
Topaz com a saída do DTB composto.

`dt-doc-validate` e `dt-mk-schema` passaram para o binding final. Base e
compostos foram recompilados de todas as fontes staged com `tools/build_dts.py`
(dtc 1.7 e `fdtoverlay`) e validados individualmente:

| DTB | Erros | Assinaturas | Erros pinctrl Khaje | Avisos (sem schema) | Diferença vs. CI anterior |
|---|---:|---:|---:|---:|---:|
| `khaje-idp-nopmi.dtb` | 769 | 563 | 0 | 210 | -64 |
| `khaje-idp-nopmi-topaz.dtb` | 1011 | 720 | 0 | 227 | -77 |
| `khaje-idp-nopmi-tapas.dtb` | 1011 | 721 | 0 | 227 | -77 |
| **total (assinaturas únicas)** | **2791** | **724** | **0** | **664** | **-218** |

O `tools/dt_validate_report.py`, aplicado à saída concatenada, retornou
`OK (sem regressao em relacao a linha de base)`. A medição inicial local usou
um adaptador temporário de `libfdt` apoiado em `tools/fdt_inventory.py`, pois o
`pylibfdt` nativo não compilou no host sem `Python.h`.

### Confirmação oficial do CI pós-0016

A run `39067847004` (commit `213855e`) recompilou DTBs e kernel, e o
`dt-validate` oficial reproduziu **2791 erros, 724 assinaturas e 664 avisos**,
sem erros de `qcom,khaje-pinctrl.yaml`. O gate de regressão passou e o baseline
foi atualizado a partir de `dtbs_check.log`. A inspeção posterior mostrou que
`dt_binding_check` tinha sido marcado como sucesso sem selecionar schemas:
`DT_SCHEMA_FILES` usava vírgulas em vez de `:` e `CROSS_COMPILE` não incluía
`gnu-`.

A run `39069450075` (commit `31a046f`) corrigiu a seleção e compilou os exemplos,
mas revelou erros de meta-schema em `qcom,bengal.yaml` e nos quatro bindings de
clock Khaje, além de avisos yamllint nas listas RPM-SMD. O patch 0016 removeu
limites redundantes de arrays `items`, declarou `reg` junto a `reg-names` e
citou nomes de propriedades com vírgula. Também foi adicionado `dt-doc-validate`
direto no workflow, pois o Makefile upstream suprime o status de erro desse
validador.

A run `39071211672` (commit `0dd27b1`) aplicou a série 0001–0016 e passou nos
dois jobs: build do kernel em 19m10s e validação DTS/DTBO em 2m36s. O log de
`dt_binding_check` contém `LINT` e compilação (`DTEX`/`DTC`) dos 12 schemas
selecionados, sem diagnósticos de erro ou avisos; o `dt-doc-validate` direto
também passou. `dt-validate` manteve os mesmos 2791 erros, 724 assinaturas e
664 avisos, e o gate retornou `OK (sem regressao)`. Portanto, as correções de
schema estão confirmadas pelo CI; o backlog restante é dos bindings 6.12/5.15
listados abaixo. A tentativa local anterior, no clone sparse, parou por faltar
`arch/x86/Makefile`.

### Confirmação oficial do port UFS 0017 e status (17/10/2026)

A run `39090488896` (commit `5b21a5a`) aplicou a série 0001–0017. O kernel e
os DTBs compilaram; `dt_binding_check` e o `dt-doc-validate` direto passaram
sem avisos nem erros. A binding QMP agora permite os nove clocks específicos
do SM6225, mantém as listas exatas por compatible e descreve a ausência de
reset externo/domínio de energia no PHY Khaje. `ufsphy_mem@4807000` não gera
mais diagnósticos em nenhum dos três DTBs. Os 54 valores `status = "ok"` em
`device-tree/source/` também foram normalizados para `"okay"`.

O baseline oficial caiu de **2791 erros/724 assinaturas** para **2686/695**,
com os mesmos **664 avisos sem schema**; o gate retornou `OK (sem regressao)`.
Na medição de 39090488896, o host `ufshc@4804000` ainda tinha compatible
curto, `reg-names` divergentes e propriedades vendor não descritas. O patch
0018 acrescenta `qcom,sm6225-ufshc` com fallback `qcom,ufshc`, preserva
`ufs_mem` para MCQ, nomeia a outra região `ice` e ordena `ice_core_clk` como
o último dos nove clocks, conforme os consumidores upstream. A condição do
binding exige também os clocks, a PHY e os dois caminhos ICC que o driver
obtém no probe. A DTS remove propriedades vendor sem consumidor 6.12, incluindo
os limites de Gear 3, não lidos pelo driver; o gear efetivo depende da
negociação host/dispositivo e precisa ser conferido em hardware.

A run `39129187629` (commit `2f66a18`) compilou os três DTBs, passou o gate
de `dt-validate`, `dt_binding_check` e `dt-doc-validate` direto. O schema
`qcom,ufs.yaml` e seu exemplo SM6225 foram selecionados/compilados, sem
avisos/erros de binding, e não há diagnósticos do host UFS em nenhum dos três
DTBs. O baseline oficial foi atualizado de **2686/695/664** para **2632
erros/679 assinaturas/664 avisos**; a redução é de 54 erros e 16 assinaturas.
O job separado de build do kernel também passou e compilou a imagem. Nenhum
teste de boot ou hardware foi executado.

### Confirmação oficial do QUP/GENI (run 39289149697)

A run `39289149697` (commit `e71b4f5`) revalidou os três DTBs base/topaz/tapas,
o gate de regressão, os schemas/exemplos da série e o build da imagem. A
medição dessa run foi **2487 erros, 643 assinaturas e 640 avisos sem schema**;
o baseline versionado permaneceu em **2632/679/664**. A diferença observada é
-145 erros, -36 assinaturas e -24 avisos; `dt_validate_report.py` retornou
`OK (sem regressao)`. Não houve diagnósticos `qcom,geni-se`, I2C/SPI/serial GENI
ou UFS nos três DTBs. `dt_binding_check`, `dt-doc-validate`, build DTB/DTBO e
build do kernel passaram.

As correções alinharam o wrapper GENI para células 2/2; os filhos para nomes
`i2c@`/`spi@`/`serial@`, `reg` de quatro cells, compatibles e `clock-names = "se"`; I2C4 preserva 400 kHz em `clock-frequency` e usa ICC/DMA por phandles
simbólicos. SPI/serial usam os dois caminhos ICC que os drivers pedem; o I2C
mantém os três caminhos e DMA. O UART mapeia os estados vendor `active`/`sleep`
para `default`/`sleep` upstream e mantém a segunda IRQ de wake e RX em GPIO no
estado de sleep. Propriedades vendor sem leitor no alvo foram removidas, sem
remover o `iommus` padrão do wrapper.

Para tornar o filho I2C legado validável, `bq2589x@6A` foi normalizado para
`bq2589x@6a`; propriedades custom `ti,bq2589x,*`, `intr-gpio` e `usb-switch1`
sem leitor no kernel 6.12 foram removidas. O compatible `ti,bq2589x-1` foi
mantido por não haver evidência suficiente para escolher uma variante BQ
upstream (`ti,bq25890`/`92`/`95`/`96`); esse nó não tem match no alvo e não
representa suporte funcional do carregador. Não houve boot nem teste de
carregamento/hardware. O baseline não foi atualizado: continua sendo apenas o
limite de não regressão, não a medição atual.

### Backlog por schema (DTB base, CI anterior a 0015)

A tabela abaixo é histórica, não o estado atual: o grupo GENI citado nela foi resolvido na run `39289149697`.

| Schema | Erros | Causa |
|---|---|---|
| `dt-core.yaml` | 549 | propriedades `qcom,*` do 5.15 sem binding na árvore 6.12 (`qcom,cpus`, `qcom,qmi-dev-name`, `qcom,instance-id`, `qcom,devfreq`, `qcom,glink-label`, `transport`, `vote`, `qcom,freq-domain`, `qcom,lmh-dcvs`, `qcom,dump-size`, `qcom,cdev-alias`, ...) |
| `simple-bus.yaml` | 85 | filhos de `/soc` sem `reg` e sem `ranges` (o schema exige `ranges` vazio quando não há `reg`) |
| `pinctrl/qcom,khaje-pinctrl.yaml` | 64 | binding Khaje incompleto no baseline anterior (patch 0001); patch 0015 + `gpio-ranges` zeraram esse grupo no `dt-validate` oficial da run 39067847004 |
| `soc/qcom/qcom,geni-se.yaml` | 22 | `clock-names` do GENI 5.15 (`se`) não confere com o schema 6.12 |
| demais | ~113 | `sdhci-msm`, `qcom,mpm`, `qcom,spmi-pmic`, `syscon-common`, `qcom,ufs`, `bengal`, `opp-v2`, `qcom,smmu`, `qcom,geni-se`, `idle-states`, ... |

Não aparecem mais na lista o binding RPM-SMD, o schema dos nós CTI e o
`vendor-prefixes.yaml`: as correções de schema desta rodada zeraram os
136 + 37 + 27 erros que eles somavam.

### Correções já aplicadas

- **binding pinctrl Khaje** (patch 0015): separa estados mux de estados pinconf-only, valida wrappers aninhados e evita que `patternProperties` trate propriedades do controlador como nós de estado. **DTS**: acrescenta `gpio-ranges = <&tlmm 0 0 114>` ao controller Bengal; os dois itens zeraram os erros `qcom,khaje-pinctrl.yaml` nos três DTBs na run oficial 39067847004.
- **binding RPM-SMD** (patch 0008): `qcom,set` e `qcom,regulator-type` sem
  `type` faziam o dtschema recusar a propriedade ("missing type
  definition") e comparar os bytes crus contra o `enum`. Note que
  `type: integer` **não** resolve: o dtschema não conhece esse tipo, ele
  obtém o tipo a partir do `$ref` (`/schemas/types.yaml#/definitions/uint32`).
  O padrão dos nomes de regulador (`"^((s|l|lvs|5vs)[0-9]*)|(boost-bypass)|(bob)$"`)
  também estava sem agrupamento, o que fazia qualquer propriedade iniciada
  em `s` (inclusive `status`) ser validada como se fosse um regulador.
- **binding PHY UFS** (patches 0005/0017): o SM6225 (Khaje) tem nove clocks
  (`ref_clk_src`, `ref_aux_clk`, `qref_clk` + clocks de símbolo RX/TX), não os
  três do grupo compartilhado. O patch 0017 eleva o limite geral que impedia a
  exceção de nove, mantém as restrições específicas por compatible, admite a
  ausência de reset externo/domínio de energia para este PHY e acrescenta um
  exemplo compilável. A DTS remove do nó PHY `reg-names`, `lanes-per-direction`,
  o reset acoplado ao host e limites de corrente que o driver QMP não consome.
- **valores `status` na DTS**: as 54 propriedades `status = "ok"` foram
  convertidas para `status = "okay"`, valor aceito pelo core schema; os erros
  correspondentes desapareceram do baseline oficial.
- **DTS**: `coresight-name` (87 nós) removida — a propriedade foi eliminada
  no upstream 6.12 e nenhum driver da árvore a lê; `reg-names` dos nós CTI
  removida e unidades normalizadas para hex minúsculo (o schema exige
  `^cti(@[0-9a-f]+)$`); `bias-disable = <0>` virou flag; o label do nó
  `aliases` foi removido (gerava um `phandle` rejeitado pelo schema de
  aliases); a tecla `vol_up` virou `key-vol-up` (padrão do schema
  `gpio-keys`); `ranges` vazio nos nós `cluster-device*`.
- **GENI/QUP (DTS)**: bindings/drivers 6.12 alinham `clock-names = "se"`, compatibles, nomes dos nós e recursos; o I2C4 teve os ICC/DMA codificados com phandles. Os seletores vendor `qcom,wrapper-core`, `qcom,wakeup-byte`, `qcom,clk-freq-out` e os marcadores de touchscreen sem leitor foram retirados; 400 kHz foi preservado em `clock-frequency`. A UART conserva a IRQ de wake e estados pinctrl padrão compatíveis. A validação oficial não acusa GENI nos três DTBs.
- **carregador BQ legado**: as propriedades custom sem leitor 6.12 foram removidas, mas `ti,bq2589x-1` continua sem match upstream; não se afirma suporte ao carregador.
- **`qcom,iommu-dma-addr-pool` (auditoria do alvo 6.12)**: as 23
  ocorrências em seis arquivos de `device-tree/source/` foram removidas;
  `device-tree/reference/` foi preservado como evidência da DTS/FDT downstream.
  A auditoria dos leitores e bindings do alvo não encontrou consumidor nem
  definição para essa propriedade. `arm,smmu.yaml`/`qcom,iommu.yaml` não a
  descrevem; o GPI usa `iommus`, `dma-channels`/`dma-channel-mask` e a API
  DMA (`dma_alloc_coherent`), sem pool vendor. O binding FastRPC documenta
  `iommus`/`qcom,nsessions`; o driver lê propriedades do contexto, sem pool.
  A binding IPA usa `iommus`/`memory-region`, e o driver mapeia recursos
  pela API IOMMU; CoreSight TMC usa `iommus`/DMA padrão; DWC3 usa a API DMA
  padrão. Os context banks legacy `qcom,qcedev`, IPA e SDE não têm leitor
  6.12 para esse campo. Mantivemos `iommus` e os recursos DMA padrão; a
  remoção não valida funcionamento dos stacks vendor, pools downstream,
  firmware ou hardware. A primeira run após a remoção (`39294474977`) mediu
  2430 erros/635 assinaturas/640 avisos, mas o gate falhou por uma nova
  assinatura agregada de `Unevaluated properties` no DWC3; a etapa não foi
  concluída. A correção em validação alinha o filho a `usb@4e00000` e remove,
  após auditoria do alvo, `qcom,iommu-dma`, `snps,disable-clk-gating`,
  `snps,usb3-u1u2-disable` e `usb-core-id` do nó DWC3, sem leitor/binding 6.12.
  `maximum-speed` foi mantido porque `drivers/usb/dwc3/core.c` o lê via
  `usb_get_maximum_speed()`; `iommus` também foi preservado. A correção aguarda
  nova CI; 2487/643/640 da run `39289149697` continua sendo a última medição
  verde. Outras ocorrências de `qcom,iommu-dma` em nós distintos ainda
  aguardam auditoria separada. Não houve teste em hardware.
- **prefixos vendor** (patch 0014): `bat`, `synaptics`, `fpc`, `fsm`,
  `mi`, `nopmi`, `pd`, `sc`, `si`, `sm`, `touch`, `vib`, `gpio-key`,
  `rt-tcpc`, `rt1711pd`, `tcpc-dual`, `typec`, `ln8000_charger`,
  `pin_assignment` e `signal` registrados em `vendor-prefixes.yaml` — sem
  as entradas o `dt-validate` rejeita cada propriedade que os usa.

## Próximos passos do backlog

1. **Propriedades vendor `qcom,*`** (maior fatia restante): auditar cada
   propriedade contra leitor e binding 6.12. Estender binding apenas quando
   houver consumidor no alvo; remover a propriedade da DTS importada quando
   não houver leitor, sem inventar schema para metadado inerte. A remoção de
   `qcom,iommu-dma-addr-pool` está aplicada, mas aguarda CI; priorizar depois
   propriedades recorrentes como `qcom,cpus`, `qcom,qmi-dev-name`,
   `qcom,instance-id`, `qcom,freq-domain`, `qcom,lmh-dcvs`, `qcom,dump-size`,
   `qcom,cdev-alias` e `qcom,glink-label`.
2. **Filhos de `/soc` sem `reg`**: o `simple-bus` do upstream exige
   `ranges` (vazio) nesses nós; são ~40 marcadores de vendor que hoje
   geram 85 erros no DTB base.
3. **Propriedades `qcom,*` ainda sem binding/leitor**: continuar pelo log da
   próxima CI após a auditoria e remoção de `qcom,iommu-dma-addr-pool`; a medição
   desta remoção ainda não é conhecida. Os diagnósticos GENI foram zerados na run
   `39289149697`; não reabrir esse bloco sem nova evidência. `sdhci-msm` e
   `simple-bus` continuam entre os demais grupos de erro.
4. Manter o gate: cada correção deve reduzir ou manter o baseline, e nunca
   introduzir assinatura/regressão.
