#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from putttrack.venue import BallAsset, VenueApplication, build_server, load_course


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the PuttTrack one-hole local demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    course = load_course(ROOT / "configs/course/demo_one_hole.json")
    colors = ["Blue", "Orange", "Purple", "Green", "Red", "Yellow", "Pink", "White"]
    balls = [
        BallAsset(
            ball_id=f"ball-{index:02d}",
            label=f"{color} {index:02d}",
            color=color.lower(),
            number=f"{index:02d}",
        )
        for index, color in enumerate(colors, start=1)
    ]
    app = VenueApplication(course, balls, run_root=ROOT / "runs/venue_demo")
    server = build_server(app, args.host, args.port)
    print(
        f"PuttTrack demo check-in: http://{args.host}:{server.server_address[1]}/checkin"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
