# Auditoria dos reguladores PM6125: stock × série 6.18

Análise de 2026-11-06. Compara cada rail RPM-SMD que a série declara
com o que o **firmware do aparelho** usa, e confirma que nenhum
consumidor ficou órfão.

## Por que isso importa mais do que parece

As tensões iniciais dos rails **não são ajustadas em runtime** na
maioria dos drivers que portamos. Dois casos concretos, verificados no
código mainline:

- `drivers/phy/qualcomm/phy-qcom-snps-femto-v2.c` só chama
  `regulator_bulk_enable()` / `_disable()`. Não existe um
  `regulator_set_voltage()` em nenhum caminho — a tensão que o PHY
  recebe é exatamente o `qcom,init-voltage` do RPM.
- O mesmo vale para o codec e para o `hci_qca` do Bluetooth.

Ou seja: `qcom,init-voltage` errado no DTS = rail errado no hardware,
sem aviso, sem log, sem deferral. Por isso a comparação foi feita
contra o FDT do aparelho e não contra um downstream genérico de
família (Bengal), que é onde os valores originais da série tinham
nascido.

## Método

Três fontes, todas do próprio aparelho:

| Fonte | O que é |
|---|---|
| `device-tree/reference/topaz-live-reference.dts` | FDT live do topaz, já no repo desde a fase 5.15 |
| `device-tree/reference/khaje-base-reference.dts` | DT base do Khaje (dump do firmware) |
| `dtbs/01_dtbdump_*Khaje_SoC.dtb` do repo `xiaomi-6225-AD` | terceira cópia independente, baixada em 2026-11-06 |

As três concordam entre si em todos os 13 rails. A série, em cinco
deles, não concordava.

## Resultado: 13 de 13 idênticos

Depois das correções abaixo, `min/init/max` de cada rail na série é
byte a byte igual ao do firmware.

| Rail | min / init / max (µV) | Consumidor principal |
|---|---|---|
| `l4` | 720.000 / 880.000 / 1.050.000 | UFS `vdda-phy`, USB HS core (`vdda-pll`), CSIPHY0-2 |
| `l5` | 1.650.000 / 2.960.000 / 3.050.000 | microSD `vqmmc` |
| `l9` | 1.504.000 / 1.800.000 / 2.000.000 | painel `vddio`, codec, touch, WLAN `vddio` |
| `l11` | 1.700.000 / 1.800.000 / 1.950.000 | UFS `vccq2` |
| `l12` | 1.620.000 / 1.800.000 / 1.980.000 | USB HS `vdda18` |
| `l14` | 1.700.000 / 1.700.000 / 1.900.000 | codec `vdd-buck` e `vdd-mic-bias` |
| `l15` | 2.700.000 / 3.080.000 / 3.544.000 | USB HS `vdda33` |
| `l16` | 1.700.000 / 1.700.000 / 1.900.000 | BT `vddxo`, WLAN `1.8-xo` |
| `l17` | 1.220.000 / 1.220.000 / 1.304.000 | BT `vddrf`, WLAN `1.3-rfa` |
| `l18` | 1.100.000 / 1.232.000 / 1.300.000 | UFS `vdda-pll`, DSI ctrl/phy, SS PHY |
| `l22` | 2.950.000 / 2.960.000 / 3.300.000 | microSD `vmmc` |
| `l23` | 3.200.000 / 3.200.000 / 3.400.000 | BT `vddch0` (PA) |
| `l24` | 2.700.000 / 2.960.000 / 3.544.000 | UFS `vcc` |

## As cinco correções

Todas eram `qcom,init-voltage` (e em três casos também a janela) vindos
de `bengal-regulator.dtsi`, não do Khaje.

| Rail | Antes (init) | Agora | Consequência que isso evitava |
|---|---:|---:|---|
| `l12` | 1.624.000 | 1.800.000 | PHY USB HS com 1,62 V num rail de 1,8 V (–10%) |
| `l15` | 2.920.000 | 3.080.000 | PHY USB HS com 2,92 V num rail de 3,08 V (–5%) |
| `l17` | 1.152.000 | 1.220.000 | core do BT com 1,152 V num rail de 1,22 V (–5,6%) |
| `l22` | 2.952.000 | 2.960.000 | `vmmc` do cartão 8 mV abaixo do firmware |
| `l5` | 1.648.000 | 2.960.000 | `vqmmc` nascendo em 1,65 V, e não em 2,96 V |

Duas outras correções vieram da comparação com as referências do
próprio repo (não do `bengal`):

| Rail | Antes | Agora | Origem |
|---|---:|---:|---|
| `l14` | 1.696.672 / 1.900.992 | 1.700.000 / 1.900.000 | valor não batia com nenhuma das três fontes |
| `l16` | 1.704.000 / 1.904.000 | 1.700.000 / 1.900.000 | idem |

Sobre `l5`: o `mmc` core **vai** ajustar o `vqmmc` no power-up
(`sdhci_msm_set_vqmmc()` → `mmc_regulator_set_vqmmc()`), então o init
baixo não era fatal. Mesmo assim ficou alinhado: se o power IRQ não
chegar, o rail em repouso fica no valor que o firmware considera
correto para cartão SD em high-speed. Com `max = 3,05 V`, um pedido de
3,3 V do core assenta em 3,05 V — exatamente o que o stock faz.

## Nome enganoso: `vdda-pll` é o core, não a PLL

`qcom,usb-snps-femto-v2.yaml` exige três supplies: `vdda-pll`,
`vdda18`, `vdda33`. O texto do binding diz que `vdda-pll` é
"phandle to the regulator VDD supply node". No topaz isso é
`pm6125_l4` (0,88 V), não um rail de 1,2 V. O nome carrega a herança
do SM8250, onde a PLL tinha rail próprio. Não "corrigir" o
`vdda-pll-supply = <&pm6125_l4>` do `0068`: ele está certo pelo
binding e pelo hardware.

## Consumidores órfãos: nenhum

Todos os `*-supply = <&pm6125_lXX>` da série apontam para um rail
declarado. O contrário também foi verificado: sobram rails declarados
sem consumidor (`l5`, `l12`, `l15`, `l17`), o que é esperado — são
rails que o RPM inicializa e cujo consumidor é um driver que ainda não
está no DTS (ou o PHY, que só habilita).

## O que deliberadamente não foi declarado

- `s3`/`s5` (CX/MX): no mainline esses domínios vão por
  `rpmpd`/power-domains, não por regulador. O downstream usa
  `regulator-cdev-supply` e `vdd_cx-supply`; são caminhos diferentes
  para o mesmo hardware. Declarar os dois criaria dois donos.
- `l7`, `l8`, `l13`, `l19`, `l20`, `l21`, `s1`, `s7`, `s8`: existem no
  firmware, sem consumidor na série. `l7`/`l8` são do ICNSS (Wi-Fi não
  portado) e `s7`/`s8` são rails do PM8008 que não temos. Entram
  quando o driver correspondente entrar.
- O `regulator-s6` que aparece com min/max diferentes está no
  **exemplo** do binding `0008`, não em DTS de produção. Não é
  divergência.

## Como reproduzir

A auditoria virou ferramenta: `tools/audit_regulators.py` lê as duas
referências do repo (`topaz-live-reference.dts` e
`khaje-base-reference.dts`), extrai `min/init/max` de cada
`regulator-lN`, faz o mesmo nos patches (ignorando patches de binding,
cujo YAML tem exemplos com rails fictícios) e compara.

```sh
tools/audit_regulators.py            # só o veredito + divergências
tools/audit_regulators.py --verboso  # rail por rail, com a fonte
```

Saída atual:

```
OK: 13 rail(s) conferido(s), todos iguais ao FDT do aparelho
so' em topaz-live-reference.dts (sem consumidor na serie): l1, l2, l3,
  l6, l7, l8, l10, l13, l19, l20, l21, s1, s3, s5, s6, s7, s8
```

A segunda linha não é erro: são os rails do aparelho que a série ainda
não usa (ver seção acima). A ferramenta existe para rodar de novo a
cada patch que trouxer consumidor novo — se alguém colar uma tensão de
outro SoC, a auditoria acusa na hora.

O que fica registrado como método: para rail, a fonte é o **firmware do
aparelho**, nunca o downstream de outro SoC da mesma família. Bengal e
Khaje compartilham pinagem, mas não tensão de repouso.
