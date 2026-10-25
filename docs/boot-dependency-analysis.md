# Análise de dependência mínima de boot — topaz/tapas (SM6225/Khaje) no GKI 6.12

> Documento de decisão (item 3 do plano): **quais drivers/configs são indispensáveis
> para o kernel 6.12 subir no aparelho** e **qual estratégia adotar** (portar o stack
> vendor agora × caminho de boot mínimo).
>
> Fontes primárias (todas verificadas nesta rodada):
> - `.config` efetivo do build de CI (`config-khaje.config`, branch `ci-artifacts`, 11.274 linhas; run `39040529520`);
> - base pinada `EdMory/android_kernel_common_sm8850` @ `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`;
> - DTS/DTBO de referência do aparelho (`device-tree/reference/`);
> - inventários já versionados (`docs/boot-partition-inventory.md`, `docs/module-inventory.md`).

---

## 1. Resumo executivo (decisão)

| | |
|---|---|
| **O que já está pronto** | Base 6.12 + patches 0001–0014 + DTB/DTBO topaz (`0x30022`) + `Image-khaje`; quatro imagens de boot geradas estaticamente. CI kernel/DTS `39040529520` e CI da ramdisk `39040529561` verdes. |
| **O que bloqueia o boot Android completo** | `msm_partition` não existe na base 6.12; além disso faltam drivers vendor de display/GPU e a cadeia AVB ainda não está preparada. O bootloader desbloqueado, `recovery_b` e backups completos ainda não foram verificados. |
| **O que não bloqueia o marco serial mínimo** | A ramdisk própria não monta `/system` nem carrega módulos vendor; os serviços de display, GPU, câmera, WLAN, touch e fingerprint ficam fora deste primeiro marco. |
| **Estratégia escolhida** | **C — híbrida**: **B2a (console serial) → B2b (ADB, pendente) → B1 (Android userspace) → A (stack vendor)**. Nada de stack vendor antes de o kernel subir. |

**Estado atual:** o B2a está preparado: kernel 6.12 + init estático + BusyBox shell
no UART `ttyMSM0`. Esta ramdisk **não tem `adbd`**, portanto ADB não é prometido ainda.
O próximo passo antes de qualquer flash é resolver os bloqueios de segurança
(bootloader, backups — sobretudo `recovery_b` — e plano AVB/recuperação); nenhuma
imagem foi testada no aparelho.

---

## 2. Cadeia de boot por estágio (o que precisa existir em cada estágio)

| # | Estágio | Responsável | Requisito no kernel 6.12 | Estado |
|---|---|---|---|---|
| 1 | Bootloader → `Image` | bootloader (Xiaomi) | `Image` válido + cmdline/bootconfig preservados | ✅ `Image-khaje` empacotado em `boot_b-khaje-6.12.img`; AVB digest stale |
| 2 | Kernel: console inicial | `ttyMSM0` (GENI) | `CONFIG_SERIAL_QCOM_GENI_CONSOLE=y`; DTB `chosen.bootargs` inclui `console=ttyMSM0,115200n8` | ✅ config/DTB conferidos; UART não testado em hardware |
| 3 | Kernel: early boot / initramfs | `init_boot` mínima | ELF AArch64 estático, CPIO `newc`, `/dev/console`, `CONFIG_BINFMT_ELF=y`, `CONFIG_DEVTMPFS=y` | ✅ imagem gerada e validada pelo CI; sem teste no aparelho |
| 4 | Kernel: **storage** (UFS) | `ufs-qcom` + PHY QMP UFS | `CONFIG_SCSI_UFSHCD=y`, `CONFIG_SCSI_UFS_QCOM=y`, `CONFIG_PHY_QCOM_QMP_UFS=y` | ✅ build/config; enumeração UFS não testada |
| 5 | Kernel: partições Android | Android `init` | F2FS/EROFS/dm-verity/dm=y; `msm_partition` não existe na base | ⚠️ B2a contorna isso; Android userspace continua bloqueado |
| 6 | Userspace mínimo | `/init` + BusyBox shell | shell interativo pelo UART; ADB exigiria `adbd` + gadget/PHY compatível | ✅ B2a serial pronto; B2b ADB pendente |
| 7 | Framework Android | SurfaceFlinger, HALs | GPU (KGSL ou Adreno a6xx), display (DSI vendor), câmera, WLAN, touch, fingerprint | ❌ fora do escopo do boot mínimo |
| 8 | **Fallback de recuperação** | `pstore/blk`, `recovery_b` | `CONFIG_PSTORE_BLK=y`; `recovery_b` ainda não extraída/verificada | ⚠️ bloqueio de segurança antes de qualquer flash |

---

## 3. Matriz de dependências (subsistema → driver → evidência → bloqueante?)

| Subsistema | Driver 6.12 | Evidência | Bloqueia o *boot mínimo*? |
|---|---|---|---|
| **Storage UFS (host)** | `drivers/ufs/host/ufs-qcom.c` existe e casa com `compatible = "qcom,ufshc"` (`khaje.dtsi:2693`) | base pinada + DTS do port | `CONFIG_SCSI_UFS_QCOM=y`; hardware ainda não testado |
| **PHY UFS** | `drivers/phy/qualcomm/phy-qcom-qmp-ufs.c` + patch 0006 | patch 0006 | ✅ config/build conferidos |
| **Regulador UFS** | `REGULATOR_QCOM_SMD_RPM` (0009) + `PINCTRL_KHAJE` (0002) | fragmento de config | ✅ config/build conferidos |
| **Filesystems** | `EXT4=y`, `F2FS=y`, `EROFS=y` | config CI `39040529520` | ✅ símbolos embutidos; B2a não monta storage |
| **Device-mapper / verity** | `BLK_DEV_DM=y`, `DM_VERITY=y`; `DM_CRYPT` não exigido no B2a | config CI | ✅ config conferida; AVB no boot ainda não planejado |
| **Partições dinâmicas** | `msm_partition` não existe em `drivers/md` da base nem upstream 6.12 | listagem base + upstream | ⚠️ bloqueia Android `init`, contornado no B2a |
| **Console** | `SERIAL_QCOM_GENI=y`, `SERIAL_QCOM_GENI_CONSOLE=y`; `console=ttyMSM0,115200n8` no DTB | config + DTB do CI | ✅ estático; UART ainda não testado |
| **ADB/USB** | `USB_CONFIGFS=y`, `USB_CONFIGFS_F_FS=y`, `USB_DWC3=y`; DTS usa PHY USB sem equivalente 6.12 e ramdisk sem `adbd` | config + `khaje-usb.dtsi` + conteúdo da ramdisk original | ⚠️ B2b pendente; não há ADB na imagem atual |
| **RAM/SMEM/IPCC/RPM** | `QCOM_SMEM/SCM/IPCC/SMD_RPM=y`, `QCOM_AOSS_QMP=y` | config do CI | ✅ config/build conferidos |
| **Clocks** | `COMMON_CLK_QCOM=y`, `SM_GCC_6225=y` (patches 0010/0011) | fragmento | ✅ config/build conferidos |
| **Interconnect** | `INTERCONNECT_QCOM_BENGAL=y` (patch 0007) | fragmento | ✅ config/build conferidos |
| **PSTORE/recuperação** | `CONFIG_PSTORE_BLK=y`; base sem `ramoops`, `recovery_b` ainda sem backup verificado | config CI + listagem `fs/pstore` | ⚠️ recuperação precisa ser preparada antes do flash |
| **MODVERSIONS/KMI** | `MODVERSIONS` ❌ (KABI não versionado) | config do CI | não (port não modular) |
| **GPU** | base tem Adreno 6.x (`drivers/gpu/drm/msm/adreno/a6xx_*`) ✅; KGSL do OEM ❌ | base pinada | ❌ não bloqueia kernel |
| **Display** | `DRM_MSM=m` ✅ mas a base **não tem chips/painéis DSI** (só `dsi_host.c`/`dsi_manager.c`/`phy/`) ❌ → exige port do DSI vendor | base pinada | ❌ não bloqueia kernel (tela escura) |
| **Câmera** | `VIDEO_QCOM_CAMSS` ausente no fragmento; CAMSS existe na base sem match SM6225. A fonte vendor `camera.ko` foi localizada separadamente, mas ainda não integrada/portada (ver [`camera-port-audit.md`](camera-port-audit.md)). | config + base | ❌ não bloqueia o boot mínimo do kernel |
| **WLAN** | QCACLD (vendor) ❌; `CONFIG_WLAN_VENDOR_*` ausentes | config | ❌ não bloqueia kernel |
| **Touch / Fingerprint** | `focaltech_ts_i2c`, `goodix_fp` (vendor 5.15) ❌ | `docs/module-inventory.md` | ❌ não bloqueia kernel |

**Correção em relação à análise inicial:** o UFS não está ausente na base 6.12. O símbolo
é `CONFIG_SCSI_UFS_QCOM`; a promoção de `m` para `y` e a ativação de F2FS/EROFS/dm-verity
foram aplicadas e validadas no `.config` do CI. Continua ausente o parser Qualcomm de
partições dinâmicas (`msm_partition`), então o init Android original segue fora do
caminho mínimo B2a.

---

## 4. Diagnóstico do `.config` efetivo (config do CI)

O `.config` publicado pela run `39040529520` tem 11.274 linhas. Os símbolos
boot-critical que antes estavam ausentes ou como módulos foram promovidos e
validados como embutidos (`=y`):

```
CONFIG_SCSI_UFS_QCOM=y
CONFIG_BLK_DEV_DM=y
CONFIG_DM_VERITY=y
CONFIG_F2FS_FS=y
CONFIG_EROFS_FS=y
CONFIG_USB_CONFIGFS=y
CONFIG_USB_CONFIGFS_F_FS=y
CONFIG_PSTORE_BLK=y
CONFIG_PHY_QCOM_QMP_UFS=y
CONFIG_PINCTRL_KHAJE=y
```

O que continua ausente é o parser de partições dinâmicas `msm_partition` (não existe
na base 6.12) e o `adbd` userspace: a ramdisk original de `init_boot` não contém esse
binário. O B2a contorna o parser e não depende de ADB; o B2b vai precisar de um
`adbd` AArch64 compatível e do gadget USB/PHY correspondente.

**Notas de GKI:** `GKI_HIDDEN_UFS_CONFIGS` não está ativo; as opções de UFS são
visíveis ao fragmento. `ANDROID_GKI_KABI`/`ANDROID_USB_CONFIGFS` não estão presentes,
ou seja, o build é baseado no GKI, sem KABI estrito — aceitável para este bring-up
monolítico, mas sem prometer compatibilidade de módulos externos.

---

## 5. Opções de estratégia avaliadas

### Opção A — portar agora o stack vendor completo (KGSL + SDE/DSI + techpack de câmera + QCACLD + FocalTech + Goodix)
- **Volume:** 6 famílias de drivers out-of-tree de milhares de linhas cada, todos em 5.15 (`vermagic 5.15.41` — ver `docs/module-inventory.md`), com dependências entre si (SDE ↔ KGSL ↔ DSI; techpack ↔ CAMSS; QCACLD ↔ `cnss2`/`wlan_firmware_service`).
- **Risco:** alto. Qualquer falha no display/GLES derruba o SurfaceFlinger, e um kernel que não sobe impede **avaliar** qualquer um desses drivers.
- **Veredicto:** **não é o próximo passo**; continua sendo o objetivo de médio prazo.

### Opção B — caminho de boot mínimo
- **B1 — manter a ramdisk original (`init_boot` genérica):** exige o stack completo de storage (UFS embutido + F2FS + EROFS + dm-verity + `msm_partition`) e ainda assim o framework gráfico não sobe (sem DSI/GPU vendor) → o `init` do Android morre ao montar `/system` ou falha depois. Ganha-se pouco em relação a B2 e custa o parser de partições dinâmicas.
- **B2 — ramdisk `init_boot` mínima própria (init estático + BusyBox shell):** o objetivo é o kernel subir e deixar o *dmesg* acessível pelo console serial. Esta ramdisk ainda **não inclui `adbd`**; o shell é pelo UART (`console=ttyMSM0,115200n8`). É o marco clássico de "kernel bring-up": valida pinctrl, clocks, RPM-SMD, interconnect, PHY UFS, host UFS e console — exatamente o que a série 0001–0014 entrega. Risco baixo, reversível (o `init_boot` original permanece preservado).
- **Veredicto:** **B2a (serial) está preparado e validado estaticamente**; B2b (ADB) permanece pendente; B1 é a fase seguinte após coletar evidência do primeiro boot.

### Opção C — híbrida B2 → B1 → A (recomendada)
1. **B2a (serial):** kernel 6.12 + init mínimo + BusyBox shell no console UART (sem storage Android completo) → validar o port. **B2b (ADB) fica pendente:** nem a ramdisk original contém `adbd`; ainda é preciso obter/construir um binário AArch64 compatível e configurar o gadget USB.
2. **B1:** fechar storage (UFS `=y`, F2FS, EROFS, dm-verity, `msm_partition`) e conseguir `init` do Android vivo até o ponto de falhar por ausência de display/GPU → mapear os drivers vendor que faltam com evidência (dmesg), não por suposição.
3. **A:** portar o stack vendor por ondas (display+GPU primeiro, depois WLAN, câmera, touch, fingerprint), cada onda com build + CI verde.

**Por que C e não só B:** B2a dá o feedback mais rápido, mas não prova que o
armazenamento do aparelho funciona; B1 sem esse console seria lento para depurar. C
entrega evidência em cada degrau e mantém o objetivo final (Android usável) no radar.

---

## 6. Execução da fase B2a e próximos bloqueios

1. **Fragmento de config** `config/topaz-khaje.config` — **aplicado nesta rodada**:
   `CONFIG_SCSI_UFS_QCOM=y`, `CONFIG_BLK_DEV_DM=y`, `CONFIG_DM_VERITY=y`,
   `CONFIG_F2FS_FS=y`, `CONFIG_EROFS_FS=y`, `CONFIG_USB_CONFIGFS=y`,
   `CONFIG_USB_CONFIGFS_F_FS=y`, `CONFIG_PSTORE_BLK=y`. O script
   `tools/configure_kernel.sh` passou a exigir esses símbolos como `=y`, então o
   CI falha se alguma dependência não for satisfeita na base 6.12.
   **Adiado:** `CONFIG_MODVERSIONS` (sem módulos externos no port, não é
   bloqueante) e `msm_partition` (depende da resposta da questão 1 da §7).
2. **DTB/DTBO**: **montados estaticamente** com a base `khaje-idp-nopmi.dtb` do build 6.12 no FDT#1 (`qcom,msm-id=0x206`) de `vendor_boot` e o overlay topaz 6.12 na entrada 51 de `dtbo`. Ambos cabem nos slots originais; nenhuma validação em aparelho foi feita.
3. **`boot.img`**: empacotar `Image-khaje` no cabeçalho do `boot_b` original (preservando header/cmdline/bootconfig/os_version; movendo o vbmeta e ajustando offsets do footer) — **feito estaticamente**. A ferramenta [`tools/bootimg.py`](boot-image-tooling.md) valida os quatro formatos por ida-e-volta byte a byte e gera `boot`/`vendor_boot`/`dtbo`/`init_boot` (detalhes e hashes em [`docs/boot-image-tooling.md`](boot-image-tooling.md)). A assinatura/digest ficam obsoletos; falta um bypass AVB adequado antes de qualquer teste.
4. **`init_boot` mínima**: **concluída/validada no CI `39040529561`**. CPIO `newc` não comprimido com `/init` estático AArch64, BusyBox, `/dev/console` e shell serial; sem `adbd`. O `init_boot_b` original permanece preservado e a imagem derivada ainda não foi testada no aparelho.
5. **Pré-requisitos de segurança (bloqueantes para qualquer flash):** bootloader desbloqueado (estado desconhecido — precisa ser verificado), backups verificados de `boot_b`, `init_boot_b`, `vendor_boot_b`, `dtbo`, `vbmeta`, `vbmeta_system` e **`recovery_b` (nunca extraída)**, e um caminho de recuperação testado.

---

## 7. Riscos e perguntas em aberto

| # | Questão | Impacto | Como resolver |
|---|---|---|---|
| 1 | O aparelho usa partições dinâmicas ("super")? | define se `msm_partition` é obrigatório | coletar GPT/`lsblk` do aparelho (via `adb`/`fastboot`), sem alterar partições |
| 2 | O bootloader está desbloqueado? | sem isso, não há flash de `boot.img` custom | `fastboot getvar unlocked` / MIUI "OEM unlocking" |
| 3 | Origem do cmdline/console | `boot_b` tem cmdline vazio; `vendor_boot` traz seu cmdline e o DTB 6.12 define `chosen.bootargs` com `console=ttyMSM0,115200n8` | ambos são preservados no repack; só verificar UART no aparelho, sem gravar nada |
| 4 | Phys USB: o DTS usa `qcom,usb-ssphy-qmp-dp-combo`, sem driver 6.12 equivalente | `adbd` sem função de alta velocidade USB | reescrever o nó para o combo upstream (`qcom,qmp-combo`) ou portar o driver vendor |
| 5 | Endpoints `msm_drm`/DSI ausentes | tela escura na fase B2 | port do DSI vendor (fase A) |
| 6 | `recovery_b` nunca extraída | sem fallback se o boot falhar | extrair e verificar (sha256) antes de qualquer escrita |

---

## 8. Validação e status do boot chain

| Item | Resultado |
|---|---|
| Run `39026074996` | ❌ falhou no gate porque o fragmento pedia `CONFIG_RAMOOPS`, inexistente na base 6.12; o gate evitou seguir com configuração inválida. |
| Correção | `CONFIG_RAMOOPS` → `CONFIG_PSTORE_BLK` (backend presente na base). |
| Run `39026267325` | ✅ base kernel + DTS/schema verdes após a correção original. |
| Run `39040529520` | ✅ kernel `Image-khaje` + DTBs/DTBOs; gate `dt-validate` e `dt_binding_check` verdes. |
| Run `39040529561` | ✅ workflow independente da ramdisk: BusyBox estático AArch64, init estático, CPIO validado (`/dev/console` char 5:1). |
| Imagens finais | ✅ `boot`, `vendor_boot`, `dtbo` e `init_boot` geradas; originais fazem round-trip byte-idêntico. Hashes em `docs/boot-image-tooling.md`. Nenhuma gravação/teste em hardware. |
| `.config` efetivo (11.274 linhas) | UFS, dm-verity, F2FS, EROFS, USB configfs, PSTORE_BLK, QMP UFS PHY e pinctrl Khaje como `=y`. |

O storage Android está configurado para o próximo degrau, mas o parser de partições
`msm_partition` continua ausente; o `adbd` também não foi incluído na ramdisk B2a.
Portanto, esta entrega é **serial-only** e não promete Android nem ADB.

**Bloqueios absolutos antes de qualquer flash:** confirmar o estado do bootloader,
obter e verificar backups incluindo `recovery_b`, definir o bypass AVB correto, e
planejar uma recuperação testada. A assinatura/digest das imagens custom não é válida;
nada foi flashado ou testado no aparelho.

---

## 9. Referências internas

- `docs/boot-partition-inventory.md` — layout do boot chain, offsets e hashes das DTBs.
- `docs/module-inventory.md` — 320 módulos 5.15 e suas dependências (base do escopo da fase A).
- `docs/dts-integration-status.md`, `docs/dt-schema-validation.md` — estado da integração DT/schema.
- `config/topaz-khaje.config`, `tools/configure_kernel.sh` — fragmento de config e merge no defconfig GKI.
- `.github/workflows/dts-validate.yml` — CI (build da base, build do kernel, `dt-validate` + gate).
- `.github/workflows/initramfs.yml`, `initramfs/minimal-init.c`, `tools/initramfs.py` — init estático/BusyBox e CPIO B2a.
- `docs/boot-image-tooling.md`, `tools/bootimg.py`, `tools/build_flash_images.sh` — formatos, validação e montagem local das quatro imagens.
