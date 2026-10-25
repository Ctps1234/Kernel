# Auditoria de port de touchscreen Topaz — FocalTech FT3519T

## Resultado resumido

O IC de touch do painel M7 `_0a` (o ativo no aparelho capturado) é um
**FocalTech FT3519T**. Ele fala o protocolo de report genérico da FocalTech
que o driver upstream `edt-ft5x06` já implementa, com uma única diferença: as
coordenadas são de **15 bits** (os 3 bits de fração vêm empacotados no byte de
pressão e no byte alto de X), em vez dos 12 bits que o driver upstream extrai.
O patch [`0022`](../patches/0022-input-edt-ft5x06-ft3519.patch) adiciona o
compatible `focaltech,ft3519` ao `edt-ft5x06` com esse desempaque, mais o
binding. O nó de teste vive desabilitado em
[`device-tree/test/khaje-touch-upstream.dtsi`](../device-tree/test/khaje-touch-upstream.dtsi).

**Estado: compilação apenas.** O patch foi gerado contra a base fixada
(`0efd3abd3`) e o fragmento DTS passou por pré-processamento (cpp com os
includes do kernel) + parse sintático/resolução de labels sobre a base Khaje
encenada. Nada foi ativado, probado ou testado em hardware.

## Como o IC foi identificado (era o ponto em aberto)

A DTS vendor (`touchscreen_m7.dtsi`) só diz `focaltech,fts` em `0x38` para o
painel `_0a` e `goodix,gt9896` em `0x5d` para o `_0b`; a captura de runtime
mostra `focaltech_ts_i2c` carregado e `goodix_ts_9896` não carregado
([`module-inventory.md`](module-inventory.md)). Três fontes independentes
fecham a identidade:

1. **Firmware no vendor do aparelho:** os blobs proprietários do topaz
   (`vendor_xiaomi_topaz`, espelhos crDroid/Xiaomi-SD685-Devs) contêm um único
   firmware FocalTech: `focaltech_ts_fw_samsung_ft3519t.bin` — painel Samsung
   (o M7) + IC **FT3519T**.
2. **Driver vendor configurado para FT3519T:** há drops públicos do driver
   FocalTech com `FTS_CHIP_TYPE = _FT3519T` (ex.: `drivers/input/touchscreen/
   FT3519T/` no kernel stone/Redmi Note 12 5G). Nele, a série do FT3519 é
   `0x89` e a tabela `FTS_CHIP_TYPE_MAPPING` declara os bytes de chip ID
   `0x54, 0x52` (registradores `0xA3`/`0x9F`). Ou seja: **o FT3519 se
   identifica no barramento como "FT5452"**.
3. **Implementações rodando no hardware real:** os projetos topaz-woa
   (`TopazTouch`, Windows) e HelioDarwin (XNU) trazem driver para o touch do
   topaz chamando-o de FT5452, em `0x38` no QUP0 SE2, IRQ GPIO 80, reset
   GPIO 86, AVDD GPIO 36 sem regulador — exatamente os recursos da nossa DTS.
   É o mesmo chip: eles leram o ID `0x5452` do registrador.

Consequência prática: o `focaltech,ft5452` que já existe no upstream **não**
serve como alias. No upstream ele é um LCD in-cell de 5 pontos com
coordenadas de 12 bits; o FT3519T é um on-cell AMOLED de **10 pontos** com
coordenadas de 15 bits. Daí o compatible novo.

## O protocolo de report (por que o edt-ft5x06 serve)

Comparado byte a byte, o formato do FT3519 é o `GENERIC_FT` do upstream:

| Aspecto | Driver vendor FT3519T | `edt-ft5x06` (GENERIC_FT) |
|---|---|---|
| Leitura | a partir do reg. `0x01`; `buf[1]` = TD_STATUS (reg. `0x02`) | a partir do reg. `0x00`, `tdata_offset = 3` |
| Registro de ponto | 6 bytes a partir do reg. `0x03 + 6i` | 6 bytes a partir do reg. `0x03 + 6i` ✓ |
| Evento | bits 7:6 do byte XH (`flag = buf >> 6`) | `type = buf[0] >> 6` ✓ |
| Tracking ID | bits 7:4 do byte YH | `id = (buf[2] >> 4) & 0x0f` ✓ |
| Coordenadas | 15 bits (ver abaixo) | 12 bits (`be16 & 0x0fff`) ✗ → patch 0022 |
| Slots vazios | buffer pré-preenchido `0xFF` | tipo `0x3` (RESERVED) é ignorado ✓ |

O desempaque de 15 bits do vendor (parser `TOUCH_DEFAULT` do drop FT3519T,
com o código 12-bit original comentado logo acima dele) é:

```c
x = ((XH & 0x0F) << 11) + (XL << 3) + ((PRE & 0xC0) >> 5) + ((XH & 0x20) >> 5);
y = ((YH & 0x0F) << 11) + (YL << 3) + ((PRE & 0x30) >> 3) + ((XH & 0x10) >> 4);
p = PRE & 0x0F;
```

O HelioDarwin, no hardware real, lê a parte inteira 12-bit (faixa observada
0..1349 × 0..2999) e usa os bits 7:6/5:4 de `PRE` como fração de 2 bits,
convertendo com `(v * 4 + frac) / 5` para pixels do painel. É a mesma
grandeza: o firmware reporta posição em **décimos de pixel do painel**
(1349 ≈ 10800/8), e o valor de 15 bits do vendor cai em 0..10799 ×
0..23999 — idêntico ao `focaltech,display-coords` da DTS. O patch 0022
reporta os 15 bits crus e deixa a faixa declarada em
`touchscreen-size-x/y = 10800/24000`, como o vendor faz.

A baseline 6.12 já traz `focaltech,ft5452` e `focaltech,ft8719` no
`edt-ft5x06`, mas não o `focaltech,ft3518` (que o upstream ganhou depois do
6.12). O FT3518 é outra série (`0x81`) e não foi assumido equivalente: o
patch adiciona só o FT3519, com `max_support_points = 10`
(`focaltech,max-touch-number` e `FTS_MAX_POINTS_SUPPORT` concordam) e a flag
`hires_coords` no `edt_i2c_chip_data`.

## Recursos de placa (DTS)

De `touchscreen_m7.dtsi` e do FDT ativo, sobre `&qupv3_se2_i2c`
(`i2c@4a88000`, QUPv3 SE2, IRQ GIC SPI 329, clock `GCC_QUPV3_WRAP0_S2_CLK`):

- endereço `0x38`; IRQ TLMM 80 (falling); reset TLMM 86 (flag `1` =
  active-low);
- **AVDD não é regulador**: é `focaltech,avdd-gpio = <&tlmm 36>` (load
  switch; o HelioDarwin confirma "no regulator"). O `edt-ft5x06` pede
  `vcc`/`iovcc` via `regulator_get`, então o fragmento de teste modela o
  GPIO 36 como `regulator-fixed` (`touch_avdd`) em `vcc-supply`;
- **IOVCC 1.8V não declarado pelo vendor** (always-on na prática). O
  fragmento usa `&L9A` (rail 1.8V de IO do painel nesta placa) como
  placeholder **não confirmado**;
- pinctrl vendor `pmx_ts_active` = gpio80/86/36, função gpio, DS8,
  pull-up → estado achatado `ts-active-upstream-state` no fragmento;
- o nó vendor do barramento (`qcom,i2c-geni`) carrega `dmas` (GPI),
  `interconnects` e `qcom,wrapper-core`; o pai `qupv3_0` já usa o
  compatible upstream `qcom,geni-se-qup`. O fragmento só sobrepõe o
  compatible para `qcom,geni-i2c` e `clock-frequency = 400000`; a
  reconciliação completa com o binding upstream é bloqueio de ativação.

Config embutida para o driver compilar no `Image`:
`CONFIG_TOUCHSCREEN_EDT_FT5X06=y` + barramento upstream
(`I2C`/`QCOM_GENI_SE`/`I2C_QCOM_GENI`, `INPUT_TOUCHSCREEN`) em
[`config/topaz-khaje.config`](../config/topaz-khaje.config) e no `REQUIRED`
de `tools/configure_kernel.sh`.

## O que fica de fora (deliberado)

- **Firmware update** com `focaltech_ts_fw_samsung_ft3519t.bin`: o IC roda
  com o firmware gravado; o caminho de upgrade do driver vendor
  (`focaltech_flash`) não foi portado.
- **Pressão/área**: só posição, como os demais FocalTech genéricos do
  upstream. (No FT3519 a pressão são só os 4 bits baixos de `PRE`; os bits
  altos são a fração das coordenadas.)
- **Gestos, ESD check, modos Xiaomi** (`xiaomi-touch`/`xiaomi_touch_game`,
  `lct_tp`, `xm_adapter_class`) e o acoplamento com o painel via
  `panel_event_notifier` (0015, ainda sem produtor no DRM upstream):
  paridade com a HyperOS, não requisito de touch básico.
- **Variante Goodix GT9896** do painel `_0b`: protocolo Berlin, sem driver
  neste passo; o aparelho capturado é o FocalTech.
- **Comportamento de probe/PM não verificado**: o `identify()` do
  `edt-ft5x06` lê `0xBB` e depois `0xA6` (no FT, `FTS_REG_FW_VER`), e o
  resume escreve de volta `threshold`/`gain` (`0x80`/`0x92`) lidos do
  próprio chip. Chips FocalTech genéricos toleram isso upstream, mas no
  FT3519T continua hipótese até haver hardware.

## Fontes

- Blobs topaz (nome do firmware): `crdroidandroid/proprietary_vendor_xiaomi_topaz`
  e `Xiaomi-SD685-Devs/vendor_xiaomi_topaz` (`topaz-vendor.mk`).
- Driver vendor FT3519T (tabela de chip ID, parser 15-bit):
  `crdroidandroid/android_kernel_xiaomi_stone`, `drivers/input/touchscreen/FT3519T/`
  (`focaltech_config.h`, `focaltech_common.h`, `focaltech_core.c`).
- Hardware real: `MakrSas/topaz-woa` (`drivers/TopazTouch`) e
  `squeeeezy/HelioDarwin` (`xnu/patches/0083-topaz-touch-ft5452.patch`).
- Upstream: `drivers/input/touchscreen/edt-ft5x06.c` da base fixada
  (com `ft5452`, sem `ft3518`) e do `torvalds/linux` (com `ft3518`).
- DTS/FDT locais: `device-tree/source/qcom/display/display/touchscreen_m7.dtsi`,
  `device-tree/reference/topaz-live-reference.dts`,
  `device-tree/source/qcom/bengal-qupv3.dtsi` (`qupv3_se2_i2c`).
