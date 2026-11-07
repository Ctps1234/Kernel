# Clock do DSI no 6.18: por que o painel do topaz depende de DSC

Análise de 2026-11-06. Fonte do código: `drivers/gpu/drm/msm/dsi/dsi_host.c`
da base ACK `android17-6.18@1afe39e` (2648 linhas), funções
`dsi_adjust_pclk_for_compression()`, `dsi_get_pclk_rate()`,
`dsi_byte_clk_get_rate()` e `dsi_calc_clk_rate_v2()`.

O painel do topaz (`m7 38 0c 0a`) é **DSC obrigatório**. Não é um
detalhe de otimização: sem compressão o link DSI ficaria em
~2,36 Gbps por lane, muito acima do que essa PHY opera com folga.
Este documento fecha a conta e registra o que o host 6.18 faz com ela.

## 1. O modo, lido do FDT stock

Do nó `qcom,mdss_dsi_panel_m7_38_0c_0a_fhdp_video` (timing@0):

| Parâmetro | Valor | Propriedade downstream |
|---|---:|---|
| Largura ativa | 1080 | `qcom,mdss-dsi-panel-width = <0x438>` |
| Altura ativa | 2400 | `qcom,mdss-dsi-panel-height = <0x960>` |
| H front / back / pulse | 120 / 120 / 28 | `h-front-porch`, `h-back-porch`, `h-pulse-width` |
| V front / back / pulse | 20 / 10 / 2 | `v-front-porch`, `v-back-porch`, `v-pulse-width` |
| Taxa de quadro | 120 Hz | `qcom,mdss-dsi-panel-framerate = <0x78>` |
| Lanes | 4 | `lane-0..3-state` |
| bpp do painel | 24 (RGB888) | `qcom,mdss-dsi-bpp = <0x18>` |

Portanto:

```
htotal = 1080 + 120 + 120 + 28 = 1348
vtotal = 2400 +  20 +  10 +  2 = 2432
pclk   = htotal × vtotal × fps = 1348 × 2432 × 120 = 393.400.320 Hz
```

Esse é o `mode->clock` que o driver de painel declara ao DRM
(393.400 kHz, o valor que o DRM arredonda em kHz).

## 2. O que o host faz com esse número

`dsi_get_pclk_rate()` começa em `mode->clock * 1000` e, **se
`msm_host->dsc` não for nulo**, substitui pelo valor ajustado:

```c
new_hdisplay = DIV_ROUND_UP(mode->hdisplay * drm_dsc_get_bpp_int(dsc),
                            dsc->bits_per_component * 3);
new_htotal   = mode->htotal - mode->hdisplay + new_hdisplay;
pclk         = mult_frac(mode->clock * 1000u, new_htotal, mode->htotal);
```

Ou seja: a compressão encurta só a parte ativa da linha; os porches
ficam como estão (`h_total - hdisplay` não muda). Depois:

```c
byte_clk = mult_frac(pclk, bpp, 8 * lanes);   /* D-PHY  */
byte_clk = mult_frac(pclk, bpp, 16 * lanes);  /* C-PHY  */
```

e, em `dsi_calc_clk_rate_v2()`, `src_clk = pclk * bpp / 8`.

Com `bits_per_pixel = 8` (Q4: `8 << 4`) e `bits_per_component = 8`:

```
new_hdisplay = ceil(1080 × 8 / 24) = 360
new_htotal   = 1348 - 1080 + 360   = 628
pclk         = 393.400.320 × 628 / 1348 = 183.275.520 Hz
```

## 3. Os números do topaz

| Grandeza | Sem DSC | Com DSC (o que vale) |
|---|---:|---:|
| pclk | 393,400 MHz | **183,276 MHz** (46,6% do nominal) |
| `byte_clk` (4 lanes, 24 bpp) | 295,050 MHz | **137,457 MHz** |
| Taxa por lane | 2360 Mbps | **1100 Mbps** |
| `src_clk` (v2) | 1180,2 MHz | 549,8 MHz |

A taxa por lane sem compressão já explica a obrigatoriedade: 2,36 Gbps
por lane, com 4 lanes, é acima do que a PHY DSI 7nm v4.1 do SM6225
opera de forma confortável (a faixa típica documentada para esses
painéis fica em torno de 1,1–1,2 Gbps por lane). Com DSC o link cai
para 1,1 Gbps — exatamente a faixa em que o painel foi validado na
camada vendor.

## 4. O que isso implicou na série

O `0021` (`drm/panel: xiaomi m7`) preenche `dsi->dsc` antes do
`mipi_dsi_attach()`, com os valores do stock: slice 540×20, 2 slices
por linha (`slice_count = 1080/540`), 8 bpp, 8 bpc, block prediction.
Sem isso o host cairia no caminho sem DSC e pediria 295 MHz de
`byte_clk` — o painel não acenderia, e a PHY provavelmente nem
travaria o PLL.

Consequências que valem registrar:

1. **`qcom,compression-mode = "dsc"` não é decorativo.** Se um dia o
   painel for trocado por um driver que não configure `dsi->dsc`, o
   primeiro sintoma é `byte_clk` 60% acima do necessário.
2. **DFPS mexe no pclk.** O host recalcula
   `dsi_calc_clk_rate_v2()` a cada mudança de modo. O stock lista
   `<120 90 60>`; como `vtotal` muda com o porch (`dfps_immediate_porch_mode_vfp`),
   cada taxa tem seu pclk. O `0021` fixa 120 Hz hoje — DFPS é
   trabalho de Nível 1.
3. **`slice_per_pkt` é 1 no host.** O comentário em
   `dsi_update_dsc_timing()` é explícito:
   `pkt_per_line = slice_per_intf` (`slice_per_pkt` só é 1). O vendor
   declarava `qcom,mdss-dsc-slice-per-pkt = <2>`. A diferença muda o
   enquadramento dos pacotes DSI, não o stream DSC em si (os slices
   são justapostos), então é provável que funcione — mas **não está
   provado em hardware** e entra na lista de coisas a conferir no
   primeiro teste de painel, junto com o PPS regenerado.
4. **O `pps_selector` é o último argumento de
   `mipi_dsi_compression_mode_ext()`**, não `slice_per_pkt`. O `0021`
   passa `0` (PPS #0), que é o correto: o PPS é enviado antes, com
   `mipi_dsi_picture_parameter_set()`.

## 5. O que ainda não se sabe

- Se o painel aceita o PPS regenerado pelo `drm_dsc_pps_payload_pack()`
  bit a bit igual ao pacote 0x9e do vendor. O `0021` reconstrói o PPS
  a partir de `struct drm_dsc_config`, e os campos que o
  `drm_dsc_config` não modela (por exemplo os `rc_range_params` que o
  vendor manda explicitamente) precisam bater. O `0021` traz os
  valores do vendor em `rc_buf_thresh`/`rc_range_params`.
- Se `slice_per_pkt = 1` (host) com o painel programado para 2 gera
  imagem correta. Teste de hardware.
- O clock real que a PLL entrega: o mainline pede o `byte_clk`
  calculado, mas quem escolhe o VCO é o `dsi_phy_7nm.c`. Se a
  frequência pedida não for atingível com o `refgen` do SM6225, o
  `clk_set_rate()` arredonda e a taxa por lane muda.

Nada disso bloqueia o Nível 0 (o painel não é necessário para o kernel
chegar ao init); é material para o Nível 1.
