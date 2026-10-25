import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.render_summary import AnalysisError, render_summary_document, render_summary_file
from scripts.update_stock_tracker import discover_run_directories, update_tracker


def sample_analysis(date="2026-10-24", ticker="NVDA"):
    return {
        "schema_version": 2,
        "video": {
            "date": date,
            "youtuber": "Market Channel",
            "title": "Weekly market update",
            "url": "https://www.youtube.com/watch?v=abc123",
        },
        "current_events": [
            {"topic": "FOMC | CPI", "summary": "Rates may move valuations."}
        ],
        "market": {
            "stance": "mixed",
            "summary": "Momentum is positive, but risks remain.",
            "outlook": "Expect volatility.",
        },
        "stocks": [
            {
                "ticker": ticker,
                "company": "NVIDIA" if ticker == "NVDA" else "Apple",
                "stance": "bullish",
                "action": "watch",
                "key_levels": "180 強支撐，跌破偏空",
                "outlook": "Constructive above support.",
            }
        ],
        "note": "ASR may mishear proper nouns.",
    }


class ReportingTests(unittest.TestCase):
    def test_summary_uses_concise_fixed_sections(self):
        document = render_summary_document(sample_analysis())

        self.assertIn("## 基本資料", document)
        self.assertIn("## 時事", document)
        self.assertIn("## 整體股市", document)
        self.assertIn("## 個股分析", document)
        self.assertIn("FOMC \\| CPI", document)
        self.assertIn("180 強支撐，跌破偏空", document)
        self.assertNotIn("時間戳", document)
        self.assertNotIn("上漲／看多原因", document)

    def test_invalid_or_duplicate_stock_data_fails_loudly(self):
        invalid = sample_analysis()
        invalid["stocks"][0]["action"] = "strong-buy"
        with self.assertRaises(AnalysisError):
            render_summary_document(invalid)

        duplicate = sample_analysis()
        duplicate["stocks"].append(copy.deepcopy(duplicate["stocks"][0]))
        with self.assertRaises(AnalysisError):
            render_summary_document(duplicate)

        invalid_date = sample_analysis()
        invalid_date["video"]["date"] = "20261024"
        with self.assertRaises(AnalysisError):
            render_summary_document(invalid_date)

    def test_tracker_rebuild_is_sorted_by_ticker_youtuber_and_date(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runs = root / "runs"
            older = runs / "Market Channel__UC123" / "older"
            newer = runs / "Market Channel__UC123" / "newer"
            second_channel = runs / "Alpha Channel__UC456" / "aapl"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            second_channel.mkdir(parents=True)
            (older / "analysis.json").write_text(
                json.dumps(sample_analysis("2026-10-20", "AAPL")), encoding="utf-8"
            )
            (newer / "analysis.json").write_text(
                json.dumps(sample_analysis("2026-10-24", "NVDA")), encoding="utf-8"
            )
            second_channel_analysis = sample_analysis("2026-10-22", "AAPL")
            second_channel_analysis["video"]["youtuber"] = "Alpha Channel"
            (second_channel / "analysis.json").write_text(
                json.dumps(second_channel_analysis), encoding="utf-8"
            )
            render_summary_file(older)
            render_summary_file(newer)
            render_summary_file(second_channel)
            output = root / "stock-tracker.md"

            discovered = discover_run_directories([], runs)
            update_tracker(discovered, output)
            first = output.read_text(encoding="utf-8")
            update_tracker(discovered, output)
            second = output.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertLess(first.index("Alpha Channel"), first.index("Market Channel"))
            self.assertLess(first.index("2026-10-20"), first.index("2026-10-24"))
            self.assertLess(first.index("AAPL"), first.index("NVDA"))
            self.assertEqual(first.count("NVDA"), 1)
            self.assertNotIn("分析日期", first)
            self.assertNotIn("下跌／風險", first)

    def test_tracker_uses_newest_date_within_same_ticker_and_youtuber(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runs = root / "runs"
            for name, date in (("older", "2026-10-20"), ("newer", "2026-10-24")):
                run = runs / "Market Channel__UC123" / name
                run.mkdir(parents=True)
                (run / "analysis.json").write_text(
                    json.dumps(sample_analysis(date, "AAPL")), encoding="utf-8"
                )

            output = root / "stock-tracker.md"
            update_tracker(discover_run_directories([], runs), output)
            tracker = output.read_text(encoding="utf-8")

            self.assertLess(tracker.index("2026-10-24"), tracker.index("2026-10-20"))


if __name__ == "__main__":
    unittest.main()
