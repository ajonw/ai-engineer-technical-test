"""Measure runtime and peak memory while profiling a CSV stream.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

# Enable direct invocation: python scripts/profile_memory.py data.csv
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from csv_insights import profile_csv


def peak_rss_mib() -> float | None:
    """Maximum resident set size; platform-specific and process-wide."""
    try:
        import resource
        measured = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # On macOS ru_maxrss is bytes; on Linux it is KiB.
        divisor = 1024 * 1024 if sys.platform == 'darwin' else 1024
        return round(measured / divisor, 3)
    except (ImportError, AttributeError, OSError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('--sample-size', type=int, default=256)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--trace-allocations', action='store_true',
                        help='Also trace Python allocations (slower for large files)')
    args = parser.parse_args()

    if args.trace_allocations:
        tracemalloc.start()
    begin = time.perf_counter()
    try:
        report = profile_csv(args.csv_path, sample_size=args.sample_size)
    finally:
        if args.trace_allocations:
            _, traced_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            traced_peak = None
    elapsed = time.perf_counter() - begin

    report['performance'] = {
        'elapsed_seconds': round(elapsed, 3),
        'peak_process_rss_mib': peak_rss_mib(),
        'peak_tracemalloc_mib': round(traced_peak / (1024 * 1024), 3) if traced_peak is not None else None,
        'measurement_note': (
            'Peak RSS is the OS-recorded process high-water mark on Unix; '
            'it is not an incremental allocation count. '
            'Traced allocations are optional and exclude some native allocations.'
        ),
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + '\n', encoding='utf-8')
        print(f'Wrote {args.output}: {report["rows"]:,} rows in {elapsed:.2f}s; '
              f'peak process RSS {report["performance"]["peak_process_rss_mib"]} MiB')
    else:
        print(rendered)


if __name__ == '__main__':
    main()
