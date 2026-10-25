#!/usr/bin/env python3
"""Extrai e decodifica as sequencias de comandos do painel M7 (Topaz).

Le `qcom,mdss-dsi-on-command` / `qcom,mdss-dsi-pre-off-command` (formato
byte-array) do dtsi local do painel M7 _0a e emite linhas C no estilo
upstream (mipi_dsi_*_seq_multi), para o driver panel-xiaomi-m7.

Formato vendor de cada pacote (dsi_cmd_desc serializado):
  byte0: data type (0x39 generic long, 0x15 generic short 1-param,
         0x05 DCS short 0-param, 0x04 generic short 0-param...)
  byte1: last, byte2: vc, byte3: ack, byte4: wait_ms (apos o envio)
  byte5..6: comprimento do payload (big-endian)
  byte7..: payload (primeiro byte = comando)

O pacote longo cujo payload comeca com 0x9e e o PPS (Picture Parameter
Set) do DSC: ele NAO e transcrito; o driver o regenera via
drm_dsc_pps_payload_pack() a partir dos parametros DSC do FDT
(8bpp/8bpc, slices 2x 540x20, block prediction, DSC 1.1).

Uso:
  tools/extract_m7_panel_seq.py [dtsi] > seq.c.txt
"""
import re
import sys

DEFAULT = "device-tree/source/qcom/display/display/dsi_panel_m7_38_0c_0a_fhdp_video.dtsi"
PROPS = ("qcom,mdss-dsi-on-command", "qcom,mdss-dsi-pre-off-command")

DCS_NAMES = {
    0x10: "mipi_dsi_dcs_enter_sleep_mode_multi",
    0x11: "mipi_dsi_dcs_exit_sleep_mode_multi",
    0x28: "mipi_dsi_dcs_set_display_off_multi",
    0x29: "mipi_dsi_dcs_set_display_on_multi",
}


def extract(text, prop):
    m = re.search(re.escape(prop) + r"\s*=\s*\[([0-9a-fA-F\s]+)\]", text)
    if not m:
        raise SystemExit(f"propriedade {prop} (formato byte-array) nao encontrada")
    return bytes(int(b, 16) for b in m.group(1).split())


def decode(blob):
    i = 0
    while i < len(blob):
        dtype, last, vc, ack, wait = blob[i:i + 5]
        dlen = (blob[i + 5] << 8) | blob[i + 6]
        payload = blob[i + 7:i + 7 + dlen]
        if len(payload) != dlen:
            raise SystemExit(f"pacote truncado em offset {i}: len={dlen}")
        yield dtype, wait, payload
        i += 7 + dlen


def emit(prop, blob):
    fn = "on" if "on-command" in prop and "pre-off" not in prop else "off"
    print(f"\t/* {prop} ({len(blob)} bytes) */")
    npkt = 0
    for dtype, wait, payload in decode(blob):
        npkt += 1
        if payload and payload[0] == 0x9E and len(payload) >= 89:
            print("\t/* PPS: regenerado de drm_dsc_config (vendor: pacote 0x9e) */")
            print("\tdrm_dsc_pps_payload_pack(&pps, &ctx->dsc);")
            print("\tmipi_dsi_picture_parameter_set_multi(dsi_ctx, &pps);")
            print("\tmipi_dsi_compression_mode_ext_multi(dsi_ctx, true,")
            print("\t\t\t\t\t    MIPI_DSI_COMPRESSION_DSC, 0);")
        elif dtype in (0x05, 0x04) and payload and payload[0] in DCS_NAMES:
            print(f"\t{DCS_NAMES[payload[0]]}(dsi_ctx);")
        else:
            args = ", ".join(f"0x{b:02x}" for b in payload)
            print(f"\tmipi_dsi_generic_write_seq_multi(dsi_ctx, {args});")
        if wait:
            print(f"\tmipi_dsi_msleep(dsi_ctx, {wait});")
    print(f"\t/* fim de {prop}: {npkt} pacotes (fn sugerida: m7_{fn}) */")
    return npkt


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    text = open(path).read()
    total = 0
    for prop in PROPS:
        total += emit(prop, extract(text, prop))
    print(f"/* total: {total} pacotes */", file=sys.stderr)


if __name__ == "__main__":
    main()
