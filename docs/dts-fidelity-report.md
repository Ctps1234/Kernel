# Fidelidade das DTS do projeto vs. o FDT do aparelho

Comparação entre as device trees do projeto (fontes públicas + port local) e
os snapshots do FDT real do aparelho, em `device-tree/reference/`:

- `khaje-base-reference.dts` — base Khaje do aparelho (DTB pareado com o DTBO);
- `topaz-overlay-51-reference.dtso` — overlay de board topaz do aparelho
  (entrada 51, board id `0x30022`);
- `topaz-live-reference.dts` — FDT ativo do aparelho (base + overlay aplicados).

Ferramenta: `tools/compare_dts.py` (compara caminhos de nós e propriedades;
aceita `.dts` ou `.dtb` via `--dtc`).

## Base Khaje

| Métrica | Valor |
|---|---|
| Nós na referência do aparelho | 1977 |
| Nós no nosso DTB compilado | 1343 |
| Nós em comum | 1288 (65,1% da referência) |

Os 689 nós da referência que não aparecem no nosso DTB base se agrupam em:

| Grupo | Nós | Origem no aparelho |
|---|---|---|
| `/soc/spf_core_platform` | 460 | subárvore de áudio (SoundWire/SPF), entregue pelo overlay de áudio |
| `/soc/qcom,kgsl-3d0@5900000` | 53 | KGSL/GPU proprietário (DT do driver vendor, não existe em árvore pública) |
| `/soc/pinctrl@400000` (filhos) | 32 | nós de pin por GPIO injetados/configurados no FDT do aparelho |
| `/soc/qcom,cam-cpas@5c11000` | 17 | stack de câmera proprietária (CPAS) |
| `/soc/gpu-bw-tbl`, `/soc/gpu-opp-table` | 22 | tabelas de OPP/BW de GPU montadas em runtime |
| `/soc/thermal-zones` (filhos) | 12 | nomes de filhos divergentes (cooling-maps) |
| `/soc/qcom,cam_smmu`, `mdss_*`, `qcom,vidc*`, `slim*`, `remoteproc-adsp` | ~40 | display/câmera/vídeo, delivered pelos overlays de display e câmera |

Ou seja: a diferença é **distribuição entre base e overlays**, mais conteúdo
proprietário (KGSL, câmera, áudio do FDT do aparelho). O esqueleto do SoC
(base DTB Khaje) está coberto.

## Overlay de board topaz

| Métrica | Valor |
|---|---|
| Nomes de nó no DTBO do aparelho | 157 |
| Nomes de nó no nosso overlay (após preprocess) | 66 |
| Nomes em comum | 42 |

Identidade conferida e idêntica: `model`, `compatible = "qcom,khaje-idp",
"qcom,khaje", "qcom,idp"`, `qcom,msm-id = <0x206 0x10000>` e
`qcom,board-id = <0x30022 0>`.

Os 115 nomes de nó que existem no DTBO do aparelho e não no overlay público
são, em sua maioria, nós de drivers proprietorários sem fonte neste port:

| Função | Nós no DTBO do aparelho |
|---|---|
| Digitalização (fingerprint) | `fpc1020`, `focaltech@38`, `goodix-sunrise@5d`, `goodix_fp` |
| Carregamento | `bq2589x@6A`, `ln8000_charger@51`, `sc8551-charger@66`, `rt-pd-manager` |
| Antena/ANT | `aw87xxx_pa_59@59` |
| Microfones | `fs16xx@34`, `maxim_ds28e16` |
| LED driver | `wl2866d@28` |
| One-wire | `onewire_gpio`, `onewire_gpio_active/sleep` |
| PA/sensores térmicos | `thermal-screen`, `si_pa_L`, `sipa_i2c_L@2b`, `rf_pa1_therm_default` |
| Pinctrl explícito de GPIO | `msm_gpio_65/83/104`, `msm_cdc_pinctrl@92/106`, `msm_gpio_*_output_high` |
| Display/câmera (no DTBO do aparelho) | `qcom,mdss_dsi_ctrl0@5e94000`, `qcom,mdss_dsi_phy0@5e94400`, `qcom,mdss_mdp`, `qcom,cam-sensor0..3`, `qcom,camera-flash@*`, `qcom,actuator0`, `qcom,eeprom0..3` |

No port, display e câmera chegam pelos overlays dedicados
(`topaz-sde-display-idp-nopmi.dtsi` e `topaz-camera-sensor-idp.dtsi`), e não
pelo overlay de board — diferença de distribuição, não de cobertura. Já
fingerprint, carregamento, ANT, microfones, LED e one-wire **não têm fonte
disponível** neste port: são drivers Android proprietários que ainda precisam
ser portados (ou substituídos) na etapa de paridade.

## Display: painel M7 e DSC

A comparação direta do FDT ativo com as DTS locais encontrou uma diferença de propriedades no painel selecionado:

| Fonte | Seleção / dados DSC |
|---|---|
| FDT live do aparelho | `qcom,dsi-default-panel` aponta ao phandle `0x345` (`m7_38_0c_0a`); o nó declara 8 bpp e 8 bpc. |
| DTS local Topaz `_0a` | Após comparação direta com a FDT, declara 8 bpp e 8 bpc; somente esses dois campos foram alinhados, mantendo o nó M7 e os demais dados intactos. |
| DTS local Topaz `_0b` | Variante alternativa, também declara 8 bpp e 8 bpc; isso não torna o nó `_0b` equivalente ao `_0a` ativo. |

O FDT real seleciona `_0a`. O diff completo de 91 propriedades mostrou que, antes do ajuste, somente bpp/bpc divergiam (89/91 idênticas); a fonte local `_0a` foi alinhada aos 8/8 da FDT e agora coincide nas propriedades comparadas. A coincidência com `_0b` é considerada apenas para esses valores, sem inferir PPS ou outros parâmetros DSC. A seleção, os comandos e os demais dados M7 foram preservados; Creek/O19A não fornece referência de painel para substituição. A validação DTS/DTBO contra o commit 6.12 fixado também aplicou o overlay de display ao composto Topaz: o phandle `qcom,dsi-default-panel` resolve para o nó M7 `_0a`, com bpp/bpc 8/8 e `slice-per-pkt=2`. Para permitir a aplicação, referências de phandle foram corrigidas para os labels M7 já declarados (`dsi_m7_...`), sem alterar dados do painel. Isso não substitui DT-schema nem build do kernel; ver [`display-port-audit.md`](display-port-audit.md).

## Wi‑Fi: ICNSS2

A FDT base do aparelho e a FDT live incluem `/soc/qcom,icnss@C800000`, compatible `qcom,icnss`, com recursos MMIO, IOMMU/IOVA, reguladores, IRQs, MSA e SMP2P usados pelo caminho WLAN. A fonte local `device-tree/source/qcom/khaje.dtsi` mantém a reserva `wlan_msa_mem`, o SMP2P WLAN base e `ipa_smmu_wlan`, mas não contém o nó `qcom,icnss` nem o filho `qcom,smp2p_map_wlan_1_in` presente no FDT real. Assim, a DTS atualmente versionada não reproduz o dispositivo platform ICNSS2 necessário para o módulo WLAN observado. Preservar os valores da referência e validar cada phandle/recurso antes de acrescentar o nó; comparação detalhada em [`wifi-port-audit.md`](wifi-port-audit.md).

## Câmera: blocos SoC e overlay de sensores

A FDT base e a FDT live expõem o pipeline vendor de câmera: `qcom,cam-req-mgr`, três CSIPHY `qcom,csiphy-v1.2.1`, CCI `qcom,cci-v1.2`, CPAS/CDM, `qcom,cam-isp`, três pares `qcom,csid530`/`qcom,tfe530`, PPI/TPG, OPE e context banks `qcom,msm-cam-smmu-cb`. O overlay Topaz adiciona quatro slots `qcom,cam-sensor` genéricos, EEPROMs, actuator, flash e `wl2866d@28`.

A fonte local [`topaz-camera-sensor-idp.dtsi`](../device-tree/source/qcom/camera/topaz-camera-sensor-idp.dtsi) contém os periféricos do overlay, mas `device-tree/source/qcom/khaje.dtsi` não define os controladores SoC de câmera nem a label `cam_cci0` que o overlay referencia. Portanto, a DTS versionada não reproduz o bloco de câmera da FDT base; compilar o DTBO de sensores separadamente não confirma que ele possa ser aplicado ao DTB Khaje local. Reconciliar todos os recursos/phandles com a FDT pareada e identificar os sensores físicos antes do port funcional. A análise de drivers está em [`camera-port-audit.md`](camera-port-audit.md).

## Consequências

1. A fundação de boot (base Khaje + overlay de board `0x30022`) está coberta
   pelas DTS públicas e compila no build do kernel.
2. O DTBO real do aparelho carrega nós adicionais de periféricos
   proprietários; ao portar esses drivers, os nós correspondentes devem ser
   recriados a partir do snapshot de referência, não apenas do DTB base.
3. As tabelas de runtime (OPP/BW de GPU, reserved-memory com endereços reais)
   são injetadas pelo bootloader/driver e não pertencem às DTS.
