# Defconfig do topaz (fragmento sobre o GKI 6.12)

Estado: **rascunho, não validado pela CI ainda.** Nada aqui foi compilado localmente, nem flashado.

## Arquivos

- [`topaz.fragment`](topaz.fragment): símbolos `CONFIG_` do port topaz, aplicados sobre `arch/arm64/configs/gki_defconfig` da base fixada `0efd3abd`.
- [`../../tools/check_defconfig.sh`](../../tools/check_defconfig.sh): roda `gki_defconfig`, `merge_config.sh -m`, `olddefconfig` e compara cada símbolo pedido com o `.config` final. Relatório em `defconfig-report.txt`.

## Como os símbolos foram escolhidos

Cada linha vem de um compatível da DT curada (`device-tree/topaz/`) ou de um símbolo criado pelos patches da série local. Não vem da configuração do aparelho: `google_drive/topaz-5.15.config` é uma configuração GKI genérica 5.15.78. Ela marca como `is not set` os drivers Qualcomm de SoC (`PINCTRL_MSM`, `COMMON_CLK_QCOM`, `SCSI_UFS_QCOM`, `PHY_QCOM_QMP`), porque no aparelho eles são módulos de fornecedor. Por isso ela não serve como fonte direta.

## O que fica de fora (escopo C)

Display, câmera, áudio, USB, SD/eMMC, carregador, toque, impressão digital, DSP/modem e Wi-Fi/BT. Os mesmos subsistemas saíram da DT curada.

## Limites conhecidos

- Não há módulos de fornecedor nem o stack de display/GPU. Os módulos 5.15 do aparelho não são compatíveis com 6.12 (KMI diferente).
- `qcom,pwm-lpg` e `qcom,qpnp-vibrator-ldo-tz` da DT curada não têm símbolo mapeado aqui.
- `qcom,smem` não aparece como nó na curada; `QCOM_SMEM` entra porque o RPM-SMD depende dele. Confirmar quando a DT tiver o nó.
- A verificação da CI diz quais símbolos o Kconfig 6.12 não aceita e quais o `olddefconfig` desativou por dependência. Ela não prova que o kernel compila nem que o aparelho bota.
