#!/usr/bin/env python3
"""
Self-test nhanh: doctor + unit smoke (Phase 9).

  python selftest.py
  python selftest.py --quick   # chi doctor, khong chay tests_phase1
"""
from __future__ import annotations

import argparse, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    import common as K
    import version as V
    K.setup_console()
    ap = argparse.ArgumentParser(description="Skool Downloader self-test")
    ap.add_argument("--quick", action="store_true", help="Chi doctor, bo unit tests")
    a = ap.parse_args()

    print(V.version_string())
    print("=" * 50)

    import doctor as D
    rep = D.run_doctor()
    D.print_report(rep)
    rc = 1 if rep.get("fail") else 0

    if not a.quick:
        print("----- unit smoke (tests_phase1.py) -----")
        p = subprocess.run([sys.executable, str(HERE / "tests_phase1.py")], cwd=str(HERE))
        if p.returncode != 0:
            rc = 1
    else:
        print("(skip unit tests — --quick)")

    print("=" * 50)
    print("SELFTEST", "FAIL" if rc else "OK", f"— {V.__version__}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
