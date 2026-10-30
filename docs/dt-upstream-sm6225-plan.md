# Plano: DT upstream-style do SM6225/topaz para a base ACK 6.18

## Por que este documento

A série `patches-6.18/` compila e linka a `Image` na ACK
`android17-6.18` (run `40983813425`), mas a imagem ainda não tem
**DTB da placa** nesta base: a ACK não traz `sm6225.dtsi` e as DTS
do projeto (`device-tree/source/`) estão no formato vendor
(downstream), incompatível com os drivers/bindings upstream que a
série habilita. Este plano mapeia como construir `sm6225.dtsi` +
`sm6225-xiaomi-topaz.dts` no estilo upstream, em fatias validáveis,
sem inventar dados de hardware.

Estratégia de boot continua a híbrida já decidida
(`docs/boot-dependency-analysis.md`): primeiro marco = console
serial mínimo, sem stack vendor. Este documento cobre só a parte
Device Tree desse caminho na trilha 6.18.

## Âncoras e evidências disponíveis

| Fonte | Uso |
|---|---|
| `sm6115.dtsi` upstream (ACK 6.18, 3464 linhas) + placas `sm6115-fxtec-pro1x`, `sm6115p-lenovo-j606f` | **Modelo estrutural**: mesmo SoC-class Bengal; copiar a organização e trocar apenas o que o Khaje tiver de diferente comprovado. |
| `device-tree/reference/topaz-live-reference.dts` (13978 linhas, FDT vivo do aparelho) | **Fonte primária de dados**: endereços, IRQs, clocks, reguladores, reserved-memory, pinos. |
| `device-tree/source/` (54 arquivos vendor importados) | Tradução nó-a-nó vendor→upstream já praticada na trilha 6.12; ver `docs/dts-integration-status.md`, `docs/dts-fidelity-report.md`, `docs/device-tree-inventory.md`. |
| `pmos-tapas` / `sm6225-mainline` (referências externas registradas) | Mapa de hardware e prova de que o SM6225 sobe com kernel mainline; **não** é drop-in (drivers/DT próprios, outra base). |
| Bindings da própria série (patches 0001/0003/0005/0008/0011/0014/0030/0031/0032/0033) | Contrato que os nós precisam satisfazer (`dtbs_check` é o juiz). |

## Compatibles que a DT precisa declarar (estado atual da série)

Do SoC (drivers da série ou matches adicionados sobre upstream):

- `qcom,khaje-gcc`, `qcom,khaje-dispcc`, `qcom,khaje-gpucc` (+ debugcc)
  — clocks próprios do patch 0010; o SM6115 upstream usa outros
  compatibles, então os nós de clock **não** podem ser cópia direta.
- `qcom,khaje-pinctrl` — TLMM (0001/0002).
- `qcom,khaje-mdss`, `qcom,khaje-dpu`, `qcom,khaje` (match UBWC do
  0017 — é o compat de SoC que o FDT vendor declara na raiz; decidir
  o compat de raiz upstream aqui: provável `qcom,sm6225` novo, o que
  obriga a adicionar match UBWC para ele — item já anotado no
  README da série).
- `qcom,sm6225-dsi-phy-7nm` — DSI PHY (série).
- `qcom,sm6225-qmp-ufs-phy` (0005/0006) + host UFS — PHY em
  `0x4807000`, host em `0x4804000` (ver `docs/ufs-qmp-phy-port.md`);
  supplies `vdda-phy`/`vdda-pll` precisam de providers topaz
  reais comprovados no FDT, não os labels do IDP.
- `qcom,bengal-bimc` — interconnect (0007). **Pergunta aberta**:
  o driver declara um único compatible; confirmar se
  system_noc/config_noc entram como nós adicionais com dados
  próprios ou se o modelo é outro (rotas FDT conhecidas:
  system_noc → bimc → config_noc).
- RPM SMD (0008/0009): reguladores são descritos como recursos
  aninhados, não no formato upstream clássico — a DT deve seguir a
  *nossa* binding, com os trilhos do FDT (PM6125 etc.).
- `qcom,sm6225-adsp-pas` — PAS/ADSP (0026/0027/0028).
- `qcom,sm6225-sndcard` (0032) + macros LPASS com fallback
  SM6225→SM6115 (0030) + LPI pinctrl (0031): nós RX/TX/VA/SWD
  com os clocks do binding (VA: `mclk`, `dcodec`, `npl`).

Da placa topaz:

- Painel `xiaomi,m7-38-0c-0a` (0014) atrás do DSI, com o
  panel-event-notifier (0015) se o binding pedir.
- Touchscreen FT3519: **não há driver upstream** na base; o config
  exige `TOUCHSCREEN_EDT_FT5X06` por herança da 6.12. DT não deve
  declarar nó que nenhum driver casa — pendência de driver,
  não de DT.
- `ovti,wl2866d-i2c` (0033) no barramento I2C da câmera; sensores
  (S5KJN1 sem driver upstream, OV08D10 presente) dependem da
  decisão CAMSS vs Spectra, fora deste plano.

## Diferenças SM6225 × SM6115 a comprovar no FDT (não presumir)

1. **CPUs/clusters e OPPs** (Kryo 260: prime/cluster diferente do
   SM6115), `capacity-dmips-mhz`, idle states, cpufreq-hw/EPSS.
2. **Clock IDs e resets**: os headers `dt-bindings/clock` do SM6115
   upstream não servem para os controladores Khaje (0010) — a DT
   usa os IDs definidos pelos patches 0003/0010.
3. **MDSS 6.10 × 6.3**: base/len/IRQ do MDSS, DSI e PHY; catálogo
   já casado por compatible, mas o nó precisa dos recursos certos.
4. **QUP/GENI**: quantidade e endereços das instâncias SE
   (UART de console é o primeiro consumidor — marco serial).
5. **Interconnect**: conjunto de NoCs e larguras (ver pergunta
   aberta acima) e `interconnects` dos consumidores (UFS, MDSS...).
6. **Reserved-memory**: regiões do FDT vivo (rmtfs, modem, adsp,
   cdsp, cont-framebuffer etc.) copiadas com endereços reais.
7. **SMMU/apps_smmu, tsens, SCM, SEE, RPM glink** — presentes no
   SM6115; conferir compat/endpoints no FDT.

## Fatias propostas (cada uma = patch novo na série + gate CI)

Numeração continua a partir de 0034 em `patches-6.18/`.

- **S1 – SoC mínimo serial**: `sm6225.dtsi` com CPUs/PSCI/timer/GIC,
  `gcc`, `rpmcc`, TLMM, QUP+UART do console, interconnect mínimo,
  `smd-rpm`/reguladores base; `sm6225-xiaomi-topaz.dts` só com
  `chosen` (stdout-path), `memory`, reserved-memory e o UART.
  Gate: `dtbs` compila + `dtbs_check` dos arquivos novos no CI.
  Objetivo: paridade com o marco B2a da 6.12 (prompt no serial),
  quando houver aparelho para testar.
- **S2 – Storage**: UFS host+PHY com supplies/ICC reais; gate
  `dtbs_check`. (Cargas `vdda-*` comprovadas no FDT vivo:
  85700/18300 µA sobre `pm6125_l4`/`pm6125_l18` — ver 0006.)
- **S3 – Display**: MDSS/DPU/DSI/PHY + painel M7 + dispcc/gpucc;
  validar também o comportamento de TE/modo-comando anotado no
  0016 quando houver hardware.
- **S4 – Áudio/ADSP**: LPASS (macros, LPI pinctrl, SoundWire),
  sndcard e ADSP PAS com firmware-name do 0026.
- **S5 – Placa**: I2C/GPIO expanders, WL2866D, leds/teclas, PMIC
  (PM6125 via SPMI), thermal-zones a partir do FDT.
- **S6 – Câmeras**: só após decisão CAMSS vs Spectra.

## Gate de CI a adicionar (junto da S1)

No job `kernel-build` do `google-mainline.yml`, após o `Image`:
`make ARCH=arm64 ... dtbs` (ao menos o DTB novo) e
`make dtbs_check DT_SCHEMA_FILES=<bindings/nós novos>` em passo
separado reportando na mesma issue `ci-report`. `dt-doc-validate`
completo das bindings modificadas pela série inteira é desejável,
mas como passo próprio (pode ser ruidoso no início; começar pelos
arquivos novos da S1).

## Fora de escopo / decisões pendentes do dono

- ~~Promover a série 6.18 a principal~~ — **decidido pelo dono:
  prosseguir com a 6.18.** Destino final da trilha 6.12 (congelar
  vs. remover) é decisão separada, sem pressa.
- ~~Valores `init_load_uA` da PHY UFS e providers de
  `vdda-phy`/`vdda-pll`~~ — resolvido do FDT vivo (85700/18300 µA,
  `pm6125_l4`/`pm6125_l18`); falta só a *tradução* dos nós para a
  binding upstream na S2 e, um dia, a confirmação em runtime.
- Informações do aparelho ainda necessárias (confirmações de
  estado atual, backups de segurança e canal de log de boot):
  ver `docs/hardware-info-needed.md`.
- Touch FT3519 e câmera S5KJN1/CAMSS: frentes de driver próprias.

## Disciplina (a mesma das fatias anteriores)

Nenhum endereço, IRQ, clock ou trilho entra na DT sem fonte
citável (FDT vivo, DTS vendor importado ou binding). Onde o SM6115
e o FDT divergirem, vence o FDT; onde o FDT for vendor-format, o
nó é *traduzido* para o binding upstream, nunca colado. Cada fatia
só é dada como pronta com `dtbs`/`dtbs_check` verdes no CI — e
isso continua não sendo evidência de boot.
