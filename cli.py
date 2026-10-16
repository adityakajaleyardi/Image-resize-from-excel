"""Command line entry point.

Running `python cli.py` with no arguments behaves the way the old
`image_processor.py` script did: it reads Config.csv (or Config.xlsx) from the
current folder, processes the source file it names, and writes into the output
folder beside it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.events import LEVEL_FAIL, LEVEL_OK, LEVEL_SKIP, LEVEL_WARNING, Event
from app.processing import ProcessingConfig, ProcessingError, run

_LEVEL_LABELS = {
    LEVEL_OK: " OK ",
    LEVEL_FAIL: "FAIL",
    LEVEL_SKIP: "SKIP",
    LEVEL_WARNING: "WARN",
}

DEFAULT_PROPERTY_MAP = "PropertyHMY.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-processor",
        description="Download, resize and rename property images listed in a CSV export.",
    )
    parser.add_argument("--config", type=Path, help="Config.csv or Config.xlsx to read settings from.")
    parser.add_argument("--source", type=Path, help="Source CSV to process (overrides the config).")
    parser.add_argument(
        "--property-map",
        type=Path,
        help=f"Property code to id mapping CSV (default: {DEFAULT_PROPERTY_MAP} if present).",
    )
    parser.add_argument("--output", type=Path, help="Output folder (overrides the config).")
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Do not wait for ENTER when finished. Use this in scripts.",
    )
    return parser


def print_event(event: Event) -> None:
    label = _LEVEL_LABELS.get(event.level)
    if label is None:
        print(f"[INFO] {event.message}")
    elif event.row is None:
        print(f"[{label}] {event.message}")
    else:
        print(f"[Row {event.row:03} | {label}] {event.message}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    working_dir = Path.cwd()

    if args.config:
        config = ProcessingConfig.from_file(args.config)
        print(f"[INFO] Configuration loaded from {args.config}")
    else:
        config, config_path = ProcessingConfig.discover(working_dir)
        print(
            f"[INFO] Configuration loaded from {config_path.name}"
            if config_path
            else "[INFO] No config file found. Using built in defaults."
        )

    source_path = args.source or working_dir / config.sourcefile
    output_dir = args.output or working_dir / config.outputfolder

    property_map = args.property_map
    if property_map is None:
        candidate = working_dir / DEFAULT_PROPERTY_MAP
        property_map = candidate if candidate.exists() else None

    try:
        summary = run(
            config=config,
            source_path=source_path,
            hmy_path=property_map,
            output_dir=output_dir,
            on_event=print_event,
        )
    except ProcessingError as error:
        print(f"[ERROR] {error}")
        return 1

    print(
        f"\nDone. {summary.succeeded} processed, "
        f"{summary.failed} failed, {summary.skipped} skipped, of {summary.total} rows."
    )
    print(f"Output folder: {summary.output_dir}")

    if not args.no_pause and sys.stdin is not None and sys.stdin.isatty():
        input("\nPress ENTER to close...")

    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
