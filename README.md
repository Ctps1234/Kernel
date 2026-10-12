# Redmi Note 12 4G — kernel Android GKI 6.12

Projeto de bring-up/port para o Redmi Note 12 4G (topaz/tapas). **Estado: par FDT/DTBO confirmado e série local 0001–0011 preparada: pinctrl/RPMCC Khaje, PHY UFS SM6225, interconnect Bengal, reguladores RPM-SMD e providers GCC/DISPCC/GPUCC/debugcc com votos de tensão. A série completa aplica em sequência e passou revisão estática; ainda não há DTS/DTBO de fonte buildável, defconfig final, compilação ou imagem para testar/flashar.**

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
- A base AOSP/common 6.12 consultada não tem DTS Khaje/SM6225/topaz nem providers Khaje/Bengal completos. O manifest Qualcomm Platform 5.0 R47 fornece um `soc-repo` com fontes Khaje/Bengal e uma DTS IDP genérica, mas não uma DTS topaz/tapas; a versão efetiva do common kernel não foi verificada (o Makefile do `soc-repo` diz 6.11.0 e o pin `kernel/common` não pôde ser recuperado). É referência de SoC/port, não substituição validada da base GKI. A série local [`0001–0011`](patches/README.md) inclui pinctrl Khaje (eGPIO), RPMCC, PHY UFS SM6225, interconnect Bengal, reguladores RPM-SMD, suporte de votos de tensão/debug clocks e providers GCC/DISPCC/GPUCC/debugcc. Os 11 patches aplicam em sequência e `git diff --check` passou; PyYAML confirmou sintaxe de YAML, não DT-schema. O binding pinctrl passou `dt-doc-validate`; RPMCC/UFS/Bengal/RPM-SMD e os quatro novos bindings de clock ainda aguardam validação formal. DTS/DTBO e defconfig ainda faltam; não houve compilação nem teste de boot.
- Até este levantamento, não foi localizada uma árvore completa 6.12 específica para topaz/tapas. Foi validado um mirror mantido da linha CodeLinaro `android16-6.12-lts`, descendente da branch AOSP `android16-6.12`; o R47 não substitui esse alvo sem validar o pin `kernel/common`. Detalhes, hash fixado e ressalvas de proveniência estão em [`docs/gki-source-validation.md`](docs/gki-source-validation.md).
- O mapa DTB/DTBO e os nós relevantes estão em [`docs/device-tree-inventory.md`](docs/device-tree-inventory.md); a matriz separa explicitamente o que há no common 6.12 do que oferecem a referência Xiaomi 5.15 e o `soc-repo` Qualcomm R47 (ref R67) em [`docs/driver-port-matrix.md`](docs/driver-port-matrix.md). Os `.ko` do aparelho identificam dependências, mas não são compatíveis com KMI 6.12 e não reconstituem todas as fontes proprietárias.

## Próximos passos

1. Concluir a fundação de boot antes dos periféricos: transformar a base Khaje + overlay topaz `0x30022` em DTS/DTBO 6.12 versionáveis; integrar e revisar a série 0001–0011 (pinctrl, RPMCC, UFS PHY, Bengal, RPM-SMD e clocks Khaje); validar bindings/DT-schema e fechar a configuração GKI/defconfig.
2. Revisar estaticamente as novas dependências de votos (RPM-SMD/regulator e clocks críticos) e mapear cada consumidor do FDT à série port; não compilar antes de a integração de boot solicitada estar completa.
3. Só então avançar para periféricos e paridade Android: KGSL/GPU, SDE/display, câmera, QCACLD/Wi‑Fi, FocalTech e Goodix; não reutilizar binários 5.15 no KMI 6.12.
4. Após concluir a integração e fechar a configuração, usar GitHub Actions para clonar o commit fixado `0efd3abd3c356d644ea49f6ed37e9830b78d34e3`, compilar e arquivar logs/hashes. Nenhum build foi iniciado nesta etapa.
5. Antes de qualquer teste de boot, confirmar backups verificáveis de `boot` e recovery e um método de recuperação. Não sobrescrever partições durante a fase de levantamento.

**Não flashar nenhuma imagem produzida nesta fase de levantamento.**
