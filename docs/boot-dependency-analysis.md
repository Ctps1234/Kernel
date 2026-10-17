# Análise de dependência mínima de boot — topaz/tapas (SM6225/Khaje) no GKI 6.12

> Documento de decisão (item 3 do plano): **quais drivers/configs são indispensáveis
> para o kernel 6.12 subir no aparelho** e **qual estratégia adotar** (portar o stack
> vendor agora × caminho de boot mínimo).
>
> Fontes primárias (todas verificadas nesta rodada):
> - `.config` efetivo do build de CI (`config-khaje.config`, branch `ci-artifacts`, 11.244 linhas);
> - base pinada `EdMory/android_kernel_common_sm8850` @ `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`;
> - DTS/DTBO de referência do aparelho (`device-tree/reference/`);
> - inventários já versionados (`docs/boot-partition-inventory.md`, `docs/module-inventory.md`).

---

## 1. Resumo executivo (decisão)

| | |
|---|---|
| **O que já está pronto** | Base 6.12 + série de patches 0001–0014 + DTB/DTBO de topaz (`0x30022`) + `Image-khaje` compilando no CI (run `38992157178` verde). |
| **O que bloqueia o boot hoje** | (a) driver de host UFS da Qualcomm está como **módulo** (`CONFIG_SCSI_UFS_QCOM=m`) — storage é boot-critical; (b) faltam **F2FS** (`/data`), **EROFS** (`/system`,`/vendor`), **dm-verity** e **fs/dm** (a ramdisk do Android monta as partições com verificação); (c) **gadget USB** é módulo (`CONFIG_USB_CONFIGFS=m`) → `adbd` sem `ffs`; (d) **parser de partições dinâmicas (`msm_partition`) não existe na base** → o "super" do Android 13+ não é interpretável; (e) `/chosen` do DTB é **vazio** → o `cmdline` vem exclusivamente do cabeçalho da partição `boot` (precisa ser preservado no repack). |
| **O que não é bloqueante para o kernel subir** | DSI/painéis (display), GPU, câmera, WLAN, touch, fingerprint: o framework gráfico não sobe, mas o **kernel** sobe e o console serial funciona. |
| **Estratégia escolhida** | **C — híbrida, em 3 fases** (recomendação unânime entre as opções avaliadas abaixo): **B2 → B1 → A**. Nada de stack vendor antes de o kernel subir. |

**Recomendação em uma frase:** o próximo marco é um **boot mínimo de kernel** (fase B2:
kernel 6.12 + console serial + `adbd` via USB gadget, com uma ramdisk `init_boot`
mínima própria), porque é o único caminho que valida pinctrl/clocks/reguladores/UFS do
port com risco baixo e sem depender de nenhum driver vendor; só depois se fecha a
paridade de storage (fase B1) e, por último, o stack vendor (fase A).

---

## 2. Cadeia de boot por estágio (o que precisa existir em cada estágio)

| # | Estágio | Responsável | Requisito no kernel 6.12 | Estado |
|---|---|---|---|---|
| 1 | Bootloader → `Image` | bootloader (Xiaomi) | `Image` válido + **cmdline preservado** do `boot` original | ⚠️ CI gera `Image-khaje`; falta empacotar em `boot.img` v4 |
| 2 | Kernel: console inicial (early) | `ttyMSM0` (GENI) | `CONFIG_SERIAL_QCOM_GENI=y` + `CONFIG_SERIAL_QCOM_GENI_CONSOLE=y` | ✅ já ativos |
| 3 | Kernel: early boot / initramfs | `init_boot` (ramdisk genérico, 2.888.965 B) | `CONFIG_BINFMT_ELF=y`, `CONFIG_DEVTMPFS=y`, `CONFIG_TMPFS=y` | ✅ |
| 4 | Kernel: **storage** (UFS) | `ufs-qcom` + PHY QMP UFS | `CONFIG_SCSI_UFSHCD=y` ✅, `CONFIG_SCSI_UFS_QCOM=**m**` ⚠️ → precisa `=y`; `CONFIG_PHY_QCOM_QMP_UFS=y` ✅ (patch 0006) | ⚠️ módulo em storage boot-critical |
| 5 | Kernel: partições do Android | `init` da ramdisk | `CONFIG_F2FS_FS` ❌, `CONFIG_EROFS_FS` ❌, `CONFIG_DM_VERITY` ❌, `CONFIG_BLK_DEV_DM=**m**` ⚠️, **`msm_partition` inexistente na base** ❌ | ❌ bloqueante |
| 6 | Userspace mínimo | `adbd` | `CONFIG_USB_CONFIGFS=**m**` ⚠️ + `CONFIG_USB_CONFIGFS_F_FS=y` ✅ + `CONFIG_USB_DWC3=y` ✅ + PHY USB (`qcom,usb-hsphy-snps-femto` / `qcom,usb-ssphy-qmp-dp-combo`) | ⚠️ módulo; PHYs exigem adaptation de DT/driver |
| 7 | Framework Android | SurfaceFlinger, HALs | GPU (KGSL ou Adreno a6xx), display (DSI vendor), câmera, WLAN (QCACLD), touch, fingerprint | ❌ fora do escopo do boot mínimo |
| 8 | **Fallback de recuperação** | `pstore/blk`, `recovery_b` | `CONFIG_PSTORE=y` ✅, `CONFIG_PSTORE_BLK` ❌ (e não há ramoops na base ✗); partição `recovery_b` nunca extraída | ❌ bloqueante (segurança) |

---

## 3. Matriz de dependências (subsistema → driver → evidência → bloqueante?)

| Subsistema | Driver 6.12 | Evidência | Bloqueia o *boot mínimo*? |
|---|---|---|---|
| **Storage UFS (host)** | `drivers/ufs/host/ufs-qcom.c` — existe na base; `compatible = "qcom,ufshc"` **igual ao do DTS** (`khaje.dtsi:2693`) | base pinada + DTS do port | **SIM** — está `=m` |
| **PHY UFS** | `drivers/phy/qualcomm/phy-qcom-qmp-ufs.c` + patch 0006 (`qcom,sm6225-qmp-ufs-phy`) | patch 0006 | ✅ pronto |
| **Regulador UFS** | `REGULATOR_QCOM_SMD_RPM` (patch 0009) + `PINCTRL_KHAJE` (0002) | fragmento de config | ✅ pronto |
| **Filesystems** | `EXT4=y` ✅, `F2FS` ❌, `EROFS` ❌ | config do CI | **SIM** (para `/data` e `/system`) |
| **Device-mapper / verity** | `BLK_DEV_DM=m` ⚠️, `DM_VERITY` ❌, `DM_CRYPT` ❌ | config do CI | **SIM** (se a ramdisk original for usada) |
| **Partições dinâmicas** | `msm_partition` — **não existe** em `drivers/md` da base **nem no upstream 6.12** (é driver Qualcomm-only) | listagem de `drivers/md` (base e torvalds v6.12) | **SIM** se o aparelho usar "super" |
| **Console** | `SERIAL_QCOM_GENI=y`, `SERIAL_QCOM_GENI_CONSOLE=y` | config do CI | ✅ pronto |
| **ADB/USB** | `USB_CONFIGFS=m` ⚠️, `USB_CONFIGFS_F_FS=y` ✅, `USB_DWC3=y` ✅; PHYs: base tem `phy-qcom-snps-femto-v2.c` ✅ e `phy-qcom-qmp-combo.c` ✅, mas o DTS usa `qcom,usb-ssphy-qmp-dp-combo` ❌ (sem equivalente 6.12) | config + `khaje-usb.dtsi` | **SIM** (para `adbd`) |
| **RAM/SMEM/IPCC/RPM** | `QCOM_SMEM/SCM/IPCC/SMD_RPM=y`, `QCOM_AOSS_QMP=y` | config do CI | ✅ pronto |
| **Clocks** | `COMMON_CLK_QCOM=y`, `SM_GCC_6225=y` (patches 0010/0011) | fragmento | ✅ pronto |
| **Interconnect** | `INTERCONNECT_QCOM_BENGAL=y` (patch 0007) | fragmento | ✅ pronto |
| **PSTORE/recuperação** | `PSTORE=y` ✅; a base **não traz** `fs/pstore/ramops.c` (backend ramoops inexistente ✗) — existe o `pstore/blk` (`CONFIG_PSTORE_BLK`, "not set" ❌), que é o backend usado pelo Android (partição "ram") | config do CI + listagem de `fs/pstore` da base | não (recomendável) |
| **MODVERSIONS/KMI** | `MODVERSIONS` ❌ (KABI não versionado) | config do CI | não (port não modular) |
| **GPU** | base tem Adreno 6.x (`drivers/gpu/drm/msm/adreno/a6xx_*`) ✅; KGSL do OEM ❌ | base pinada | ❌ não bloqueia kernel |
| **Display** | `DRM_MSM=m` ✅ mas a base **não tem chips/painéis DSI** (só `dsi_host.c`/`dsi_manager.c`/`phy/`) ❌ → exige port do DSI vendor | base pinada | ❌ não bloqueia kernel (tela escura) |
| **Câmera** | `QCOM_CAMSS` ausente no config; `drivers/media/platform/qcom/camss` existe na base mas sem chips do SM6225 | config + base | ❌ não bloqueia kernel |
| **WLAN** | QCACLD (vendor) ❌; `CONFIG_WLAN_VENDOR_*` ausentes | config | ❌ não bloqueia kernel |
| **Touch / Fingerprint** | `focaltech_ts_i2c`, `goodix_fp` (vendor 5.15) ❌ | `docs/module-inventory.md` | ❌ não bloqueia kernel |

**Correção de um dado anterior:** o UFS **não está ausente** na base 6.12. O símbolo no
6.12 é `CONFIG_SCSI_UFS_QCOM` (não `UFS_QCOM`/`UFS_FS`): o host controller Qualcomm
existe em `drivers/ufs/host/ufs-qcom.c` e casa com o `compatible = "qcom,ufshc"` do
DTS — só que compilado como **módulo**. O que realmente falta é o *parser* de
partições dinâmicas (`msm_partition`) e os *filesystems* do Android.

---

## 4. Diagnóstico do `.config` efetivo (config do CI)

**Ausentes (bloqueiam):**

```
# CONFIG_F2FS_FS is not set        → /data (Android usa f2fs)
# CONFIG_EROFS_FS is not set       → /system e /vendor (Android 13+ usa EROFS)
# CONFIG_DM_VERITY is not set      → verificação de integridade das partições
# CONFIG_DM_CRYPT is not set       → dm-crypt (usado por/userspace de /data)
CONFIG_BLK_DEV_DM=m               → precisa =y para o dm-verity
CONFIG_SCSI_UFS_QCOM=m            → precisa =y (storage boot-critical)
CONFIG_USB_CONFIGFS=m             → precisa =y (adbd sem insmod)
# CONFIG_PSTORE_BLK is not set    → backend de pstore (a base não tem ramoops)
# CONFIG_MODVERSIONS is not set    → sem versionamento de símbolos (KMI)
```

**Presentes e suficientes para o arranque:** `SERIAL_QCOM_GENI(_CONSOLE)=y`,
`EXT4_FS=y`, `DEVTMPFS=y`, `TMPFS=y`, `BLK_DEV_LOOP=y`, `BINFMT_ELF=y`,
`PSTORE=y`, `PRINTK=y`, `DEBUG_FS=y`, `PROC_FS=y`, `SYSFS=y`, `SMP=y`,
`QCOM_SMEM/SCM/IPCC/SMD_RPM=y`, `QCOM_AOSS_QMP=y`, `PINCTRL_KHAJE=y`,
`REGULATOR_QCOM_SMD_RPM=y`, `PHY_QCOM_QMP_UFS=y`, `INTERCONNECT_QCOM_BENGAL=y`,
`COMMON_CLK_QCOM=y`, `SM_GCC_6225=y`, `ANDROID_KABI_RESERVE=y`, `LTO_NONE=y`.

**Notas de GKI:** `GKI_HIDDEN_UFS_CONFIGS` **não** está ativo (as opções de UFS são
visíveis e editáveis — bom para o fragmento), mas o fragmento só "cola" na
config final se o símbolo existir na árvore; `ANDROID_GKI_KABI`/`ANDROID_USB_CONFIGFS`
não estão presentes, ou seja, o build atual é um kernel *baseado* no GKI, não um GKI
com KABI estrito — aceitável para um port monolítico, e a decisão fica registrada
aqui para não se prometer "GKI compatível" indevidamente.

**Correção aplicada:** o símbolo do host UFS nesta base é `CONFIG_SCSI_UFS_QCOM`
(6.12 renomeou `UFS_QCOM`/`UFS_FS`); ele já estava habilitado, porém como
**módulo** — daí a promoção para `=y`.

---

## 5. Opções de estratégia avaliadas

### Opção A — portar agora o stack vendor completo (KGSL + SDE/DSI + techpack de câmera + QCACLD + FocalTech + Goodix)
- **Volume:** 6 famílias de drivers out-of-tree de milhares de linhas cada, todos em 5.15 (`vermagic 5.15.41` — ver `docs/module-inventory.md`), com dependências entre si (SDE ↔ KGSL ↔ DSI; techpack ↔ CAMSS; QCACLD ↔ `cnss2`/`wlan_firmware_service`).
- **Risco:** alto. Qualquer falha no display/GLES derruba o SurfaceFlinger, e um kernel que não sobe impede **avaliar** qualquer um desses drivers.
- **Veredicto:** **não é o próximo passo**; continua sendo o objetivo de médio prazo.

### Opção B — caminho de boot mínimo
- **B1 — manter a ramdisk original (`init_boot` genérica):** exige o stack completo de storage (UFS embutido + F2FS + EROFS + dm-verity + `msm_partition`) e ainda assim o framework gráfico não sobe (sem DSI/GPU vendor) → o `init` do Android morre ao montar `/system` ou falha depois. Ganha-se pouco em relação a B2 e custa o parser de partições dinâmicas.
- **B2 — ramdisk `init_boot` mínima própria (init estático + shell + `adbd`):** o kernel sobe, o console serial mostra o *dmesg* completo e o `adbd` expõe um shell. É o marco clássico de "kernel bring-up": valida pinctrl, clocks, RPM-SMD, interconnect, PHY UFS, host UFS, console, USB — exatamente o que a série 0001–0014 entrega. Risco baixo, reversível (basta trocar de volta a `init_boot` original).
- **Veredicto:** **é o próximo passo** (B2), com B1 como fase seguinte.

### Opção C — híbrida B2 → B1 → A (recomendada)
1. **B2:** kernel 6.12 + console + `adbd` (sem storage Android completo) → validar o port.
2. **B1:** fechar storage (UFS `=y`, F2FS, EROFS, dm-verity, `msm_partition`) e conseguir `init` do Android vivo até o ponto de falhar por ausência de display/GPU → mapear os drivers vendor que faltam com evidência (dmesg), não por suposição.
3. **A:** portar o stack vendor por ondas (display+GPU primeiro, depois WLAN, câmera, touch, fingerprint), cada onda com build + CI verde.

**Por que C e não só B:** B2 dá o feedback mais rápido, mas não prova que o
armazenamento do aparelho funciona; B1 sem B2 seria lento para depurar. C entrega
evidência em cada degrau e mantém o objetivo final (Android usável) no radar.

---

## 6. Plano de execução da fase B2 (próximo marco)

1. **Fragmento de config** `config/topaz-khaje.config` — **aplicado nesta rodada**:
   `CONFIG_SCSI_UFS_QCOM=y`, `CONFIG_BLK_DEV_DM=y`, `CONFIG_DM_VERITY=y`,
   `CONFIG_F2FS_FS=y`, `CONFIG_EROFS_FS=y`, `CONFIG_USB_CONFIGFS=y`,
   `CONFIG_USB_CONFIGFS_F_FS=y`, `CONFIG_PSTORE_BLK=y`. O script
   `tools/configure_kernel.sh` passou a exigir esses símbolos como `=y`, então o
   CI falha se alguma dependência não for satisfeita na base 6.12.
   **Adiado:** `CONFIG_MODVERSIONS` (sem módulos externos no port, não é
   bloqueante) e `msm_partition` (depende da resposta da questão 1 da §7).
2. **DTB/DTBO**: decidir se a fase B2 reutiliza o `vendor_boot` original (base Khaje + overlay topaz já extraídos) ou se a base passa a vir do build 6.12 (patch 0010+ exige reescrita de clocks/reguladores nos DTBs → a base 6.12 só estará correta após o port completo dos clocks; **recomendação: B2 usa o `vendor_boot` original** e só o kernel é substituído).
3. **`boot.img`**: empacotar `Image-khaje` no cabeçalho do `boot_b` original (preservando `cmdline`, `bootconfig`, `os_version`, assinatura/vbmeta) — a ferramenta de `mkbootimg` ainda precisa ser DT (hoje o repo só publica `Image-khaje`/`System.map`).
4. **`init_boot` mínima**: ramdisk própria (init estático + `adbd` ou `toybox` + shell) para a fase B2; o `init_boot_b` original fica preservado e é restaurado em caso de falha.
5. **Pré-requisitos de segurança (bloqueantes para qualquer flash):** bootloader desbloqueado (estado desconhecido — precisa ser verificado), backups verificados de `boot_b`, `init_boot_b`, `vendor_boot_b`, `dtbo`, `vbmeta`, `vbmeta_system` e **`recovery_b` (nunca extraída)**, e um caminho de recuperação testado.

---

## 7. Riscos e perguntas em aberto

| # | Questão | Impacto | Como resolver |
|---|---|---|---|
| 1 | O aparelho usa partições dinâmicas ("super")? | define se `msm_partition` é obrigatório | coletar GPT/`lsblk` do aparelho (via `adb`/`fastboot`), sem alterar partições |
| 2 | O bootloader está desbloqueado? | sem isso, não há flash de `boot.img` custom | `fastboot getvar unlocked` / MIUI "OEM unlocking" |
| 3 | `cmdline` original (console/root/verity) | se o repack perder o cmdline, não há console | extrair do cabeçalho do `boot_b` original e reaplicar literalmente |
| 4 | Phys USB: o DTS usa `qcom,usb-ssphy-qmp-dp-combo`, sem driver 6.12 equivalente | `adbd` sem função de alta velocidade USB | reescrever o nó para o combo upstream (`qcom,qmp-combo`) ou portar o driver vendor |
| 5 | Endpoints `msm_drm`/DSI ausentes | tela escura na fase B2 | port do DSI vendor (fase A) |
| 6 | `recovery_b` nunca extraída | sem fallback se o boot falhar | extrair e verificar (sha256) antes de qualquer escrita |

---

## 8. Validação do ajuste de configuração

| Item | Resultado |
|---|---|
| Run `39026074996` | ❌ **falhou de propósito** no gate de `tools/configure_kernel.sh`: o fragmento pedia `CONFIG_RAMOOPS`, que **não existe** na base (a base traz `fs/pstore/blk.c`, sem `ramops.c`). O gate funcionou: build barrado antes de gastar tempo de compilação. |
| Correção | `CONFIG_RAMOOPS` → `CONFIG_PSTORE_BLK` (backend de pstore usado pelo Android, partição "ram"). |
| Run `39026267325` | ✅ **verde** — job `Kernel build (port dos drivers)` e job `Device trees (dtbs + dt-schema)` (3m37s), incluindo o gate de `dt-validate` e o `dt_binding_check`. |
| `.config` final (publicado no branch `ci-artifacts`, 11.274 linhas) | `CONFIG_SCSI_UFS_QCOM=y`, `CONFIG_BLK_DEV_DM=y`, `CONFIG_DM_VERITY=y`, `CONFIG_F2FS_FS=y`, `CONFIG_EROFS_FS=y`, `CONFIG_USB_CONFIGFS=y`, `CONFIG_USB_CONFIGFS_F_FS=y`, `CONFIG_PSTORE_BLK=y` — todos aplicados. |

Ou seja: **o storage do Android (host UFS + f2fs + EROFS + dm-verity) e o canal de
ADB (gadget USB embutido) já estão habilitados no build oficial**; o que ainda falta
para o aparelho subir é a árvore de drivers (o `msm_partition`), a imagem de boot
empacotada, a `init_boot` mínima e a verificação do bootloader.

---

## 9. Referências internas

- `docs/boot-partition-inventory.md` — layout do boot chain, offsets e hashes das DTBs.
- `docs/module-inventory.md` — 320 módulos 5.15 e suas dependências (base do escopo da fase A).
- `docs/dts-integration-status.md`, `docs/dt-schema-validation.md` — estado da integração DT/schema.
- `config/topaz-khaje.config`, `tools/configure_kernel.sh` — fragmento de config e merge no defconfig GKI.
- `.github/workflows/dts-validate.yml` — CI (build da base, build do kernel, `dt-validate` + gate).
