import json
from pathlib import Path
import tempfile
import unittest

from scripts.prepare import (
    channel_run_name,
    extract_youtube_id,
    find_existing_youtube_run,
    local_run_name,
    normalize_upload_date,
    parse_captions,
    timestamp,
    youtube_run_name,
)


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

    def test_youtube_run_name_uses_stable_metadata_not_channel_name(self):
        first = {"id": "b_ZVO8_QfJ0", "upload_date": "20261024", "channel": "Original name"}
        renamed = {**first, "channel": "Renamed / invalid: channel"}

        self.assertEqual(youtube_run_name(first), "2026-10-24_b_ZVO8_QfJ0")
        self.assertEqual(youtube_run_name(renamed), youtube_run_name(first))
        self.assertEqual(normalize_upload_date(None), "unknown-date")

    def test_channel_run_name_is_readable_safe_and_stable(self):
        metadata = {
            "channel": "视野/环球:财经",
            "channel_id": "UC_Stable-123",
        }

        self.assertEqual(channel_run_name(metadata), "视野-环球-财经__UC_Stable-123")
        self.assertEqual(
            channel_run_name({**metadata, "channel": "频道已改名"}),
            "频道已改名__UC_Stable-123",
        )

    def test_extract_youtube_id_supports_common_url_shapes(self):
        video_id = "b_ZVO8_QfJ0"
        self.assertEqual(extract_youtube_id(f"https://www.youtube.com/watch?v={video_id}&t=10"), video_id)
        self.assertEqual(extract_youtube_id(f"https://youtu.be/{video_id}?si=test"), video_id)
        self.assertEqual(extract_youtube_id(f"https://www.youtube.com/shorts/{video_id}"), video_id)

    def test_existing_video_id_reuses_legacy_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            legacy = output_root / "20261025T191055Z-f0f5b04a"
            legacy.mkdir()
            (legacy / "metadata.json").write_text(
                json.dumps({"id": "b_ZVO8_QfJ0"}), encoding="utf-8"
            )

            self.assertEqual(find_existing_youtube_run(output_root, "b_ZVO8_QfJ0"), legacy)

    def test_existing_video_id_is_found_inside_channel_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            nested = output_root / "Market Channel__UC123" / "2026-10-24_b_ZVO8_QfJ0"
            nested.mkdir(parents=True)
            (nested / "metadata.json").write_text(
                json.dumps({"id": "b_ZVO8_QfJ0"}), encoding="utf-8"
            )

            self.assertEqual(find_existing_youtube_run(output_root, "b_ZVO8_QfJ0"), nested)

    def test_local_run_name_is_stable_for_the_same_path(self):
        video = Path("videos") / "market update.mp4"
        self.assertEqual(local_run_name(video), local_run_name(video))
        self.assertTrue(local_run_name(video).startswith("local_market-update_"))


if __name__ == "__main__":
    unittest.main()
