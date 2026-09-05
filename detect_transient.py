"""Decide whether a failed GitHub Actions run log looks transient.

Reads failed-job log text on stdin. If it matches a transient/infrastructure
signature (network blips, mirror timeouts, apt races, 5xx, runner infra),
prints the matched fragment and exits 0. Otherwise exits 1 — the failure looks
real and should not be retried automatically.

Patterns come from ``default-patterns.txt`` next to this script, optionally
extended or replaced by ``--patterns-file``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_PATTERNS_FILE = Path(__file__).resolve().parent / "default-patterns.txt"


def load_patterns(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [s for line in lines if (s := line.strip()) and not s.startswith("#")]


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pat in patterns:
        try:
            compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error as exc:  # a typo in one pattern must not break the rest
            print(f"skipping invalid pattern {pat!r}: {exc}", file=sys.stderr)
    return compiled


def find_transient(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for rx in patterns:
        match = rx.search(text)
        if match:
            return match.group(0)
    return None


def resolve_patterns(patterns_file: Path | None, mode: str) -> list[str]:
    patterns: list[str] = []
    if not (patterns_file and mode == "replace"):
        patterns.extend(load_patterns(DEFAULT_PATTERNS_FILE))
    if patterns_file:
        patterns.extend(load_patterns(patterns_file))
    return patterns


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns-file", type=Path, default=None)
    parser.add_argument("--mode", choices=("append", "replace"), default="append")
    args = parser.parse_args(argv)

    patterns = compile_patterns(resolve_patterns(args.patterns_file, args.mode))
    hit = find_transient(sys.stdin.read(), patterns)
    if hit is None:
        return 1
    print(hit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
