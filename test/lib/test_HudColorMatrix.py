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
        self.assertEqual(matrix.shift_primary_color(), "#fe8101")
        self.assertEqual(matrix.shift_secondary_color(), "#69d9da")
        self.assertEqual(matrix.shift_color(*REFERENCE_ORANGE), REFERENCE_ORANGE)

    def test_custom_matrix_shifts_reference_orange(self):
        matrix = HudColorMatrix([
            [1.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 1.0],
        ])

        self.assertEqual(matrix.shift_reference_orange(), "#69ffda")
        self.assertEqual(matrix.shift_primary_color(), "#feff01")
        self.assertEqual(matrix.shift_secondary_color(), "#69ffda")

    def test_red_sky_blue_matrix_shifts_reference_orange(self):
        matrix = HudColorMatrix([
            [0.5, -0.5, -2.0],
            [0.0, 2.0, 2.0],
            [0.0, 0.0, 2.0],
        ])

        self.assertEqual(matrix.shift_reference_orange(), "#34ffff")
        self.assertEqual(matrix.shift_primary_color(), "#7f8300")
        self.assertEqual(matrix.shift_secondary_color(), "#34ffff")

    def test_load_from_appdata_reads_override_file(self):
        with mock.patch("src.lib.HudColorMatrix.parse") as mock_parse:
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
            self.assertEqual(matrix.shift_primary_color(), "#feff01")
            self.assertEqual(matrix.shift_secondary_color(), "#69ffda")


if __name__ == "__main__":
    unittest.main()
