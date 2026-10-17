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

## Consequências

1. A fundação de boot (base Khaje + overlay de board `0x30022`) está coberta
   pelas DTS públicas e compila no build do kernel.
2. O DTBO real do aparelho carrega nós adicionais de periféricos
   proprietários; ao portar esses drivers, os nósCorresponding devem ser
   recriados a partir do snapshot de referência, não apenas do DTB base.
3. As tabelas de runtime (OPP/BW de GPU, reserved-memory com endereços reais)
   são injetadas pelo bootloader/driver e não pertencem às DTS.
