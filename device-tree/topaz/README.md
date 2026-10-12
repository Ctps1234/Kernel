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
5. compara o resultado com o FDT ativo de referência (`topaz-live-reference.dts`) e grava um diff informativo.

O workflow [`device-tree.yml`](../../.github/workflows/device-tree.yml) executa o script em GitHub Actions e publica os artefatos. Ele não é executado localmente aqui porque o sandbox não tem `dtc` (sem flex/bison).

## O que isto **não** valida ainda

- **Bindings / DT-schema** (`dt-validate`, `dtbs_check`): ainda não executado. Depende dos bindings da base 6.12 com os patches 0001–0011 aplicados.
- **Diferenças com o FDT ativo**: o diff é só informativo. Ele inclui nós e propriedades do bootloader e reatribuições de phandle locais ao overlay.
- **Hardware**: nada aqui foi testado no aparelho. Não flashar.

## Próxima etapa (fase 2 — curadoria)

Gerar uma DTS de SoC (`khaje.dtsi`) e uma de placa (`topaz.dts`) reduzidas aos nós usados pelo port 6.12, com bindings revisados, e manter a conversão mecânica como trilha de auditoria.
