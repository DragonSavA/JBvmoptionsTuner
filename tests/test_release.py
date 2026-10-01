from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_release import build_release


@unittest.skipUnless(shutil.which("git"), "Requires Git")
class ReleaseArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.root / "unused-hooks"))
        (self.project / ".gitignore").write_text(".env\n.venv/\nconfig.json\n", encoding="utf-8")
        (self.project / "pyproject.toml").write_text(
            '[project]\nversion = "1.0.0"\n', encoding="utf-8"
        )
        (self.project / "main.py").write_text(
            "print('committed application')\n", encoding="utf-8", newline="\n"
        )
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Initial fixture")
        self.commit = self.git("rev-parse", "HEAD")

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=self.project, check=True, capture_output=True, encoding="utf-8"
        ).stdout.strip()

    def test_archive_uses_committed_version_and_excludes_local_files(self) -> None:
        (self.project / "main.py").write_text("uncommitted draft", encoding="utf-8")
        (self.project / "pyproject.toml").write_text(
            '[project]\nversion = "9.9.9"\n', encoding="utf-8"
        )
        (self.project / ".env").write_text("local test value", encoding="utf-8")
        (self.project / "config.json").write_text("{}", encoding="utf-8")
        (self.project / "untracked.txt").write_text("untracked test file", encoding="utf-8")
        metadata = build_release(self.project, self.root / "dist")
        self.assertEqual(metadata["version"], "1.0.0")
        self.assertEqual(metadata["commit"], self.commit)
        self.assertEqual(metadata["tag"], f"v1.0.0-{self.commit[:12]}")
        archive = Path(metadata["archive"])
        with zipfile.ZipFile(archive) as stream:
            files = {name for name in stream.namelist() if not name.endswith("/")}
            self.assertEqual(
                files,
                {
                    "JBvmotionsTuner-1.0.0/.gitignore",
                    "JBvmotionsTuner-1.0.0/pyproject.toml",
                    "JBvmotionsTuner-1.0.0/main.py",
                },
            )
            self.assertEqual(
                stream.read("JBvmotionsTuner-1.0.0/main.py"), b"print('committed application')\n"
            )
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(
            Path(metadata["checksum"]).read_text(encoding="utf-8"), f"{digest}  {archive.name}\n"
        )
        self.assertEqual(
            json.loads((self.root / "dist" / "release.json").read_text(encoding="utf-8")), metadata
        )
        build_release(self.project, self.root / "dist")
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)

    def test_explicit_revision_remains_bound_to_the_tested_commit(self) -> None:
        (self.project / "pyproject.toml").write_text(
            '[project]\nversion = "1.1.0"\n', encoding="utf-8"
        )
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Later fixture")
        metadata = build_release(self.project, self.root / "dist", self.commit)
        self.assertEqual(metadata["version"], "1.0.0")
        self.assertEqual(metadata["commit"], self.commit)

    def test_invalid_version_cannot_escape_output_directory(self) -> None:
        (self.project / "pyproject.toml").write_text(
            '[project]\nversion = "../invalid"\n', encoding="utf-8"
        )
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Invalid fixture version")
        with self.assertRaises(ValueError):
            build_release(self.project, self.root / "dist")
        self.assertFalse((self.root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
