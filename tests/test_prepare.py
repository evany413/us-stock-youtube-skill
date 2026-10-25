import unittest

from scripts.prepare import parse_captions, timestamp


class PrepareTests(unittest.TestCase):
    def test_timestamp_formats_whole_seconds(self):
        self.assertEqual(timestamp(3723.9), "01:02:03")

    def test_parse_captions_merges_identical_overlapping_text(self):
        data = {
            "events": [
                {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "NVDA"}]},
                {"tStartMs": 1500, "dDurationMs": 2000, "segs": [{"utf8": "NVDA"}]},
                {"tStartMs": 4000, "dDurationMs": 1000, "segs": [{"utf8": "risk"}]},
            ]
        }

        self.assertEqual(
            parse_captions(data),
            [
                {"start": 0.0, "end": 3.5, "text": "NVDA"},
                {"start": 4.0, "end": 5.0, "text": "risk"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
