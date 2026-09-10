"""Unit tests for protocol.py against real frames from the meter.

Pure python: no Home Assistant import, runs under plain unittest or pytest.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "custom_components",
        "accublue_local",
    ),
)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import protocol  # noqa: E402
from fixtures import (  # noqa: E402
    EXPECTED_CHLORINE,
    SET0_HEX,
    SET1_HEX,
    SET2_HEX,
    STATUS_IDLE_HEX,
    STATUS_RUNNING_HEX,
)


def _wells() -> list[list[list[int]]]:
    return [
        protocol.parse_wells(bytes.fromhex(SET0_HEX)),
        protocol.parse_wells(bytes.fromhex(SET1_HEX)),
        protocol.parse_wells(bytes.fromhex(SET2_HEX)),
    ]


class TestCommands(unittest.TestCase):
    """The meter silently ignores commands that are not 12 bytes long."""

    def test_commands_are_zero_padded_to_12_bytes(self) -> None:
        self.assertEqual(protocol.cmd(protocol.CMD_RUN_TEST), bytes.fromhex("020000000000000000000000"))
        self.assertEqual(protocol.cmd(protocol.CMD_FETCH_PENDING), bytes.fromhex("030000000000000000000000"))
        self.assertEqual(protocol.cmd(protocol.CMD_CLEAR_ERROR, 4), bytes.fromhex("040400000000000000000000"))
        self.assertEqual(protocol.cmd(protocol.CMD_CALIBRATE), bytes.fromhex("050000000000000000000000"))

    def test_error_codes_round_trip(self) -> None:
        for code, name in protocol.ERRORS.items():
            self.assertEqual(protocol.ERROR_CODES[name], code)


class TestParseStatus(unittest.TestCase):
    """39 byte status frame from characteristic 1503."""

    def test_idle_frame(self) -> None:
        frame = bytes.fromhex(STATUS_IDLE_HEX)[: protocol.STATUS_LEN]
        self.assertEqual(len(frame), 39)
        status = protocol.parse_status(frame)
        self.assertFalse(status["measuring"])
        self.assertFalse(status["calibrating"])
        self.assertFalse(status["pending_test_data"])
        self.assertIsNone(status["progress"])
        self.assertTrue(status["stopped"])
        self.assertEqual(status["fw"], "2.26")
        self.assertEqual(status["serial"], "36951-0925")
        self.assertEqual(status["error"], "none")
        self.assertEqual(status["last_error"], "none")
        self.assertEqual(status["test_counter"], 6)
        self.assertEqual(status["overflow_bits"], 0)
        self.assertEqual(status["cur_speed"], 0)
        self.assertEqual(status["direction"], "cw")

    def test_running_frame(self) -> None:
        frame = bytes.fromhex(STATUS_RUNNING_HEX)[: protocol.STATUS_LEN]
        status = protocol.parse_status(frame)
        self.assertTrue(status["measuring"])
        self.assertTrue(status["started"])
        self.assertFalse(status["stopped"])
        self.assertEqual(status["progress"], 2)
        self.assertEqual(status["cur_speed"], 2997)
        self.assertEqual(status["cur_tach"], 166)
        self.assertEqual(status["direction"], "ccw")
        self.assertEqual(status["motor_state"], 3)
        self.assertEqual(status["error"], "none")

    def test_trailing_padding_is_ignored(self) -> None:
        full = bytes.fromhex(STATUS_IDLE_HEX)
        self.assertGreater(len(full), protocol.STATUS_LEN)
        self.assertEqual(
            protocol.parse_status(full), protocol.parse_status(full[: protocol.STATUS_LEN])
        )

    def test_unknown_error_byte_passes_through(self) -> None:
        frame = bytearray(bytes.fromhex(STATUS_IDLE_HEX)[: protocol.STATUS_LEN])
        frame[20] = 99
        self.assertEqual(protocol.parse_status(bytes(frame))["error"], 99)


class TestParseWells(unittest.TestCase):
    """88 byte well frames: 4 channels of 11 uint16 LE."""

    def test_shape(self) -> None:
        wells = protocol.parse_wells(bytes.fromhex(SET0_HEX))
        self.assertEqual(len(wells), 4)
        for channel in wells:
            self.assertEqual(len(channel), 11)
            for value in channel:
                self.assertTrue(0 <= value <= 0xFFFF)

    def test_first_and_last_values(self) -> None:
        wells = protocol.parse_wells(bytes.fromhex(SET0_HEX))
        # 0x2540 = 9536 is the first uint16 LE of the set 0 notify
        self.assertEqual(wells[0][0], 9536)
        self.assertEqual(wells[0][10], 24129)
        self.assertEqual(wells[3][10], 23831)

    def test_set2_is_all_zeros_on_disk_203(self) -> None:
        wells = protocol.parse_wells(bytes.fromhex(SET2_HEX))
        self.assertEqual(wells, [[0] * 11 for _ in range(4)])

    def test_only_the_first_88_bytes_are_used(self) -> None:
        full = bytes.fromhex(SET0_HEX)
        self.assertGreater(len(full), protocol.WELLS_LEN)
        self.assertEqual(
            protocol.parse_wells(full), protocol.parse_wells(full[: protocol.WELLS_LEN])
        )


class TestCalculate(unittest.TestCase):
    """Results must match what the reference client produced on the same wells."""

    def test_chlorine_matches_the_real_run(self) -> None:
        self.assertEqual(protocol.calculate(_wells(), "chlorine"), EXPECTED_CHLORINE)

    def test_combined_is_total_minus_free(self) -> None:
        results = protocol.calculate(_wells(), "chlorine")
        self.assertAlmostEqual(
            results["combined_chlorine"],
            round(results["total_chlorine"] - results["free_chlorine"], 2),
            places=2,
        )

    def test_salt_adds_salt_and_keeps_the_shared_factors(self) -> None:
        results = protocol.calculate(_wells(), "salt")
        self.assertIn("salt", results)
        self.assertEqual(results["free_chlorine"], EXPECTED_CHLORINE["free_chlorine"])
        self.assertEqual(results["alkalinity"], EXPECTED_CHLORINE["alkalinity"])
        # the salt disc uses its own pH and hardness curves
        self.assertNotEqual(results["ph"], EXPECTED_CHLORINE["ph"])
        self.assertNotEqual(results["calcium_hardness"], EXPECTED_CHLORINE["calcium_hardness"])
        self.assertLessEqual(results["salt"], 9999.0)

    def test_bromine_replaces_the_chlorine_factors(self) -> None:
        results = protocol.calculate(_wells(), "bromine")
        self.assertIn("bromine", results)
        for key in ("free_chlorine", "total_chlorine", "combined_chlorine", "salt", "cyanuric_acid"):
            self.assertNotIn(key, results)

    def test_every_sanitizer_produces_its_declared_factors(self) -> None:
        for sanitizer in protocol.SANITIZERS:
            results = protocol.calculate(_wells(), sanitizer)
            expected = [protocol.FACTOR[fid] for fid, _ws, _prec in protocol.RESULTS[sanitizer]]
            self.assertEqual(list(results), expected)
            for name in expected:
                self.assertIn(name, protocol.ALL_FACTORS)

    def test_clamps_hold(self) -> None:
        results = protocol.calculate(_wells(), "chlorine")
        self.assertGreaterEqual(results["ph"], 6.3)
        self.assertLessEqual(results["ph"], 8.7)
        self.assertGreaterEqual(results["cyanuric_acid"], 5.0)
        self.assertLessEqual(results["calcium_hardness"], 900.0)
        for value in results.values():
            self.assertGreaterEqual(value, 0.0)

    def test_zero_wells_do_not_raise(self) -> None:
        blank = [[[0] * 11 for _ in range(4)] for _ in range(3)]
        for sanitizer in protocol.SANITIZERS:
            results = protocol.calculate(blank, sanitizer)
            for value in results.values():
                self.assertGreaterEqual(value, 0.0)


class TestWellMap(unittest.TestCase):
    """Disk 203 layout sanity."""

    def test_every_result_factor_has_a_well_and_a_name(self) -> None:
        for sanitizer in protocol.SANITIZERS:
            for fid, well_set, precision in protocol.RESULTS[sanitizer]:
                self.assertIn(fid, protocol.FACTOR)
                self.assertIn(well_set, (0, 1, 2))
                self.assertGreaterEqual(precision, 0)
                if fid != 17:  # combined chlorine is derived, it has no well
                    self.assertIn(fid, protocol.WELL)

    def test_blank_is_well_index_10(self) -> None:
        self.assertEqual(protocol.WELL[0], 10)


if __name__ == "__main__":
    unittest.main()
