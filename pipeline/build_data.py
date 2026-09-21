#!/usr/bin/env python3
"""Build site data JSON (and PNG fallbacks) from research-release CSVs.

Usage:
  python build_data.py                       # all exhibits
  python build_data.py --exhibit portfolio_formation
  python build_data.py --check               # exit 1 if committed JSON would change
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import write_json  # noqa: E402
from sources import DEFAULT_CONFIG, load_sources  # noqa: E402
from exhibits import portfolio_formation  # noqa: E402

WEB = Path(__file__).resolve().parents[1]
EXHIBITS = {"portfolio_formation": portfolio_formation}
VOLATILE_KEYS = {"built_at"}


def _stable(payload: dict) -> str:
    p = json.loads(json.dumps(payload))
    p["meta"] = {k: v for k, v in p.get("meta", {}).items() if k not in VOLATILE_KEYS}
    return json.dumps(p, sort_keys=True, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exhibit", choices=sorted(EXHIBITS), action="append")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--data-dir", type=Path, default=WEB / "site" / "data")
    ap.add_argument("--img-dir", type=Path, default=WEB / "site" / "assets" / "img")
    ap.add_argument("--check", action="store_true", help="do not write; fail if JSON would change")
    a = ap.parse_args(argv)

    sources = load_sources(a.config)
    names = a.exhibit or sorted(EXHIBITS)
    rc = 0
    for name in names:
        mod = EXHIBITS[name]
        payload = mod.build(sources)
        out_json = a.data_dir / f"{name}.json"
        if a.check:
            if not out_json.exists():
                print(f"[check] {out_json} missing", file=sys.stderr)
                rc = 1
                continue
            old = json.loads(out_json.read_text(encoding="utf-8"))
            if _stable(old) != _stable(payload):
                print(f"[check] {out_json} differs from freshly built data", file=sys.stderr)
                rc = 1
            else:
                print(f"[check] {name}: unchanged")
            continue
        write_json(out_json, payload)
        mod.render_png(payload, a.img_dir / f"{name}.png")
        print(f"[build] {name}: {out_json} ({out_json.stat().st_size:,} bytes), {a.img_dir / (name + '.png')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
