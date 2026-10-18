# Port da PHY UFS Khaje (SM6225) para Android Common 6.12

## Decisão de implementação

A implementação Qualcomm Platform 5.0 R47 (`kernel/qcom`, commit `1c96d1325813d872d0206ffafe70c88823c86d6c`) usa o framework downstream `ufs_qcom_phy`; o alvo fixado (`EdMory/android_kernel_common_sm8850`, commit `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`) usa o driver upstream `phy-qcom-qmp-ufs.c` e as tabelas `qmp_phy_cfg`. Os patches [`0005-dt-bindings-qmp-ufs-sm6225.patch`](../patches/0005-dt-bindings-qmp-ufs-sm6225.patch) e [`0006-phy-qmp-ufs-sm6225.patch`](../patches/0006-phy-qmp-ufs-sm6225.patch) adaptam os dados Khaje a esse modelo; o patch [`0017`](../patches/0017-dt-bindings-qcom-sm6225-ufs-phy.patch) corrige os limites da binding e acrescenta o exemplo de nove clocks. A binding fica separada do driver, como recomendado pelo processo de submissão do kernel. Não importa o framework PHY downstream nem seu probe.

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

A adaptação mantém a sequência genérica upstream: o QMP gere os reguladores e clocks da binding, escreve as tabelas de configuração, remove o PCS de reset, inicia o SerDes e aguarda `PCS_READY_STATUS`. A referência R47 também escreve os dados sob reset, inicia o SerDes e espera o PCS ficar pronto, mas faz isso pelo framework `ufs_qcom_phy`; as APIs de power, reset e clocks downstream não foram copiadas. A correspondência das tabelas foi auditada e o driver passou pelo build do kernel nas runs CI 39071211672 e 39090488896; a sequência de power/reset/clock e `PCS_READY_STATUS` ainda não foi exercitada em hardware.

## Integração DTS e validação de schema

As fontes `device-tree/source/qcom/khaje.dtsi` e `khaje-idp.dtsi` contêm a PHY e o host UFS ativos; a run CI `39090488896` compilou o kernel, os DTBs e o exemplo da binding. A binding QMP local preserva o contrato dos demais SoCs e acrescenta uma condição específica para `qcom,sm6225-qmp-ufs-phy`: nove clocks de entrada com nomes exatos, em vez do limite genérico de três. O driver QMP obtém os clocks do nó em bulk e publica os clocks de símbolo para o host.

O patch 0017 também deixa claro que o PHY Khaje não usa reset externo nem genpd: o caminho de configuração usa o reset PCS por software; o controle de reset externo é opcional e o DTS não inventa um phandle para fechar o ciclo host↔PHY. O `power-domains` também não é declarado porque não há domínio genpd conectado ao PHY no DTS ativo. Permanecem as fontes `vdda-phy`/`vdda-pll` ligadas a `L4A`/`L18A`; esses rails e a sequência elétrica ainda precisam de confirmação em hardware.

Para refletir o driver upstream, o nó PHY remove `reg-names`, `lanes-per-direction`, o reset apontando ao host e limites de corrente que o QMP não consome. Os 54 valores inválidos `status = "ok"` da árvore DTS inteira foram normalizados para `"okay"`. No log oficial da run `39090488896`, `ufsphy_mem@4807000` já não tem diagnósticos de `dt-validate` em nenhum dos três DTBs.

O host `ufshc@4804000` continua fora do schema de `qcom,ufs`: ainda usa somente `compatible = "qcom,ufshc"`, nomes de recurso `ufs_mem`/`ufs_ice` e propriedades do downstream 5.15 não descritas no binding 6.12. Não renomear `ufs_mem` para `std` como correção cosmética: o driver MCQ consulta o recurso pelo nome `ufs_mem` e falha se ele não existir. A próxima etapa é adicionar um compatible SM6225 e a validação condicional adequada sem quebrar MCQ, depois decidir propriedade por propriedade quais itens vendor precisam ser portados ao driver, mapeados para propriedades upstream ou removidos por serem ignorados.

A comparação com a DTS de referência Qualcomm Platform 5.0 R47 (`la_platform_vendor_qcom-opensource_devicetree`, commit `66167e56588bd7c0c9ec91e1e5c464512f6c4db6`) acrescenta dados concretos, mas não uma DTS pronta para importar. `qcom/khaje.dtsi` descreve a PHY em `0x4807000` (`0xe00`), duas lanes, o host em `0x4804000`, nove clocks legados por nó, limites de Gear 3 no host e as rotas ICC `system_noc → bimc` e `bimc → config_noc`; ambos os nós começam desabilitados. A placa `khaje-idp.dtsi` adiciona o compatible downstream, habilita os nós e associa `vdda-phy` a `L4A`, `vdda-pll` a `L18A`, além dos rails do host e resets. Esses labels e tensões pertencem à implementação IDP/PMIC Qualcomm: a binding local descreve a estrutura de clocks SM6225, mas não comprova a correspondência elétrica com topaz.

O `dt_binding_check`/`dt-doc-validate` passou sem avisos ou erros na run `39090488896`. Já o `dt-validate` continua apontando erros no host UFS, não na PHY: as três variantes base/topaz/tapas reportam o compatible genérico, `reg-names` e propriedades/tipos vendor. Isso é diferente de dizer que todos os DTBs estão schema-clean.

## Estado de validação

- A comparação estática de tabelas acima passou para Gear 1–3, Gear 4 e Rate B; a simetria de lanes também foi confirmada.
- `git diff --check` passou na série aplicada; `scripts/checkpatch.pl --no-tree --strict --no-signoff` passou sem erros, avisos ou checks nos patches 0003–0006. `--no-tree` é necessário na sparse checkout temporária.
- A run CI 39090488896 compilou binding/exemplo e passou `dt_binding_check`, `dt-doc-validate`, DTBs e kernel sem avisos ou erros de binding. `dt-validate` não aponta mais a PHY UFS, mas ainda registra incompatibilidades do host descritas acima.
- A imagem `Image-khaje` foi compilada no CI, mas não houve boot, validação de sequência elétrica nem gravação em hardware.
