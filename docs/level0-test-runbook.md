# Runbook do primeiro teste em hardware (Nível 0)

Objetivo: provar que o **nosso kernel 6.18 chega ao `init` do Android**
no topaz, com captura de log mesmo se falhar. Não é para "usar o
celular": é um teste de bancada, com rollback pronto.

Estado: imagens prontas e validadas
(`out-618/`, tar `topaz-618-test-images-2026-11-04.tar.gz` no Drive).
**Nada foi gravado no aparelho.** Nenhum passo abaixo roda sem você.

O DTB dentro dessas imagens é anterior a três ajustes de DTS
(card-detect do microSD, `orientation` da câmera e o `output-high` do
AVDD do touch) — nenhum deles muda o caminho de boot, então o tar
continua servindo para o teste de Nível 0. Para refazer as imagens com
o DTB atual, antes de gravar:

```sh
tools/fetch_ci_artifacts.sh     # Image + DTB da última run (branch ci-artifacts-6.18)
tools/build_flash_images_618.sh # refaz out-618/ com roundtrip dos originais
```

O `fetch_ci_artifacts.sh` existe porque o zip de artefato do Actions não
baixa deste ambiente (blob storage bloqueado); o branch do próprio
repositório baixa. Sem ele, `build_flash_images_618.sh` precisa de um
diretório de artefatos passado à mão.

---

## O que o teste NÃO faz (e por que é menos arriscado do que parece)

| Fato | Consequência |
|---|---|
| `vbmeta_b` tem **flags = 3** (verification + hashtree desligados) | não é preciso reassinar nem apagar `vbmeta`; hash "errado" é aceito |
| `init_boot` é **cópia idêntica** da ROM | o `adbd`/init de primeiro estágio é o da Lunaris, não inventamos nada |
| `vendor_boot` mantém **a ramdisk vendor original da Lunaris OS** (258 módulos) | só trocamos o FDT #1 e o bootconfig |
| Só o slot `_b` é tocado | `_a` fica intacto como estava (não há imagens válidas lá, mas nada é sobrescrito) |
| `dtbo` entra com **uma** entrada alterada (51) | as outras 51 continuam byte-idênticas |
| Bootloader desbloqueado | `fastboot` volta mesmo com boot quebrado (ABL roda antes do kernel) |

O risco real não é "brick": é **o teste não passar** e o aparelho ficar
em loop de reboot até você restaurar as imagens originais da Lunaris OS.
Os arquivos originais estão no dump (`dump-lineage.tar.gz`, hashes
conferidos) e podem ser re-extraídos das partições a qualquer momento.
Não se trata da ROM Xiaomi de fábrica.

## Riscos conhecidos que só o hardware resolve

1. **`boot_devices`**: o `/proc/bootconfig` da Lunaris mostra
   `soc/4804000.ufshc` (nome do nó SoC downstream). Nosso DTB usa
   `soc@0`. Se o ABL derivar o caminho do DTB que ele mesmo carregou,
   vira `soc@0/4804000.ufshc` e casa. Se ele usar string fixa,
   `init` não acha o `super` e para no primeiro estágio.
   → sintoma: logo do bootloader, tela apaga, sem boot animation, e
   volta pro bootloader ou reinicia; log no ramoops diz
   `Failed to find /dev/block/...`/`FirstStageMount failed`.
2. **`/data` com `wrappedkey`**: sem qseecom não há como derivar a
   chave. `init` deve falhar em montar `/data` e seguir (ou reiniciar
   para recovery), **sem formatar nada**. Formatar é decisão sua, e
   não faz parte deste teste.
3. **UFS**: se o PHY/host não subir, não há partição nenhuma — o
   mesmo sintoma do item 1, distinguível no log (`ufshcd` x
   `boot_devices`).

## Antes de encostar no aparelho

- Bateria **> 50 %** (não dá para carregar com kernel de teste).
- Cabo USB bom + `fastboot` funcionando no PC (`fastboot --version`).
- Termux com root no aparelho, para o dump de segurança (passo 0).
- Espaço para guardar ~260 MB de backup das partições da Lunaris OS.

### Passo 0 — dump de segurança das 5 partições (slot `_b`)

No aparelho, com root (os caminhos `by-name` são os medidos):

```sh
su -c 'mkdir -p /sdcard/bk && for p in boot_b vendor_boot_b dtbo_b init_boot_b vbmeta_b; do
  dd if=/dev/block/by-name/$p of=/sdcard/bk/$p.img bs=4M; done'
sha256sum /sdcard/bk/*.img
```

Conferir contra os hashes dos dumps originais da Lunaris OS registrados
em `docs/boot-partition-inventory.md`. Se baterem, o rollback para a
Lunaris fica verificável mesmo se o dump do Drive sumir.

### Passo 1 — bootloader

```sh
adb reboot bootloader          # ou: desligar + Vol- + Power
fastboot devices               # tem que listar o serial
fastboot getvar current-slot   # esperado: b
```

### Passo 2 — gravar as 4 imagens

```sh
fastboot flash boot_b        boot_b-618.img
fastboot flash vendor_boot_b vendor_boot_b-618.img
fastboot flash dtbo_b        dtbo_b-618.img
fastboot flash init_boot_b   init_boot_b-618.img
fastboot reboot
```

Não toque em `vbmeta`, `super`, `userdata`, `persist` nem `modem`.

### Passo 3 — observar (cronômetro na mão)

Anotar, em ordem, o que acontece:

| Tempo | Esperado se está indo bem |
|---|---|
| 0–3 s | tela do bootloader (aviso de desbloqueio) |
| 3–10 s | tela apaga / LED acende — kernel carregou |
| 10–30 s | boot animation da Lunaris ou tela preta com `adb` disponível |
| > 60 s parado | provável hang no primeiro estágio |

O sinal mais útil é **`adb devices`**: se aparecer `device` ou
`recovery`, o kernel chegou ao userspace e o teste deu certo no
essencial.

### Passo 4 — capturar o log

**Se o `adb` aparecer:**

```sh
adb shell dmesg                > dmesg.txt
adb shell cat /proc/bootconfig > bootconfig.txt
adb shell 'cat /proc/cmdline'  > cmdline.txt
adb shell 'ls /sys/fs/pstore'  > pstore.txt
adb shell 'cat /proc/version'
```

**Se não aparecer nada** (o caso provável na primeira tentativa):
o kernel registra `PSTORE_CONSOLE` no `ramoops@5d000000` (nosso DT
tem a região e o config força `PSTORE_RAM=y`). Então, depois de o
aparelho reiniciar sozinho:

```sh
# restaurar o boot original da Lunaris e ler a RAM reservada
fastboot flash boot_b boot_b.img          # do backup da Lunaris
fastboot reboot
adb shell su -c 'ls -l /sys/fs/pstore'
adb pull /sys/fs/pstore/console-ramoops-0
```

Se o aparelho ficar em loop sem reiniciar o suficiente, segurar
**Vol- + Power** ~15 s e restaurar o boot da Lunaris pelo bootloader.

### Passo 5 — rollback completo

```sh
fastboot flash boot_b        boot_b.img
fastboot flash vendor_boot_b vendor_boot_b.img
fastboot flash dtbo_b        dtbo_b.img
fastboot flash init_boot_b   init_boot_b.img
fastboot reboot
```

(`boot_b.img` etc. = os do passo 0, ou os extraídos do dump.)

## O que me mandar depois do teste

1. `dmesg.txt` (ou `console-ramoops-0`) — é o mais importante: nele
   se lê `Booting Linux on physical CPU`, a versão do kernel e o
   primeiro `probe` que falhou.
2. `bootconfig.txt` — fecha a dúvida do `boot_devices`.
3. O que a tela fez no passo 3 (mesmo "nada" é informação).

Com isso a próxima iteração é cirúrgica: um `probe` que falha no log
vira um patch de três linhas, em vez de tentativa e erro.

## Critérios de abortar na hora

- `fastboot flash` falhar por `partition not found` → **parar**;
  os nomes mudaram e o mapa precisa ser reconferido.
- Sem `fastboot devices` → problema de cabo/driver, não de imagem;
  não insistir no flash.
- Aparelho esquentar de forma anormal nos primeiros 30 s → desligar
  (kernel sem polling térmico pode rodar solto).
