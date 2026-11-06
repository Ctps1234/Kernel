# Referência externa: `ivoszbg/linux-next` (`v6.14rc5-khaje`)

Data da análise: 2026-11-06.

## O que é

Fork do `linux-next` (pai `ColinIanKing/linux-next`) mantido por Ivaylo
Ivanov. O branch `v6.14rc5-khaje` é um **único commit WIP**
(`36d45318`, "[DIRTY] khaje && tb128fu support", 2025-05-22) sobre
v6.14-rc5, que adiciona suporte a SM6225 (Khaje) voltado ao tablet
Lenovo TB128FU. Último push do repo: 2025-09-10.

Nada disso está upstream: é trabalho de port em andamento, com
`// khaje` inline e tabelas não limpas.

## Veredito

**Não é fonte para importar** — base mais antiga (6.14-rc5 vs. a nossa
6.18), é um WIP declaradamente "dirty" e metade do commit é
específica do tablet (painel NT36523, touch NT36523, carregador
SY6974, `mmc@4744000`).

**É útil como cross-check independente.** É a primeira implementação
de SM6225 em mainline que encontramos além da nossa, e ela bate com
várias escolhas nossas que até então não tinham segunda opinião.

## O que bate (valida a nossa série)

| Item | Deles | Nosso | Situação |
|---|---|---|---|
| Speedbins A610 | `{206,1} {235,1} {200,2} {216,2} {157,3} {127,4}` | patch `0024`: idêntico | ✔ confirma |
| Pinos TLMM | 124 | patch `0002`: 124 | ✔ confirma |
| MDSS/DPU | bump `sm6375` para `core_minor_ver = 10` | patch `0016`: khaje já é `6.10` | ✔ confirma |
| ICC | compatibles `qcom,bengal-*` | patch `0007`: idem | ✔ confirma |
| PHY UFS | `lanes = 2`, `max_supported_gear = UFS_HS_G4`, `ufsphy_v4_regs_layout` | patch `0006`: mesmo esqueleto | ✔ compatível |
| Alimentação da PHY | `vdda-phy` / `vdda-pll` | `0036`: `pm6125_l4` / `pm6125_l18` | ✔ compatível |

Detalhe que checamos por causa do repo deles: o `reg` da PHY UFS.
Nós usamos `0xe00`, eles `0x1000` (igual ao `sm6115.dtsi` da base). O
maior offset escrito pelo layout v4 é `0xc00` (`pcs`), então **os dois
cobrem** — não é bug, mas `0x1000` é o valor convencional.

## O que eles têm e nós não (e se importa)

- **UFS: frequências de unipro de 200 MHz e 50 MHz** (`ufs-qcom.c` +
  `ufs-qcom.h`). O host upstream só conhece 37.5/75/100/150/201.5/
  300/403 MHz. **Hoje não precisamos**: nossa tabela de unipro no
  `gcc-sm6225` para em 150 MHz (G2), e todas as taxas que o nosso DT
  pede estão na lista suportada. Vira item de backlog **se** um dia
  habilitarmos G4/300 MHz.
- **QCE** (`crypto@1b20000`): nós temos o PRNG (`crypto@1b3a000`,
  patch `0077`). QCE não é usado por FBE/ICE do Android.
- **Tabelas da PHY UFS reaproveitadas de `sm8150`** em vez das nossas
  `sm6225_ufsphy_rx` / `_pcs` (que vieram do downstream). É a
  alternativa a testar **se** o UFS falhar no hardware: trocar por
  `sm8150_ufsphy_{tx,rx,pcs}` é uma mudança de uma linha por tabela e
  elimina a variável "tabela inventada".
- `crypto`, CTIs (coresight), `i2c@4a80000/4a8c000/4a94000`,
  `mmc@4744000`: escolhas de placa do tablet, não lacunas nossas.

## Se algo falhar no primeiro boot

Ordem de suspeição sugerida por esta comparação:

1. **UFS** → testar as tabelas `sm8150` na PHY (ver acima) antes de
   mexer em clock.
2. **Display** (Nível 1) → comparar nosso `khaje-dpu` com o deles; a
   única diferença é que eles *alteram* o `sm6375`, nós já declaramos
   `6.10` — mesma conclusão por caminhos diferentes.
3. **Touch** → o deles é NT36523 (tablet), o nosso FT3519T; nada a
   aproveitar.
