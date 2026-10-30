# Informações do aparelho: o que falta (e o que já temos)

Pedido ao dono do topaz para destravar a fase de **teste em
hardware** da trilha 6.18. Para continuar *escrevendo código*
(DT upstream S1, a partir do FDT já versionado) **não falta nada
desta lista** — ela fecha os furos que só o aparelho físico
resolve e prepara o primeiro boot com segurança.

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

## 1) Respostas rápidas (5 min, sem ferramenta)

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

Nada aqui escreve no aparelho. Cole a saída (ou suba os `.txt`
no Drive como das outras vezes):

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

Ainda faltam, da análise de `docs/boot-dependency-analysis.md`:

- **`recovery_b` nunca foi extraída** — é o fallback se um boot
  de teste falhar. Extrair + `sha256` + cópia **fora do
  aparelho**, junto das demais imagens.
- **`vbmeta_system`** do slot ativo, idem.
- Confirmar que os dumps já guardados ainda são os do sistema
  atual; se houve OTA/troca de ROM depois da captura, recapturar
  `boot`/`init_boot`/`vendor_boot`/`dtbo`/`vbmeta` do slot
  ativo (só os hashes/tamanhos precisam ser *reportados*; as
  imagens ficam no Drive, como hoje).
- `persist`, `modemst1/2`, `fsg`: vale ter cópia **offline sua**
  por segurança, mas **não enviar** — contêm calibração/IMEI.

## Privacidade — o que NÃO enviar

IMEI, número de série, MACs, `fastboot getvar all` cru (contém
serial/IMEI — filtre), dumps de `persist`/`modemst`, contas ou
arquivos pessoais. Hashes e tamanhos bastam para as partições
sensíveis.

## Prioridade mínima que destrava a próxima etapa

As respostas do item 1 (sobretudo **bootloader**, **principal
vs. bancada** e **serial sim/não**) + o bloco adb sem root do
item 2. Com isso eu: (a) fecho o desenho do primeiro teste de
boot (serial × sem-serial, slot de teste, AVB), (b) confirmo se
o FDT de referência continua válido para escrever a DT S1, e
(c) deixo o pacote de recuperação pronto antes de qualquer
imagem sair do CI em direção ao aparelho.
