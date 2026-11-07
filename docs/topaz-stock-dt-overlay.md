# DT stock do topaz em texto: overlay de placa do `xiaomi-6225-AD`

Análise de 2026-11-06. Fonte:
`github.com/xiaomi-6225-AD/android_device_xiaomi_topaz-kernel`,
branch `lineage-21`, pasta `dtbs/` (repo de kernel prebuilt).

Até aqui a gente só tinha o **binário** do DT stock (extraído do
`vendor_boot` do dump) e nenhum `dtc` no sandbox para ler. Este repo
traz os mesmos artefatos já prontos, e agora existe ferramenta no
repo para abrir os dois.

## O que tem lá

| Arquivo | Tamanho | O que é |
|---|---:|---|
| `01_dtbdump_..._Khaje_SoC.dtb` | 282.232 B | DT base do Khaje (SM6225), `msm-id = <0x206 0x10000>` |
| `02_..._Khaje_SoC.dtb` | 282.240 B | idem, variante de build |
| `03_..._Khajeg_SoC.dtb` | 264.028 B | Khajeg (`0x249`) |
| `04_..._Khajep_QRD.dtb` | 59.256 B | Khajep QRD (`0x231`) |
| `05_..._Khajep_SoC.dtb` | 209.132 B | Khajep |
| `06_..._Khajeq_SoC.dtb` | 207.181 B | Khajeq (`0x232`) |
| `dtbo.img` | 8.388.608 B | 49 entradas, 3.423.313 B úteis |

Cada `dtbdump` é um DT **completo** (memória, CPUs, `soc@0`), não um
fragmento. O `dtbo.img` segue o formato AOSP: cabeçalho
`d7b7ab1e` + tabela de entradas de 32 B.

**A entrada 48 é a placa do aparelho:**

```
model     = "Qualcomm Technologies, Inc. KHAJE IDP nopmi topaz"
msm-id    = <0x206 0x10000>
board-id  = <0x30022 0x0>
pmic-id   = <0x2d 0x0 0x0 0x0>
tamanho   = 121.465 B
```

Contra o dtbo do aparelho (dump de 2026-11-04, entrada 51): mesmo
`model`, mesmo `board-id`, mesmo `pmic-id`, 121.458 B. A diferença de
**7 bytes** é consistente com outro build do mesmo overlay (não é
outra placa). Vale dizer o que se sabe e o que não se sabe: o conteúdo
é a mesma camada de placa, mas **não foi confirmado byte a byte**
contra a entrada do aparelho — isso exige rebaixar o dump e comparar.

## Ferramentas novas

Nenhuma das duas existia no sandbox (`dtc` nunca esteve disponível):

- `tools/fdt_dump.py` — FDT binário → DTS. Faz o que
  `dtc -I dtb -O dts` faz, incluindo listas de strings
  (`compatible = "a", "b"`), células hexadecimais e bytes crus.
- `tools/fdt_overlay_dump.py` — overlay → DTS **com os phandles
  resolvidos por nome**. Um `.dtbo` cru é ilegível (`target =
  <0xffffffff>`); o script lê `__fixups__`, casa cada posição com o
  `__symbols__` do DT base e imprime `&tlmm`, `&L24A`, etc.

Reprodução:

```sh
git clone --depth 1 --filter=blob:none --sparse \
    -b lineage-21 \
    https://github.com/xiaomi-6225-AD/android_device_xiaomi_topaz-kernel
cd android_device_xiaomi_topaz-kernel && git sparse-checkout set dtbs

tools/fdt_dump.py dtbs/01_dtbdump_*.dtb > khaje.dts
python3 - <<'PY'   # extrai a entrada 48
import struct
d = open('dtbs/dtbo.img','rb').read()
_,_,_,esz,cnt,eoff,_ = struct.unpack('>IIIIIII', d[:28])
sz,off,_,_ = struct.unpack('>IIII', d[eoff+48*esz:eoff+48*esz+16])
open('topaz.dtbo','wb').write(d[off:off+sz])
PY
tools/fdt_overlay_dump.py topaz.dtbo --base khaje.dtb > topaz-board.dts
```

## Inventário de hardware que o overlay revela

Nada disso estava documentado antes (o DT stock binário não era
legível). Tudo em GPIO do TLMM, salvo indicação.

**Touch** (`fragment@47`, i2c SE2 `4a88000`, `qcom,i2c-touch-active =
"focaltech,fts"`):
`focaltech@38` com IRQ GPIO 80, reset GPIO 86, avdd GPIO 36,
`display-coords = <0 0 0x2a2f 0x5dbf>` (1080×2400 em décimos).
O mesmo fragmento declara `goodix-sunrise@5d` como alternativa
(`goodix,gt9896`) e fragmentos anteriores trazem `synaptics_tcm@20` /
`novatek@62` desligados — são as variantes de fornecedor da placa.

**Câmeras** (`fragment@33`, `cci0`; e os 4 `qcom,cam-sensor`):

| Sensor | MCLK | Reset | CCI | CSIPHY | Flash/E²PROM |
|---|---:|---:|---:|---:|---|
| `cam-sensor0` | 20 | 18 | 0 | 0 | sim / sim |
| `cam-sensor1` | 21 | 24 | 1 | 2 | não / sim |
| `cam-sensor2` | 27 | 19 (+100) | 1 | 1 | sim / sim |
| `cam-sensor3` | 28 | 99 (+68) | 0 | 1 | sim / sim |

**Flash LED**: `qcom,camera-flash@0` tem `cci-master = <1>` e
**nenhum `compatible` de driver nem endereço I²C** — o chip do flash
não é identificado nem pelo DT stock. Confirma o que já estava
registrado: o IC vive atrás da CCI1 e não é declarado.

**WL2866D**: `wl2866d@28` no SE1 (`4a84000`), `en-gpio` TLMM 26,
`id_reg = 3`, `id_val = 0x64`, `id_val1 = 0x55`, `inits = <4 0x4b 0xe 0xf>`.
Bate exatamente com o nosso `0063`.

**RT1711H**: `rt1711h@4e` no SE1, IRQ em GPIO 93 (`rt1711h_int_n`
muxa `gpio93`) — bate com o nosso `0063`.

**NFC**: `st_st21nfc@08` no SE4 (`4a90000`) — bate com o `0050`.

**Carregador/energia**: `bq2589x@6A`, `sm5602@71` (medidor),
`sc8551@66`/`ln8000@51` (charge pump) no SE1; `qcom,nopmi-chg`,
`onewire_gpio` e `maxim_ds28e16` (autenticação de bateria).

**UI/botões**: volume+ no GPIO 5 do **PM6125**, vibrador no GPIO 8 do
PM6125 (`qcom,qpnp-vibrator-ldo-tz`), SIM tray custom,
`oled_vci`/`eldo9_pin` no pinctrl do PMIC.

**Display**: `qcom,dsi-display-primary` com TE no GPIO 81,
`vddio = L9A`, painel padrão = phandle 0x47. O overlay traz 7
definições de painel (td4330 cmd/vídeo, nt36672e 90/120 Hz, "m7 ..."
fhdp) — a escolha real é feita em runtime pelo painel detectado, então
o Nível 1 precisa cobrir os dois vídeo/cmd (1080×2400,
`panel-width = 0x438`, `panel-height = 0x8e8`).

**Áudio**: `wsa881x-i2c-codec@e/@44`, `fs16xx@34`, `aw87xxx_pa_59@59`
no SE1, `tasha`/`bolero` no `spf_core_platform`.

## Confronto com a nossa série

O que bate (segunda opinião em cima de valores que já tínhamos):

| Item | Stock | Série 6.18 |
|---|---|---|
| PHY UFS `reg` | `0x4807000` + `0xe00` | idêntico (`0xe00` — menor que os `0x1000` do `sm6115.dtsi`, e correto) |
| PHY UFS rails | `L4A` (85.700 µA) / `L18A` (18.300 µA) | `pm6125_l4` / `pm6125_l18` — mesmos números |
| UFS host | `vcc = L24A` (800 mA), `vccq2 = L11A` (800 mA), `reset-gpios` GPIO 113 | idêntico, no `0036` |
| microSD | `vmmc = L22A` (2,96 V), `vqmmc = L5A`, `cd-gpios` GPIO 88 | `0071` — mesmos rails |
| WL2866D | `@28` SE1, en GPIO 26, `id_val 0x64/0x55` | idêntico |
| RT1711H | `@4e` SE1, IRQ GPIO 93 | idêntico |
| NFC | `@08` SE4 | idêntico |
| Touch (controlador) | `focaltech,fts` @0x38 | nosso `0022` estende `edt-ft5x06` com `focaltech,ft3519` |

Varredura completa em 2026-11-06 (todos os nós de placa da série
contra o overlay): **um** divergência real, já corrigida, e uma
propriedade downstream que não se porta.

1. **`cd-gpios` do microSD — corrigido.** O stock diz
   `<&tlmm 0x58 0x1>` (**ACTIVE_LOW**); o nosso `0071` dizia
   `GPIO_ACTIVE_HIGH` com a justificativa "a camada da Xiaomi inverte
   o IDP". O overlay do topaz *é* a camada da Xiaomi e diz o
   contrário. A prova independente está no pinctrl do próprio DT base:
   `sdc2_on/sd-cd` configura `gpio88` com **`bias-pull-up`** — o
   switch do slot aterra o pino quando há cartão, logo cartão presente
   = nível baixo. Corrigido em dois pontos: `0071` passa a
   `GPIO_ACTIVE_LOW` e `0070` ganha o estado de pino `cd-pins`
   (gpio88, `bias-pull-up` no on, `bias-disable` no off) que estava
   faltando nos estados `sdc2-on`/`sdc2-off`.
2. **`qcom,vddp-ref-clk-supply`** existe no stock (`L18A`, 100 µA) mas
   **não existe no mainline 6.18**: nem o driver (nenhum `vddp` em
   `ufs-qcom.c`) nem o binding `qcom,ufs.yaml`. É propriedade
   downstream; não portar.

O que a varredura confirmou (nada a mudar):

| Bloco | Stock | Série |
|---|---|---|
| Touch | `focaltech@38` SE2, IRQ 80, reset 86, avdd 36 | `0053`: idêntico |
| Câmera frontal | MCLK1 = TLMM 21, reset 24, CCI1, CSIPHY2 | `0057`: idêntico |
| Câmera traseira | MCLK0 = TLMM 20, reset 18, CCI0, CSIPHY0 | `0058`: idêntico |
| NFC | `@08` SE4, IRQ 70, reset 69 | `0050`/`0088`: idêntico |
| Botão volume+ | PM6125 GPIO 5, active-low | `0048`: idêntico |
| Vibrador | PM6125 GPIO 8, active-low | `0052`: idêntico |
| WL2866D | `@28` SE1, en GPIO 26 | `0063`: idêntico |
| RT1711H | `@4e` SE1, IRQ 93 | `0063`: idêntico |
| Painel padrão | `m7 38 0c 0a`, 120 Hz, h 28/120/120, v 2/10/20 | `0021`: idêntico |

Sobre o painel: o `qcom,dsi-default-panel` do overlay aponta para a
entrada `m7 38 0c 0a fhdp video`, que é exatamente o painel do `0021`.
Cuidado ao reler o dump: o painel tem mais de um bloco de timing (o
`td4330` logo acima usa 10/68/76), e comparar com o bloco errado dá
uma falsa divergência de porches.

## Próximos usos

- **Nível 0** não muda: nada aqui é bloqueador de boot.
- **Nível 1** (display): os painéis do overlay dão timings reais —
  substitui chute por dado na hora de portar `td4330`/`nt36672e`.
- **Nível 2**: câmera (MCLK/reset por sensor), touch, carga e áudio
  agora têm pinagem exata.
- Se for preciso **certeza byte a byte**, o caminho é rebaixar
  `dump-lineage.tar.gz` do Drive, extrair a entrada 51 do `dtbo_b.img`
  e rodar os dois dumps lado a lado.
