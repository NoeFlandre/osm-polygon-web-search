# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "accelerate>=1.10.0",
#   "torch>=2.7.0",
#   "transformers>=5.0.0",
# ]
# ///

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from osm_polygon_web_search.grid5000_worker import run_worker


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Classify one compressed sentence payload on a GPU"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    count = run_worker(
        args.input,
        args.checkpoint,
        args.output,
        device=args.device,
        batch_size=args.batch_size,
    )
    print(f"classified={count}")


if __name__ == "__main__":  # pragma: no cover
    main()
