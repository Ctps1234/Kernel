#!/usr/bin/env python3
"""Recolhe um DTB publicado em comentarios de issue pelo CI.

Ferramenta par de tools/ci_publish_dtb.sh: o workflow publica o DTB do
topaz em base64 num comentario da issue de relatorio (o blob storage
dos artefatos do Actions nao e' alcancavel deste sandbox), e este
script junta as partes de volta num arquivo local.

Uso:
  tools/fetch_dtb.py <sha-ou-latest> <saida.dtb> [opcoes]

O primeiro argumento casa por prefixo o sha da rodada marcada em cada
comentario; "latest" pega a rodada mais recente publicada.

Opcoes:
  --titulo T   titulo da issue de relatorio (default: o do job de build)
  --label L    label da issue (default: ci-report)
  --listar     so' lista as rodadas publicadas, sem baixar nada

Exemplos:
  tools/fetch_dtb.py latest /tmp/topaz.dtb
  tools/fetch_dtb.py d8c7312 /tmp/topaz-d8c7312.dtb --listar
"""
import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys

TITULO_PADRAO = "CI: relatorio de build do kernel 6.18 (port Khaje)"
MARCADOR = re.compile(
    r"<!--\s*dtb-b64 v1 run=(?P<run>\S+) sha=(?P<sha>[0-9a-f]+) "
    r"part=(?P<i>\d+)/(?P<n>\d+) file=(?P<file>\S+) sha256=(?P<sum>[0-9a-f]+)\s*-->"
)
BLOCO = re.compile(r"```\n(?P<b64>[A-Za-z0-9+/=\n]+?)```", re.S)


def gh(*args, entrada=None):
    saida = subprocess.run(("gh",) + args, capture_output=True, text=True,
                           input=entrada, check=False)
    if saida.returncode != 0:
        raise SystemExit("gh falhou: %s\n%s" % (" ".join(args), saida.stderr.strip()))
    return saida.stdout


def repo_atual():
    return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()


def numero_da_issue(repo, label, titulo):
    bruto = gh("issue", "list", "--repo", repo, "--label", label, "--state", "open",
               "--limit", "50", "--json", "number,title")
    for item in json.loads(bruto):
        if item["title"] == titulo:
            return item["number"]
    raise SystemExit("issue nao encontrada: %r (label %s)" % (titulo, label))


def comentarios(repo, numero):
    bruto = gh("api", "repos/%s/issues/%d/comments?per_page=100" % (repo, numero),
               "--paginate")
    # --paginate concatena paginas JSON: junta tudo num vetor so'.
    pedacos, prof, inicio = [], 0, None
    for i, c in enumerate(bruto):
        if c == "[" and prof == 0:
            inicio = i
        if inicio is not None:
            if c == "[":
                prof += 1
            elif c == "]":
                prof -= 1
                if prof == 0:
                    pedacos.extend(json.loads(bruto[inicio:i + 1]))
                    inicio = None
    return pedacos


def rodadas(comentarios_):
    """sha -> {run, file, sum, partes{i: b64}} das marcacoes encontradas."""
    achado = {}
    for c in comentarios_:
        corpo = c.get("body") or ""
        m = MARCADOR.search(corpo)
        if not m:
            continue
        bloco = BLOCO.search(corpo[m.end():])
        if not bloco:
            continue
        chave = (m["sha"], m["run"])
        entrada = achado.setdefault(chave, {"file": m["file"], "sum": m["sum"],
                                            "n": int(m["n"]), "partes": {}})
        entrada["partes"][int(m["i"])] = bloco["b64"].strip()
    return achado


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sha", help="prefixo do sha da rodada, ou 'latest'")
    ap.add_argument("saida", nargs="?", help="arquivo .dtb de saida")
    ap.add_argument("--titulo", default=TITULO_PADRAO)
    ap.add_argument("--label", default="ci-report")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()

    repo = repo_atual()
    numero = numero_da_issue(repo, args.label, args.titulo)
    achado = rodadas(comentarios(repo, numero))
    if not achado:
        raise SystemExit("nenhum DTB publicado na issue #%d" % numero)

    def ordenar(chave):
        sha, run = chave
        return (0, int(run)) if run.isdigit() else (1, 0)

    chaves = sorted(achado, key=ordenar, reverse=True)
    if args.listar or not args.saida:
        for sha, run in chaves:
            e = achado[(sha, run)]
            print("%s run=%s %s %d/%d partes sha256=%s"
                  % (sha, run, e["file"], len(e["partes"]), e["n"], e["sum"]))
        if not args.saida:
            return

    if args.sha == "latest":
        escolhida = chaves[0]
    else:
        casa = [k for k in chaves if k[0].startswith(args.sha)]
        if not casa:
            raise SystemExit("nenhuma rodada publicada com sha %r" % args.sha)
        escolhida = casa[0]

    entrada = achado[escolhida]
    faltando = [i for i in range(1, entrada["n"] + 1) if i not in entrada["partes"]]
    if faltando:
        raise SystemExit("partes faltando: %s" % faltando)

    b64 = "".join(entrada["partes"][i] for i in range(1, entrada["n"] + 1))
    dados = base64.b64decode(b64)
    soma = hashlib.sha256(dados).hexdigest()
    if soma != entrada["sum"]:
        raise SystemExit("sha256 nao confere: %s != %s" % (soma, entrada["sum"]))

    with open(args.saida, "wb") as f:
        f.write(dados)
    print("%s: %s, %d bytes, sha256 %s" % (args.saida, entrada["file"],
                                           len(dados), soma))


if __name__ == "__main__":
    sys.exit(main())
