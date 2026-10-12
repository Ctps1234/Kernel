# Comparação de base: 6.1 × 6.12 (upstream)

Data: 2026-10-12. Objetivo: decidir se vale trocar a base 6.12 por 6.1 para o port do Redmi Note 12 4G (topaz).

## Fontes e limitações

- **Árvore usada:** `torvalds/linux` nas tags `v6.1` (`7614896350aa20764c5eca527262d9eb0a57da63`) e `v6.12` (`06090c9b622a7e1f797e775db4c035e0d779b76e`).
- **Não foi possível usar o GKI do Google:** o espelho `aosp-mirror/kernel_common` tem os branches `android14-6.1-2025-12` e `android16-6.12-2025-12` apontando para um commit vazio ("Initial commit"). Por isso a comparação é com upstream. O GKI adiciona patches Android, mas não adiciona os drivers abaixo.
- **Base atual do repositório:** `EdMory/android_kernel_common_sm8850` @ `0efd3abd3c356d644ea49f6ed37e9830b78d34e3` (6.12). Não foi comparada aqui, mas é derivada de 6.12.

## Resultado por item

| Item necessário | 6.1 upstream | 6.12 upstream | Observação |
|---|---|---|---|
| Wi-Fi `ath10k_snoc` (`qcom,wcn3990-wifi`) | Sim | Sim | Igual nas duas versões. |
| DPU `sm6125` (`dpu_5_4_sm6125`) | **Não encontrado** | Sim | Busca em `dpu_hw_catalog.c` sem resultado no 6.1. |
| Painel `nt36672e` (driver) | **Não existe** (404) | Sim (`panel-novatek-nt36672e.c`) | Só afeta se o painel `m7` for NT36672E. |
| Touch `edt-ft5x06` (FT5x06 / FT5426 / FT5452) | Genérico, só `focaltech,ft6236` | Genérico + `ft5426`, `ft5452` | Nenhuma das duas cobre a família FTS do stock. |
| Touch `goodix` | Sim | Sim | Igual. |
| DTS SoCs parecidos (`sm6125`, `sm6115`) | `sm6125.dtsi` | `sm6115.dtsi`, `sm6125.dtsi` e 2 DTS extras | Nenhuma das duas tem `khaje` / `sm6225`. |

## Conclusão

- **6.12 tem mais do que precisamos.** Os dois itens que faltam no 6.1 (DPU `sm6125` e driver `nt36672e`) são justamente os de display.
- **Trocar para 6.1 não facilita o display.** Pelo contrário: seria preciso portar esses dois itens do zero ou de outro branch.
- **Wi-Fi e touch não mudam** de forma relevante entre as duas versões.
- **Bloqueios que continuam iguais nas duas versões:** firmware do WCN3990 (vem do vendor), identificação do IC do painel `m7`, família FTS do touch e a fonte da GPU.

**Decisão recomendada:** manter a base 6.12.

## Pendências desta comparação

- Não verifiquei o `dsi-phy` (`qcom,dsi-phy-v4.1`) nas duas versões. A busca no `dsi_phy_14nm.c` não retornou nada útil, então fica em aberto.
- Se o usuário quiser o GKI real do Google, é preciso outro espelho com os branches `android14-6.1-*` e `android16-6.12-*` com conteúdo.
