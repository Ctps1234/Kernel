# Ferramenta de empacotamento das imagens de boot (topaz/tapas, GKI 6.12)

Documento de referência da ferramenta [`tools/bootimg.py`](../tools/bootimg.py) e do
script [`tools/build_flash_images.sh`](../tools/build_flash_images.sh), que transformam
os artefatos do CI (kernel 6.12 + DTB/DTBO) em **imagens flasháveis** do aparelho,
preservando byte a byte tudo o que não muda (cmdline, bootconfig, ramdisk vendor,
rodapé AVB, padding).

> **Estado:** as três imagens foram geradas e validadas localmente
> (ida-e-volta byte a byte idêntica nos originais). **Nenhum flash foi feito** e
> **nada foi testado em hardware**.

---

## 1. Formatos (deduzidos dos binários reais, não do AOSP "de livro")

### 1.1 `boot` / `init_boot` — Android boot image v4 (little-endian)

| Offset | Tamanho | Campo |
|---|---|---|
| 0x00 | 8 | magic `ANDROID!` |
| 0x08 | 4 | `kernel_size` |
| 0x0c | 4 | `ramdisk_size` (0 no `boot` do aparelho) |
| 0x10 | 4 | `os_version` (0x220001a9) |
| 0x14 | 4 | `header_size` (1584) |
| 0x18 | 16 | `reserved[4]` |
| 0x28 | 4 | `header_version` (4) |
| 0x2c | 1536 | `cmdline` (**vazio** neste aparelho) |

Layout do arquivo: cabeçalho → kernel (offset 4096) → padding de página → resto da
partição (padding + rodapé AVB de 64 bytes, magic `AVBf` no fim).

**O cmdline não está no cabeçalho**: no Android 11+ ele vem da partição `bootconfig`,
que **não é tocada** por este fluxo — é por isso que o repack não precisa recriar
nenhum cmdline. (O `vendor_boot` carrega um cmdline próprio, também preservado.)

### 1.2 `vendor_boot` — Android vendor boot image v4 (little-endian, layout Qualcomm)

| Offset | Campo | Valor no aparelho |
|---|---|---|
| 0x00 | magic `VNDRBOOT` | — |
| 0x08 | `header_version` | 4 |
| 0x0c | `page_size` | 4096 |
| 0x18 | `vendor_ramdisk_size` | 15.019.760 |
| 0x1c | `cmdline[2048]` | `rcu_nocbs=all rcutree.enable_rcu_lazy=1 disable_dma32=on bootconfig buildvariant=userdebug` |
| 0x834 | `dtb_size` (tamanho da região DTB) | 1.305.239 |
| 0x844 | nº de entradas da tabela DTB | 1 |
| 0x84c | `bootconfig_size` | 85 |

A **região DTB** começa na primeira página depois do ramdisk vendor
(`align(page_size + vendor_ramdisk_size, page_size)` = 15.024.128) e contém **6 FDTs
contíguos**, sem padding entre eles:

| FDT | offset | tamanho | `compatible` | `qcom,msm-id` |
|---|---|---|---|---|
| 0 | 15.024.128 | 282.474 | `qcom,khaje` | 0x24a |
| **1** | **15.306.602** | **282.466** | `qcom,khaje` | **0x206 ← o do aparelho** |
| 2 | 15.589.068 | 264.262 | `qcom,khajeg` | 0x249 |
| 3 | 15.853.330 | 59.256 | `qcom,khajep-qrd` | 0x231 |
| 4 | 15.912.586 | 209.366 | `qcom,khajep` | 0x231 |
| 5 | 16.121.952 | 207.415 | `qcom,khajeq` | 0x232 |

O bootloader escolhe o FDT pelo `qcom,msm-id` do aparelho (`0x206`) → **FDT#1** é o que
precisa ser substituído. A base 6.12 que geramos (`khaje-idp-nopmi.dtb`) declara
`compatible = "qcom,khaje-idp", "qcom,khaje", "qcom,idp"` e
`qcom,msm-id = <0x206 0x10000 0x24a 0x10000>` (cobre os dois ids de Khaje).

### 1.3 `dtbo` — Android DTBO (header e entradas big-endian, layout Qualcomm/mkdtimg)

| Offset | Campo | Valor |
|---|---|---|
| 0x00 | magic | `0xd7b7ab1e` (bytes `d7 b7 ab 1e`) |
| 0x04 | `total_size` (little-endian) | 3.528.433 |
| 0x08 | `header_size` | 32 |
| 0x0c | `dt_entry_size` | 32 |
| 0x10 | `dt_entry_count` | 52 |
| 0x14 | `dt_entries_offset` | 32 |
| 0x18 | `page_size` | 4096 |

Cada entrada (32 bytes, **big-endian**): `dt_size`, `dt_offset`, `id`, `rev`,
`custom[4]`. Os 52 FDTs são contíguos a partir do offset 1.696. A **entrada 51** é o
overlay do topaz (offset 3.408.255, 121.458 bytes, SHA-256
`8a490755f0b4b520bea6a72321b4f035a203efb96f91f99851c5c26521384157` — confere com o
inventário).

---

## 2. O que a ferramenta faz

```
tools/bootimg.py inspect <imagem>            # estrutura da imagem
tools/bootimg.py roundtrip <in> <out>        # parse -> rebuild -> comparação
tools/bootimg.py set-kernel  --image in.img --kernel Image --out out.img
tools/bootimg.py set-dtb     --image in.img --index 1  --dtb base.dtb  --out out.img
tools/bootimg.py set-overlay --image in.img --index 51 --dtbo ov.dtbo  --out out.img
```

Sem dependências externas (só a biblioteca padrão do Python 3).

**Regras de segurança embutidas:**

- `set-kernel` mantém o tamanho da partição e **preserva o rodapé AVB** no fim
  (o conteúdo dele fica obsoleto — é o motivo de exigir verificação desabilitada);
  a `kernel_size` do cabeçalho é reescrita e conferida por SHA-256 do kernel embutido.
- `set-dtb` **não desloca nada**: o novo FDT é gravado no lugar do original, o
  resto é preenchido com zeros e o campo *total size* do FDT é reescrito para o
  tamanho original — assim a região DTB continua **contígua** e o bootloader
  percorre os 6 FDTs exatamente como antes.
- `set-overlay` reconstrói a imagem inteira (tabela + FDTs contíguos) e recalcula
  os offsets e o `total_size`, preservando o tamanho do arquivo e a cauda da partição.

---

## 3. Validação

**Ida-e-volta (parse → rebuild) sobre os três originais do aparelho:**

| Imagem | Resultado | SHA-256 (entrada = saída) |
|---|---|---|
| `boot_b.img` | **IDENTICA** | `6d86d08507aeb10b3c255366b73d33147f46b7879eb0d7bd7f4926547b562d6e` |
| `vendor_boot_b.img` | **IDENTICA** | `1e5bef747311bce352acb6e778afc256d9a01d59351b2070836f4e96575eb502` |
| `dtbo_b.img` | **IDENTICA** | `a1be5f733acf4077c174eb2046ac25db67e605855b3ecbb19296df3b48c09138` |

Ou seja: os três formatos estão entendidos o bastante para reescrever qualquer campo
sem corromper o resto.

**Imagens geradas (a partir do `Image-khaje` e dos DTBs do CI, run `39026267325`):**

| Artefato | Tamanho | SHA-256 |
|---|---|---|
| `google_drive/out/boot_b-khaje-6.12.img` | 134.217.728 | `ac3dce59069ceab3e787a8295a38339f679f4a29e933ce9c006c7be54a24655d` |
| `google_drive/out/vendor_boot_b-khaje-6.12.img` | 100.663.296 | `4fc0bc9acdb3ff63b16c76249d7882f0876e5c69c31240787c6d48ed7bc77aca` |
| `google_drive/out/dtbo_b-khaje-6.12.img` | 25.165.824 | `4be8b75a771548e6ff30e49e25cf8a9b715412c9551f2abc9cb37e7eb33e8821` |

Kernel embutido conferido: SHA-256 `b2965890137decf4a87d8e0eedde1e8a501d3852fe687349715619f51f161efd`
= `Image-khaje` do CI.

> Essas imagens ficam fora do Git (`google_drive/` está no `.gitignore`): são
> artefatos grandes e privados do aparelho.

---

## 4. O que falta antes do primeiro flash

1. **Bootloader desbloqueado** — sem isso nada é gravável; o estado atual é desconhecido.
2. **AVB** — as imagens não são assinadas. O fluxo usual é flashar um `vbmeta` com
   `--disable-verity --disable-verification` antes de `boot`/`vendor_boot`/`dtbo`.
3. **Backups verificados** de `boot_b`, `init_boot_b`, `vendor_boot_b`, `dtbo`,
   `vbmeta_b` e **`recovery_b` (nunca extraída)**.
4. **`init_boot` mínima** — a ramdisk genérica do aparelho tenta montar `/system`
   (partições dinâmicas, `msm_partition` inexistente na base 6.12) e não sobe.
   Para o marco "boot mínimo" é preciso um `init_boot` próprio (init estático) —
   é o próximo item de trabalho.
5. **Riscos conhecidos do primeiro boot:** a tela permanece escura (sem DSI/painéis
   vendor na base 6.12) e o framework gráfico não sobe; o objetivo do marco é o
   **console serial** e o `dmesg` do kernel.
