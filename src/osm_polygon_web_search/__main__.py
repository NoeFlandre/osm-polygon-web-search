import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .data_root import data_root
from .pipeline import DEFAULT_KEYWORDS, DEFAULT_PBF, DEFAULT_RESULT_COUNT, run_poc


def main(argv: Sequence[str] | None = None) -> None:
    if not argv:
        print(data_root())
        return

    parser = argparse.ArgumentParser(description="Run the OSM polygon web-search POC")
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    parser.add_argument("--keyword", action="append", dest="keywords")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=data_root() / "runs" / "poc",
    )
    parser.add_argument("--results", type=int, default=DEFAULT_RESULT_COUNT)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--all-variants", action="store_true")
    args = parser.parse_args(list(argv))
    if args.plan_only and args.search:
        parser.error("--plan-only and --search are mutually exclusive")

    output_path = run_poc(
        args.pbf,
        output_dir=args.output_dir,
        keywords=args.keywords or DEFAULT_KEYWORDS,
        search=args.search,
        result_count=args.results,
        all_variants=args.all_variants,
    )
    print(output_path)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
