#!/usr/bin/env python3
"""Compara dois FDTs/overlays por significado, nao por bytes.

Serve para responder "este dtbo e' o mesmo que aquele?" quando os dois
vem de builds diferentes. O `dtc` reordena fragmentos, numera phandles
por ordem de alocacao e muda o tamanho do blob, mas o conteudo pode ser
identico. Comparar texto nao resolve: a mesma referencia aparece como
`<0x1c>` num arquivo e `<0x4d>` no outro.

O comparador faz duas passadas:

1. canoniza e compara. As chaves sao o *alvo* de cada fragmento (nao o
   numero dele), e valores que apontam para simbolos externos viram
   `&simbolo`.
2. reconcilia o que sobrou. Se duas celulas numericas diferem, elas
   ainda podem ser o mesmo phandle mal numerado; entao cada lado e'
   resolvido para o *nome do no* que ele aponta, e se os nomes batem a
   diferenca e' aceita.

A reconciliacao e' segura porque so roda em celulas que ja diferem: um
escalar como `reg = <0x3>` e' igual nos dois lados e nunca chega la.

Uso:
  tools/fdt_compare.py a.dtbo b.dtbo --base soc.dtb
  tools/fdt_compare.py a.dtb b.dtb            # FDTs completos
  tools/fdt_compare.py a.dtbo b.dtbo --base soc.dtb --verboso
"""

import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fdt_dump import parse, percorrer  # noqa: E402
from fdt_overlay_dump import mapa_fixups, mapa_simbolos  # noqa: E402


def _props(no):
    return {nome: valor for nome, valor in no.props}


def _mapa_donos(raiz):
    """phandle interno -> caminho do no dentro da imagem."""
    dono = {}
    for no in percorrer(raiz):
        props = _props(no)
        for chave in ("phandle", "linux,phandle"):
            if chave in props and len(props[chave]) >= 4:
                (valor,) = struct.unpack(">I", props[chave][:4])
                dono[valor] = no.path()
    return dono


def _nome_curto(caminho):
    """'/fragment@47/__overlay__/cam-vaf' -> 'cam-vaf'."""
    if "/__overlay__/" in caminho:
        return caminho.split("/__overlay__/", 1)[1]
    return caminho.lstrip("/")


def _texto_limpo(valor):
    """Lista de strings bem formada ("a\\0b\\0"), ou None.

    Um array de celulas (`<0x34 0x0 0x35 0x0>`) tambem e' feito de bytes
    imprimiveis e nulos, entao exigir segmentos nao vazios separados por
    um unico NUL e' o que separa string de celula.
    """
    if not valor or valor[-1] != 0:
        return None
    corpo = valor[:-1]
    if not corpo:
        return None
    segmentos = corpo.split(b"\0")
    if any(not seg for seg in segmentos):
        return None
    if not all(all(32 <= b < 127 for b in seg) for seg in segmentos):
        return None
    return valor.decode("utf-8", "replace")


class Plano(object):
    """Conteudo normalizado de um FDT/overlay.

    `.fragmentos` : alvo -> lista de dicts {caminho relativo: {prop: valor}}
    `.donos`      : phandle -> nome curto do no que ele aponta
    """

    def __init__(self, raiz, base_raiz=None):
        self.simbolos = mapa_simbolos(base_raiz) if base_raiz is not None \
            else {}
        self.donos = {k: _nome_curto(v) for k, v in _mapa_donos(raiz).items()}
        self.fragmentos = {}
        tem_fixups = any(no.name == "__fixups__" for no in raiz.children)
        if tem_fixups:
            self.fixups = mapa_fixups(raiz)
            self._le_overlay(raiz)
        else:
            self.fixups = {}
            self.fragmentos["/"] = [self._subarvore(raiz)]

    def _le_overlay(self, raiz):
        alvo_por_fragmento = {}
        for (caminho, prop, idx), simbolo in self.fixups.items():
            if prop == "target" and idx == 0:
                alvo_por_fragmento[caminho] = simbolo

        props_raiz = {}
        for nome, valor in raiz.props:
            if nome in ("phandle", "linux,phandle"):
                continue
            props_raiz["/"] = props_raiz.get("/", {})
            props_raiz["/"][nome] = self._valor("/", nome, valor)
        if props_raiz:
            self.fragmentos["<raiz>"] = [props_raiz]

        for filho in raiz.children:
            if not filho.name.startswith("fragment"):
                continue
            caminho = "/" + filho.name
            alvo = alvo_por_fragmento.get(caminho)
            if alvo is None:
                props = _props(filho)
                if "target-path" in props:
                    alvo = props["target-path"].rstrip(b"\0").decode()
                else:
                    alvo = "?fragment:" + filho.name
            overlay = None
            for neto in filho.children:
                if neto.name == "__overlay__":
                    overlay = neto
                    break
            plano = self._subarvore(overlay) if overlay is not None else {}
            self.fragmentos.setdefault(alvo, []).append(plano)

    def _subarvore(self, raiz_no, _rel=""):
        plano = {}
        props = {}
        for nome, valor in raiz_no.props:
            if nome in ("phandle", "linux,phandle"):
                continue
            props[nome] = self._valor(raiz_no.path(), nome, valor)
        plano[_rel or "/"] = props
        for filho in raiz_no.children:
            plano.update(self._subarvore(filho, _rel + "/" + filho.name))
        return plano

    def _valor(self, caminho_no, nome_prop, valor):
        texto = _texto_limpo(valor)
        if texto is not None:
            return ("texto", texto)
        if not valor or len(valor) % 4:
            return ("bytes", valor.hex())
        return ("celulas",
                struct.unpack(">%dI" % (len(valor) // 4), valor))

    def resolve(self, caminho_no, nome_prop, indice, celula):
        simbolo = self.fixups.get((caminho_no, nome_prop, indice))
        if simbolo:
            return "&" + simbolo
        return self.donos.get(celula)

    def assinatura(self, plano):
        linhas = []
        for caminho, props in plano.items():
            for prop, (tipo, valor) in props.items():
                linhas.append("%s|%s=%s" % (caminho, prop,
                                            _formata(tipo, valor)))
        return "\n".join(sorted(linhas))


def _formata(tipo, valor):
    if tipo == "texto":
        return "texto:" + valor
    if tipo == "bytes":
        return "bytes:" + valor
    return "celulas:" + " ".join("0x%x" % c for c in valor)


def _iguais(pa, pb, plano_a, plano_b, caminho, prop):
    """(igual?, explicacao). Aplica a reconciliacao de phandle."""
    if pa == pb:
        return True, None
    if pa[0] != pb[0]:
        return False, None
    if pa[0] != "celulas" or len(pa[1]) != len(pb[1]):
        return False, None
    for i, (ca, cb) in enumerate(zip(pa[1], pb[1])):
        if ca == cb:
            continue
        na = plano_a.resolve(caminho, prop, i, ca)
        nb = plano_b.resolve(caminho, prop, i, cb)
        if not na or not nb or na != nb:
            return False, None
    return True, "phandles equivalentes (mesmo no, numeracao diferente)"


def compara(plano_a, plano_b):
    problemas = []
    alvos = sorted(set(plano_a.fragmentos) | set(plano_b.fragmentos))
    for alvo in alvos:
        fa = plano_a.fragmentos.get(alvo, [])
        fb = plano_b.fragmentos.get(alvo, [])
        if not fa or not fb:
            problemas.append((alvo, "alvo so em %s"
                              % ("A" if fa else "B"), []))
            continue
        # pareamento por melhor sobreposicao, para variantes do mesmo alvo
        usados = set()
        for pa in fa:
            melhor, melhor_nota = None, -1
            for j, pb in enumerate(fb):
                if j in usados:
                    continue
                nota = _nota(pa, pb, plano_a, plano_b)
                if nota > melhor_nota:
                    melhor, melhor_nota = j, nota
            if melhor is None:
                continue
            usados.add(melhor)
            difs = _diff(pa, fb[melhor], plano_a, plano_b, alvo)
            if difs:
                problemas.append((alvo, "fragmento diferente", difs))
        for j, pb in enumerate(fb):
            if j not in usados:
                problemas.append((alvo, "fragmento extra em B", []))
    return problemas


def _nota(pa, pb, plano_a, plano_b):
    nota = 0
    for caminho in set(pa) & set(pb):
        for prop in set(pa[caminho]) & set(pb[caminho]):
            igual, _ = _iguais(pa[caminho][prop], pb[caminho][prop],
                               plano_a, plano_b, caminho, prop)
            nota += 1 if igual else 0
    return nota


def _diff(pa, pb, plano_a, plano_b, alvo):
    difs = []
    for caminho in sorted(set(pa) | set(pb)):
        if caminho not in pb:
            difs.append("[%s] so em A" % caminho)
            continue
        if caminho not in pa:
            difs.append("[%s] so em B" % caminho)
            continue
        for prop in sorted(set(pa[caminho]) | set(pb[caminho])):
            if prop not in pb[caminho]:
                difs.append("[%s] %s so em A" % (caminho, prop))
                continue
            if prop not in pa[caminho]:
                difs.append("[%s] %s so em B" % (caminho, prop))
                continue
            igual, explicacao = _iguais(pa[caminho][prop], pb[caminho][prop],
                                        plano_a, plano_b, caminho, prop)
            if not igual:
                difs.append("[%s] %s: A=%s B=%s"
                            % (caminho, prop,
                               _formata(*pa[caminho][prop])[:120],
                               _formata(*pb[caminho][prop])[:120]))
            elif explicacao:
                difs.append("[%s] %s: %s" % (caminho, prop, explicacao))
    return difs


def main(argv):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--base", default=None,
                    help="DT base para resolver os simbolos do overlay")
    ap.add_argument("--max", type=int, default=30,
                    help="maximo de alvos com diferenca a imprimir")
    ap.add_argument("--verboso", action="store_true",
                    help="mostra tambem as diferencas ja reconciliadas")
    args = ap.parse_args(argv)

    base = parse(open(args.base, "rb").read()) if args.base else None
    plano_a = Plano(parse(open(args.a, "rb").read()), base)
    plano_b = Plano(parse(open(args.b, "rb").read()), base)
    problemas = compara(plano_a, plano_b)

    # diferencas so de numeracao de phandle nao contam
    def so_phandle(alvo, tipo, difs):
        return bool(difs) and all("phandles equivalentes" in d for d in difs)

    reais = []
    for alvo, tipo, difs in problemas:
        if so_phandle(alvo, tipo, difs):
            if args.verboso:
                print("  [ok] %s: %s" % (alvo, difs[0]))
            continue
        reais.append((alvo, tipo, difs))

    if not reais:
        print("IGUAIS: %d alvo(s) de fragmento, nenhuma diferenca real"
              % len(plano_a.fragmentos))
        return 0

    print("%d alvo(s) com diferenca real:" % len(reais))
    for alvo, tipo, difs in reais[: args.max]:
        print("  [%s] %s" % (tipo, alvo))
        for linha in difs[:12]:
            print("      " + linha)
        if len(difs) > 12:
            print("      ... mais %d" % (len(difs) - 12))
    if len(reais) > args.max:
        print("  ... mais %d alvo(s)" % (len(reais) - args.max))
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = None
        sys.exit(0)
