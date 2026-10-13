# Defconfig do topaz (fragmento sobre o GKI 6.12)

Estado: **fragmento verificado contra o Kconfig 6.12 na CI** (commit `c24c3bc`, run `38326327058`: verificação de símbolos passou, 42 símbolos pedidos). Inclui display (clocks `SM_DISPCC/GPUCC/DEBUGCC_6225` e pilha `DRM_MSM` com DPU, DSI e PHY 14nm), sem painel e sem GPU. No mesmo commit, o build de kernel (run `38326327090`: parcial e completo) passou e os clocks de display compilaram. Isso prova que o código compila na CI; não prova que a tela acende, e nada foi flashado.

## Arquivos

- [`topaz.fragment`](topaz.fragment): símbolos `CONFIG_` do port topaz, aplicados sobre `arch/arm64/configs/gki_defconfig` da base fixada `0efd3abd`.
- [`../../tools/check_defconfig.sh`](../../tools/check_defconfig.sh): roda `gki_defconfig`, `merge_config.sh -m`, `olddefconfig` e compara cada símbolo pedido com o `.config` final. Relatório em `defconfig-report.txt`.

## Como os símbolos foram escolhidos

Cada linha vem de um compatível da DT curada (`device-tree/topaz/`) ou de um símbolo criado pelos patches da série local. Não vem da configuração do aparelho: `google_drive/topaz-5.15.config` é uma configuração GKI genérica 5.15.78. Ela marca como `is not set` os drivers Qualcomm de SoC (`PINCTRL_MSM`, `COMMON_CLK_QCOM`, `SCSI_UFS_QCOM`, `PHY_QCOM_QMP`), porque no aparelho eles são módulos de fornecedor. Por isso ela não serve como fonte direta.

## O que fica de fora (escopo C)

Display, câmera, áudio, USB, SD/eMMC, carregador, toque, impressão digital, DSP/modem e Wi-Fi/BT. Os mesmos subsistemas saíram da DT curada.

## Correções feitas pela verificação

- `CONFIG_QCOM_CPUFREQ_HW` → `ARM_QCOM_CPUFREQ_HW`; `CONFIG_GPIO_KEYS` → `KEYBOARD_GPIO`; `CONFIG_PINCTRL_SPMI_GPIO` → `PINCTRL_QCOM_SPMI_PMIC` (nomes do Kconfig 6.12).
- Dependências que o `olddefconfig` exigia: `COMMON_CLK_QCOM` (para `QCOM_CLK_SMD_RPM`), `ARM_SMMU` (para `ARM_SMMU_QCOM`), `PINCTRL_MSM` (bloco `if PINCTRL_MSM` de `Kconfig.msm`, para `PINCTRL_KHAJE`) e `PHY_QCOM_QMP` (bloco `if PHY_QCOM_QMP`, para `PHY_QCOM_QMP_UFS`).

## Limites conhecidos

- Não há módulos de fornecedor nem o stack de display/GPU. Os módulos 5.15 do aparelho não são compatíveis com 6.12 (KMI diferente).
- `qcom,pwm-lpg` e `qcom,qpnp-vibrator-ldo-tz` da DT curada não têm símbolo mapeado aqui.
- `qcom,smem` não aparece como nó na curada; `QCOM_SMEM` entra porque o RPM-SMD depende dele. Confirmar quando a DT tiver o nó.
- A verificação da CI diz quais símbolos o Kconfig 6.12 não aceita e quais o `olddefconfig` desativou por dependência. Ela não prova que o kernel compila nem que o aparelho bota.
