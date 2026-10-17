# Validação DT-schema (dt-validate) do port topaz/tapas

Documenta o estado da validação de schema das device trees do Redmi Note 12
4G (topaz/tapas) contra os bindings do upstream 6.12, o gate de regressão
usado no CI e o backlog que falta para zerar o `dt-validate`.

## Como a validação roda

O job *Device trees (dtbs + dt-schema)* do workflow
`.github/workflows/dts-validate.yml` faz, nesta ordem:

1. clone da base fixada (`0efd3abd3c356d644ea49f6ed37e9830b78d34e3`) e
   aplicação da série 0001–0014;
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
9. `dt_binding_check` com escopo nos bindings tocados pela série.

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
para 1088.

### Backlog por schema (DTB base)

| Schema | Erros | Causa |
|---|---|---|
| `dt-core.yaml` | 549 | propriedades `qcom,*` do 5.15 sem binding na árvore 6.12 (`qcom,cpus`, `qcom,qmi-dev-name`, `qcom,instance-id`, `qcom,devfreq`, `qcom,glink-label`, `transport`, `vote`, `qcom,freq-domain`, `qcom,lmh-dcvs`, `qcom,dump-size`, `qcom,cdev-alias`, ...) |
| `simple-bus.yaml` | 85 | filhos de `/soc` sem `reg` e sem `ranges` (o schema exige `ranges` vazio quando não há `reg`) |
| `pinctrl/qcom,khaje-pinctrl.yaml` | 64 | binding Khaje (patch 0001) ainda não descreve os grupos usados pela DTS 5.15 |
| `soc/qcom/qcom,geni-se.yaml` | 22 | `clock-names` do GENI 5.15 (`se`) não confere com o schema 6.12 |
| demais | ~113 | `sdhci-msm`, `qcom,mpm`, `qcom,spmi-pmic`, `syscon-common`, `qcom,ufs`, `bengal`, `opp-v2`, `qcom,smmu`, `qcom,geni-se`, `idle-states`, ... |

Não aparecem mais na lista o binding RPM-SMD, o schema dos nós CTI e o
`vendor-prefixes.yaml`: as correções de schema desta rodada zeraram os
136 + 37 + 27 erros que eles somavam.

### Correções já aplicadas

- **binding RPM-SMD** (patch 0008): `qcom,set` e `qcom,regulator-type` sem
  `type` faziam o dtschema recusar a propriedade ("missing type
  definition") e comparar os bytes crus contra o `enum`. Note que
  `type: integer` **não** resolve: o dtschema não conhece esse tipo, ele
  obtém o tipo a partir do `$ref` (`/schemas/types.yaml#/definitions/uint32`).
  O padrão dos nomes de regulador (`"^((s|l|lvs|5vs)[0-9]*)|(boost-bypass)|(bob)$"`)
  também estava sem agrupamento, o que fazia qualquer propriedade iniciada
  em `s` (inclusive `status`) ser validada como se fosse um regulador.
- **binding PHY UFS** (patch 0005): o SM6225 (Khaje) tem nove clocks
  (`ref_clk_src`, `ref_aux_clk`, `qref_clk` + clocks de símbolo RX/TX) e
  não os três clocks do grupo compartilhado.
- **DTS**: `coresight-name` (87 nós) removida — a propriedade foi eliminada
  no upstream 6.12 e nenhum driver da árvore a lê; `reg-names` dos nós CTI
  removida e unidades normalizadas para hex minúsculo (o schema exige
  `^cti(@[0-9a-f]+)$`); `bias-disable = <0>` virou flag; o label do nó
  `aliases` foi removido (gerava um `phandle` rejeitado pelo schema de
  aliases); a tecla `vol_up` virou `key-vol-up` (padrão do schema
  `gpio-keys`); `ranges` vazio nos nós `cluster-device*`.
- **prefixos vendor** (patch 0014): `bat`, `synaptics`, `fpc`, `fsm`,
  `mi`, `nopmi`, `pd`, `sc`, `si`, `sm`, `touch`, `vib`, `gpio-key`,
  `rt-tcpc`, `rt1711pd`, `tcpc-dual`, `typec`, `ln8000_charger`,
  `pin_assignment` e `signal` registrados em `vendor-prefixes.yaml` — sem
  as entradas o `dt-validate` rejeita cada propriedade que os usa.

## Próximos passos do backlog

1. **Bindings vendor das propriedades `qcom,*`** (maior fatia do backlog):
   escrever bindings para as propriedades que a DTS 5.15 usa e que a
   árvore 6.12 não descreve, começando pelas que mais repetem
   (`qcom,cpus`, `qcom,qmi-dev-name`, `qcom,instance-id`, `qcom,freq-domain`,
   `qcom,lmh-dcvs`, `qcom,dump-size`, `qcom,cdev-alias`, `qcom,glink-label`).
2. **Binding do pinctrl Khaje** (patch 0001): completar os grupos de pin
   usados pela DTS 5.15 (`qupv*_se*_i2c_pins`, `cam_sensor_*`, ...).
3. **Filhos de `/soc` sem `reg`**: o `simple-bus` do upstream exige
   `ranges` (vazio) nesses nós; são ~40 marcadores de vendor que hoje
   só geram 85 erros no DTB base.
4. **GENI/SE e `sdhci-msm`**: alinhar `clock-names`/`reg-names` da DTS com o
   schema 6.12, ou estender os bindings para aceitar os nomes 5.15.
5. Manter o gate: cada correção deve reduzir a linha de base, e nunca
   aumentá-la.
