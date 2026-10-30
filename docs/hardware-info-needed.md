# Informações do aparelho: o que falta (e o que já temos)

Pedido ao dono do topaz para destravar a fase de **teste em
hardware** da trilha 6.18. Para continuar *escrevendo código*
(DT upstream S1, a partir do FDT já versionado) **não falta nada
desta lista** — ela fecha os furos que só o aparelho físico
resolve e prepara o primeiro boot com segurança.

## Respostas recebidas do dono (e o que elas impõem)

- **Aparelho principal, funcionando, NÃO pode parar.** Isto é a
  restrição dominante: **nenhum flash experimental neste
  aparelho** até existir (a) backup completo e verificado
  incluindo `recovery` do slot ativo, (b) caminho de volta ao
  sistema atual ensaiado/documentado passo a passo, e
  (c) um método de teste que não deixe o telefone inutilizável
  se o kernel novo travar no primeiro segundo. Enquanto isso,
  todo o avanço é via CI (config + build + `dtbs_check`) e
  evidências coletadas do sistema atual em somente leitura.
- **Bootloader desbloqueado.** Bom: remove o bloqueio/wipe do
  unlock de qualquer plano futuro. Não autoriza nada por si só
  (AVB/`vbmeta` e fallback continuam a desenhar antes).
- **Mesma ROM da captura, com root.** A coleta de runtime
  (30/out/2026) mostrou contexto SELinux `u:r:ksu:s0`, ou
  seja, **KernelSU** (não Magisk) — o tanto faz para a
  coleta, mas fica registrado. Os dumps de
  `boot`/`vendor_boot`/`init_boot`/`dtbo` continuam válidos:
  fingerprint e `dtb_idx=1`/`dtbo_idx=51` batem com a coleta
  (detalhes em "Coleta recebida" abaixo).
- **Sem conversor UART.** O marco "prompt no console serial"
  (B2a) não é o primeiro teste possível. Alternativas a
  desenhar nesta ordem:
  1. **ramoops/pstore**: o FDT vivo já reserva
     `ramoops@5d000000` (2 MiB; record 256 KiB, console
     512 KiB, pmsg 1 MiB) — a mesma região que o kernel stock
     lê. Para ela servir desde o boot inicial, a S1 precisa
     incluir o nó `ramoops` na DT nova **e** o fragmento subir
     `CONFIG_PSTORE_RAM=y` + `CONFIG_PSTORE_CONSOLE=y` (hoje a
     ACK traz `PSTORE_RAM=m`, inútil para panic/hang cedo e
     para o initramfs mínimo, que não carrega módulos). Leitura
     seria via reboot de volta ao sistema atual
     (`/sys/fs/pstore`) — formato ramoops é compatível entre
     kernels, mas a sobrevivência da RAM no reboot forçado
     deste bootloader ainda é hipótese a validar, não fato.
  2. **Splash contínuo** (`cont_splash_region@5c000000` no
     FDT): no mínimo um sinal de 1 bit — se travar antes do
     display, a tela fica no logo; útil só como diagnóstico
     grosseiro.
  3. **ADB no initramfs**: só depois que USB (DWC3/PHY) e um
     `adbd` entrarem no caminho — fase B2b, posterior.
- Ainda em aberto (menor): NFC sim/não, RAM exata, tela
  original vs. trocada, recovery custom instalada ou não, e
  SO do PC. Storage a coleta já fechou: **128 GB** (SK hynix
  `HN8T062EHKX039`), com microSD de 32 GB presente.

## Já temos — não precisa enviar de novo

Da captura anterior (ver `docs/device-tree-inventory.md` e
`docs/boot-partition-inventory.md`):

- Identidade: Redmi Note 12 4G **topaz** global,
  `KHAJE IDP nopmi topaz`, MSM ID `0x206`, board ID `0x30022`.
- FDT vivo mesclado + DTB base (índice 1) + overlay 51,
  decompilados em `device-tree/reference/`.
- Imagens do slot `_b` (no Drive, fora do Git): `boot`,
  `vendor_boot`, `init_boot`, `dtbo`, `vbmeta`, com hashes.
- Inventário de módulos 5.15 carregados, painel selecionado
  (`m7 38 0c 0a`, 1080×2400), touch FocalTech em uso
  (`focaltech_ts_i2c`), fingerprint Goodix em uso.
- UFS: PHY em `0x4807000`, host em `0x4804000` limitado a Gear 3,
  supplies `vdda-phy=pm6125_l4` / `vdda-pll=pm6125_l18` com
  máximos 85700/18300 µA (do próprio FDT).

## Coleta recebida (30/out/2026, pasta "Topaz info" no Drive)

Rodada via `collect_ondevice_topaz.sh` com `COLLECT_RECOVERY=1`
(18 arquivos, hashes conferidos no `SHA256SUMS` do pacote).
Resumo do que ela confirma — nenhum identificador do aparelho
foi transcrito para este repositório:

- **Sistema idêntico à captura**: fingerprint
  `Redmi/topaz_global/topaz:15/AQ3A.240829.003/OS2.0.204.0.VMGMIXM`,
  sistema Android 17 (SDK 37), slot `_b`, `dtb_idx=1`,
  `dtbo_idx=51`, SKU de hardware `m7n`, `hwversion 2.39.0`.
  Os dumps de referência continuam válidos para a DT S1.
- **FDT vivo**: 357122 bytes — mesmo tamanho do
  `topaz-live.dtb` guardado; o sha256 difere, como esperado:
  `/sys/firmware/fdt` carrega campos voláteis por boot
  (kaslr/rng seed etc.). Com fingerprint e índices de DTB/DTBO
  iguais, a referência em `device-tree/reference/` segue válida.
- **Bootloader/AVB**: o bootconfig diz
  `verifiedbootstate=orange` (desbloqueado, como informado),
  enquanto as props `ro.boot.*` reportam `green`/`locked` —
  spoof de integridade da ROM/KSU. Para decisões de AVB vale
  o bootconfig, não as props.
- **Cmdline real** (filtrada): `console=ttyMSM0,115200n8`,
  `log_buf_len=2M`, painel forçado
  `qcom,mdss_dsi_panel_m7_38_0c_0a_fhdp_video`, touch
  `focaltech_ts`, fingerprint Goodix, `buildvariant=userdebug`.
- **Root**: KernelSU (`u:r:ksu:s0`), não Magisk.
- **Storage**: UFS SK hynix `HN8T062EHKX039` (128 GB);
  microSD de 32 GB presente (`mmcblk1`) — mídia externa útil
  para cópias de backup.
- **Partições**: A/B virtual, `super` de ~7,0 GiB com grupo
  `xiaomi_dynamic_partitions_b` (odm/product/system/
  system_dlkm/system_ext/vendor/vendor_dlkm); mapa `by-name`
  confere com o inventário anterior.
- **`recovery_b` extraída por leitura**: 100 MiB, sha256
  registrado no pacote e imagem guardada na pasta do Drive
  (fora do Git). Fecha o maior furo do item 3.
- **Entrada**: touch `fts_ts` (1080×2400, I2C) + `gpio-keys` +
  `qpnp_pon`; áudio `bengal-idp-snd-card`.
- Limites desta rodada: `dmesg` cobre só as últimas ~9 min de
  runtime (uptime de ~6 dias; sem log de boot), e o
  `regulator_summary` não veio (debugfs desmontado — opcional:
  montar com `mount -t debugfs debugfs /sys/kernel/debug`
  como root e reler; os valores do FDT já bastam por ora).

## 1) Respostas rápidas (5 min, sem ferramenta)

*Status: itens 1, 3, 4 e 6 respondidos (ver "Respostas
recebidas" acima). Restam 2 (SKU/tela) e 5 (PC/SO), não
bloqueantes.*

1. O aparelho está **funcionando hoje**, bootando normal? É
   aparelho **principal ou de bancada** (pode ficar dias fora do
   ar se um teste der errado)?
2. **SKU**: tem NFC? Memória/armazenamento (ex. 6/128)? A tela é
   a **original** ou já foi trocada? (Painel trocado pode ser
   outra variante que não a `m7 38 0c 0a` do FDT.)
3. **Bootloader desbloqueado?** (cadeado aberto no boot /
   "Mi Unlock status" nas opções de desenvolvedor)
4. **ROM e root atuais**: continua a mesma da captura
   (sistema Android 17 sobre vendor 15, slot `_b`)? Tem
   Magisk/root funcional? Recovery custom instalada (qual)?
5. Tem **PC com adb/fastboot** funcionando com ele (qual SO)?
6. **Canal de log do primeiro boot**: tem conversor USB-UART
   (1,8 V) e disposição/experiência para abrir o aparelho até
   os test points — ou o primeiro teste precisa ser **sem abrir**
   (aí desenhamos para pstore/display/ADB em vez de serial)?

> **Não** desbloqueie o bootloader só para responder isto:
> no Xiaomi o unlock apaga os dados. Estado atual basta.

## 2) Coleta somente-leitura via adb (quando puder)

A coleta padrão é somente leitura e não toca nenhuma partição.
A única exceção é o modo opcional `COLLECT_RECOVERY=1`, que lê a
partição `recovery` e grava a imagem temporária em
`/sdcard/Download` para depois baixá-la ao PC. O jeito curto é o script
[`tools/collect_topaz_info.sh`](../tools/collect_topaz_info.sh),
rodado no seu PC com o aparelho autorizado no adb — ele faz
exatamente os comandos abaixo (usa o root se houver, filtra
seriais de cmdline/bootconfig e gera `SHA256SUMS`):

```sh
tools/collect_topaz_info.sh ./topaz-info
# opcional, com root: tambem despeja recovery_<slot>.img
COLLECT_RECOVERY=1 tools/collect_topaz_info.sh ./topaz-info
```

Revise a pasta antes de subir ao Drive (o `dmesg` pode conter
MACs). A saída local `topaz-info/` na raiz deste repositório
também está no `.gitignore`, para não entrar no Git por acidente.

### Alternativa: direto pelo celular (Termux + root, sem PC)

Baixe [`tools/collect_ondevice_topaz.sh`](../tools/collect_ondevice_topaz.sh)
para a pasta Download do aparelho (no GitHub: abra o arquivo e
use a opção de baixar o conteúdo original/raw). Depois, num
terminal com root concedido no Magisk — o Termux serve:

```sh
su
sh /sdcard/Download/collect_ondevice_topaz.sh
```

Com o dump de leitura da `recovery` do slot ativo:

```sh
su
COLLECT_RECOVERY=1 sh /sdcard/Download/collect_ondevice_topaz.sh
```

O resultado fica em `/sdcard/Download/topaz-info` (pasta
Download, visível no gerenciador de arquivos). Compacte e
compartilhe a pasta depois de revisar — principalmente o
`dmesg-stock.txt`. A imagem da `recovery` pode ficar só com
você/no Drive; para o projeto basta o hash dela. O script
exige uid 0 e avisa se o root não estiver ativo; ele não faz
reboot, não usa fastboot e não escreve em nenhuma partição.

Manualmente, os comandos equivalentes via adb são:

```sh
adb shell getprop ro.product.model
adb shell getprop ro.product.device
adb shell getprop ro.build.fingerprint
adb shell getprop ro.boot.slot_suffix
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.vbmeta.device_state
adb shell getprop ro.boot.flash.locked
adb shell getprop ro.vendor.build.fingerprint
adb shell uname -a
adb shell cat /proc/cmdline
adb shell cat /proc/bootconfig
adb shell ls /dev/block/by-name
adb shell cat /sys/block/sda/device/model
adb shell cat /sys/block/sda/device/vendor
adb shell getevent -i | grep -A2 -i "touch\|fts\|goodix"
adb shell dumpsys input | grep -i -m5 "touch\|focal"
```

Se tiver root (ajuda muito nas fases S2/S3, não bloqueia a S1):

```sh
adb shell su -c dmesg > dmesg-stock.txt
adb shell su -c sha256sum /sys/firmware/fdt
adb shell su -c "cat /sys/kernel/debug/regulator/regulator_summary" \
    | grep -E "pm6125_l4|pm6125_l18"
adb shell su -c lsmod
adb shell su -c lpdump | head -n 50
```

O `sha256sum` do FDT diz se a árvore ativa ainda é a mesma da
captura; se mudou (OTA/reflash desde então), aí sim vale subir
um `/sys/firmware/fdt` novo pelo Drive (binários não vão ao Git).

Em modo fastboot (**só leitura**, nada de `flashing`/`oem`):

```sh
fastboot getvar product
fastboot getvar current-slot
fastboot getvar unlocked
fastboot getvar secure
```

## 3) Backups — bloqueante antes de QUALQUER flash

Da análise de `docs/boot-dependency-analysis.md`:

- **`recovery_b`: FEITO (30/out/2026).** Extraída por leitura
  com hash registrado; cópia fora do aparelho na pasta
  "Topaz info" do Drive. Manter também uma segunda cópia
  (PC ou o microSD) é recomendado.
- **`vbmeta_system_b`** do slot ativo: ainda falta (64 KiB; o
  `vbmeta_b` já temos). Leitura idêntica à da recovery.
- Dumps guardados confirmados como sendo do sistema atual
  pela coleta (fingerprint/índices iguais) — sem necessidade
  de recaptura enquanto não houver OTA/troca de ROM.
- `persist`, `modemst1/2`, `fsg`: vale ter cópia **offline sua**
  por segurança, mas **não enviar** — contêm calibração/IMEI.

## Privacidade — o que NÃO enviar

IMEI, número de série, MACs, `fastboot getvar all` cru (contém
serial/IMEI — filtre), dumps de `persist`/`modemst`, contas ou
arquivos pessoais. Hashes e tamanhos bastam para as partições
sensíveis.

## Prioridade mínima que destrava a próxima etapa

As respostas principais do item 1 já chegaram; elas retiram o
flash experimental dos planos de curto prazo neste aparelho.
O que destrava trabalho útil agora, sem nenhum risco ao
sistema atual, é a coleta somente-leitura do item 2 (de
preferência com root, via `tools/collect_topaz_info.sh` no PC
ou `tools/collect_ondevice_topaz.sh` no próprio celular),
incluindo hash do FDT ativo, `dmesg` stock e `lpdump`, mais o
dump de leitura da `recovery` (`COLLECT_RECOVERY=1`). Com isso
eu: (a) confirmo se o FDT e os dumps de referência continuam
válidos para escrever a DT S1, (b) desenho a S1 já com o canal
de log sem UART (`ramoops`/`pstore`) e (c) deixo o pacote de
recuperação um passo mais completo. Nenhuma imagem sai do CI
em direção ao aparelho nesta fase.
