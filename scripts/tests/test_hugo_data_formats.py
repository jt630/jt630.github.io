"""Guard: every file under data/ must be a format Hugo can load.

Hugo parses everything in data/ at build time and fails the WHOLE site
build on a format it doesn't know. This already happened once: the first
close-price harvest wrote data/price_history/*.jsonl and broke every
deploy (run #329) until it moved to research/. The auction-monitor
workflow runs this suite before its bot commits to main, so a bad data
file is caught before it can take the site down.
"""

import os
import unittest

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
HUGO_DATA_FORMATS = {".yaml", ".yml", ".json", ".toml", ".csv", ".xml"}


class HugoDataFormatTests(unittest.TestCase):
    def test_every_data_file_is_hugo_loadable(self):
        bad = []
        for root, _dirs, files in os.walk(DATA_DIR):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in HUGO_DATA_FORMATS:
                    bad.append(os.path.relpath(os.path.join(root, name), DATA_DIR))
        self.assertEqual(
            bad, [],
            f"Hugo can't load these data/ files, move them outside data/ "
            f"(e.g. research/): {bad}",
        )


if __name__ == "__main__":
    unittest.main()
