# Device Tree topaz — fases 1 (conversão mecânica) e 2 (curadoria)

Esta pasta contém o item 1 do plano: transformar a base Khaje + overlay topaz em arquivos versionáveis. A fase 1 é a trilha de auditoria; a fase 2 é a DT curada, gerada a partir dela.

## Conteúdo

| Arquivo | Origem | Observação |
|---|---|---|
| [`topaz-overlay.dtso`](topaz-overlay.dtso) | Gerado por [`tools/symbolize_overlay.py`](../../tools/symbolize_overlay.py) a partir de [`topaz-overlay-51-reference.dtso`](../reference/topaz-overlay-51-reference.dtso) | Overlay `/plugin/` com referências simbólicas (`&label`). 363 referências externas à base e 170 internas foram convertidas usando apenas `__fixups__`, `__local_fixups__` e `__symbols__` do próprio dtc. |
| Base Khaje | [`khaje-base-reference.dts`](../reference/khaje-base-reference.dts) | Ainda usada como está: phandles numéricos (`<0x126>`), sem labels. Nenhuma conversão foi feita aqui. |
| [`khaje.dtsi`](khaje.dtsi) | Gerado por [`tools/curate_dt.py`](../../tools/curate_dt.py) a partir da base | **Fase 2 (escopo C).** SoC reduzida ao port 6.12: 161 de 1978 nós da base. Phandles viram `&label` quando o alvo está no arquivo. |
| [`topaz.dts`](topaz.dts) | Gerado por `tools/curate_dt.py` a partir do overlay e do FDT ativo | **Fase 2 (escopo C).** Inclui `khaje.dtsi`; define as propriedades de raiz, `/memory` e um bloco `&label { … }` por fragment mantido do overlay. |
| [`excluidos.txt`](excluidos.txt) | Gerado por `tools/curate_dt.py` | Trilha de auditoria do escopo C: fragmentos e nós do overlay que saíram da DT curada, com o motivo. |
| [`topaz-overlay.dtso`](topaz-overlay.dtso) (entrada) | Fase 1 | Continua completo (50 fragmentos). A curada usa só os fragmentos mantidos. |

A conversão do overlay é exata por construção: cada célula `0xffffffff` apontada por `__fixups__` vira `&label`, e cada phandle local apontado por `__local_fixups__` vira `&label` do próprio overlay. Os 9 `0xffffffff` restantes são valores literais de calibração térmica (`-1`), não referências. O gerador é determinístico e o workflow confere se o arquivo versionado continua igual à saída do script.

## Validação

`tools/validate_dt.sh` roda, nesta ordem:

1. confere se o overlay versionado é a saída atual de `symbolize_overlay.py`;
2. compila a base com `dtc`;
3. compila o overlay como plugin com `dtc -@`;
4. aplica o overlay na base com `fdtoverlay`;
5. compara o resultado com o FDT ativo de referência (`topaz-live-reference.dts`) com [`tools/dts_semantic_diff.py`](../../tools/dts_semantic_diff.py), que compara por nó e propriedade e troca phandles por caminhos.

O workflow [`device-tree.yml`](../../.github/workflows/device-tree.yml) executa o script em GitHub Actions. O sandbox não tem `dtc` (sem flex/bison), então a validação só existe na CI.

### Resultado (run `38278723796`, commit `d9b850a`)

- Base, overlay (`dtc -@`) e merge (`fdtoverlay`) **compilam e aplicam sem erro**.
- Comparação semântica com o FDT ativo de referência:
  - **2136 nós idênticos** nas duas árvores.
  - Propriedades só no ativo (3): `/memory:ddr_manufacturer_id`, `/memory:ddr_size` e `/soc/xiaomi_touch:get_panel_info`, injetadas pelo bootloader.
  - Valores brutos diferentes (5):
    - raiz `model`, `compatible` e `qcom,board-id`. O `fdtoverlay` **não aplica propriedades da raiz do overlay**, só fragments. Logo, a placa precisa definir essas propriedades na fase 2, ou o bootloader precisa injetá-las;
    - `/memory:reg`: preenchido pelo bootloader com as faixas reais de RAM;
    - `/firmware/android/fstab/vendor:status`: `ok` na base decompilada e `disabled` no ativo. O overlay não altera esse nó; a diferença vem do ambiente de runtime.
  - Diferença só após a troca por phandle (1): `qcom,mdss-dsi-on-command` do painel m7. Os valores brutos são idênticos (135 células); a diferença vem do próprio método de comparação, que converte números que coincidem com phandles.

Os itens acima são diferenças esperadas (bootloader/runtime), não erros de conversão.

### Validação dt-schema (run `38280602426`, commit `806c336`)

Job `dt-schema` (com `continue-on-error`), na base fixada `0efd3abd3c356d644ea49f6ed37e9830b78d34e3` com os patches 0001–0011 aplicados:

- **`dt-doc-validate` nos bindings da série: sem erros.** Corrigidos na série: `minItems`/`maxItems` redundantes com `items` (khaje-gcc, -dispcc, -gpucc, -debugcc e bengal), `reg` ausente com `reg-names` (khaje-dispcc, -gpucc, -gcc), `linux,phandle`/`name` sem tipo (pinctrl) e `qcom,set`/`qcom,regulator-type` (enum inteiro) sem tipo (rpm-smd). O `phandle` do pinctrl continua `true`: com `$ref: phandle` o dt-validate falhava com `property has multiple types`.
- **`dt-mk-schema`: sem erros da série.** Restam só avisos do upstream: `firmware/gunyah-cma-mem.yaml` (não parseia) e `fsl,liodn` em bindings de outros subsistemas (tipos conflitantes).
- **`dt-validate` do DTB mesclado: executa até o fim**, mas o log lista violações. O job termina com sucesso porque o script só falha se o `dt-validate` retornar erro; a lista abaixo continua pendente:
  - `bias-disable`: a base tem `bias-disable = <0x0>` (4 bytes); o binding espera flag booleana. O driver lê só a presença, então é divergência de schema, não de funcionamento.
  - `/` (qcom,khaje): nó `memory` placeholder com `device_type` e `reg` (zeros) não permitidos por `root-node.yaml`. Deve ser preenchido/removido na fase 2.
  - `aliases`: `phandle` (294) tratado como alias, não é array. Candidato a remoção na fase 2.
  - `cpu@N`: `qcom,freq-domain` e `qcom,lmh-dcvs` aparecem como bytes. O nó `phandle = <0x5>` existe na base (dispositivo de performance), então a hipótese é limitação do dtschema para propriedades sem binding de CPU (cells desconhecidas), não phandle quebrado. **Confirmado na CI:** a causa era falta de binding. O patch `0012` declara as duas propriedades em `arm/cpus.yaml`, e os erros de `cpu@N` sumiram (ver "Resultados da CI (escopo C)").
  - O log completo está no artefato `topaz-dt-schema` do run. Não foi possível contar todas as violações pelas anotações (truncadas).

### O que ainda **não** foi validado

- **DT-schema do DTB mesclado**: executado, mas as violações listadas acima ainda não foram corrigidas (fase 2). Bindings da série: sem erros.
- **Hardware**: nada aqui foi testado no aparelho. Não flashar.

## Fase 2 — DT curada (escopo C)

**Decisão:** a DT curada é reduzida ao escopo do port 6.12. Saem da curada e de `topaz.dts` os subsistemas fora do port inicial, porque não há driver 6.12 nesta série para eles e o dt-schema não tem como validar as propriedades vendor deles:

- display (MDSS/DSI/SDE, painel, backlight do painel) (dependem do painel);
- toque: **exceção controlada.** O nó de vendor `focaltech@38` (`focaltech,fts`) sai, e o barramento `qupv3_se2_i2c` perde as propriedades vendor `qcom,touch-active` e `qcom,i2c-touch-active`. No lugar entra o nó upstream `touchscreen@38` (`focaltech,ft5452`, driver `edt-ft5x06`), emitido por `TOUCH_PORT_BLOCK` em `tools/curate_dt.py`. Valores vindos da stock: IRQ no GPIO 80 (`0x50 0x02`), reset no GPIO 86 (`0x56 0x01`), coordenadas 10799×23999. O regulador fixo `touch_avdd` liga o GPIO 36 (AVDD da stock). Goodix e Synaptics continuam fora. O pinctrl entra como `ts_int_active` (GPIO 80) e `ts_reset_active` (GPIO 86), com os valores do `pmx_ts_*` da stock (mux gpio, pull-up, drive 8). O AVDD (GPIO 36) não tem pinctrl próprio, porque é regulador fixo. **Iovcc:** a stock não declara regulador de IO para o touch (o nó `focaltech,fts` nem o barramento `qupv3_se2_i2c` têm `supply`). Por isso não se adiciona `iovcc-supply`; o driver usa regulador fictício. **Pendência:** polaridade do reset. Nada disso foi testado em hardware.
- câmera (CCI, CSIPHY, CPAS, TFE/IFE, OPE, sensores, EEPROM, flash `ovti,wl2866d`);
- carregador, Type-C e bateria (incluindo o 1-wire `onewire_gpio`/`maxim,ds28e16`);
- áudio (SPF/LPASS, codecs WCD, SoundWire, ref clocks, amplificador de speaker `si,sia81xx`);
- USB (DWC3 e PHYs HS/SS), SD/eMMC (`sdhci-msm`), impressão digital;
- depuração (CoreSight, JTAG, EUD), DSP/modem (remoteproc, FastRPC), IPA, Wi-Fi/BT, TrustZone e criptografia.

Não é exclusão da fase 1: o overlay completo continua em `topaz-overlay.dtso`, e `excluidos.txt` lista cada fragmento e nó removido, com o motivo. A regra é o regex `EXCLUDE_COMPAT` em `tools/curate_dt.py`, aplicado ao `compatible` (do overlay, da base ou do FDT ativo). Também há `EXCLUDE_PATHS` (ex.: `/soc/thermal-screen`, que não tem compatible). O fecho não traz de volta um nó excluído. Se um overlay mantido referenciar um nó excluído, o gerador para com erro.

O que fica: CPUs, PSCI, GIC/timers, RPM-SMD (regulators e clocks), SMEM/glink, SPMI/PMIC (vadc, adc_tm, gpios, pwm), TLMM e os estados de pinctrl usados, UFS (controlador e PHY), UART e I²C de baixa velocidade, reserved-memory, thermal zones e `/memory` (valores do FDT ativo).

### Como gerar e verificar

```sh
python3 tools/curate_dt.py --out-dir device-tree/topaz          # gera e verifica
python3 tools/curate_dt.py --out-dir device-tree/topaz --check  # só verifica
```

Normalizações intencionais (todas documentadas no gerador):

- **Labels:** a base decompilada não tem labels nos nós, então eles vêm de `__symbols__`. Phandles viram `&label` só nas propriedades que o gerador conhece: listas com células do provedor (`clocks`, `resets`, `power-domains`, `interrupts-extended`, `phys`, `dmas`, `iommus`, `qcom,freq-domain`, `sound-dai` etc.), referências simples (`interrupt-parent`, `memory-region`, `operating-points-v2`, `qcom,lmh-dcvs` etc.), `*-supply` e `*-gpio(s)`. Demais valores ficam numéricos, com o `phandle` do nó preservado.
- **Fecho:** nós referenciados pelo overlay mantido, fecho transitivo por phandles, ancestrais, `/cpus`, `/psci`, `/reserved-memory`, `/firmware`, `/chosen`, `/aliases` e os alvos dos aliases. Filhos do overlay com o mesmo nome de um nó da base também puxam esse nó, para o overlay não criar um nó parcial.
- **`/memory`:** sai da base e entra em `topaz.dts` como `memory@40000000`, com o `reg` do FDT ativo.
- **Raiz:** as propriedades de raiz que o overlay define vão para `topaz.dts` (o `fdtoverlay` da fase 1 não as aplicava, segundo o docstring do gerador).
- **`bias-disable = <0x0>`** vira a flag `bias-disable;` (binding 6.12 define booleana).
- **`status = "ok"`** vira `"okay"`. Linux aceita os dois, mas o dt-schema só aceita `okay`. Na comparação com o ativo os dois valores são iguais.
- **`/aliases`:** o `phandle` não é copiado. Aliases cujo alvo saiu também saem.

### O que é verificado localmente

`--check` reanalisa `topaz.dts` (resolvendo o include, os blocos `&label` e os labels) e compara com o FDT ativo, nó por nó e valor por valor. Resultado do gerador atual:

- 209 nós na curada, contra 2137 no ativo (1928 removidos pelo escopo C e pelo fecho).
- Nenhum nó extra, nenhum `&label` sem alvo, nenhuma referência decodificada apontando para fora da curada, e os 11 aliases do ativo estão cobertos, exceto os 4 de SD e áudio excluídos (esperados).
- 7 divergências de valor, todas esperadas: `/aliases` `mmc0`/`mmc1` (SD fora do escopo), `swr0`/`swr1` (áudio fora do escopo); `/firmware/android/fstab/vendor status` (base `ok`, ativo `disabled`, origem em runtime, já documentado na fase 1); `/memory ddr_manufacturer_id` e `/memory ddr_size` (só no ativo, injetados pelo bootloader).

Isso não prova que a DT compila nem que é válida pelo dt-schema. Essas provas ficam na CI.

### Na CI

- `compile-and-merge`: `tools/compile_curated_dt.sh` regenera a DT curada, exige que os arquivos versionados (`khaje.dtsi`, `topaz.dts`, `excluidos.txt`) sejam idênticos à saída do gerador e compila `topaz.dts` com `cpp` + `dtc`. A DT curada e o DTB entram no artefato `topaz-dt-validate`.
- `dt-schema`: valida o DTB curado com o mesmo schema processado do DTB mesclado (log `dt-validate-curated.log`). O resumo mostra os erros por propriedade e por compatível (anotação `dtschema erros por propriedade`), porque a anotação do log completo é truncada.

### Resultados da CI (antes do escopo C)

- Run [`38284596380`](https://github.com/Ctps1234/Kernel/actions/runs/38284596380), commit `841fa41`: `compile-and-merge` e `dt-schema` **success**; DT curada (315 nós, com display/câmera/áudio/carregador): **1491 erros** de `dt-validate`, contra 2761 no DTB mesclado. Principais compatíveis: `qcom,sde-kms` (86), `qcom,cam-sensor` (70), `qcom,eeprom` (46), `qcom,nopmi-chg` (32), `qcom,sdhci-msm-v5` (23), `qcom,swr-mstr` (22), `qcom,bengal-asoc-snd` (22), `qcom,ufshc` (19), `qcom,cci-v1.2` (19), `sm,sm5602` (18), `arm,armv8` (16). Quase todos são vendor sem binding na série. Os erros de `qcom,freq-domain` e `qcom,lmh-dcvs` em `cpu@N` (8 + 8) são falta de binding em `cpus.yaml` na base 6.12, não erro de conversão.
- Os erros de `mk-schema` no log são da base (`fsl,liodn`, `gunyah-cma-mem`), não da DT topaz.

### Resultados da CI (escopo C)

- Run [`38292834431`](https://github.com/Ctps1234/Kernel/actions/runs/38292834431), commit `a5bf854` (escopo C sem o ajuste de áudio/câmera): `compile-and-merge` e `dt-schema` **success**. DT curada: **203 erros** (antes: 1491). Mesclado: 2761.
- Run [`38293210451`](https://github.com/Ctps1234/Kernel/actions/runs/38293210451), commit `4520c5b` (ajuste de áudio/câmera e patch `0012`): `compile-and-merge` e `dt-schema` **success**. DT curada: **172 erros** de `dt-validate`, 209 nós. Mesclado: 2745.
- O binding `0012` zerou os erros de `qcom,freq-domain` e `qcom,lmh-dcvs` em `cpu@N` (eram 16). `compatible` de `arm,armv8` também sumiu da lista.
- `compile-and-merge` confirmou a regeneração: os arquivos versionados são idênticos à saída do gerador, e `topaz.dts` compila com `dtc` na CI.

Resíduos da curada (172), ainda sem correção nesta fase. São propriedades vendor de nós mantidos, sem binding na base 6.12 ou com tipo divergente:

- `qcom,ufshc` (19), `simple-bus` (19), `qcom,geni-se-qup` (18), `qcom,mpm-khaje` (9), `qcom,rpm-smd-regulator-resource` (6), `qcom,spmi-pmic` (6), `qcom,i2c-geni` (6), `qcom,gpi-dma` (5), `qcom,cpufreq-hw` (3), `qcom,pm6125-gpio` (3), `qcom,scm` (2), `android,vendor` (3), `qcom,wrapper-core` (6).
- Propriedades: `compatible` (12), `status` (o `"OK"` maiúsculo da base em um nó de QUP foi normalizado para `"okay"` nesta rodada; o resto aguarda CI), `reg-names`, `#address-cells`/`#size-cells`, `$nodename`, `qcom,iommu-dma`/`dma-addr-pool`, `qcom,affinity`, `cluster-pd*` no psci, `parts`/`dev`/`mnt_flags`/`fsmgr_flags` do fstab, e 1 erro cada em `vibrator_gpio`, `thermal-message`, `interconnect`, `clocks` e `dsi_pll_codes`. O `dsi_pll_codes` (`khaje.dtsi`, linha 1167) fica na curada porque o overlay mantido o referencia por `pll_codes_region` (`topaz-overlay.dtso`, linha 1778); Além disso, o gerador emite o mesmo nó também em `topaz.dts` (bloco `&soc`, com `label` e `reg` idênticos). O `dtc` faz o merge sem efeito, mas é duplicação do gerador: fica registrada como pendência, não corrigida nesta rodada.

Esses erros não são novos: são o estado do port 6.12 para os nós que a curada mantém. Não há exclusão adicional sem decisão do usuário. Cada grupo precisa de binding próprio (série 0013 em diante) ou de exclusão documentada.

### Próxima etapa

- Decidir se o `dt-schema` vira bloqueante. Hoje é `continue-on-error: true`, então os 172 erros não quebram a CI.
- Criar bindings para os grupos de maior volume (`qcom,ufshc`, `qcom,geni-se-qup`, `qcom,mpm-khaje`, `qcom,rpm-smd-regulator-resource`), ou excluí-los com registro em `excluidos.txt`.
- Run [`38301446029`](https://github.com/Ctps1234/Kernel/actions/runs/38301446029), commit `d76a833`: normalização `"OK"` → `"okay"` aplicada, mas a curada continua com 172 erros e 6 de `status`. Os 6 erros de `status` não vêm do `"OK"`; o resumo da CI não mostra o valor. Precisa do log completo do `dt-validate-curated` para identificar.
- Corrigir no gerador a duplicação do `dsi_pll_codes` (`khaje.dtsi` e `topaz.dts`), identificando o fragmento que emite o bloco `&soc`.
- Decidir o `status` de `/firmware/android/fstab/vendor` (base `ok`, ativo `disabled`) e a origem de `/memory ddr_*`.
- Integrar os nós mantidos ao kernel: drivers 6.12 e configuração GKI.
- Hardware: nada aqui foi testado no aparelho. Não flashar.
