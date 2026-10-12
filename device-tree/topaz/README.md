# Device Tree topaz — fases 1 (conversão mecânica) e 2 (curadoria)

Esta pasta contém o item 1 do plano: transformar a base Khaje + overlay topaz em arquivos versionáveis. A fase 1 é a trilha de auditoria; a fase 2 é a DT curada, gerada a partir dela.

## Conteúdo

| Arquivo | Origem | Observação |
|---|---|---|
| [`topaz-overlay.dtso`](topaz-overlay.dtso) | Gerado por [`tools/symbolize_overlay.py`](../../tools/symbolize_overlay.py) a partir de [`topaz-overlay-51-reference.dtso`](../reference/topaz-overlay-51-reference.dtso) | Overlay `/plugin/` com referências simbólicas (`&label`). 363 referências externas à base e 170 internas foram convertidas usando apenas `__fixups__`, `__local_fixups__` e `__symbols__` do próprio dtc. |
| Base Khaje | [`khaje-base-reference.dts`](../reference/khaje-base-reference.dts) | Ainda usada como está: phandles numéricos (`<0x126>`), sem labels. Nenhuma conversão foi feita aqui. |
| [`khaje.dtsi`](khaje.dtsi) | Gerado por [`tools/curate_dt.py`](../../tools/curate_dt.py) a partir da base | **Fase 2.** DT da SoC reduzida: 315 de 1978 nós da base. Phandles viram `&label` quando o alvo está no arquivo. |
| [`topaz.dts`](topaz.dts) | Gerado por `tools/curate_dt.py` a partir do overlay e do FDT ativo | **Fase 2.** Inclui `khaje.dtsi`; define as propriedades de raiz, `/memory` e um bloco `&label { … }` por fragment do overlay. |

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
  - `cpu@N`: `qcom,freq-domain` e `qcom,lmh-dcvs` aparecem como bytes. O nó `phandle = <0x5>` existe na base (dispositivo de performance), então a hipótese é limitação do dtschema para propriedades sem binding de CPU (cells desconhecidas), não phandle quebrado. **A confirmar** (ex.: validar com um binding de CPU que declare essas propriedades).
  - O log completo está no artefato `topaz-dt-schema` do run. Não foi possível contar todas as violações pelas anotações (truncadas).

### O que ainda **não** foi validado

- **DT-schema do DTB mesclado**: executado, mas as violações listadas acima ainda não foram corrigidas (fase 2). Bindings da série: sem erros.
- **Hardware**: nada aqui foi testado no aparelho. Não flashar.

## Fase 2 — DT curada

Gerada por [`tools/curate_dt.py`](../../tools/curate_dt.py), sem edição manual:

```sh
python3 tools/curate_dt.py --out-dir device-tree/topaz          # gera e verifica
python3 tools/curate_dt.py --out-dir device-tree/topaz --check  # só verifica
```

O que o gerador faz:

- **Labels:** a base decompilada não tem labels nos nós, então eles vêm de `__symbols__`. Phandles viram `&label` só nas propriedades que o gerador conhece: listas com células do provedor (`clocks`, `resets`, `power-domains`, `interrupts-extended`, `phys`, `dmas`, `iommus`, `qcom,freq-domain`, `sound-dai` etc.), referências simples (`interrupt-parent`, `memory-region`, `operating-points-v2`, `qcom,lmh-dcvs` etc.), `*-supply` e `*-gpio(s)`. Demais valores ficam numéricos, com o `phandle` do nó preservado; assim o `dtc` produz os mesmos números.
- **Fecho de nós:** mantém os nós referenciados pelo overlay (126 labels), o fecho transitivo por phandles, os ancestrais, `/cpus`, `/psci`, `/reserved-memory`, `/firmware`, `/chosen`, `/aliases` e os alvos dos aliases. Filhos do overlay com o mesmo nome de um nó da base também puxam esse nó, para o overlay não criar um nó parcial.
- **`/memory`:** sai do SoC e entra em `topaz.dts` como `memory@40000000`, com o `reg` do FDT ativo.
- **Raiz:** as propriedades de raiz que o overlay define vão para `topaz.dts`. Segundo o docstring do gerador, o `fdtoverlay` da fase 1 não as aplicava.
- **Normalizações intencionais:** `bias-disable = <0x0>` vira a flag `bias-disable;` (o binding 6.12 define booleana; o driver só lê a presença). O `phandle` em `/aliases` não é copiado (o nó de aliases não deve carregar `phandle`).

### O que é verificado localmente

`--check` reanalisa `topaz.dts` (resolvendo o include, os blocos `&label` e os labels) e compara com o FDT ativo, nó por nó e valor por valor. Resultado do gerador atual:

- 475 nós na curada, contra 2137 no ativo (1662 removidos por não serem usados pelo overlay nem por dependências).
- Nenhum nó extra, nenhum `&label` sem alvo, nenhuma referência decodificada apontando para fora da curada, nenhum alias perdido (11 de 11). Phandles não decodificados ficam numéricos e são contados, não erro (1 nesta execução).
- 4 divergências de valor, todas esperadas: `fstab/vendor status` (base `ok`, ativo `disabled`, origem em runtime, já documentado na fase 1); `/soc/xiaomi_touch get_panel_info`, `/memory ddr_manufacturer_id` e `/memory ddr_size` (só no ativo, injetados pelo bootloader ou origem não confirmada).

Isso não prova que a DT compila nem que é válida pelo dt-schema. Essas provas ficam na CI.

### Na CI

- `compile-and-merge`: `tools/compile_curated_dt.sh` regenera a DT curada, exige que os arquivos versionados sejam idênticos à saída do gerador (geração determinística) e compila `topaz.dts` com `cpp` + `dtc`. A DT curada e o DTB entram no artefato `topaz-dt-validate`.
- `dt-schema`: valida o DTB curado com o mesmo schema processado do DTB mesclado (log `dt-validate-curated.log`).

Resultado da CI desta fase (run [`38283896478`](https://github.com/Ctps1234/Kernel/actions/runs/38283896478), commit `28887c0`):

- `compile-and-merge` e `dt-schema`: **success** (o job `dt-schema` segue `continue-on-error`).
- Verificação da DT curada gerada: idêntica aos arquivos versionados; `cpp` + `dtc` sem erro.
- `dt-validate` do DTB curado: **1529 erros** (mesclado: 2761). Principais categorias no DTB curado:
  - `status = "ok"` (38): dt-schema aceita só `okay`/`disabled`/`reserved`/`fail`/`fail-needs-probe`. Linux aceita `ok`, mas a DT curada ainda não normalizou.
  - Propriedades vendor sem binding na base 6.12 (ficam como bytes): `rgltr-*` (36), `cci-master` (12), `gpio-req-tbl-*` (33), `gpio-no-mux` (11), `clock-rates` e `clock-cntl-level` (18), `qcom,lpi-gpios`, `qcom,codec-*` e `timing@0: qcom,mdss-dsi-*` (DSI do painel).
  - `qcom,freq-domain` (8) e `qcom,lmh-dcvs` (8) em `cpu@N`: a base 6.12 não documenta essas propriedades em `cpus.yaml`, então o `dt-validate` não decodifica o phandle. A conversão está correta (`&label` no fonte, valor numérico no DTB).
  - `compatible` (16), `status` (15), `'ranges' is a required property` (7), `$nodename` (7): precisam de revisão caso a caso.
- Os erros de `mk-schema` que aparecem no log são da base (`fsl,liodn`, `gunyah-cma-mem`), não da DT topaz.
- A contagem por propriedade agora é publicada como anotação `notice` (`dtschema erros por propriedade`), porque a anotação do log completo é truncada na página do run.

Nada disso bloqueia a CI. Corrigir os erros exige decidir entre bindings novos (série de patches) e reduzir ainda mais a DT curada (ver próxima etapa).

## Próxima etapa (fase 2, continuação)

- Revisar o resultado do `dt-validate` do DTB curado e corrigir o que for da DT (não do schema).
- Decidir o `status` de `/firmware/android/fstab/vendor` (base `ok`, ativo `disabled`).
- Confirmar a origem de `/soc/xiaomi_touch get_panel_info` e de `/memory ddr_*`.
- Revisar o bloco `/memory` (valores do ativo) e a licença dos arquivos gerados antes de qualquer submissão.
- Integrar os nós curados ao kernel: drivers 6.12 para cada nó mantido, e a configuração GKI.
- Hardware: nada aqui foi testado no aparelho. Não flashar.
