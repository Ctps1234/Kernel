# Cruzamento: nossa série 6.18 × device tree LineageOS (AOSP 16) do tapas/topaz

Registro de 2026-11-03. O usuário roda hoje uma ROM **AOSP Android 16
compilada para o topaz (userdebug)** e forneceu a device tree:
`SM6225-Android-Playground/android_device_xiaomi_tapas` — árvore
LineageOS unificada tapas/topaz. Este documento cruza o contrato
kernel↔userspace dessa árvore com a nossa série `patches-6.18/` e
atualiza o checklist do primeiro boot Android (Nível 0). Nada aqui foi
testado em hardware; é análise estática das fontes públicas da ROM.

> **Correção (2026-11-04):** a ROM instalada no aparelho do usuário é
> **Lunaris OS** (derivada AOSP), não LineageOS. O cruzamento abaixo foi
> construído sobre a device tree LineageOS pública do tapas/topaz, que
> segue como referência estrutural (as árvores AOSP destes aparelhos
> derivam dela), mas os fatos da instância real — kernel prebuilt,
> bootconfig, cmdline, flags do vbmeta, ramdisk do vendor_boot — serão
> confirmados a partir dos dumps das partições de boot da Lunaris
> extraídos do aparelho, e as linhas afetadas serão atualizadas.

## O que a ROM é (fatos da árvore)

- LineageOS (Android 16), `lineage_tapas`, unificada tapas/topaz.
- **Kernel prebuilt downstream 5.15** (`TARGET_FORCE_PREBUILT_KERNEL`,
  módulos em `vendor_ramdisk`/`system_dlkm`/`vendor_dlkm`, caminho
  `lib/modules/5.15.94`). Ou seja: a ROM espera o kernel vendor; o
  nosso 6.18 entra no lugar da `Image` + DTB, e toda a árvore de
  módulos dela vira peso morto (não carrega, por desenho nosso).
- **Vendor construído** a partir de 1.343 blobs extraídos da HyperOS
  Android 15 (OS2.0.205) + HALs Lineage/QTI. Não é a partição vendor
  stock intocada, mas as HALs de baixo nível continuam as downstream.
- **AVB já resolvido**: `BOARD_AVB_ENABLE` com `--flags 3`
  (verificação e hashtree desativadas) e testkeys. Trocar
  boot/vendor_boot/dtbo não briga com AVB neste setup — um dos
  bloqueadores antigos cai.

## Contrato extraído × nossa série

| Item | Expectativa da ROM (fonte) | Nossa série 6.18 | Ação |
|---|---|---|---|
| Partições no 1º estágio | `fstab.qcom` usa `/dev/block/by-name/*`, `/dev/block/bootdevice/by-name/*` e dinâmicas via liblp/dm-linear | UFS+FS+dm embutidos | Provavelmente **dispensa o `msm_partition`** (by-name vem de PARTNAME + bootdevice do bootconfig). Validar no boot; o bloqueador da análise 6.12 pode estar superado |
| `/data` | F2FS + `fileencryption=...+wrappedkey_v0`, `metadata_encryption=...wrappedkey_v0`, inlinecrypt | Sem `qseecom`/KeyMint TEE | ❌ `/data` atual não monta. Nível 0 realista: formatar sem wrappedkey (mexe no fstab do vendor **da ROM**) ou portar qseecom |
| Firmware de DSPs/modem | **Um** diretório: `firmware_directories /vendor/firmware_mnt/image/` (ueventd); zap stock é `a610_zap.mdt` (+`.bXX`) | DT pede `qcom/sm6225/xiaomi/topaz/...`; ADSP como `.mbn` | Ajustar `firmware-name` p/ nomes "pelados": `modem.mdt`, `adsp.mdt`, `cdsp.mdt`, `a610_zap.mdt` (**patch 0093**) |
| USB gadget | bootconfig `androidboot.usbcontroller=4e00000.dwc3` | Core nomeado `usb@4e00000` → device `4e00000.usb` | Renomear não fecha: `snps,dwc3.yaml` exige `$nodename: ^usb` (tentativa reprovou no CI `41746297645`). Alinhar **no repack**: bootconfig do `vendor_boot` de teste vira `androidboot.usbcontroller=4e00000.usb` (como nos ports Android mainline) |
| microSD (vold) | caminho `soc/4784000.sdhci/mmc_host*` | Nó `mmc@4784000` → `4784000.mmc` | Renomear p/ `sdhci@4784000` ou ajustar fstab no repack (não bloqueia boot) |
| Display/GPU | SDM composer + mapper QTI + blobs Adreno (KGSL `/dev/kgsl-3d0`) | DRM/MSM + DPU upstream | ❌ incompatível; Nível 1 exige drm_hwcomposer + Mesa no lugar (vendor da ROM trocado) |
| Câmera | Provider CamX 2.4 + ~370 blobs | CAMSS upstream | ❌ caminho é libcamera |
| Áudio | AGM/PAL HIDL (AudioReach vendor) | q6apm/ASoC upstream | ⚠️ mesma família (AudioReach), interfaces divergem; trabalho médio |
| Wi‑Fi | `qcwcn`/QCACLD (`/dev/wlan`) | ath10k nl80211 | ❌ HAL Wi‑Fi da ROM é p/ QCACLD; usar HAL genérica AOSP |
| BT | Stack QTI (smd/rfkill/`hci_uart` downstream) | hci_uart serdev upstream | ⚠️ HAL nova sobre HCI do kernel |
| **IR blaster** | `android.hardware.ir-service.example` (HAL AOSP sobre LIRC) | `ir-spi-led` → `/dev/lirc0` | ✅ **compatível por desenho**; provável primeiro periférico funcional |
| NFC | `android.hardware.nfc@1.2-service.st` (`/dev/st21nfc`) | st-nci (netlink NCI) | ❌ trocar pela HAL NCI AOSP |
| Touch | input genérico (+ idc/keylayout da árvore) | edt-ft5x06/FT3519T | ✅ compatível |
| Fingerprint | Serviço Xiaomi + TEE | — | ❌ sem `qseecom` |
| Bateria/saúde | `/sys/class/qcom-battery/*`, health QTI | Sem charger/FG PM6125 upstream | ❌ até existir driver; PMIC carrega autônomo no default |
| Térmica/vibração | `thermal-service.qti`, vibrator QTI (QPNP) | tsens; sem haptics | ⚠️ degrada; não bloqueia boot |
| Sensores | SSC via ADSP (adsprpc downstream) | fastrpc upstream existe na ACK | ⚠️ incerto; depende de compat de ioctl/userspace |

## Checklist Nível 0 (kernel → init Android), atualizado

1. ~~AVB~~ — resolvido pela própria ROM (`--flags 3`).
2. Gerar as 4 imagens 6.18 com `tools/bootimg.py` a partir das
   imagens **desta ROM** (não mais das stock): `boot` (Image),
   `vendor_boot` (FDT 0x206 + bootconfig corrigido se preciso),
   `dtbo` neutro, `vbmeta` como está.
3. ~~Auditar `modules.load` do vendor ramdisk **desta ROM**~~ —
   **feito (2026-11-03)**, fontes em
   `SM6225-Android-Playground/android_device_xiaomi_tapas-kernel`.
   O `modules/vendor_ramdisk/modules.load` (1º estágio) lista
   ~85 módulos; todos os que estão no caminho de montagem têm
   equivalente **built-in** na nossa série: `ufs_qcom` +
   `phy-qcom-ufs*`, `pinctrl-khaje`, `gcc-khaje`/`clk-smd-rpm`,
   `qnoc-bengal`, `rpm-smd(-regulator)`, `spmi-pmic-arb` +
   `qcom-spmi-pmic`, `arm_smmu`, `qcom-mpm`, `qcom-scm`, `qrtr`.
   O restante é logging/minidump/memshare — falha de `insmod`
   vira só ruído de log. **Conclusão: nenhum módulo 5.15 é
   crítico para montar `/system`/`/vendor`** (o `ufshcd-crypto-qti`
   só importa para o `/data`, item 6). No 2º estágio
   (`vendor_dlkm`) morrem como esperado display/camera/bateria etc.
4. Ajustes de DT derivados da tabela (firmware-name, nome do DWC3)
   como patches próprios da série, antes do teste.
5. SELinux permissivo no cmdline/bootconfig do teste; userdebug já
   dá `adb root` para coletar dmesg/logcat.
6. Decidir o destino do `/data` (formatar sem wrappedkey × qseecom)
   — **é o item que mais pode custar tempo no Nível 0**.
7. Pré-requisitos de segurança inalterados: backup verificado de
   todas as partições (incl. `recovery`), plano de retorno, e o
   teste restrito a um slot. **Nada disso é autorização de flash**;
   é o roteiro para quando o usuário decidir.

## Conclusão

A ROM atual do usuário é o melhor alvo possível para o primeiro
boot Android do nosso kernel: sistema padrão e depurável, AVB
aberto, contrato documentado em código aberto. A fronteira do
trabalho continua sendo o vendor (blobs downstream), exatamente
como no plano “vendor novo” — mas agora com o mapa completo das
expectativas, itemizável HAL a HAL.


## Confirmações da instância real (Lunaris, dumps de 2026-11-04)

Com os dumps das partições de boot da Lunaris em mãos (ver
`docs/boot-partition-inventory.md`, captura 2026-11-04), os fatos da
árvore LineageOS acima foram confrontados com a ROM de verdade:

- **Kernel**: a instância usa um prebuilt downstream
  **5.15.211 "dexter1"** (não o 5.15.94 da árvore de referência).
  Para nós é indiferente — substituímos `Image`+DTB de qualquer forma.
- **DT**: FDT#1 e overlay #51 **byte-idênticos ao pacote stock** da
  Xiaomi. Repack confirmado: nosso DTB entra no índice 1 e a entrada
  51 é neutralizada com FDT vazio (`tools/empty_overlay.py`).
- **1º estágio**: o `modules.load` real tem 86 entradas e o `fstab`
  é o mesmo da árvore (lógicas by-name/liblp; `/data` f2fs com
  `wrappedkey_v0`; `modem` FAT → `/vendor/firmware_mnt`, confirmando
  os nomes pelados do patch 0093). Vale a conclusão da auditoria:
  nenhum módulo é crítico para montar `system`/`vendor`; extras da
  ROM (sched-walt, zram, mi_memory) são só ruído de `insmod`.
- **AVB**: `vbmeta_b` com **flags = 3** confirmado no binário.
- **Bootconfig**: o `usbcontroller=4e00000.dwc3` vive nos 85 bytes de
  bootconfig do `vendor_boot`; a reescrita para `4e00000.usb` está
  implementada (`bootimg.py set-bootconfig`). Já `bootdevice` e
  `boot_devices` são gerados pelo bootloader — atenção no 1º boot:
  o valor medido (`soc/4804000.ufshc`) usa o nome downstream do nó
  SoC; o nosso DTB usa `soc@0`. Se o ABL derivar o caminho do DTB
  carregado, vem certo automaticamente; conferir em
  `/proc/bootconfig` no primeiro teste.
- **cmdline viva** é a downstream (console `ttyMSM0`, painel
  `msm_drm`, props de fingerprint/touch) — no nosso boot vale o
  `chosen` do nosso DTB; sem conversor UART no setup, sem impacto.

Checklist do Nível 0 após esta rodada:

- ☑ Backups completos e verificados por hash (incl. `recovery`).
- ☑ Ferramenta de repack validada nas imagens reais (roundtrip
  byte-idêntico) + `set-bootconfig` e overlay vazio prontos.
- ☑ Pipeline `tools/build_flash_images_618.sh` escrito.
- ☐ Gerar as imagens 6.18 — falta trazer `Image`+DTB do CI (o
  sandbox não alcança o storage de artifacts do Actions; relay via
  Drive pelo usuário, como os dumps).
- ☐ Decisão do `/data` (wrappedkey), SELinux permissivo no teste e
  autorização explícita — **nada de flash antes disso**.
