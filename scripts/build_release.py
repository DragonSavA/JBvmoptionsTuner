"""Build a source ZIP from one committed Git snapshot, never from local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path


def git_output(project_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=project_root, check=True, capture_output=True, encoding="utf-8"
    ).stdout.strip()


def build_release(project_root: Path, output_dir: Path, revision: str = "HEAD") -> dict[str, str]:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    commit = git_output(project_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    project = tomllib.loads(git_output(project_root, "show", f"{commit}:pyproject.toml"))
    version = project["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", version):
        raise ValueError("The project version cannot be used in an archive name.")
    short_commit = commit[:12]
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"JBvmotionsTuner-{version}-{short_commit}.zip"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--prefix=JBvmotionsTuner-{version}/",
            f"--output={archive}",
            commit,
        ],
        cwd=project_root,
        check=True,
    )
    checksum = archive.with_suffix(".zip.sha256")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    metadata = {
        "version": version,
        "commit": commit,
        "tag": f"v{version}-{short_commit}",
        "archive": str(archive),
        "checksum": str(checksum),
    }
    (output_dir / "release.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--revision", default="HEAD")
    arguments = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    metadata = build_release(project_root, arguments.output_dir, arguments.revision)
    print(f"Built {metadata['archive']} from {metadata['commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
