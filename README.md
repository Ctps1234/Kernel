# Redmi Note 12 4G — kernel Android GKI 6.12

Projeto de bring-up/port para o Redmi Note 12 4G (topaz/tapas). **Estado: par FDT/DTBO confirmado e série local 0001–0014 aplicada e verificada na base Android Common 6.12 fixada (`0efd3abd...`): pinctrl/RPMCC Khaje, PHY UFS SM6225, interconnect Bengal, reguladores RPM-SMD e providers GCC/DISPCC/GPUCC/debugcc com votos de tensão. As device trees de topaz/tapas estão versionadas em `device-tree/source/` e entram na árvore do kernel por staging determinístico (`tools/integrate_dts.py`): 102/102 includes resolvidos, DTB/DTBO compilados pelo build do kernel com dtc 1.7 e fragmento de configuração do port em `config/topaz-khaje.config`. O build da imagem do kernel passou no CI (`LD vmlinux`, `OBJCOPY arch/arm64/boot/Image`) e o `dt-validate` virou um gate de regressão com linha de base versionada (833 erros conhecidos no DTB base, backlog de bindings vendor em [`docs/dt-schema-validation.md`](docs/dt-schema-validation.md)). Falta a paridade Android (KGSL, câmera, QCACLD, fingerprint, carregador); nada foi testado em hardware.**

## Hardware confirmado

| Campo | Valor |
|---|---|
| Modelo reportado | `23021RAA2Y` |
| Codinomes | produto `topaz`, vendor `tapas` |
| SoC | Qualcomm `SM6225` (Snapdragon 685) |
| Plataforma / board | `bengal` / `khaje` |
| Device Tree `compatible` | `qcom,khaje-idp`, `qcom,khaje`, `qcom,idp` |
| Arquitetura | ARM64 |

## Estado atual do aparelho

- FDT ativo reanalisado; base Khaje índice 1 e overlay topaz entrada 51 foram pareados por MSM/board IDs. Há referências sanitizadas da base, overlay e FDT ativo em `device-tree/reference/` (não compiladas/não prontas para boot). Resumo em [`docs/device-tree-inventory.md`](docs/device-tree-inventory.md); ferramentas de inventário/extração em `tools/`; blobs privados em `google_drive/` ignorados pelo Git.
- Mapa de módulos ativos e dependências em [`docs/module-inventory.md`](docs/module-inventory.md), arquivo recebido em `google_drive/topaz-module-map.txt`.
- Sistema/ROM em execução: Android 17, API 37. O vendor/base do aparelho é Android 15; o fingerprint recebido (`Redmi/topaz_global/topaz:15/AQ3A.240829.003/OS2.0.204.0.VMGMIXM:user/release-keys`) reflete essa versão do vendor, não a versão do sistema Android 17.
- Slot ativo reportado: `_b`; as cinco imagens de boot foram recebidas e analisadas (incluindo `boot_b.img.gz`). Partições e resultados estão em [`docs/boot-partition-inventory.md`](docs/boot-partition-inventory.md). A combinação base DTB Khaje + overlay topaz (board ID `0x30022`) foi identificada; o `boot_b` confirma header v4 e kernel 5.15.211/Clang 20.
- Kernel em execução: `5.15.211dexter1-g42deba085a84`, compilado com Clang 20.0.0 segundo `/proc/version`.
- Há módulos em `/vendor/lib/modules`, `/vendor_dlkm/lib/modules` e `/system_dlkm/lib/modules`.
- A listagem mostra uma pasta `system_dlkm` identificada como `5.15.94`.
- `modinfo` reportou o mesmo `vermagic` para `msm_kgsl`, `msm_drm`, `camera` e `qca_cld3_wlan`: `5.15.41 SMP preempt mod_unload modversions aarch64`. Isso identifica o release usado ao compilar esses módulos; não é, sozinho, um fingerprint completo do KMI.

## Configuração recebida pelo Drive

O arquivo `google_drive/topaz-5.15.config` foi baixado e analisado; o usuário confirmou que `/proc/config.gz` no aparelho retorna o mesmo conteúdo. Ele tem características de uma configuração Android GKI 5.15 (`CONFIG_ANDROID=y`, `CONFIG_MODVERSIONS=y`, `CONFIG_TRIM_UNUSED_KSYMS=y`, LTO full e CFI). O cabeçalho, porém, identifica **Linux/arm64 5.15.78**, Clang 14.0.7 e uma whitelist do build `android13-5.15-2023-03`, enquanto `/proc/version` informa 5.15.211 / Clang 20. A discrepância está confirmada; os metadados parecem herdados ou gerados em etapas diferentes, então não devem ser usados para inferir o release/toolchain efetivos. A configuração embutida é útil como referência. O inventário dos módulos ativos e de suas dependências está concluído em [`docs/module-inventory.md`](docs/module-inventory.md); os quatro módulos críticos consultados reportam `vermagic 5.15.41`.

## Alvo confirmado

Alvo confirmado: **Linux 6.12 com Android/GKI**, para o sistema Android 17 em execução sobre vendor/base Android 15. A linha `android16-6.12-lts` é a base candidata; o commit e as ressalvas de proveniência estão em [`docs/gki-source-validation.md`](docs/gki-source-validation.md).

O KMI é específico da combinação de release Android e versão do kernel; a compatibilidade não é mantida ao trocar de branch/kernel. Portanto, os módulos atuais de 5.15 não podem ser presumidos compatíveis com 6.12: será necessário recompilá-los a partir de source ou portar/substituir os drivers necessários.

## Fontes e limitações conhecidas

- A árvore pública oficial da Xiaomi [`topaz-t-oss`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/topaz-t-oss) é uma referência Android 13/5.15.41, não uma árvore 6.12. Ela inclui drivers Khaje para GCC/DISPCC/GPUCC/debug clocks, RPM clocks, pinctrl e UFS PHY; interconnect Bengal; e fontes Goodix/FPC de fingerprint, minidump/DCVS/performance e `panel_event_notifier`.
- A mesma árvore pública não expôs KGSL (`msm_kgsl`), QCACLD/ICNSS2, o stack vendor camera-kernel/techpack, nem o driver touchscreen FocalTech específico. DRM/MSM upstream, CAMSS e drivers genéricos não são comprovadamente substitutos diretos dos drivers e HALs ativos.
- A base AOSP/common 6.12 consultada não tem DTS Khaje/SM6225/topaz nem providers Khaje/Bengal completos. O manifest Qualcomm Platform 5.0 R47 fornece um `soc-repo` com fontes Khaje/Bengal e uma DTS IDP genérica, mas não uma DTS topaz/tapas; a versão efetiva do common kernel não foi verificada (o Makefile do `soc-repo` diz 6.11.0 e o pin `kernel/common` não pôde ser recuperado). É referência de SoC/port, não substituição validada da base GKI. A série local [`0001–0014`](patches/README.md) inclui pinctrl Khaje (eGPIO), RPMCC, PHY UFS SM6225, interconnect Bengal, reguladores RPM-SMD, suporte de votos de tensão/debug clocks, providers GCC/DISPCC/GPUCC/debugcc e os headers dt-bindings que a base 6.12 não traz. Os 14 patches aplicam em sequência sobre o commit fixado, `git diff --check` passou e a verificação estática de includes fecha em 102/102; o `dt_binding_check` do CI (dt-schema) passou sem erros. As DTS/DTBO de topaz/tapas passaram a ser versionáveis e versionadas (`device-tree/source/` + `device-tree/kernel/`), com DTB/DTBO compilados pelo build do kernel. A comparação com o FDT real do aparelho está em [`docs/dts-fidelity-report.md`](docs/dts-fidelity-report.md): o DTBO do aparelho carrega nós de drivers proprietários (fingerprint, carregador, ANT, microfones, LED, one-wire) que ainda não têm fonte neste port.
- Até este levantamento, não foi localizada uma árvore completa 6.12 específica para topaz/tapas. Foi validado um mirror mantido da linha CodeLinaro `android16-6.12-lts`, descendente da branch AOSP `android16-6.12`; o R47 não substitui esse alvo sem validar o pin `kernel/common`. Detalhes, hash fixado e ressalvas de proveniência estão em [`docs/gki-source-validation.md`](docs/gki-source-validation.md).
- O mapa DTB/DTBO e os nós relevantes estão em [`docs/device-tree-inventory.md`](docs/device-tree-inventory.md); a matriz separa explicitamente o que há no common 6.12 do que oferecem a referência Xiaomi 5.15 e o `soc-repo` Qualcomm R47 (ref R67) em [`docs/driver-port-matrix.md`](docs/driver-port-matrix.md). Os `.ko` do aparelho identificam dependências, mas não são compatíveis com KMI 6.12 e não reconstituem todas as fontes proprietárias.

## Próximos passos

1. Fechar o backlog de DT-schema: escrever os bindings vendor das propriedades `qcom,*` que a DTS 5.15 usa (a maior fatia são ~550 erros de `dt-core.yaml`), completar o binding de pinctrl Khaje e alinhar os `clock-names` do GENI. Cada redução tem de baixar a linha de base do gate, nunca subi-la.
2. Revisar estaticamente as novas dependências de votos (RPM-SMD/regulator e clocks críticos) e mapear cada consumidor do FDT à série port, agora com o DTB compilado como referência.
3. Só então avançar para periféricos e paridade Android: KGSL/GPU, SDE/display, câmera, QCACLD/Wi‑Fi, fingerprint (FPC/Goodix), carregador e ANT; os nós desses periféricos só existem no DTBO real do aparelho e precisam ser recriados a partir da referência. Não reutilizar binários 5.15 no KMI 6.12.
4. Manter a validação no CI (`.github/workflows/dts-validate.yml`): clone do commit fixado `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`, aplicação da série, staging das DTS, `dtbs`, `dt-validate` com gate de regressão, `dt_binding_check` e build da imagem, com logs e artefatos publicados no branch `ci-artifacts`.
5. Antes de qualquer teste de boot, confirmar backups verificáveis de `boot` e recovery e um método de recuperação. Não sobrescrever partições durante a fase de levantamento.

**Não flashar nenhuma imagem produzida nesta fase de levantamento.**
