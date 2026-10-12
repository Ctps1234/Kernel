# Referências de Device Tree topaz/Khaje

Os arquivos `.dts`/`.dtso` nesta pasta são decompilações de FDT para análise, geradas pelo utilitário standard-library `tools/decompile_fdt.py`:

- `khaje-base-reference.dts`: DTB base Khaje, índice 1 do `vendor_boot_b.img`.
- `topaz-overlay-51-reference.dtso`: overlay topaz, entrada 51 do `dtbo_b.img`.
- `topaz-live-reference.dts`: FDT v17 ativo de `/sys/firmware/fdt`, já mesclado em runtime.

Propriedades voláteis de `/chosen` e campos com nomes comuns de identidade foram filtrados. Os três resultados foram varridos por padrões comuns de MAC/IMEI/número de série/calibração, sem correspondências. A filtragem por nomes conhecidos não garante, por si só, que todo dado de dispositivo tenha sido removido.

Para regenerar base e overlay dos blobs privados:

```sh
python3 tools/extract_android_dt.py \
  google_drive/vendor_boot_b.img google_drive/dtbo_b.img \
  --msm-id 0x206 --board-id 0x30022 --out-dir /tmp/topaz-dt
python3 tools/decompile_fdt.py /tmp/topaz-dt/base-dtb-1.dtb \
  --output device-tree/reference/khaje-base-reference.dts
python3 tools/decompile_fdt.py /tmp/topaz-dt/overlay-entry-51.dtbo \
  --plugin --output device-tree/reference/topaz-overlay-51-reference.dtso
python3 tools/decompile_fdt.py google_drive/topaz-live.dtb \
  --output device-tree/reference/topaz-live-reference.dts
```

**Estes arquivos são só material de referência. Não são DTS upstream revisados, não foram validados com `dtc`/`dtbs_check` e não devem ser usados para boot.** Ainda contêm nós/properties vendor, phandles numéricos e, no overlay, fragments/fixups originais. Antes da integração, separar SoC/placa, validar recursos e reservas, revisar bindings e converter os nós suportados para APIs 6.12. O FDT/DTBO binário de entrada continua privado e ignorado pelo Git.
