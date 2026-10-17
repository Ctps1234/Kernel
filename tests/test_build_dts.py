import tempfile
import unittest
from pathlib import Path

from tools import build_dts


class BuildDtsTests(unittest.TestCase):
    def test_find_sources_keeps_overlays_as_dtbo_targets(self):
        overlays = (
            "topaz-khaje-idp-nopmi-overlay.dtso",
            "tapas-khaje-idp-nopmi-overlay.dtso",
            "topaz-sm5602-khaje-idp-nopmi-overlay.dtso",
            "tapas-sm5602-khaje-idp-nopmi-overlay.dtso",
        )
        with tempfile.TemporaryDirectory() as kernel_tree:
            root = Path(kernel_tree) / build_dts.DTS_SUBDIR
            root.mkdir(parents=True)
            (root / "khaje-idp-nopmi.dts").touch()
            for name in overlays:
                (root / name).touch()

            targets = build_dts.find_sources(kernel_tree)

        outputs = {name for name, _source, _is_base in targets}
        self.assertIn("khaje-idp-nopmi.dtb", outputs)
        for name in overlays:
            self.assertIn(name[:-len(".dtso")] + ".dtbo", outputs)
        self.assertNotIn("khaje-idp-nopmi-topaz.dtb", outputs)
        self.assertNotIn("khaje-idp-nopmi-tapas.dtb", outputs)


if __name__ == "__main__":
    unittest.main()
