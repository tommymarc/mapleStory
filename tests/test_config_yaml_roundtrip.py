import os
import tempfile
import unittest

from src.utils.common import (
    convert_tuples_to_lists,
    load_yaml,
    save_yaml,
)


class ConfigYamlRoundtripTests(unittest.TestCase):
    def test_nested_tuples_are_converted_before_saving(self):
        converted = convert_tuples_to_lists(
            {"template_scales": ((0.95, 0.9), (1.0, 1.0))}
        )
        self.assertEqual(
            converted,
            {"template_scales": [[0.95, 0.9], [1.0, 1.0]]},
        )

    def test_nametag_scales_roundtrip_without_python_tags(self):
        config = {
            "nametag": {
                "enable": True,
                "name": "风吹雀雀很凉",
                "template_scales": ((0.95, 0.9), (0.95, 0.95), (1.0, 1.0)),
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, ".config_tmp.yaml")
            save_yaml(config, path)
            with open(path, encoding="utf-8") as handle:
                raw = handle.read()
            loaded = load_yaml(path)

        self.assertNotIn("!!python/tuple", raw)
        self.assertIn("风吹雀雀很凉", raw)
        self.assertEqual(
            loaded["nametag"]["template_scales"],
            ((0.95, 0.9), (0.95, 0.95), (1.0, 1.0)),
        )

    def test_legacy_python_tuple_tags_can_still_be_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "legacy.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "nametag:\n"
                    "  template_scales:\n"
                    "  - !!python/tuple\n"
                    "    - 0.95\n"
                    "    - 0.9\n"
                    "  - !!python/tuple\n"
                    "    - 1.0\n"
                    "    - 1.0\n"
                )
            loaded = load_yaml(path)

        self.assertEqual(
            loaded["nametag"]["template_scales"],
            ((0.95, 0.9), (1.0, 1.0)),
        )


if __name__ == "__main__":
    unittest.main()
