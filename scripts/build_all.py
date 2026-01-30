#!/usr/bin/env python3
"""Automated pipeline: download -> extract DOF -> build dataset."""

from __future__ import annotations

import subprocess
import sys


STEPS = [
    [sys.executable, "scripts/download_data.py", "--skip-acs"],
    [sys.executable, "scripts/extract_dof_state.py"],
    [sys.executable, "scripts/build_dataset.py"],
]


def main() -> int:
    for cmd in STEPS:
        print("Running:", " ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
