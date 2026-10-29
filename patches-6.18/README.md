# Série sobre o ACK da Google (`android17-6.18`)

Rebase da série local (`../patches/`, base Android Common 6.12) sobre a
árvore oficial da Google, fixada em:

- repo: `https://github.com/aosp-mirror/kernel_common`
- branch: `android17-6.18`
- commit: `1afe39edbe66c201d26f23f2e3396583238f6842` (Linux 6.18-rc6)

Decisão e plano completos em
[`../docs/google-mainline-vendor-plan.md`](../docs/google-mainline-vendor-plan.md).
Os nomes de arquivo são idênticos aos da série 6.12 para manter o mapa
1:1 entre as duas. As mensagens de commit são as originais (mencionam a
árvore 6.12); o conteúdo é o mesmo, com os ajustes de contexto abaixo.
Nada aqui foi compilado ainda nesta base, muito menos testado em
hardware: o gate atual é aplicação limpa em sequência
(`.github/workflows/google-mainline.yml`).

## Estado (2026-10-29)

Rebaseados e verificados aplicando limpos, em ordem, sobre o commit
fixado: **0001–0011** (fundação de SoC: pinctrl, RPMCC, PHY UFS,
interconnect Bengal, reguladores RPM-SMD, votos de tensão/debug de
clock e os controladores GCC/DISPCC/GPUCC/debugcc Khaje).

Sete entraram sem nenhum ajuste (0001, 0002, 0003, 0006, 0007, 0008,
0009). Quatro exigiram hunks manuais, todos conferidos por
comportamento contra o código 6.18:

- **0004** (`clk-smd-rpm.c`): include `<linux/clk.h>` recolocado após a
  entrada nova `<linux/cleanup.h>`; em `clk_smd_rpm_set_rate()`, a
  atribuição `r->rate = rate` no caminho de clock desabilitado foi
  portada para o novo formato upstream (`guard(mutex)` + `return 0`,
  sem o `goto out` do 6.12).
- **0005** (binding QMP UFS): `qcom,sm6225-qmp-ufs-phy` inserido na
  posição alfabética atual da lista (entre sm6125 e sm6350); o bloco
  `allOf` de clocks entrou sem ajuste.
- **0010** (votos de tensão): os quatro callbacks
  prepare/unprepare/pre/post_rate_change adicionados a
  `clk_rcg2_floor_ops` (o hunk gêmeo em `clk_rcg2_ops` entrou limpo);
  `struct qcom_cc_regmap_update` e os campos `clk_regulators`/
  `num_clk_regulators`/`pre_probe` de `qcom_cc_desc` recolocados em
  `common.h`; em `common.c`, includes e os helpers de
  deinit/unvote recolocados, o bloco de init de reguladores +
  `pre_probe` posicionado logo após a alocação de `cc` (antes do
  attach de power domains e da configuração de PLLs, preservando a
  semântica 6.12) e a chamada `qcom_cc_enable_critical_clocks()`
  adaptada ao novo caminho de erro `goto put_rpm`.
- **0011** (controladores Khaje): apenas o `Makefile` — as linhas
  `debugcc-khaje.o`/`dispcc-khaje.o` recolocadas em volta da entrada
  nova upstream `camcc-milos.o`. Os quatro drivers novos
  (gcc/dispcc/gpucc/debugcc) entraram sem ajuste.

`checkpatch.pl --strict` nos quatro patches manuais: mesmo resultado
das contrapartes 6.12 (único ERROR pré-existente da série inteira:
falta de `Signed-off-by`); nenhum achado novo introduzido pelo rebase.

## Pendentes (0012–0033)

Disposição medida no plano; resumo:

- aplicar limpos na medição original, só reexportar no fluxo:
  0012, 0013 (cuidado: sem separador `---`), 0015, 0018, 0022, 0024,
  0027, 0031;
- rebase trivial (contexto de Makefile/Kconfig/binding): 0020, 0021,
  0025, 0033;
- rebase com revisão: 0014 (recortar prefixo a prefixo), 0016/0017
  (refatoração DPU/MDSS), 0026/0028 (tabela PAS), 0030 (recortar: TX
  SM6115 já upstream), 0032 (máquina de áudio);
- cascata do 0011, reavaliar agora que ele entrou: 0019, 0023;
- **descartar**: 0029 (resets LPASSCC SM6115 já upstream no 6.18).

## Método (para repetir nas próximas fatias)

1. Clone raso da base fixada; branch de trabalho local.
2. `git apply` em ordem; limpos viram commit com a mensagem original
   (os patches 0001–0011 não têm `From:`/`Date:`, então `git am` não
   serve; extrair assunto/corpo parando em `---` **ou** no primeiro
   `diff --git`, senão o diff inteiro vaza para a mensagem — foi o que
   quebrou a primeira exportação do 0008/0009).
3. Falhas: `git apply --reject`, inspecionar cada `.rej` contra o
   código atual, encaixar à mão preservando a semântica, nunca só o
   contexto.
4. `git format-patch` da pilha para este diretório, renomeando para os
   nomes da série 6.12.
5. Verificação do zero: worktree limpo no commit fixado, aplicar a
   série exportada em ordem e conferir `git diff` vazio contra a
   branch de trabalho.
