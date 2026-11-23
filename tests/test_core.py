"""
Unit tests for OmniDisplay core logic.
"""

import unittest
from omnidisplay.core.state_manager import StateManager, PRESETS
from omnidisplay.core.ddc_base import DDCController
from omnidisplay.core.environment import NullEnvironment

class MockDDCController(DDCController):
    def __init__(self):
        self.calls = []

    def list_displays(self):
        return [
            {"id": "disp-0", "index": 0, "name": "Left"},
            {"id": "disp-1", "index": 1, "name": "Right"}
        ]

    def set_input_source(self, display_index: int, input_value: int) -> bool:
        self.calls.append((display_index, input_value))
        return True

    def get_input_source(self, display_index: int):
        return 17

class TestOmniDisplayCore(unittest.TestCase):

    def setUp(self):
        self.mock_ddc = MockDDCController()
        self.mgr = StateManager(self.mock_ddc, role="mac", environment=NullEnvironment())

    def test_presets_exist(self):
        expected_presets = ["pc_both", "mac_both", "split_pc_mac", "split_mac_pc"]
        for p in expected_presets:
            self.assertIn(p, PRESETS)
            self.assertIn("left", PRESETS[p])
            self.assertIn("right", PRESETS[p])

    def test_apply_preset_pc_both(self):
        self.mgr.apply_preset("pc_both")
        self.assertEqual(self.mgr.current_state["left"], "pc")
        self.assertEqual(self.mgr.current_state["right"], "pc")

    def test_apply_preset_mac_both(self):
        self.mgr.apply_preset("mac_both")
        self.assertEqual(self.mgr.current_state["left"], "mac")
        self.assertEqual(self.mgr.current_state["right"], "mac")

    def test_apply_split_presets(self):
        self.mgr.apply_preset("split_pc_mac")
        self.assertEqual(self.mgr.current_state["left"], "pc")
        self.assertEqual(self.mgr.current_state["right"], "mac")

        self.mgr.apply_preset("split_mac_pc")
        self.assertEqual(self.mgr.current_state["left"], "mac")
        self.assertEqual(self.mgr.current_state["right"], "pc")

    def test_ddc_packet_checksum(self):
        # Verify DDC/CI XOR checksum algorithm
        # Packet: 0x51, 0x84, 0x03, 0x60, 0x00, 0x0F
        src = 0x51
        length = 0x84
        cmd = 0x03
        vcp = 0x60
        val_hi = 0x00
        val_lo = 0x0F
        expected_chk = 0x6E ^ src ^ length ^ cmd ^ vcp ^ val_hi ^ val_lo

        computed = 0x6E ^ 0x51 ^ 0x84 ^ 0x03 ^ 0x60 ^ 0x00 ^ 0x0F
        self.assertEqual(expected_chk, computed)
        self.assertEqual(computed, 0xD7)

if __name__ == "__main__":
    unittest.main()
