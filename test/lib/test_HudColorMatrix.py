import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.lib.HudColorMatrix import HudColorMatrix, REFERENCE_ORANGE


class TestHudColorMatrix(unittest.TestCase):
    def test_identity_matrix_preserves_reference_orange(self):
        matrix = HudColorMatrix.identity()

        self.assertEqual(matrix.shift_reference_orange(), "#69d9da")
        self.assertEqual(matrix.shift_primary_color(), "#ff7500")
        self.assertEqual(matrix.shift_secondary_color(), "#69d9da")
        self.assertEqual(matrix.shift_color(*REFERENCE_ORANGE), REFERENCE_ORANGE)

    def test_custom_matrix_shifts_reference_orange(self):
        matrix = HudColorMatrix([
            [1.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 1.0],
        ])

        self.assertEqual(matrix.shift_reference_orange(), "#69ffda")
        self.assertEqual(matrix.shift_primary_color(), "#ffff00")
        self.assertEqual(matrix.shift_secondary_color(), "#69ffda")

    def test_red_sky_blue_matrix_shifts_reference_orange(self):
        matrix = HudColorMatrix([
            [0.5, -0.5, -2.0],
            [0.0, 2.0, 2.0],
            [0.0, 0.0, 2.0],
        ])

        self.assertEqual(matrix.shift_reference_orange(), "#34ffff")
        self.assertEqual(matrix.shift_primary_color(), "#806a00")
        self.assertEqual(matrix.shift_secondary_color(), "#34ffff")

    def test_load_from_appdata_reads_override_file(self):
        with (
            mock.patch("src.lib.HudColorMatrix.EDHM") as mock_edhm,
            mock.patch("src.lib.HudColorMatrix.parse") as mock_parse,
        ):
            mock_edhm.from_system.return_value.load_color_matrix.return_value = None
            mock_root = mock.MagicMock()

            def find_tag(path):
                values = {
                    ".//MatrixRed": " 1, 0, 0 ",
                    ".//MatrixGreen": " 0, 5, 0 ",
                    ".//MatrixBlue": " 0, 0, 1 ",
                }
                element = mock.MagicMock()
                element.text = values[path]
                return element

            mock_root.find.side_effect = find_tag
            mock_parse.return_value.getroot.return_value = mock_root

            with mock.patch("os.path.isfile", return_value=True):
                matrix = HudColorMatrix.load_from_appdata("C:/Elite Dangerous")

            self.assertEqual(matrix.matrix, [[1.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 1.0]])
            self.assertEqual(matrix.shift_reference_orange(), "#69ffda")
            self.assertEqual(matrix.shift_primary_color(), "#ffff00")
            self.assertEqual(matrix.shift_secondary_color(), "#69ffda")

    def test_load_from_appdata_prefers_edhm_matrix(self):
        edhm_matrix = [
            [0.04, -0.12, 1.0],
            [0.0, 1.0, 0.2],
            [0.5, 0.05, -0.02],
        ]

        with (
            mock.patch("src.lib.HudColorMatrix.EDHM") as mock_edhm,
            mock.patch("src.lib.HudColorMatrix.parse") as mock_parse,
        ):
            mock_edhm.from_system.return_value.load_color_matrix.return_value = edhm_matrix

            matrix = HudColorMatrix.load_from_appdata("C:/Elite Dangerous")

        self.assertEqual(matrix.matrix, edhm_matrix)
        self.assertEqual(matrix.shift_primary_color(), "#0a56ff")
        self.assertEqual(matrix.shift_reference_orange(), "#69d9da")
        self.assertEqual(matrix.shift_secondary_color(), "#69d9da")
        mock_parse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
