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

    def test_tracker_rebuild_is_sorted_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runs = root / "runs"
            older = runs / "Market Channel__UC123" / "older"
            newer = runs / "Market Channel__UC123" / "newer"
            older.mkdir(parents=True)
            newer.mkdir(parents=True)
            (older / "analysis.json").write_text(
                json.dumps(sample_analysis("2026-10-20", "AAPL")), encoding="utf-8"
            )
            (newer / "analysis.json").write_text(
                json.dumps(sample_analysis("2026-10-24", "NVDA")), encoding="utf-8"
            )
            render_summary_file(older)
            render_summary_file(newer)
            output = root / "stock-tracker.md"

            discovered = discover_run_directories([], runs)
            update_tracker(discovered, output)
            first = output.read_text(encoding="utf-8")
            update_tracker(discovered, output)
            second = output.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertLess(first.index("2026-10-24"), first.index("2026-10-20"))
            self.assertEqual(first.count("NVDA"), 1)
            self.assertNotIn("分析日期", first)
            self.assertNotIn("下跌／風險", first)


if __name__ == "__main__":
    unittest.main()
