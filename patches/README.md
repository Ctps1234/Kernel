# Patches para a base Android Common 6.12 fixada

Aplicar somente à `EdMory/android_kernel_common_sm8850`, branch `aosp-new/android16-6.12-lts`, commit `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`. Esta série local de bring-up fica separada do repositório de pesquisa; ainda não tem `Signed-off-by` e **não está pronta para build de imagem, flash ou boot**.

## Série local 0001–0011

1. [`0001-dt-bindings-pinctrl-khaje.patch`](0001-dt-bindings-pinctrl-khaje.patch) documenta o binding `qcom,khaje-pinctrl`, incluindo os 185 nomes de função mux.
2. [`0002-pinctrl-khaje.patch`](0002-pinctrl-khaje.patch) adiciona dados TLMM Khaje e integração Kconfig/Makefile; adapta `msm_pingroup`/`pinfunction` e `.remove_new` às APIs 6.12. Inclui eGPIO (seletor 11, GPIO98–112) e reserva gpiochip 0–3 da referência R47. Mantém o caminho upstream `wakeirq_map`; o comportamento de wake no hardware ainda precisa de validação.
3. [`0003-dt-bindings-rpmcc-khaje.patch`](0003-dt-bindings-rpmcc-khaje.patch) documenta `qcom,rpmcc-khaje`. Não exige XO de entrada, pois essa propriedade não aparece no nó Khaje de referência.
4. [`0004-clk-rpmcc-khaje.patch`](0004-clk-rpmcc-khaje.patch) adiciona o descritor do provider RPM SMD Khaje, reutilizando objetos de clock 6.12 com IDs verificados em R47 (SNOC/BUS ID 2, CNOC/BUS ID 1, RF_CLK1/2 nos XO-buffer IDs 4/5). Preserva o voto BIMC `INT_MAX` apenas no active set e os keepalives de XO, CNOC, SNOC e QUP. Configura as taxas mínimas antes de preparar os keepalives e falha o probe se um voto essencial ou o provider interconnect filho não puder ser registrado. Não porta `msm_rpm_send_message` nem APIs privadas do vendor.
5. [`0005-dt-bindings-qmp-ufs-sm6225.patch`](0005-dt-bindings-qmp-ufs-sm6225.patch) adiciona `qcom,sm6225-qmp-ufs-phy` às listas do binding QMP UFS upstream.
6. [`0006-phy-qmp-ufs-sm6225.patch`](0006-phy-qmp-ufs-sm6225.patch) adiciona ao driver QMP UFS a configuração SM6225/Khaje, com calibrações de duas lanes para gears 1–3, overlay específico de Gear 4 e override Rate B. Usa `qmp_phy_cfg` 6.12, sem importar `ufs_qcom_phy`. A auditoria das tabelas está em [`docs/ufs-qmp-phy-port.md`](../docs/ufs-qmp-phy-port.md).
7. [`0007-interconnect-bengal.patch`](0007-interconnect-bengal.patch) porta a topologia Bengal para o framework ICC/RPM da base 6.12, adaptando QoS, slots esparsos, interface clocks e votos RPM. A análise estática comparou 92 nós, 36 arrays de links, 184 IDs RPM e 22 QoS boxes; as 126 specs Bengal da FDT ativa resolvem para slots existentes. Ainda não foi compilado nem validado por DT-schema.
8. [`0008-dt-bindings-rpm-smd-resource-regulators.patch`](0008-dt-bindings-rpm-smd-resource-regulators.patch) descreve a hierarquia direta de recursos RPM-SMD e os filhos físicos, votos por nível/floor-level e cooling-device observados na FDT; inclui o binding do pai e constantes DT de níveis/modos.
9. [`0009-regulator-rpm-smd-resource-votes.patch`](0009-regulator-rpm-smd-resource-votes.patch) adiciona suporte ao layout aninhado no driver RPM-SMD. Despacha entre reguladores físicos PM6125 e votos `vlvl`/`vfl`, preserva o caminho PMIC convencional, agrega votos por cliente e por active/sleep set, confere nome e tipo/ID do recurso antes de associar uma rail física e reverte votos físicos parciais em caso de falha.
10. [`0010-clk-qcom-vdd-class-support.patch`](0010-clk-qcom-vdd-class-support.patch) adapta o suporte a voltage-corners para `regulator`/CCF do alvo, agrega votos por classe e preserva uma proxy vote máxima até `sync_state`; acrescenta hooks de taxa para PLL/RCG, sequência de regmap com rollback e o helper `qcom,critical-devices`/`qcom,critical-clocks`. Inclui suporte debug-mux/medição sem tratar qualquer seletor Khaje como sentinela; a troca de pai em debugfs é abortada se o pai não estiver disponível.
11. [`0011-clk-qcom-khaje-clock-controllers.patch`](0011-clk-qcom-khaje-clock-controllers.patch) adiciona GCC, DISPCC, GPUCC e debugcc Khaje, IDs DT, quatro bindings e integração Kconfig/Makefile. Acrescenta ao binding comum `qcom,gcc.yaml` as propriedades de clocks críticos. Integra só os controllers ativos no FDT capturado; LPASSAONCC/LPASSAUDIOCC não entram nesta série por não haver nós controller LPASS ativos na referência topaz.
12. [`0012-dt-bindings-phy-qcom-khaje-qmp-usb3-header.patch`](0012-dt-bindings-phy-qcom-khaje-qmp-usb3-header.patch) adiciona o header `include/dt-bindings/phy/qcom,khaje-qmp-usb3.h` com as constantes `USB3_DP_*` usadas por `khaje-usb.dtsi` (importado de fonte pública de constantes Qualcomm Khaje). Necessário para compilar/aplicar o DTB base Khaje com USB.

A revisão estática do par 0008/0009 contra `device-tree/reference/topaz-live-reference.dts` contou 30 nós de recurso, 25 filhos físicos PM6125 habilitados e 8 filhos habilitados de votos por nível; não encontrou divergências no mapeamento de nome/tipo/ID. Os filhos PMIC desabilitados que compartilham o compatible de votos não são registrados como rails físicas. No GCC (phandle `0x81`), `qcom,critical-devices` referencia o nó `0xc3`; o I²C ascendente `i2c@4a84000` usa o GCC clock índice 94 (`GCC_QUPV3_WRAP0_S1_CLK`) e o wrapper ascendente usa os índices 104/105, todos mantidos preparados/habilitados pelo handler. A varredura dos specifiers na DTS mesclada encontrou 95 IDs GCC, 11 DISPCC e 5 GPUCC distintos; todos têm entradas nos respectivos arrays. Também foram mapeados os 17 IDs RPM distintos referenciados. A GCC DISP AHB ID 60, que faltava inicialmente, foi adicionada como branch critical no CBCR `0x1700c`, conforme a implementação análoga SM6115/SM6125 do alvo. Isso é auditoria estática de fonte/FDT, não teste em hardware.

As referências principais são Xiaomi `topaz-t-oss`, commit `345999da0be9cd37afdf87b15449d30b585a7091`, e Qualcomm Platform 5.0 R47 `kernel/qcom`, commit `1c96d1325813d872d0206ffafe70c88823c86d6c` (ref chamada `kernel.lnx.6.12.r67-rel`). O Makefile de `soc-repo` R47 declara 6.11.0: a árvore serve como referência de dados/implementação vendor, não como prova de compatibilidade da API/build final.

## Aplicação

Em um checkout limpo do commit fixado, aplicar e verificar cada patch em ordem:

```sh
for patch in /path/to/Kernel/patches/[0-9][0-9][0-9][0-9]-*.patch; do
    git apply --check "$patch" || exit 1
    git apply "$patch" || exit 1
done
git diff --check
```

A série completa 0001–0011 foi aplicada em ordem numa worktree temporária sparse do commit fixado; `git apply --check` passou para cada patch e `git diff --check` passou no resultado acumulado. A worktree temporária foi removida depois da verificação. PyYAML também aceitou a sintaxe dos quatro novos schemas de clock e de `qcom,gcc.yaml`, sem validar as regras DT-schema.

## Validação e limites

- O binding pinctrl 0001 já havia passado `dt-doc-validate`. PyYAML confirmou somente sintaxe YAML dos bindings RPM-SMD 0008 e dos quatro bindings de clock Khaje mais `qcom,gcc.yaml`; isso **não** confirma DT-schema. A tentativa de instalar `dtschema` em `/tmp` parou porque o `pylibfdt` exigido precisa de `Python.h`, ausente no host; `dt-doc-validate` não pôde ser executado. `dtc` e `scripts/checkpatch.pl` também não estão disponíveis na sparse checkout.
- `checkpatch.pl --no-tree --strict --no-signoff` não reportou problemas nos patches locais 0003–0006 na validação anterior. Isso não cobre 0007–0011. Os patches são rascunhos locais sem `Signed-off-by`, não submissões upstream.
- O port da PHY UFS coincide estaticamente com as tabelas Khaje R47: conjuntos normalizados de Gear 1–3 (78 registradores) e Gear 4 (76) sem divergências/extras, override Rate B de um registrador e lanes simétricas. O FDT do aparelho limita o host a G3; clocks, reguladores, domínio de energia, reset e DTS/DTBO ainda precisam ser integrados e verificados.
- A auditoria RPMCC estática mapeia os 28 IDs do provider e cobre os IDs referenciados pelo FDT ativo (`0, 1, 4, 5, 6, 7, 8, 28, 29, 68, 70, 106–111`); os pares RF_CLK1/2 `14–17` também estão no descritor.
- Nenhuma compilação do kernel, `dtbs_check`, validação DT-schema completa ou teste de boot foi executado. O usuário pediu concluir a integração antes da etapa de build; a compilação posterior será feita via GitHub Actions.
- Os patches 0010/0011 incluem o suporte `clk_vdd_class` adaptado ao regulador RPM-SMD portado e os providers GCC/DISPCC/GPUCC/debugcc com bindings. Ainda faltam DTS/DTBO 6.12 versionáveis para topaz/tapas, defconfig final, validação formal DT-schema/`dtbs_check` e os drivers Android de paridade. Não compilar nesta fase; a série continua sendo um port em andamento, não uma imagem bootável. O keepalive crítico GCC `GCC_QUPV3_WRAP0_S1_CLK` tem correspondência estática na FDT; execução e votos reais continuam sem teste em hardware.
