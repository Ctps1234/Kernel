# Plano de leitura DSI (identificação do IC do painel m7)

**Status:** rascunho para avaliação. **Nenhum comando foi enviado ao aparelho.** Este plano só entra em execução com autorização explícita e por escrito do usuário, para um passo específico.

## 1. Objetivo

Identificar o chip (IC) do DDIC do painel `m7_38_0c_0a_fhdp_video`, que hoje é desconhecido. Sem isso, o driver de painel do port 6.12 não pode ser escrito com segurança.

## 2. Por que esse plano é arriscado

- **Incidente de 2026-10-13:** leituras DCS feitas pelo `mipi_rw` (formato copiado de outro kernel) causaram falha de pacote DSI, travamento do motor de comando, timeout de commit do DPU, tela colorida e reboot. O `pstore` mostra `Failed to create message packet, rc=-22` e `wait for commit done failed`.
- **A causa exata não foi confirmada.** Não sabemos se o erro estava no formato do pacote, no tamanho da leitura ou no estado do painel.
- **A stock não faz essa leitura para o `m7`.** Verificado offline: não há nenhuma propriedade `mi,mdss-dsi-panel-build-id*` na `dtbo_b.img` nem na DT ativa (`device-tree/reference/topaz-live-reference.dts`). O `msm_drm.ko` tem a lógica de build ID, mas ela só roda se a DT configurar os comandos. Ou seja, a leitura teria de ser **montada por nós**, sem referência confiável dos bytes.

## 3. O que não fazer (proibições herdadas)

- Nenhum comando de escrita ou `tx_cmd_set`.
- Nenhum comando DCS montado a partir de outro kernel ou de outro painel.
- Nenhuma montagem de debugfs.
- Nenhuma alteração de DT para habilitar leitura de build ID.
- Nenhum flash, nenhuma escrita em partição.
- Nenhuma leitura repetida após qualquer erro.

## 4. Pré-requisitos (todos obrigatórios)

1. **Cópias de segurança verificadas** das partições `boot_b`, `vendor_boot_b`, `dtbo_b` e `vendor_dlkm_b`. Tamanho e sha256 conferidos. A `vendor_dlkm_b` já está no Drive em partes, mas ainda falta o checksum de referência do celular.
2. **Caminho de recuperação definido** e testado no papel: qual modo (fastboot/EDL) o aparelho usa, qual driver está instalado no computador do usuário ou se é só pelo celular, e quem executa a recuperação. Sem isso, o plano não começa.
3. **Bateria acima de 50%**, carregador desconectado.
4. **Captura de logs antes da leitura** (`dmesg` e `pstore`), para ter linha de base. Só leitura.
5. **Painel em estado estável:** brilho normal, sem erros DSI nos últimos minutos. Confirmar no log, sem alterar nada.
6. **Autorização explícita e por escrito** do usuário, citando este documento e o passo aprovado.

## 5. Passo único proposto (se autorizado)

**Revisado após a checagem offline (passo 6.2):** o `0xDA` não foi confirmado como ID1 padrão. O registro padrão de identificação é o `0xA1` (`read_DDB_start`), que devolve o bloco DDB: ID do fornecedor (2 bytes), ID do produto (2 bytes) e um byte de controle, ou seja, cerca de 5 bytes. A especificação MIPI DCS e a documentação de fabricantes confirmam o `0xA1`. O `msm_drm.ko` também usa a constante `MIPI_DCS_READ_DDB_START`, ou seja, a mesma família.

Passo proposto, se autorizado: **uma** leitura do `0xA1` com retorno de 5 bytes, nada mais.

Ressalvas:
- O DDB identifica o **fornecedor** (ID do fornecedor), não necessariamente o chip. Pode não bastar para fechar o IC do `m7`.
- O DDIC do `m7` pode não responder ao `0xA1` com o formato esperado.
- A leitura só é tentada pela interface padrão do kernel, sem montar pacote manual, e apenas se `/proc/mi_display/mipi_rw_prim` existir e aceitar o formato. Se não houver resposta clara ou o formato não for aceito, o plano para aqui.

Comando exato: **não definido até a checagem offline da interface do `mipi_rw` no `msm_drm.ko`** (passo 6.1 abaixo). O `msm_drm.ko` mostra mensagens de erro como `rx cmd transfer failed` e `invalid rx length`, mas o formato exato de entrada do `mipi_rw` ainda não foi decodificado.

## 6. Sequência

1. **Offline (sem aparelho):**
   - 6.1 Confirmar no `msm_drm.ko` o formato aceito pelo `mipi_rw` (quantos bytes de comando, quantos de retorno). **Status: parcial.** Achadas mensagens de erro (`read message failed read length`, `rx cmd transfer failed`, `invalid rx length`) e constantes de DCS, mas o formato de entrada do `mipi_rw` não foi decodificado.
   - 6.2 Confirmar qual registro é o ID padrão da especificação MIPI DCS. **Status: feito.** O `0xDA` não foi confirmado. O padrão é o `0xA1` (`read_DDB_start`), com retorno de cerca de 5 bytes. O plano foi revisto (seção 5).
   - 6.3 Registrar o resultado neste documento antes de pedir a autorização. **Status: feito nesta revisão.**
2. **Aparelho, leitura apenas:** captura de `dmesg` e `pstore` como linha de base (comandos do Termux, uma linha por vez, redirecionados para `/sdcard/Download/`).
3. **Aparelho, passo único:** uma leitura do `0xA1` (DDB, retorno de cerca de 5 bytes). Nada mais.
4. **Captura imediata** de `dmesg` depois da leitura, na mesma sessão.
5. **Análise offline** do resultado, antes de qualquer outro passo.
6. **Parar.** Nenhuma segunda tentativa sem nova autorização.

## 7. Critérios de aborto (parar imediatamente)

- Qualquer linha de erro DSI no `dmesg` após a leitura (`rc=`, `failed`, `timeout`, `wait for commit done`).
- Tela colorida, tela preta ou travamento.
- Reboot inesperado.
- Resposta que não seja um valor de 1 byte plausível.
- Qualquer item dos pré-requisitos não cumprido.

## 8. Recuperação

- Se o aparelho reiniciar sem boot: a recuperação exige flash das cópias de segurança. **Isso só acontece com decisão explícita do usuário.** Este plano não autoriza flash.
- Se o aparelho subir normalmente mas o painel estiver com erro: parar, capturar logs, não repetir.

## 9. Decisão necessária

- [ ] Autorizo **somente** o passo 1 da seção 6 (offline, sem aparelho).
- [ ] Autorizo o passo 2 da seção 6 (captura de linha de base, leitura apenas).
- [ ] Autorizo o passo 3 da seção 6 (uma leitura do `0xA1`, DDB), somente depois da análise offline do passo 5.
- [ ] Não autorizo nenhuma leitura DSI. Seguir pela identificação por fonte externa.

Registro da decisão: 2026-10-14, usuário autorizou o **passo 2** (captura de linha de base, só leitura). Passos 1 e 3 ainda sem autorização para o passo 3.

**Pendências na data da autorização (seção 4):** sha256 de referência da `vendor_dlkm_b` (não enviado); cópias de `boot_b`/`vendor_boot_b`/`dtbo_b` ainda não conferidas por sha256; caminho de recuperação não definido; nível de bateria não informado. O passo 2 é só leitura de logs, então segue; o passo 3 fica bloqueado até estes itens.

## 10. Resultado do passo 2 (linha de base, só leitura, 2026-10-14)

- Bateria: 60%. Uptime: 1 dia 4h58, carga média 4,11.
- `/sys/fs/pstore`: `console-ramoops-0` (482 KB) e `pmsg-ramoops-0` (1 MB), de um boot anterior, já analisados antes.
- `/proc/mi_display/`: `mipi_rw_prim` e `tx_cmd_set_prim` existem (root, 0644, 0 bytes). **Nenhum dos dois foi lido.**
- `dmesg` (23294 linhas, janela de 46959 s a 49890 s de uptime do kernel): **nenhum erro de DSI, DPU ou painel**. Há sequência normal de ligar painel (1080x2400, 120 Hz) e troca para 60 Hz, sem `rc=` negativo, sem `commit done`, sem timeout. Os erros que aparecem (binder, `fsm_speaker`, `wlan`) não são do display.
- Não há chamada de `mipi_rw` nessa janela.
- Limitação: o buffer circular não cobre o boot inteiro. Esta é uma linha de base da janela, não do boot completo.
- Revisão de dados pessoais no `dmesg` (seriais, MAC): pendente antes de compartilhar o arquivo além do Drive pessoal.

**Status:** passo 2 concluído. Passo 3 continua bloqueado pelos pré-requisitos da seção 4 (sha256 da `vendor_dlkm_b`, cópias de segurança conferidas, caminho de recuperação, decisão explícita).
