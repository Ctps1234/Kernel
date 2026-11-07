# Ferramenta de empacotamento das imagens de boot (topaz/tapas, GKI 6.12)

Documento de referência da ferramenta [`tools/bootimg.py`](../tools/bootimg.py) e do
script [`tools/build_flash_images.sh`](../tools/build_flash_images.sh), que transformam
os artefatos do CI (kernel 6.12 + DTB/DTBO + ramdisk mínima) em **imagens flasháveis** do aparelho.
Headers, cmdline, bootconfig e ramdisk vendor são preservados; os blocos AVB/vbmeta
são reposicionados/ajustados estruturalmente quando necessário, mas seus digests
ficam obsoletos. Padding liberado pelo DTBO é zerado.

> **Estado:** as quatro imagens foram geradas e verificadas estaticamente.
> Os quatro originais passam na ida-e-volta byte a byte. CI de initramfs
> `39040529561` e CI kernel/DTS `39040529520` estão verdes. **Nenhum flash foi feito**
> e **nada foi testado em hardware**.

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

No `boot_b` deste aparelho, `kernel_size=43.379.200`, `ramdisk_size=0` e o campo
`cmdline` do header está vazio. No `init_boot_b`, `kernel_size=0` e a ramdisk original
tem 2.888.965 bytes, comprimida em LZ4 legado; o novo `init_boot` usa CPIO `newc`
não comprimido, aceito pelo initramfs do kernel. O cmdline ativo vem de
`chosen.bootargs` no DTB e do cmdline próprio de `vendor_boot` (ambos preservados).

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
| 0x04 | `total_size` (big-endian) | 3.529.713 |
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
tools/bootimg.py set-ramdisk --image init_boot.img --ramdisk initramfs.cpio --out out.img
tools/bootimg.py set-dtb     --image in.img --index 1  --dtb base.dtb  --out out.img
tools/bootimg.py set-overlay --image in.img --index 51 --dtbo ov.dtbo  --out out.img
```

Sem dependências externas (só a biblioteca padrão do Python 3).

**Regras de segurança embutidas:**

- `set-kernel` mantém o tamanho da partição, reescreve `kernel_size`, move o blob
  vbmeta para depois do novo conteúdo e atualiza `original_image_size`/`vbmeta_offset`
  no rodapé AVB de 64 bytes. O digest/assinatura do vbmeta continua obsoleto; a
  imagem exige verificação AVB desabilitada. O kernel embutido é conferido por SHA-256.
- `set-ramdisk` mantém o tamanho da partição `init_boot` (8 MiB), altera `ramdisk_size`
  e os bytes da ramdisk, preserva os campos do header, e atualiza os offsets AVB
  da mesma forma. O digest/assinatura continua obsoleto.
- `set-dtb` **não desloca nada**: o novo FDT é gravado no lugar do original, o
  resto é preenchido com zeros e o campo *total size* do FDT é reescrito para o
  tamanho original — assim a região DTB continua **contígua** e o bootloader
  percorre os 6 FDTs exatamente como antes.
- `set-overlay` reconstrói a imagem inteira (tabela + FDTs contíguos) e recalcula
  os offsets e o `total_size`. Mantém o tamanho da partição, zera o espaço liberado,
  conserva o vbmeta no offset absoluto original e atualiza `original_image_size` no
  rodapé AVB. O digest assinado continua obsoleto; verificação AVB desabilitada.

---

## 3. Validação

**Ida-e-volta (parse → rebuild) sobre os quatro originais do aparelho:**

| Imagem | Resultado | SHA-256 (entrada = saída) |
|---|---|---|
| `boot_b.img` | **IDENTICA** | `6d86d08507aeb10b3c255366b73d33147f46b7879eb0d7bd7f4926547b562d6e` |
| `vendor_boot_b.img` | **IDENTICA** | `1e5bef747311bce352acb6e778afc256d9a01d59351b2070836f4e96575eb502` |
| `dtbo_b.img` | **IDENTICA** | `a1be5f733acf4077c174eb2046ac25db67e605855b3ecbb19296df3b48c09138` |
| `init_boot_b.img` | **IDENTICA** | `b2f2704ab3ddf53d71aa87e19ad74c279bb3e6194c6ebae33c587d31430085a4` |

Ou seja: os formatos estão entendidos o bastante para reescrever qualquer campo
sem corromper o resto.

**Imagens geradas com `Image-khaje`/DTBs do CI `39040529520` e ramdisk do CI `39040529561`:**

| Artefato | Tamanho | SHA-256 |
|---|---:|---|
| `google_drive/out/boot_b-khaje-6.12.img` | 134.217.728 | `bf2ce4d48bf75e12e86c66a7e9e9f29015837502b165dc8cc0421d60e6828888` |
| `google_drive/out/vendor_boot_b-khaje-6.12.img` | 100.663.296 | `4fc0bc9acdb3ff63b16c76249d7882f0876e5c69c31240787c6d48ed7bc77aca` |
| `google_drive/out/dtbo_b-khaje-6.12.img` | 25.165.824 | `69ffc6cb273ebc026d65e1db9e38549a8bfe4b77a79409f0bbf2632509b7ea9a` |
| `google_drive/out/init_boot_b-khaje-minimal.img` | 8.388.608 | `612eb196456fc21f3754d51e38535814ae4f1887640b1c18864b7646877e805d` |

Kernel embutido conferido: SHA-256 `1df8c5be8b208a89f27deae084d13110999103b645a28827543a961fe6540232`
= `Image-khaje` do CI. A ramdisk embutida em `init_boot` confere byte a byte com
`ci-artifacts/initramfs/initramfs.cpio` (2.879.092 bytes, SHA-256
`948984f26e6fec5a1438844dd055fc7b86c672ed86e7df09093cacc6e066d2bf`).

Regenerar (com os originais em `google_drive/` e a árvore de artefatos do CI
extraída, por exemplo, do branch `ci-artifacts`):

```sh
tools/build_flash_images.sh /path/to/Kernel-ci-artifacts
```

> As imagens e os blobs originais ficam fora do Git (`google_drive/` está no
> `.gitignore`): são artefatos grandes e privados do aparelho.

---

## 4. Ramdisk mínima e pré-requisitos de flash

### Conteúdo da ramdisk mínima

`initramfs/minimal-init.c` é compilado estaticamente para AArch64; o CI fixa BusyBox
1.36.1 no commit `1a64f6a20aaf6ea4dbba68bbfa8cc1ab7e5c57c4`, também estático. O
`tools/initramfs.py` monta um CPIO `newc` não comprimido para o `init_boot`. O
`tools/check_initramfs.py` valida o formato, o ELF AArch64 sem `PT_INTERP`, os links
de applets e os nós de console (`/dev/console` char 5:1 e `/dev/null` char 1:3).

Ao iniciar, o `/init` redireciona os descritores para `/dev/console`, monta procfs,
sysfs, devtmpfs e tmpfs, imprime kernel/cmdline/modelo do DT, monta debugfs/tracefs
e abre um shell BusyBox. **Não inclui `adbd`**: o acesso pretendido nesta fase é pelo
console serial, não por ADB. A configuração efetiva do CI inclui
`CONFIG_BINFMT_ELF=y`, `CONFIG_BLK_DEV_INITRD=y`, `CONFIG_DEVTMPFS=y`,
`CONFIG_SERIAL_MSM_CONSOLE=y` e `CONFIG_SERIAL_QCOM_GENI_CONSOLE=y`; o DTB base traz
`console=ttyMSM0,115200n8` em `chosen.bootargs`.

O builder preserva os 8 MiB da partição, move o blob vbmeta e atualiza os offsets
no rodapé AVB; o digest/assinatura, porém, é obsoleto após a alteração. A ramdisk
original permanece em `google_drive/init_boot_b.img` (fora do Git).

### Bloqueios antes de gravar qualquer partição

1. **Não flashar ainda.** Nenhuma imagem foi testada no aparelho; isto é uma
   preparação estática/verificável, não um teste de boot.
2. **Bootloader desbloqueado** — estado desconhecido; sem isso nada é gravável.
3. **AVB** — as imagens custom não são assinadas. É necessário planejar o bypass
   coerente para `vbmeta`/`vbmeta_system`, sem assumir que uma opção `fastboot`
   isolada basta para todos os slots.
4. **Backups verificados** de `boot_b`, `init_boot_b`, `vendor_boot_b`, `dtbo_b`,
   `vbmeta_b`, `vbmeta_system_b` e **`recovery_b` (nunca extraída)**, mais um
   caminho de recuperação testado. A imagem `vbmeta` original não foi alterada.
5. **Limite funcional:** sem DSI/painéis vendor, a tela pode permanecer escura e o
   framework gráfico não sobe. O objetivo B2 é apenas chegar ao console serial e
   obter `dmesg`; não há ADB nesta ramdisk.

As imagens permanecem privadas em `google_drive/out/` (gitignored). O script
`tools/build_flash_images.sh` só gera arquivos locais; ele **não** escreve em
`/dev/block` nem executa `fastboot`.


## Atualização 2026-11-04 — trilha 6.18 (Lunaris)

- `bootimg.py` ganhou o subcomando `set-bootconfig --key --value`
  (reescreve uma chave do bootconfig do `vendor_boot` no lugar,
  ajustando o tamanho no cabeçalho). No repack 6.18 ele alinha
  `androidboot.usbcontroller` para `4e00000.usb` (o core DWC3
  mainline chama-se `usb@4e00000` por imposição do schema
  `snps,dwc3.yaml`).
- `tools/verify_series.sh` aplica a série inteira sobre a base fixada
  num clone esparso (`--depth 1 --filter=blob:none`, só os 139
  arquivos tocados) com `git am --keep-cr`. É o gate `rebase-cost` do
  CI rodando local, em ~80 s — necessário porque o token do agente
  não tem `workflow_dispatch` e o build completo não cabe no sandbox
  (2 núcleos).
- `tools/fdt_dump.py` decompila um dtb para DTS (substitui o `dtc`,
  que o sandbox não tem) e `tools/fdt_overlay_dump.py` faz o mesmo com
  um dtbo **resolvendo os phandles por nome** via `__fixups__` +
  `__symbols__` do DT base. Foi com eles que o DT stock do topaz
  virou texto legível.
- `tools/fdt_compare.py` compara dois FDTs/overlays **por significado**:
  chaveia fragmentos pelo alvo (nunca pelo número), descarta
  `phandle`/`linux,phandle` e reconcilia as células que ainda diferem
  resolvendo cada lado para o nome do nó apontado. Existe porque
  `diff` de DTS entre builds distintos acusa centenas de diferenças
  que são só ordem de alocação. Exemplo real: o dtbo do aparelho e o
  do repo `xiaomi-6225-AD` têm 50 fragmentos idênticos e 7 bytes de
  diferença de tamanho — `fdt_compare.py` devolve `IGUAIS`;
  `--verboso` mostra os phandles renumerados um por um.
- `tools/audit_dts_pairs.py` checa os pares "*-names / lista" nos DTS
  (`clocks`/`clock-names`, `interrupts`/`interrupt-names`,
  `reg`/`reg-names`, `dmas`/`dma-names`, `power-domains`/nomes,
  `pinctrl-N`). É uma classe de erro que `dtbs_check` não pega: cada
  propriedade é válida sozinha, mas o driver pede um clock pelo nome e
  recebe outro (ou nenhum) — `probe` falha com `-ENOENT` ou o hardware
  roda com o clock errado.
- `tools/audit_compatibles.py` cruza os `compatible` dos drivers da
  série com os nós do DTS: driver que nenhum nó instancia, e entrada de
  tabela indexada pela **raiz** da árvore (`of_machine_get_match_data`,
  `soc_device_match`) que não casa com o `compatible` do DTS. A segunda
  checagem nasceu de um quase-erro: a tabela de UBWC é consultada pelo
  compatible da raiz (`qcom,sm6225`), não pelo do bloco
  (`qcom,khaje-dpu`).
- `tools/check_all.sh` roda a bateria local inteira em sequencia:
  `patch_lint` (0,2 s), `verify_series` (~80 s), `audit_dts_pairs`,
  `audit_compatibles` na árvore recém-aplicada e `audit_regulators`
  contra o FDT do aparelho. Sai 0 só' se os cinco passarem e imprime o
  caminho da árvore preservada. É o que dá para checar sem CI: build e
  `dtbs_check` continuam dependendo da run. `--sem-verify` pula a
  aplicação (usa o `audit_regulators` isolado quando se mexeu só' em
  valor de tensão).
- `tools/patch_lint.py` recomputa as contagens de cada `@@` e compara
  com o corpo do hunk. Editar patch à mão (somar uma linha `+` e
  esquecer o `+N`) é a falha mais fácil de cometer e a mais chata de
  diagnosticar, porque o `git am` só reclama no meio da série, longe
  do patch culpado. Roda em ~0,2 s, sem rede e sem árvore de kernel.
- `tools/audit_regulators.py` confere `min/init/max` de cada rail
  RPM-SMD da série contra o FDT do aparelho. Não é cosmético: o PHY
  USB (`phy-qcom-snps-femto-v2`), o codec e o BT só fazem
  enable/disable de regulador, então o `qcom,init-voltage` é a tensão
  que o hardware recebe de fato. A primeira rodada achou cinco rails
  com valores vindos do `bengal-regulator`, não do Khaje (inclusive
  `vdda18` do PHY USB em 1,62 V e `vdda33` em 2,92 V). Ver
  [`regulator-audit.md`](regulator-audit.md).
- `tools/fdt_inject_ids.py` injeta `qcom,msm-id`/`qcom,board-id`
  (copiados do FDT stock) na raiz do DTB compilado — é por essas
  props que o ABL seleciona o FDT base na região multi-FDT; o DTB
  mainline não as tem (e não deve ter). A cirurgia é mínima e
  verificada nó a nó contra o FDT original.
- `tools/empty_overlay.py` neutraliza uma entrada do dtbo com um FDT
  mínimo que preserva só as props da raiz (model/compatible/
  `qcom,msm-id`/`qcom,board-id`/`qcom,pmic-id`) e nenhum fragmento:
  aplicar o overlay downstream sobre o DTB mainline não é possível.
- `tools/build_flash_images_618.sh` é o pipeline atual: parte dos
  dumps da Lunaris (`google_drive/dump-lineage/`) e dos artefatos do
  CI 6.18, gera `google_drive/out-618/*-618.img` com roundtrip dos
  originais antes. O `init_boot` é mantido idêntico (Nível 0 Android
  usa a ramdisk genérica da ROM). Nada grava em partições.
- **Estado das imagens prontas (2026-11-06).** O `out-618/` que foi
  para o Drive saiu do `Image`/`sm6225-xiaomi-topaz.dtb` da última run
  de CI verde. Depois disso a série mudou em **poucas linhas de DTS**
  (card-detect do microSD no `0070`/`0071`, `orientation` da câmera
  frontal no `0057` e `output-high` no estado do AVDD do touch no
  `0053`), então o DTB dessas imagens está um pouco atrás do
  `patches-6.18/` atual. Nenhuma das duas muda o caminho de boot:
  card-detect só importa com cartão inserido, e `orientation` não é
  lida por driver nenhum (é descritor para userspace). O sandbox não
  compila DTB (`dtc` indisponível, seção 3), então o DTB só é refeito
  numa run de CI verde — as imagens atuais continuam válidas para o
  teste de Nível 0, e o `dtb` precisa ser regenerado antes de qualquer
  teste de câmera ou de slot de cartão.
- **Como pegar `Image`/DTB do CI sem o zip (2026-11-06).** O zip dos
  artefatos do Actions mora em
  `productionresultssa*.blob.core.windows.net`, que este sandbox não
  alcança: a API responde `302` e o download morre com `EOF`. O
  `github.com`, esse responde — então o job de build publica `Image`,
  `sm6225-xiaomi-topaz.dtb`, `.config`, os logs e um arquivo `RUN` no
  branch **`ci-artifacts-6.18`** (push forçado, mesmo padrão do
  workflow 6.12; cada run substitui o conteúdo para não empilhar 30 MB
  de `Image` por rodada no histórico). Do sandbox:
  `tools/fetch_ci_artifacts.sh` clona o branch para
  `ci-artifacts-618/`, que é justamente o diretório default do
  `build_flash_images_618.sh` — o pipeline de imagens volta a rodar
  inteiro aqui.
  Existe também um canal menor, de reserva, para quando só' o DTB
  interessa: `tools/ci_publish_dtb.sh` publica o DTB em base64 na
  issue de relatório e `tools/fetch_dtb.py` junta as partes conferindo
  o sha256.
  Nenhum dos dois foi exercitado de ponta a ponta ainda — o primeiro
  teste real é a próxima run que chegar ao build.
- Artefatos de build ficam fora do Git: `google_drive/` (dumps e
  `out-618/`) e `out-618/` na raiz já estão no ignore.
