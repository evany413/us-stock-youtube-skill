from pathlib import Path
import tempfile
import unittest

from scripts.cleanup_runs import apply_cleanup, build_cleanup_plan, discover_completed_runs


class CleanupRunsTests(unittest.TestCase):
    def _completed_run(self, root: Path) -> Path:
        run = root / "runs" / "Channel__UC123" / "2026-10-25_abc123"
        frames = run / "frames"
        frames.mkdir(parents=True)
        (run / "analysis.json").write_text("{}", encoding="utf-8")
        (run / "summary.md").write_text("summary", encoding="utf-8")
        (run / "manifest.json").write_text("{}", encoding="utf-8")
        (run / "transcript.md").write_text("transcript", encoding="utf-8")
        (run / "transcript.json").write_text("[]", encoding="utf-8")
        (run / "video.mkv").write_bytes(b"video")
        (run / "audio.wav").write_bytes(b"audio")
        (run / "frames.json").write_text("[]", encoding="utf-8")
        (frames / "000000.jpg").write_bytes(b"frame")
        (run / "video.zh-Hant.json3").write_text("caption", encoding="utf-8")
        return run

    def test_plan_selects_only_large_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            run = self._completed_run(Path(temporary_directory))

            plan = build_cleanup_plan(run)

            self.assertEqual(
                {path.name for path in plan.targets},
                {"audio.wav", "frames", "frames.json", "video.mkv"},
            )
            self.assertGreater(plan.size_bytes, 0)
            self.assertTrue((run / "video.mkv").exists())

    def test_apply_removes_artifacts_and_preserves_analysis_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            run = self._completed_run(Path(temporary_directory))

            apply_cleanup(build_cleanup_plan(run))

            for name in ("video.mkv", "audio.wav", "frames", "frames.json"):
                self.assertFalse((run / name).exists())
            for name in (
                "analysis.json",
                "summary.md",
                "manifest.json",
                "transcript.md",
                "transcript.json",
                "video.zh-Hant.json3",
            ):
                self.assertTrue((run / name).exists())

    def test_discovery_skips_unfinished_runs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            completed = self._completed_run(root)
            unfinished = root / "runs" / "Channel__UC123" / "unfinished"
            unfinished.mkdir()
            (unfinished / "analysis.json").write_text("{}", encoding="utf-8")

            discovered = discover_completed_runs([], root / "runs")

            self.assertEqual(discovered, [completed.resolve()])


if __name__ == "__main__":
    unittest.main()
