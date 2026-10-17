#!/usr/bin/env python3
"""Analisa a saida do dt-validate e compara com uma linha de base.

O dt-validate do kernel 6.12 acusa a DTS vendor do Khaje (importada do
kernel 5.15 do aparelho) contra os schemas do upstream: centenas de
propriedades `qcom,*` ainda nao tem schema na arvore 6.12 e aparecem como
erro "is not of type 'object', 'integer', ...". Zerar esse backlog exigiria
portar centenas de bindings vendor; o que interessa agora e *nao regredir*.

Por isso a ferramenta classifica a saida em:
  - avisos  : "failed to match any schema with compatible" (node sem schema,
              esperado para hardware fora da arvore);
  - erros   : violacoes reais de schema (propriedade proibida, tipo errado,
              nome fora do padrao, etc.).

As assinaturas de erro sao comparadas com uma linha de base versionada
(`docs/dt-validate-baseline.json`): assinatura nova ou contagem maior que a
da linha de base = regressao = CI falha. Contagem menor = improvement
reportado, sem falhar.

Uso:
    tools/dt_validate_report.py --log LOG [--baseline BASE] [--update] [--quiet]
"""

import argparse
import collections
import json
import os
import re
import sys

# Linha do dt-validate: "<arquivo.dtb>: <mensagem>"
ENTRY_RE = re.compile(r"^(?P<dtb>[^\s:]+\.dtb): (?P<msg>.*)$")
# Schema que produziu o erro (linha seguinte, indentada com TAB)
SCHEMA_RE = re.compile(r"^\s*from schema \$id: (?P<schema>\S+)\s*$")
# Valores binarios: b'\x00\x00\x00\x03'
BYTES_RE = re.compile(r"b'[^']*'")
# Aviso de node sem schema correspondente
UNMATCHED_RE = re.compile(r"failed to match any schema with compatible")

# Mensagens do dtc (warnings do compilador) nao sao erros de schema.
DTC_RE = re.compile(r"^[^\s:]+\.dts[io]?: ")


def parse_log(path):
    """Extrai (dtb, schema, mensagem) do log do dt-validate."""
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()

    pending = None
    for line in lines:
        schema_match = SCHEMA_RE.match(line)
        if schema_match and pending is not None:
            pending["schema"] = schema_match.group("schema")
            continue

        entry_match = ENTRY_RE.match(line)
        if entry_match:
            pending = {
                "dtb": entry_match.group("dtb"),
                "msg": entry_match.group("msg"),
                "schema": "-",
            }
            entries.append(pending)
            continue

        if DTC_RE.match(line):
            pending = None
            continue

        # Continuacao de mensagem (detalhes do oneOf) nao muda a assinatura.
    return entries


def signature(entry):
    """Assinatura estavel de um erro: schema + mensagem normalizada.

    A normalizacao troca valores binarios por um marcador e sequencias de
    digitos por "N", de modo que as dozens de instancias do mesmo problema
    (uma por regulador, por CPU, ...) colapsem em uma unica assinatura.
    Mensagens muito longas (o dt-validate do vendor-prefixes embute a lista
    completa de prefixos) sao truncadas para nao inflar a linha de base.
    """
    msg = BYTES_RE.sub("b'<bytes>'", entry["msg"])
    msg = re.sub(r"[0-9]+", "N", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    if len(msg) > 160:
        msg = msg[:160] + "..."
    return "%s\t%s" % (entry["schema"], msg)


def summarize(entries):
    """Conta erros/avisos e devolve as assinaturas de erro."""
    errors = collections.Counter()
    warnings = 0
    for entry in entries:
        if UNMATCHED_RE.search(entry["msg"]):
            warnings += 1
            continue
        errors[signature(entry)] += 1
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", required=True, help="log gerado pelo dt-validate")
    parser.add_argument("--baseline", default="docs/dt-validate-baseline.json",
                        help="linha de base com as assinaturas de erro conhecidas")
    parser.add_argument("--update", action="store_true",
                        help="reescreve a linha de base com o resultado atual")
    parser.add_argument("--quiet", action="store_true",
                        help="nao imprime o detalhamento por schema")
    args = parser.parse_args()

    if not os.path.exists(args.log):
        print("dt_validate_report: log inexistente: %s" % args.log, file=sys.stderr)
        return 2

    entries = parse_log(args.log)
    errors, warnings = summarize(entries)

    baseline = {}
    if os.path.exists(args.baseline):
        with open(args.baseline, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        baseline = data.get("signatures", {})

    new = {sig: count for sig, count in errors.items() if sig not in baseline}
    grew = {sig: (baseline[sig], count) for sig, count in errors.items()
            if sig in baseline and count > baseline[sig]}
    fixed = {sig: (baseline[sig], count) for sig, count in errors.items()
             if sig in baseline and count < baseline[sig]}

    print("dt-validate: %d erro(s) em %d assinatura(s) | %d aviso(s) sem schema"
          % (sum(errors.values()), len(errors), warnings))

    by_schema = collections.Counter()
    for sig, count in errors.items():
        by_schema[sig.split("\t", 1)[0]] += count
    if not args.quiet:
        print("erros por schema:")
        for schema, count in by_schema.most_common():
            print("  %5d  %s" % (count, schema))

    if new:
        print("\nREGRESSAO: %d assinatura(s) nova(s) de erro:" % len(new))
        for sig, count in sorted(new.items(), key=lambda item: -item[1])[:40]:
            print("  +%d  %s" % (count, sig))
    if grew:
        print("\nREGRESSAO: %d assinatura(s) com contagem maior:" % len(grew))
        for sig, (old, new_count) in sorted(grew.items(), key=lambda item: -item[1][1])[:40]:
            print("  %d -> %d  %s" % (old, new_count, sig))
    if fixed:
        print("\nmelhoras: %d assinatura(s) com contagem menor" % len(fixed))
        for sig, (old, new_count) in sorted(fixed.items(), key=lambda item: -item[1][0])[:20]:
            print("  %d -> %d  %s" % (old, new_count, sig))

    if args.update:
        payload = {
            "assinaturas": sum(errors.values()),
            "avisos": warnings,
            "signatures": dict(sorted(errors.items())),
        }
        with open(args.baseline, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        print("\nlinha de base atualizada: %s" % args.baseline)
        return 0

    if new or grew:
        print("\nresultado: FALHA (regressao de schema)")
        return 1

    print("\nresultado: OK (sem regressao em relacao a linha de base)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
