# Inventário da Device Tree — Redmi Note 12 4G (topaz/tapas)

## Fonte e identidade

- FDT ativo extraído de `/sys/firmware/fdt`: `google_drive/topaz-live.dtb`.
- Flattened Device Tree v17; 357.122 bytes, 2.138 nós; SHA-256 `8916c9594b2b2dd605f441c2b096c3eee21a546df2b824450a79d70eea8cb5b0`.
- Decompilações de referência com propriedades voláteis de `/chosen` removidas: [`base Khaje`](../device-tree/reference/khaje-base-reference.dts), [`overlay topaz 51`](../device-tree/reference/topaz-overlay-51-reference.dtso) e [`FDT ativo mesclado`](../device-tree/reference/topaz-live-reference.dts). São apenas material de análise: sem validação `dtc`/`dtbs_check`, sem suporte para boot. Regeneração e limitações em [`device-tree/reference/README.md`](../device-tree/reference/README.md).
- `model`: `Qualcomm Technologies, Inc. KHAJE IDP nopmi topaz`.
- Root `compatible`: `qcom,khaje-idp`, `qcom,khaje`, `qcom,idp`.
- IDs do FDT ativo: MSM `0x206` / subtype `0x10000`; board `0x30022` / variant `0`.

## Correspondência reprodutível de DTB e DTBO

O `vendor_boot_b.img` é v4 e contém seis FDTs concatenados na região DTB. O índice 1 é a base Khaje com MSM ID `0x206`. O `dtbo_b.img` contém uma tabela v0 com 52 entradas; a entrada 51 é o overlay topaz com MSM ID `0x206` e board ID `0x30022`. Esses são os IDs observados no FDT ativo. A entrada 50 é uma variante Khaje distinta (MSM ID `0x24a`) e não corresponde ao aparelho capturado. O overlay selecionado tem 50 fragments e exige symbols/fixups contra a base; ele inclui configurações de display, touch, câmera, áudio e alimentação, com variantes de touchscreen que aparecem desabilitadas no FDT ativo. Uma comparação estática encontrou 126 símbolos externos em `__fixups__`, todos presentes entre os 840 símbolos da decompilação da base real. Já o include closure da DTS Qualcomm R47 (`khaje.dtsi` + `khaje-idp-nopmi.dtsi`, commit `66167e56588bd7c0c9ec91e1e5c464512f6c4db6`) fornece apenas 82 desses nomes; 44 não foram encontrados. Portanto a DTS IDP R47 não pode ser usada sem reconciliação como base do DTBO topaz. Os 44 nomes ausentes aparecem nos fragments 7, 30, 34, 39, 42–46 e 49 (antena/QUP, display, touchscreen, áudio/DSP e câmera); os símbolos usados pelos fragments UFS 11–12 existem na árvore R47. A comparação de símbolos não equivale a compilar/aplicar o overlay.

A extração pode ser repetida, sem salvar artefatos no repositório, com:

```sh
python3 tools/extract_android_dt.py \
  google_drive/vendor_boot_b.img google_drive/dtbo_b.img \
  --msm-id 0x206 --board-id 0x30022 \
  --out-dir /tmp/topaz-dt
python3 tools/fdt_inventory.py google_drive/topaz-live.dtb
```

O script seleciona a base pelo MSM ID e o overlay pelo par MSM/board ID; os arquivos extraídos vão somente para o diretório passado em `--out-dir`. O DTB ativo continua sendo a referência já mesclada em runtime: a inspeção abaixo não presume que apenas combinar os dois blobs produza uma imagem pronta para boot.

## Nós relevantes observados no FDT ativo

| Bloco | Compatibles / caminhos relevantes | Observação para 6.12 |
|---|---|---|
| Clocks | `qcom,rpmcc-khaje`; `qcom,khaje-gcc`; `qcom,khaje-dispcc`; `qcom,khaje-gpucc`; `qcom,khaje-debugcc` | A série local 0003/0004 adiciona o binding e o descritor RPMCC usando os objetos SMD-RPM da base 6.12; preserva o voto BIMC `INT_MAX` apenas no active set e keepalives de XO/CNOC/SNOC/QUP. Os IDs RPM usados pelo phandle `0x23` no FDT (`0, 1, 4–8, 28–29, 68, 70, 106–111`) estão mapeados; os pares RF_CLK1/2 `14–17` também constam do descritor, embora não sejam consumidores nesta captura. Os patches 0010/0011 acrescentam classes de voltage-corner via reguladores RPM-SMD, hooks CCF/PLL/RCG, medição debug-mux, GCC/DISPCC/GPUCC/debugcc, schemas e propriedades `qcom,critical-clocks`/`qcom,critical-devices` no binding comum. A varredura estática dos specifiers no DTS mesclado encontrou 95 IDs GCC, 11 DISPCC, 5 GPUCC e 17 RPM distintos, todos presentes nos arrays/descriptors locais. No GCC (phandle `0x81`), o phandle crítico `0xc3` encontra o índice 94 (`GCC_QUPV3_WRAP0_S1_CLK`) no ancestral `i2c@4a84000` e os índices 104/105 no wrapper ascendente; o helper mantém essas referências de clock preparadas/habilitadas enquanto o provider está bound. Foi necessário implementar `GCC_DISP_AHB_CLK` ID 60 no CBCR `0x1700c`, conforme o modelo SM6115/SM6125 presente no alvo, porque o FDT Khaje o consome. Os schemas novos passaram apenas por parsing YAML; não houve validação formal DT-schema nem compilação. R47 continua referência de plataforma, não prova da API/build common 6.12. |
| Reguladores RPM-SMD | Nós `rpm-regulator-*` filhos do SMD-RPM, compatível de recurso `qcom,rpm-smd-regulator-resource` e filhos `qcom,rpm-smd-regulator`. | A série 0008/0009 adiciona bindings/header e driver para o layout aninhado, mantém o caminho convencional de PMIC, separa rails físicas PM6125 de votos de nível/floor e envia os sets active/sleep. Revisão do FDT topaz: 30 pais de recurso, 25 filhos físicos habilitados e 8 filhos de votos de nível habilitados, sem divergência de nome/tipo/ID. Os bindings RPM-SMD passaram apenas por parsing YAML; DT-schema, compilação e boot continuam pendentes. |
| Interconnect | `qcom,bengal-clk_virt`, `qcom,bengal-mmnrt_virt`, `qcom,bengal-mmrt_virt`, `qcom,bengal-system_noc`, `qcom,bengal-config_noc`, `qcom,bengal-bimc` | A base inicial common 6.12 tem `sm6115.c`, mas não Bengal. O patch local 0007 porta a topologia para o framework `qcom_icc`/`icc-rpm` do alvo, com adaptação de QoS, IDs, clocks e slots esparsos; a auditoria estática cobre 92 nós, 36 arrays de links, 184 IDs RPM e 22 QoS boxes, e as 126 specs da FDT resolvem para slots presentes. Ainda não passou DT-schema, compilação ou teste de boot. R47 continua referência de SoC, não prova da versão efetiva do kernel. |
| Pinctrl SoC | `/soc/pinctrl@400000`, `qcom,khaje-pinctrl` | A base 6.12 não tem o controlador; [`binding 0001`](../patches/0001-dt-bindings-pinctrl-khaje.patch) e [`driver 0002`](../patches/0002-pinctrl-khaje.patch) agora documentam 185 funções mux, incluindo eGPIO GPIO98–112, e adaptação estática para `msm_pingroup`/`pinfunction` do alvo. O core 6.12 não tem a API vendor `msm_gpio_mpm_wake_set()`; o impacto em wake depende de validação. Aplicação e `dt-doc-validate` passaram; ainda sem compilação, `dtbs_check` ou boot test. |
| UFS | `/soc/ufshc@4804000`, `qcom,ufshc`; `/soc/ufsphy_mem@4807000`, PHY Khaje legado | O host UFS tem binding genérico; o PHY era Khaje-específico. Os patches locais 0005 (binding) e 0006 (driver) agora portam `qcom,sm6225-qmp-ufs-phy` para o QMP upstream via `qmp_phy_cfg`; a comparação com os dados R47 confirma as tabelas G1–3, G4, Rate B e duas lanes. O host no FDT limita TX/RX a Gear 3. Falta traduzir a estrutura downstream para a binding upstream, mapear clocks, reguladores, domínio e reset e validar. Detalhes: [`port da PHY UFS`](ufs-qmp-phy-port.md). |
| GPU | `/soc/qcom,kgsl-3d0@5900000`, `qcom,kgsl-3d0`; nós KGSL/SMMU associados | A ROM carrega `msm_kgsl`; KGSL não foi encontrado nem no common 6.12 nem na árvore Xiaomi pública consultada. DRM/MSM upstream não é substituto binário nem equivalente automático do contrato KGSL/HAL. |
| Display | `qcom,sde-kms`, `qcom,dsi-ctrl-hw-v2.4`, `qcom,dsi-phy-v4.1`, `qcom,dsi-display` | Painel selecionado pelo phandle `0x345`: `m7 38 0c 0a video mode fhdp dsi panel`, 1080×2400; modos até 120 Hz e refresh dinâmico de 120/90/60 Hz. Há DRM/MSM upstream, mas catálogo DPU, DSI, painel, energia e userspace precisam ser validados para Khaje. |
| Touch | I²C FocalTech `focaltech,fts` em `0x38` e Goodix `goodix,gt9896` em `0x5d`, ambos com `status = "okay"`; Synaptics `synaptics,tcm-i2c` e Novatek `novatek,NVT-ts` estão `disabled` | A captura de módulos confirma `focaltech_ts_i2c` carregado e `goodix_ts_9896` não carregado. Isso prioriza o nó FocalTech, mas o protocolo/CI exato ainda precisa ser confirmado. `edt-ft5x06` só é alternativa se houver compatibilidade real. |
| Câmera | `qcom,cci-v1.2`, `qcom,cam-cpas`, CPAS/CDM, ISP/TFE/OPE e nós de sensor | `camera.ko` está carregado. A fonte separada `vendor_qcom_opensource_camera-kernel/topaz-t-oss` foi localizada; CAMSS V4L2 não é substituição direta. A DTS local descreve periféricos/sensores, mas ainda não o bloco SoC da FDT. Ver [`camera-port-audit.md`](camera-port-audit.md). |
| Vídeo | `/soc/qcom,vidc@5a00000`, `qcom,msm-vidc-khaje` e `qcom,msm-vidc-ar50lt` | Common 6.12 contém Venus upstream; a tabela de plataforma, firmware, buffers e interface do HAL precisam ser compatíveis antes de usá-lo. |
| Impressão digital | `goodix,fingerprint` e `fpc,fpc1020` aparecem na FDT | O módulo carregado na captura é `goodix_fp`; não foi observado módulo FPC carregado. A árvore Xiaomi 5.15 contém código de fingerprint Goodix e FPC, a portar e confirmar para o sensor realmente usado. |
| Outros | `xiaomi-touch`, nós PM6125/SPMI, ADSP/CDSP/modem e USB | Exigem configuração e revisão individual; a presença de um nó ou driver genérico não prova que a interface vendor 5.15 será atendida em 6.12. |

## Fontes usadas para o mapeamento

- Base Android/GKI candidata: `EdMory/android_kernel_common_sm8850`, branch `aosp-new/android16-6.12-lts`, commit fixado `0efd3abd3c356d644ea49f6ed37e9830b78d34e3` (mirror de terceiro; proveniência e limitações em [`gki-source-validation.md`](gki-source-validation.md)).
- Referência Xiaomi: `MiCode/Xiaomi_Kernel_OpenSource`, branch `topaz-t-oss`, commit observado `345999da0be9cd37afdf87b15449d30b585a7091` (base vendor 5.15, não alvo final).
- A listagem **AOSP/common** qcom DTS 6.12 consultada não contém `sm6225`/`khaje` nem uma placa topaz. Uma fonte separada, Qualcomm Platform 5.0 R47, contém `qcom/khaje.dtsi`, `khaje-pinctrl.dtsi` e `khaje-idp-nopmi.*`, mas não DTS/DTBO topaz/tapas; o IDP é referência de SoC, não substituto da base/overlay capturados. Detalhes e pins em [`gki-source-validation.md`](gki-source-validation.md).
- O source Xiaomi 5.15 e o `soc-repo` R67 do Platform 5.0 R47 incluem `debugcc-khaje.c`, `dispcc-khaje.c`, `gcc-khaje.c`, `gpucc-khaje.c`, `pinctrl-khaje.c`, dados RPM, interconnect Bengal e UFS PHY Khaje. O segundo é uma referência mais recente de implementação Qualcomm; seu Makefile declara 6.11.0 e o `kernel/common` do manifest ainda não pôde ser comparado/validado como alvo GKI. O mapeamento mais amplo está em [`driver-port-matrix.md`](driver-port-matrix.md).

## Próximos passos de port

1. Construir um DTS/DTBO 6.12 versionável a partir da base selecionada e do overlay topaz, revisando bindings e removendo artefatos exclusivos do dump em runtime; não copiar o DTB de produção como se fosse fonte DTS validada.
2. Antes da compilação, revisar a série local 0001–0011 de pinctrl/RPMCC/PHY UFS/interconnect/reguladores RPM-SMD/clocks Khaje; concluir o DTS/DTBO versionável e a configuração GKI/defconfig; validar formalmente os bindings e a fundação antes de avançar aos periféricos. Os providers GCC/DISPCC/GPUCC/debugcc e a compatibilidade de votos de tensão já estão portados estaticamente, ainda sem build, `dtbs_check` ou boot test.
3. Em seguida validar display/touch; tratar KGSL, câmera, Wi‑Fi e integração do HAL como bloqueadores independentes, não resolvidos pela DT.
4. A etapa de build ficará para GitHub Actions, depois que o port e a configuração estiverem definidos. Nenhuma imagem foi compilada ou gravada; não flashar durante o levantamento.

Não foram incluídos números de série, endereços MAC nem payloads de calibração neste resumo. Os blobs de entrada são artefatos privados de análise e ficam ignorados pelo Git.
