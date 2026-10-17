# Port da PHY UFS Khaje (SM6225) para Android Common 6.12

## Decisão de implementação

A implementação Qualcomm Platform 5.0 R47 (`kernel/qcom`, commit `1c96d1325813d872d0206ffafe70c88823c86d6c`) usa o framework downstream `ufs_qcom_phy`; o alvo fixado (`EdMory/android_kernel_common_sm8850`, commit `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`) usa o driver upstream `phy-qcom-qmp-ufs.c` e as tabelas `qmp_phy_cfg`. Os patches [`0005-dt-bindings-qmp-ufs-sm6225.patch`](../patches/0005-dt-bindings-qmp-ufs-sm6225.patch) e [`0006-phy-qmp-ufs-sm6225.patch`](../patches/0006-phy-qmp-ufs-sm6225.patch) adaptam os dados Khaje a esse modelo; a binding fica separada do driver, como recomendado pelo processo de submissão do kernel. Não importa o framework PHY downstream nem seu probe.

Os patches registram `qcom,sm6225-qmp-ufs-phy`, reutilizam a configuração de registradores QMP v4 do alvo e separam as tabelas comuns dos overlays HS Gear 3 e Gear 4. A configuração permite Gear 4; o FDT do aparelho limita o host UFS a Gear 3 em TX e RX, portanto o modo operacional esperado do Redmi continua até Gear 3.

## Auditoria de calibração

Fonte de referência: `drivers/phy/qualcomm/phy-qcom-ufs-qmp-v4-khaje.c` e `.h` no commit R47. A comparação estática dos registradores e valores resultou em:

| Calibração R47 | Tabelas QMP 6.12 | Comparação |
|---|---|---|
| Rate A, gears 1–3, incluindo configuração das duas lanes | SerDes/TX/RX/PCS comuns SM6225 + overlay PCS até Gear 3 | **78 pares registrador/valor correspondentes**, sem diferença nem registradores extras. O controle global de power-down é executado pelo driver QMP. |
| Rate A, Gear 4, incluindo configuração das duas lanes | Tabelas comuns + overlay de Gear 4 | **76 pares correspondentes**, sem diferença nem registradores extras. |
| Rate B | `tbls_hs_b` | O override `QSERDES_V4_COM_VCO_TUNE_MAP = 0x06` corresponde exatamente. |

Os dados de lane 0 e lane 1 são simétricos: os 40 registradores de lane por direção usados até Gear 3 e os 44 usados em Gear 4 têm os mesmos valores após normalizar o índice da lane. O QMP upstream aplica a tabela TX/RX a cada lane configurada (`lanes = 2`), cobrindo esse comportamento sem duplicar tabelas por lane.

Há duas diferenças importantes em relação a simplesmente associar a configuração SC7280 já existente:

- Para Gear 1–3, Khaje tem quatro valores próprios em `RX_MODE_01` (`0x6d`, `0x6d`, `0xed`, `0x3c`). O array `sm6225_ufsphy_rx` registra esses valores e não programa `DCC_CTRL1` nessa tabela base.
- PCS foi dividido entre configuração comum e overlays por gear. Os valores de temporização/capacidade próprios de Gear 1–3 ficam no overlay `UFS_HS_G3`; a potência/ajustes RX de Gear 4 ficam no overlay `UFS_HS_G4`. Assim, os valores PCS de G3 não são escritos quando a PHY está em G4.

O host Qualcomm upstream passa o gear numérico à PHY com `phy_set_mode_ext(..., host->phy_gear)`. O seletor de overlays do QMP usa esse gear: Gear 1–3 seleciona o overlay de Gear 3 como melhor calibração aplicável; Gear 4 seleciona o overlay de Gear 4. Em Rate B, o override SerDes é aplicado depois do overlay, na mesma ordem lógica usada pela referência.

## Sequência de inicialização

A adaptação mantém a sequência genérica upstream: o QMP gere os reguladores e clocks da binding, escreve as tabelas de configuração, remove o PCS de reset, inicia o SerDes e aguarda `PCS_READY_STATUS`. A referência R47 também escreve os dados sob reset, inicia o SerDes e espera o PCS ficar pronto, mas faz isso pelo framework `ufs_qcom_phy`; as APIs de power, reset e clocks downstream não foram copiadas. A correspondência das tabelas foi auditada e o driver passou pelo build do kernel na run CI 39071211672; a sequência de power/reset/clock e `PCS_READY_STATUS` ainda não foi exercitada em hardware.

## Integração DTS e validação ainda pendentes

As fontes `device-tree/source/qcom/khaje.dtsi` e `khaje-idp.dtsi` já incluem o UFS ativo, e o CI 39071211672 compilou os DTBs, o kernel e o exemplo de binding. Isso não significa que o nó ativo esteja schema-clean: o `dt-validate` ainda reporta incompatibilidades com os schemas upstream. A binding de `qcom,sm6225-qmp-ufs-phy` e o host UFS precisam ser alinhados ao contrato upstream, em vez de tratar o nó vendor como validado. Entre as diferenças a resolver estão:

- a binding upstream espera uma região plana `reg`, três clocks de entrada chamados `ref`, `ref_aux` e `qref`, `#phy-cells = <0>`, domínio de energia e reset com `reset-names = "ufsphy"`;
- o driver QMP solicita as fontes `vdda-phy` e `vdda-pll`; as ligações aos reguladores/PMIC corretos precisam ser comprovadas, não substituídas por fontes dummy;
- a PHY QMP publica três clocks de símbolo para o controlador UFS. O DTS precisa ligar corretamente esses clocks ao host, sem duplicar os clocks de saída listados no nó legado de nove clocks;
- o dump vendor descreve um nodo legado com `reg-names`, clocks e reset no formato downstream; esse nodo não pode ser tratado como um nó QMP upstream validado.

No `dtbs_check` da run 39071211672, `ufsphy_mem@4807000` foi reportado com nove clocks (acima do limite do schema), sem `power-domains`/`reset-names` exigidos e com propriedades vendor não aceitas. `ufshc@4804000` também diverge do binding upstream de `qcom,ufshc` em compatible, `reg-names` e propriedades vendor. Essas ocorrências permanecem na linha de base de 2791 erros; o patch 0016 corrigiu apenas meta-validação dos schemas e não alterou os nós UFS.

A comparação com a DTS de referência Qualcomm Platform 5.0 R47 (`la_platform_vendor_qcom-opensource_devicetree`, commit `66167e56588bd7c0c9ec91e1e5c464512f6c4db6`) acrescenta dados concretos, mas não um DTS pronto para importar. `qcom/khaje.dtsi` descreve a PHY em `0x4807000` (`0xe00`), duas lanes, o host em `0x4804000`, nove clocks legados por nó, limites de Gear 3 no host e as rotas ICC `system_noc → bimc` e `bimc → config_noc`; ambos os nós começam desabilitados. A placa `khaje-idp.dtsi` adiciona o compatible downstream, habilita os nós e associa `vdda-phy` a `L4A`, `vdda-pll` a `L18A`, além dos rails do host e resets. Esses labels e tensões são da implementação IDP/PMIC Qualcomm: não os copiar para topaz sem confirmar o FDT ativo e os providers portados. A estrutura de nove clocks do vendor também não é a binding upstream de três clocks de entrada e clocks de saída via PHY.

Os nós e consumidores do FDT ativo já estão em DTS/DTBO buildáveis e passaram pelo CI; a validação do schema da binding/documentação passou, mas o `dt-validate` dos nós UFS ativos ainda falha conforme os itens acima. Isso é diferente do `dt_binding_check` limpo confirmado pela run 39071211672.

## Estado de validação

- A comparação estática de tabelas acima passou para Gear 1–3, Gear 4 e Rate B; a simetria de lanes também foi confirmada.
- `git diff --check` passou na série aplicada; `scripts/checkpatch.pl --no-tree --strict --no-signoff` passou sem erros, avisos ou checks nos patches 0003–0006. `--no-tree` é necessário na sparse checkout temporária.
- `dt_binding_check` e `dt-doc-validate` direto validaram a binding e seu exemplo na run CI 39071211672; o build do kernel e dos DTBs também passou. O relatório de `dtbs_check` ainda contém os erros dos nós UFS acima.
- A imagem `Image-khaje` foi compilada no CI, mas não houve boot, validação de sequência elétrica nem gravação em hardware.
