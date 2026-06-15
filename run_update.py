"""
The morning job: fetch results -> re-parse predictions -> score -> build site.

Run locally:        python run_update.py
Run in CI:          (see .github/workflows/update.yml)

Steps are best-effort and ordered so the site is always rebuilt from the
latest available data, even if the live fetch is skipped (no token) or fails.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import build_site  # noqa: E402
import fetch_results  # noqa: E402
import parse_predictions  # noqa: E402
import score  # noqa: E402


def main():
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.environ.setdefault("RUN_TIMESTAMP", stamp)

    print("== 1/4 Parsing participant workbooks ==")
    parse_predictions.main()

    print("\n== 2/4 Fetching live results ==")
    fetch_results.main()

    print("\n== 3/4 Scoring ==")
    score.main()

    print("\n== 4/4 Building site ==")
    build_site.main()

    print("\nDone:", stamp)


if __name__ == "__main__":
    main()
