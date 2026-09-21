import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"^Elpis\d+\.\d+\.\d+$")


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def _tags(path: str, key: str) -> set[str]:
    return {
        x["release_tag"]
        for x in json.loads(
            (ROOT / path).read_text(encoding="utf-8")
        )[key]
    }


def test_every_noncurrent_tag_is_disposed():
    assert (
        _git("rev-parse", "--is-shallow-repository") == "false"
    ), "SHALLOW_HISTORY_CANNOT_ESTABLISH_TAG_DISPOSITION"

    tags = {
        t for t in _git("tag", "--list", "Elpis*").split()
        if TAG.fullmatch(t)
    }

    disposed = (
        _tags("FAILED_RELEASES.json", "failed_releases")
        | _tags("PUBLISHED_RELEASES.json", "published_releases")
        | _tags("PUBLICATION_ASSERTIONS.json", "publication_assertions")
    )

    current = "Elpis" + (
        ROOT / "VERSION"
    ).read_text(encoding="utf-8").strip()

    assert sorted(tags - disposed - {current}) == [], (
        "UNDISPOSED_RELEASE_TAG"
    )
