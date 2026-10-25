import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.install_from_github import extract_archive, find_source_root, forwarded_installer_args


class RemoteInstallerTests(unittest.TestCase):
    def test_uv_argument_separator_is_not_forwarded(self):
        self.assertEqual(forwarded_installer_args(["--", "--force"]), ["--force"])
        self.assertEqual(forwarded_installer_args(["--agent", "claude"]), ["--agent", "claude"])

    def test_extract_and_find_skill_repository(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("repo-main/SKILL.md", "---\nname: test\n---\n")
            archive.writestr("repo-main/scripts/install_skill.py", "print('install')\n")

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            extract_archive(buffer.getvalue(), destination)

            self.assertEqual(find_source_root(destination), destination / "repo-main")

    def test_extract_rejects_parent_directory_traversal(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                extract_archive(buffer.getvalue(), Path(temporary))


if __name__ == "__main__":
    unittest.main()
