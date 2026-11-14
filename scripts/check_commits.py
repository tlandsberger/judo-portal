"""Prüft, ob Commit-Nachrichten den Conventional Commits folgen (Grundlage für Version und Changelog).

Aufruf: python scripts/check_commits.py <von>..<bis>
"""

import re
import subprocess
import sys

PATTERN = re.compile(r"^(feat|fix|perf|refactor|style|docs|test|ci|build|chore|revert)(\([\w./-]+\))?!?: \S.*")


def main(revision_range: str) -> int:
    subjects = subprocess.run(
        ["git", "log", "--no-merges", "--format=%h %s", revision_range],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    invalid = [line for line in subjects if not PATTERN.match(line.split(" ", 1)[1])]
    for line in invalid:
        print(f"::error::Commit folgt nicht den Conventional Commits: {line}")
    if invalid:
        print("Format: <typ>(<bereich>)?: <beschreibung>, z. B. 'feat: Mitglieder importieren' oder 'fix(login): …'")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
