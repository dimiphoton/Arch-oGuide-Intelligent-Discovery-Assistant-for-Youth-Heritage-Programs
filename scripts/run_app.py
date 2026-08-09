#!/usr/bin/env python3
"""Lance l'interface Streamlit ArchéoGuide."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = ROOT / "app" / "Home.py"


def main() -> int:
    if not HOME.exists():
        print(f"Fichier introuvable : {HOME}")
        return 1
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(HOME), *sys.argv[1:]],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
