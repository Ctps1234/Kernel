# Device Tree topaz — fase 1 (conversão mecânica)

Esta pasta contém a primeira etapa do item 1 do plano: transformar a base Khaje + overlay topaz em arquivos versionáveis.

## Conteúdo

| Arquivo | Origem | Observação |
|---|---|---|
| [`topaz-overlay.dtso`](topaz-overlay.dtso) | Gerado por [`tools/symbolize_overlay.py`](../../tools/symbolize_overlay.py) a partir de [`topaz-overlay-51-reference.dtso`](../reference/topaz-overlay-51-reference.dtso) | Overlay `/plugin/` com referências simbólicas (`&label`). 363 referências externas à base e 170 internas foram convertidas usando apenas `__fixups__`, `__local_fixups__` e `__symbols__` do próprio dtc. |
| Base Khaje | [`khaje-base-reference.dts`](../reference/khaje-base-reference.dts) | Ainda usada como está: phandles numéricos (`<0x126>`), sem labels. Nenhuma conversão foi feita aqui. |

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

### O que ainda **não** foi validado

- **Bindings / DT-schema** (`dt-validate`, `dtbs_check`): não executado. Exige os bindings da base 6.12 com os patches 0001–0011 aplicados.
- **Hardware**: nada aqui foi testado no aparelho. Não flashar.

## Próxima etapa (fase 2 — curadoria)

Gerar uma DTS de SoC (`khaje.dtsi`) e uma de placa (`topaz.dts`) reduzidas aos nós usados pelo port 6.12, com bindings revisados, e manter a conversão mecânica como trilha de auditoria.
