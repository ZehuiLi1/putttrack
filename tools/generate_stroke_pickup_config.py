#!/usr/bin/env python3
"""Generate/check versioned shadow configuration; never edit frozen Pickup V0."""

from pathlib import Path
import argparse, hashlib, json

ROOT = Path(__file__).resolve().parents[1]


def render():
    p = json.loads((ROOT / "configs/research/stroke_pickup_shadow_v1.json").read_text())
    sha = hashlib.sha256(
        json.dumps(
            p, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    lines = [
        "/* Generated; use tools/generate_stroke_pickup_config.py. */",
        "#ifndef PT_STROKE_PICKUP_CONFIG_H",
        "#define PT_STROKE_PICKUP_CONFIG_H",
        '#define SPV1_ID "stroke_pickup_shadow_v1"',
        f'#define SPV1_CONFIG_SHA256 "{sha}"',
    ]
    for key, value in p.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            literal = str(value) + "f" if isinstance(value, float) else str(value) + "U"
            lines.append(f"#define SPV1_{key.upper()} {literal}")
    return "\n".join(lines + ["#endif", ""])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    target = ROOT / "firmware/nrf54l15_tag_app/src/stroke_pickup_config.h"
    text = render()
    if args.check:
        if not target.exists() or target.read_text() != text:
            raise SystemExit("stale shadow configuration header")
    else:
        target.write_text(text)


if __name__ == "__main__":
    main()
