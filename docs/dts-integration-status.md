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

### Includes de sistema

| Include | Disponibilidade |
|---|---|
| `dt-bindings/clock/qcom,{dispcc,gcc,gpucc}-khaje.h` | Fornecido pelo patch 0011 |
| `dt-bindings/clock/qcom,rpmcc.h` | Fornecido pelo patch 0004 (RPMCC) |
| `dt-bindings/interconnect/qcom,bengal.h` | Fornecido pelo patch 0007 |
| `dt-bindings/regulator/qcom,rpm-smd-regulator.h` | Fornecido pelo patch 0008 |
| `dt-bindings/phy/qcom,khaje-qmp-usb3.h` | **Não encontrado** nos patches nem no R47; usado por `khaje-usb.dtsi` (constantes `USB3_DP_*`). Bloqueador para USB/DTBS_CHECK |
| `dt-bindings/msm-camera.h` | Include removido de `topaz-camera-sensor-idp.dtsi` (nenhuma constante usada) |
| `bindings/audio-codec-port-types.h`, `bindings/qcom,audio-ext-clk.h`, `bindings/qcom,bolero-clk-rsc.h` | **Adicionados** em `device-tree/source/bindings/` (importados de fontes públicas Qualcomm) |
| demais (`gpio.h`, `spmi.h`, `thermal/*`, `arm/msm/qcom_dma_heap_dt_constants.h`, `qcom,qpnp-power-on.h`, `qcom,khaje-qmp-usb3.h` já listado) | Esperados no common kernel / headers padrão; confirmar na base fixada |

### Includes entre arquivos

Todos os 54 includes entre arquivos resolvem após a correção do nome de
painel (`dsi-panel-m7_…` → `dsi_panel_m7_…`). Nenhum include quebrado
restante.

## Adaptações aplicadas

- `display/display/topaz-sde-display-idp-nopmi.dtsi`: corrigidos os nomes dos
  includes dos painéis `m7_38_0c_0{a,b}` para o padrão com underscore.

## Reconciliação de compatibles (estática)

Verificados os compatibles SoC críticos usados pelos DTS importados contra os
drivers portados na série 0001–0012:

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

## Bloqueadores conhecidos para build/DTBS_CHECK

1. ~~Header `qcom,khaje-qmp-usb3.h` ausente (USB)~~ — resolvido (patch 0012).
2. ~~Headers de áudio ausentes~~ — resolvido (bindings adicionados).
3. ~~Header `msm-camera.h` ausente~~ — resolvido (include removido).
4. ~~Reconciliação de compatibles de fundação de boot~~ — verificado (tabela acima). Resta validação de API/bindings em build.
5. Defconfig final e validação DT-schema/`dtbs_check` ainda pendentes.

## Recomendação

- Manter a fundação de boot focada em `khaje-idp-nopmi.dts` +
  `topaz-khaje-idp-nopmi-overlay.dts`, adiando áudio/câmera/display avançado.
- Resolver o header USB (portar do kernel Qualcomm ou gerar constantes) antes
  de tentar `dtbs_check`.
- Não compilar/flashar/testar boot até fechar a integração e a configuração
  GKI/defconfig.
