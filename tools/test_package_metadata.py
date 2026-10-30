"""Keep MCC package metadata byte-identical except for the version string."""
import unittest
import zipfile
from build_ksp_patch import metadata_version, PATCH_BUILD
from build_names_patch import KSPF, ROOT


class PackageMetadata(unittest.TestCase):
    def test_checked_single_replacement_preserves_stock_bytes(self):
        with zipfile.ZipFile(KSPF) as z:
            stock = z.read("info.json")
        with zipfile.ZipFile(ROOT / f"firmware/patched/KSCON_2.5.99_build{PATCH_BUILD}.kspf") as z:
            result = z.read("info.json")
        self.assertEqual(result, metadata_version(stock))
        self.assertEqual(result.replace(b'"version_number": "2.5.99"',
                                        b'"version_number": "2.5.20"'), stock)
        for invalid in (b"{}", stock + stock):
            with self.assertRaises(ValueError):
                metadata_version(invalid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
