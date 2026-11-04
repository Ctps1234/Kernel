# Inventário de partições de boot — topaz/tapas

## Captura recebida

> **Atualização (2026-11-03):** o usuário reportou ter migrado a ROM
> para **AOSP Android 16 compilada para o topaz (userdebug)**. As
> capturas abaixo são do estado anterior
> e continuam válidas para o layout de partições e os formatos das
> imagens; o sistema em execução atual não é mais o descrito aqui. O
> vendor permanece o stock da Xiaomi (base Android 15), que é a
> camada relevante para as HALs.
>
> **Correção (2026-11-04):** a ROM AOSP atual é **Lunaris OS** (não
> LineageOS). Foram solicitados dumps novos de `boot`/`vendor_boot`/
> `dtbo`/`init_boot`/`vbmeta`/`recovery` do slot ativo da Lunaris,
> para análise e repack das imagens de teste 6.18.

- Slot reportado por `ro.boot.slot_suffix`: `_b` (slot ativo durante a captura).
- Sistema/ROM em execução: Android 17, API 37; vendor/base Android 15, conforme esclarecimento do usuário.
- Fingerprint recebido: `Redmi/topaz_global/topaz:15/AQ3A.240829.003/OS2.0.204.0.VMGMIXM:user/release-keys`. O usuário esclareceu que o `:15` corresponde ao vendor Android 15, não ao sistema Android 17.
- As partições A/B foram listadas em `/dev/block/by-name` e `/dev/block/bootdevice/by-name` (ambos apontam para os mesmos nós).

## Partições observadas

| Partição | Slot A | Slot B (ativo) |
|---|---|---|
| `boot` | `/dev/block/sde11` | `/dev/block/sde35` |
| `dtbo` | `/dev/block/sde17` | `/dev/block/sde41` |
| `init_boot` | `/dev/block/sde22` | `/dev/block/sde48` |
| `recovery` | `/dev/block/sde23` | `/dev/block/sde46` |
| `vbmeta` | `/dev/block/sde16` | `/dev/block/sde40` |
| `vbmeta_system` | `/dev/block/sda10` | `/dev/block/sda11` |
| `vendor_boot` | `/dev/block/sde24` | `/dev/block/sde47` |

## Imagens recebidas pelo Drive

Foram localizados cinco dumps do slot ativo:

| Arquivo | Tamanho | Resultado inicial |
|---|---:|---|
| `boot_b.img` | 134.217.728 bytes (128 MiB) | Cópia gzipada baixada (`boot_b.img.gz`, 21.076.277 bytes; gzip integrity check OK). Android boot v4; kernel de 43.379.200 bytes; ramdisk size zero; header de 1.584 bytes. Binário contém marcadores de Clang 20.0.0 e da release `5.15.211dexter1-g42deba085a84`, coerentes com o kernel reportado em execução. |
| `vendor_boot_b.img` | 100.663.296 bytes (96 MiB) | Header Android vendor boot v4; página de 4096 bytes; ramdisk vendor de 15.019.760 bytes; região DTB de 1.305.239 bytes; tabela com uma entrada; bootconfig de 85 bytes. |
| `init_boot_b.img` | 8.388.608 bytes (8 MiB) | Header Android boot v4; kernel size zero (esperado para init_boot); ramdisk genérico de 2.888.965 bytes. |
| `dtbo_b.img` | 25.165.824 bytes (24 MiB) | Tabela DTBO v0 com 52 entradas; `total_size` big-endian = 3.529.713 bytes, magic/entradas também big-endian. |
| `vbmeta_b.img` | 65.536 bytes | Imagem AVB; magic `AVB0`. |

As imagens usadas no repack (`boot_b`, `vendor_boot_b`, `init_boot_b`, `dtbo_b`) foram baixadas para `google_drive/`; os originais continuam no Drive. `vbmeta_b` não foi alterada. Os dumps e imagens derivadas são privados e não devem ser adicionados ao Git; `google_drive/` inteiro está ignorado em `.gitignore`.

## Correspondência DTB/DTBO específica de topaz

- A região DTB do `vendor_boot` começa no offset `15.024.128` e contém seis FDTs v17 contíguos. A base índice 1 começa no offset `15.306.602`, tem 282.466 bytes, `model = "Qualcomm Technologies, Inc. Khaje SoC"` e `qcom,msm-id = <0x206 0x10000>`; SHA-256 do FDT extraído: `71cd1e4abd22df5fed75ab23408eae05aa7bf9783635051858dc73205ba8664c`.
- O `dtbo` contém 52 entradas. A entrada 51 fica no offset `3.408.255`, tem 121.458 bytes e identifica `KHAJE IDP nopmi topaz`, com `qcom,msm-id = <0x206 0x10000>` e `qcom,board-id = <0x30022 0>`; SHA-256 do FDT extraído: `8a490755f0b4b520bea6a72321b4f035a203efb96f91f99851c5c26521384157`. A entrada 50 é a variante MSM `0x24a`.
- Esses IDs correspondem ao FDT ativo: `Qualcomm Technologies, Inc. KHAJE IDP nopmi topaz`, `compatible = qcom,khaje-idp, qcom,khaje, qcom,idp`, MSM ID `0x206` e board ID `0x30022`. A seleção base índice 1 + overlay 51 está identificada com boa confiança. O script `tools/extract_android_dt.py` reproduz a correspondência e pode gravar os dois blobs em `/tmp` para inspeção.

## Uso no bring-up e próximo dado

`boot`, `init_boot` e `vendor_boot` definem o formato e os ramdisks; `vendor_boot`/`dtbo` fornecem a base de DTB e o overlay correspondente; `vbmeta` informa o arranjo AVB. Manter cópias externas e verificáveis dos originais antes de qualquer teste é requisito de segurança. Preservar também `recovery_b` para recuperação.

A coleta necessária para entender o pacote de boot está completa: `boot_b` tem apenas o kernel, o ramdisk genérico está em `init_boot`, e o ramdisk vendor + DTBs estão em `vendor_boot`. Para segurança, manter também uma cópia externa e verificada de `recovery_b` antes de qualquer teste; ela não foi incluída na análise enviada. Não gravar nenhum arquivo de volta nas partições.

## Reempacotamento e ramdisk de bring-up

A ferramenta [`tools/bootimg.py`](../tools/bootimg.py), documentada em
[`docs/boot-image-tooling.md`](boot-image-tooling.md), valida os formatos por
ida-e-volta byte a byte nos quatro originais (`boot`, `vendor_boot`, `dtbo`,
`init_boot`). O script `tools/build_flash_images.sh` gera os arquivos em
`google_drive/out/` somente; não executa `fastboot` nem escreve em partições.

A ramdisk original de `init_boot` é LZ4 legado contendo CPIO `newc` (2.888.965
bytes comprimidos; 5.443.072 bytes após descompressão), com `/init` Android e
`system/bin/snapuserd`, mas sem `adbd`. A ramdisk de `vendor_boot` contém
`first_stage_ramdisk/fstab.qcom` e módulos vendor 5.15, não um segundo `/init`.
A fase de boot mínimo substitui só a ramdisk genérica de `init_boot` por um CPIO
não comprimido com init estático + BusyBox; não tenta carregar os módulos 5.15 e
não fornece ADB. O objetivo imediato é o console serial (`ttyMSM0`) e `dmesg`.

SHA-256 do `init_boot_b.img` original: `b2f2704ab3ddf53d71aa87e19ad74c279bb3e6194c6ebae33c587d31430085a4`.
O artefato mínimo derivado e o resultado final de empacotamento estão registrados
em `docs/boot-image-tooling.md` após o build do CI. Nada foi gravado ou testado no
aparelho.


## Captura 2026-11-04 (Lunaris OS)

Nova extração feita pelo usuário com `dd` **somente-leitura** a partir
de `/dev/block/by-name` (Termux com root), slot ativo `_b`
(`ro.boot.slot_suffix`), já com a Lunaris OS instalada. Arquivos em
`google_drive/dump-lineage/` (gitignored), integridade conferida por
`SHA256SUMS` (7/7 OK). Com isto, **o backup de `recovery_b` que
faltava está obtido**.

| Imagem | Bytes | Notas |
|---|---:|---|
| `boot_b.img` | 134.217.728 | v4, só kernel (43.379.200), ramdisk 0, cmdline vazio |
| `vendor_boot_b.img` | 100.663.296 | v4, ramdisk vendor 15.019.748 + região DTB 1.305.239 |
| `dtbo_b.img` | 25.165.824 | 52 entradas, total útil 3.529.713 |
| `init_boot_b.img` | 8.388.608 | v4, ramdisk genérica 3.214.821 |
| `vbmeta_b.img` | 65.536 | **flags = 3** (verificação e hashtree desligadas) |
| `vbmeta_system_b.img` | 65.536 | flags = 0 (irrelevante com o topo desligado) |
| `recovery_b.img` | 104.857.600 | backup de segurança, sem dissecação |

Achados que mudam/confirmam o quadro:

- **Kernel da ROM**: `Linux version 5.15.211dexter1-g42deba085a84
  (DexterMorgan@GitHub) ... clang` — downstream customizado, do
  **mesmo tamanho** (43.379.200) do kernel da captura de 2026-10:
  o aparelho já rodava este kernel na época da HyperOS.
- **Pacote DT idêntico ao stock**: SHA-256 do FDT#1
  (`71cd1e4a…`) e da entrada 51 do dtbo (`8a490755…`) **iguais** aos
  da captura anterior — a Lunaris não toca em DTB/DTBO. A estratégia
  de repack (nosso DTB no FDT#1, overlay 51 neutralizado) se aplica
  sem ajustes.
- **vendor_boot**: ramdisk vendor LZ4 legado (cpio de 41.203.200 B,
  271 entradas, 258 `.ko`, `modules.load` com 86 módulos de 1º
  estágio); região DTB em 15.024.128 com os mesmos 6 FDTs; tabela de
  ramdisks (108 B) em 16.330.752; **bootconfig de 85 bytes em
  16.334.848** com apenas 3 linhas (`androidboot.hardware=qcom`,
  `androidboot.memcg=1`, `androidboot.usbcontroller=4e00000.dwc3`),
  sem trailer `#BOOTCONFIG` na imagem (quem monta o blob final é o
  bootloader, como mostra o `/proc/bootconfig` vivo com
  `bootdevice=4804000.ufshc`, `dtb_idx=1`, `dtbo_idx=51`).
- **Validação da ferramenta**: `tools/bootimg.py roundtrip` reproduz
  as 4 imagens desta captura **byte a byte**.

Nada foi gravado de volta; nenhuma autorização de flash existe.
