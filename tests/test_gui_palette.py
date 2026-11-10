import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QColor

# Headless Qt Application for testing widgets
app = QApplication.instance()
if app is None:
    app = QApplication([sys.argv[0], "-platform", "offscreen"])

import gui

class TestGuiPaletteAndReadability(unittest.TestCase):
    def test_color_text_dim_validity(self):
        """Verify COLOR_TEXT_DIM parses into a valid QColor and does not fall back to black."""
        color = QColor(gui.COLOR_TEXT_DIM)
        self.assertTrue(color.isValid(), "COLOR_TEXT_DIM must be a valid QColor")
        self.assertNotEqual(color.name(), "#000000", "COLOR_TEXT_DIM must not parse as black #000000")
        
        # Verify luminance/brightness is high enough for dark background readability
        # Relative luminance calculation or simple RGB sum check
        r, g, b, _ = color.getRgb()
        self.assertGreater(g + b, 300, "COLOR_TEXT_DIM must have sufficient brightness for contrast")

    def test_color_sec_validity_and_contrast(self):
        """Verify COLOR_SEC parses into a valid bright secondary QColor."""
        color = QColor(gui.COLOR_SEC)
        self.assertTrue(color.isValid(), "COLOR_SEC must be a valid QColor")
        self.assertNotEqual(color.name(), "#000000", "COLOR_SEC must not parse as black")
        
        # Should be distinct and readable
        r, g, b, _ = color.getRgb()
        self.assertGreater(g + b, 250, "COLOR_SEC must have sufficient brightness for contrast")

    def test_palette_constants(self):
        """Verify all primary color constants parse properly."""
        for const_name in ["COLOR_ACCENT", "COLOR_IDLE", "COLOR_LISTEN", "COLOR_PROCESS", "COLOR_SPEAK", "COLOR_WARN", "COLOR_TEXT"]:
            val = getattr(gui, const_name)
            color = QColor(val)
            self.assertTrue(color.isValid(), f"{const_name} ({val}) must be a valid QColor")
            self.assertNotEqual(color.name(), "#000000", f"{const_name} must not be black")

    def test_datastream_row_instantiation(self):
        """Verify DataStreamRow widget initializes and sets data without error."""
        row = gui.DataStreamRow("NET_DOWN")
        self.assertEqual(row.key, "NET_DOWN")
        row.set_data("↓ 12.5 KB/s", is_active=True)
        self.assertEqual(row.val_text, "↓ 12.5 KB/s")

    def test_segmented_gauge_instantiation(self):
        """Verify SegmentedGauge widget initializes and bounds value."""
        gauge = gui.SegmentedGauge("CPU_LOAD", "Consolas")
        gauge.set_value(75.5)
        self.assertEqual(gauge.target_value, 75.5)
        gauge.set_value(150.0)
        self.assertEqual(gauge.target_value, 100.0)
        gauge.set_value(-20.0)
        self.assertEqual(gauge.target_value, 0.0)

if __name__ == "__main__":
    unittest.main()
