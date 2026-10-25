from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts.install_skill import PAYLOAD, SKILL_NAME, default_skills_dir, install


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class InstallSkillTests(unittest.TestCase):
    def test_install_copies_only_runtime_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_dir = Path(temporary_directory) / "skills with spaces"

            target, backup = install(REPOSITORY_ROOT, skills_dir, force=False, dry_run=False)

            self.assertEqual(target, skills_dir / SKILL_NAME)
            self.assertIsNone(backup)
            for relative_path in PAYLOAD:
                self.assertTrue((target / relative_path).exists(), relative_path)
            self.assertFalse((target / "README.md").exists())
            self.assertFalse((target / "scripts" / "install_skill.py").exists())
            self.assertFalse((target / "scripts" / "install.ps1").exists())

    def test_agent_defaults_are_platform_independent(self):
        home = Path(os.path.abspath("test-home"))
        with patch("scripts.install_skill.Path.home", return_value=home):
            with patch.dict("scripts.install_skill.os.environ", {}, clear=True):
                self.assertEqual(default_skills_dir("codex"), home / ".codex" / "skills")
            self.assertEqual(default_skills_dir("claude"), home / ".claude" / "skills")
            self.assertEqual(default_skills_dir("agents"), home / ".agents" / "skills")

    def test_codex_home_environment_variable_takes_precedence(self):
        codex_home = Path(os.path.abspath("custom-codex-home"))
        with patch.dict(
            "scripts.install_skill.os.environ",
            {"CODEX_HOME": str(codex_home)},
            clear=True,
        ):
            self.assertEqual(default_skills_dir("codex"), codex_home / "skills")

    def test_existing_install_requires_force_and_force_keeps_backup(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_dir = Path(temporary_directory) / "skills"
            target, _ = install(REPOSITORY_ROOT, skills_dir, force=False, dry_run=False)
            marker = target / "local-note.txt"
            marker.write_text("keep me", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                install(REPOSITORY_ROOT, skills_dir, force=False, dry_run=False)

            replaced_target, backup = install(
                REPOSITORY_ROOT, skills_dir, force=True, dry_run=False
            )
            self.assertEqual(replaced_target, target)
            self.assertIsNotNone(backup)
            self.assertEqual((backup / "local-note.txt").read_text(encoding="utf-8"), "keep me")
            self.assertFalse((target / "local-note.txt").exists())

    def test_dry_run_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_dir = Path(temporary_directory) / "missing" / "skills"

            target, backup = install(REPOSITORY_ROOT, skills_dir, force=False, dry_run=True)

            self.assertEqual(target, skills_dir / SKILL_NAME)
            self.assertIsNone(backup)
            self.assertFalse(skills_dir.exists())


if __name__ == "__main__":
    unittest.main()
