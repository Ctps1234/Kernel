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

Só **uma** leitura, de **um** byte, de um registro de identificação padrão do MIPI DCS (`0xDA`, ID1). É um registro somente de leitura, previsto na especificação MIPI DCS para todos os painéis.

Ressalvas:
- A especificação não garante que o DDIC do `m7` responda ao `0xDA` nem que o valor seja o ID esperado.
- A leitura só é tentada pela interface padrão do kernel, sem montar pacote manual, e apenas se `/proc/mi_display/mipi_rw_prim` existir. Se o nó não existir ou o formato do comando não for claramente aceito, o plano para aqui.

Comando exato: **não definido até a checagem offline da interface do `mipi_rw` no `msm_drm.ko`** (passo 6.1 abaixo).

## 6. Sequência

1. **Offline (sem aparelho):**
   - 6.1 Confirmar no `msm_drm.ko` o formato aceito pelo `mipi_rw` (quantos bytes de comando, quantos de retorno).
   - 6.2 Confirmar que o `0xDA` é o registro ID1 da especificação MIPI DCS.
   - 6.3 Registrar o resultado neste documento antes de pedir a autorização.
2. **Aparelho, leitura apenas:** captura de `dmesg` e `pstore` como linha de base (comandos do Termux, uma linha por vez, redirecionados para `/sdcard/Download/`).
3. **Aparelho, passo único:** uma leitura de 1 byte do `0xDA`. Nada mais.
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
- [ ] Autorizo o passo 3 da seção 6 (uma leitura de 1 byte do `0xDA`), somente depois da análise offline do passo 5.
- [ ] Não autorizo nenhuma leitura DSI. Seguir pela identificação por fonte externa.

Registro da decisão: _(preencher com data e escolha)_
