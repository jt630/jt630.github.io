#!/usr/bin/env python3
"""
test_vin_check.py - offline, stdlib-only unittest coverage for the
check-digit and model-year-code logic in vin_check.py. No network calls -
the NHTSA decode/recall functions aren't covered here, since this dev
sandbox can't reach either NHTSA host (see vin_check.py's module docstring).

Run with:
    python -m unittest discover scripts/tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import vin_check as vc  # noqa: E402


class TestCheckDigit(unittest.TestCase):
    def test_valid_real_vins(self):
        # All 18 VIN'd lots in the 2026-09-28 snapshot pass the check digit
        # per PRICE-DISCOVERY.md's Session V write-up.
        for vin in [
            "1FMZU73W64ZA57062", "1FADP3K24HL333170", "1GCEK19R9WE235032",
            "3B7HF13Z61G230463", "1D7RV1GT7BS695525", "3FADP4FJ7EM174694",
            "1J4GW68N1XC638311", "1FADP3E22FL364569", "1C4NJRBBXED626676",
            "3B7MF33W5VM550364", "1C4BJWDG7DL690849", "1J4FA49S75P329290",
            "4TANL42N8TZ179445", "1B7KF2361XJ531330", "1GCPYFEL3LZ327943",
            "1FTFX1EG2HKD27260",
        ]:
            with self.subTest(vin=vin):
                self.assertTrue(vc.check_digit_valid(vin))

    def test_wrong_length_invalid(self):
        self.assertFalse(vc.check_digit_valid("1FMZU73W64ZA5706"))  # 16 chars
        self.assertFalse(vc.check_digit_valid("1FMZU73W64ZA570622"))  # 18 chars
        self.assertFalse(vc.check_digit_valid(""))
        self.assertFalse(vc.check_digit_valid(None))

    def test_forbidden_letters_invalid(self):
        # I, O, Q are never valid in a real VIN.
        self.assertFalse(vc.check_digit_valid("1FMZU73W64ZAO7062"))
        self.assertFalse(vc.check_digit_valid("1FMZU73W64ZAI7062"))
        self.assertFalse(vc.check_digit_valid("1FMZU73W64ZAQ7062"))

    def test_tampered_check_digit_fails(self):
        # Flip the check digit (position 9, index 8) on a known-good VIN.
        good = "1FMZU73W64ZA57062"
        self.assertTrue(vc.check_digit_valid(good))
        tampered = good[:8] + ("1" if good[8] != "1" else "2") + good[9:]
        self.assertFalse(vc.check_digit_valid(tampered))

    def test_case_insensitive(self):
        self.assertTrue(vc.check_digit_valid("1fmzu73w64za57062"))


class TestMakeAliases(unittest.TestCase):
    def test_ram_matches_dodge(self):
        # vPIC decodes Ram-badged VINs as DODGE (pre-2010 WMI mapping) -
        # confirmed 2026-09-29 against 4 real live listings.
        self.assertTrue(vc._makes_match("DODGE", "Ram"))
        self.assertTrue(vc._makes_match("Dodge", "ram"))

    def test_genuinely_different_makes_do_not_match(self):
        self.assertFalse(vc._makes_match("FORD", "Chevrolet"))

    def test_case_and_whitespace_insensitive(self):
        self.assertTrue(vc._makes_match("  Ford  ", "FORD"))


class TestModelYear(unittest.TestCase):
    def test_resolves_to_nearest_cycle(self):
        # 'T' -> base 1996; a 1996-listed vehicle should resolve to 1996,
        # not 1966 or 2026.
        self.assertEqual(vc.decode_model_year("4TANL42N8TZ179445", 1996), 1996)

    def test_v_code_is_1997(self):
        self.assertEqual(vc.decode_model_year("3B7MF33W5VM550364", 1998), 1997)

    def test_no_listed_year_returns_base_code(self):
        self.assertEqual(vc.decode_model_year("4TANL42N8TZ179445"), 1996)

    def test_short_vin_returns_none(self):
        self.assertIsNone(vc.decode_model_year("SHORT"))


class TestOfflineFlags(unittest.TestCase):
    def test_bad_check_digit_short_circuits(self):
        flags = vc.offline_flags("1FMZU73W64ZA57069", listed_year=2004)  # tampered
        codes = [f["code"] for f in flags]
        self.assertIn("bad_check_digit", codes)
        # No year-mismatch flag should fire once the check digit itself failed.
        self.assertNotIn("year_mismatch", codes)

    def test_documented_tacoma_flags_odometer(self):
        flags = vc.offline_flags("4TANL42N8TZ179445", listed_year=1996, mileage=51)
        self.assertEqual([f["code"] for f in flags], ["odometer_suspect"])

    def test_documented_ram_flags_year_mismatch(self):
        flags = vc.offline_flags("3B7MF33W5VM550364", listed_year=1998)
        self.assertEqual([f["code"] for f in flags], ["year_mismatch"])

    def test_clean_vin_no_flags(self):
        flags = vc.offline_flags("1FMZU73W64ZA57062", listed_year=2004, mileage=183454)
        self.assertEqual(flags, [])

    def test_high_miles_per_year_is_a_note_not_suspect(self):
        # listed_year=2004 matches this VIN's own year code (avoids also
        # tripping year_mismatch); 600k miles over 22 years is well past
        # the 25k/year threshold without being under-1000-miles suspect.
        flags = vc.offline_flags("1FMZU73W64ZA57062", listed_year=2004, mileage=600000)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["code"], "high_miles_per_year")
        self.assertEqual(flags[0]["severity"], "note")

    def test_empty_vin_no_flags(self):
        self.assertEqual(vc.offline_flags(""), [])
        self.assertEqual(vc.offline_flags(None), [])


if __name__ == "__main__":
    unittest.main()
