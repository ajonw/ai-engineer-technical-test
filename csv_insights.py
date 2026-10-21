"""Streaming CSV profiler: bounded-memory descriptive statistics.

Usage: python csv_insights.py customer-100000.csv --output report.json
       python csv_insights.py customers-2000000.csv --sample-size 256
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path


class ColumnStats:
    def __init__(self, sample_size: int, seed: int = 42):
        self.nonempty = 0
        self.missing = 0
        self.numeric_count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum = None
        self.maximum = None
        self.samples: list[str] = []
        self.sample_size = sample_size
        self.rng = random.Random(seed)

    def observe(self, original: str | None):
        value = (original or '').strip()
        if not value:
            self.missing += 1
            return
        self.nonempty += 1
        if len(self.samples) < self.sample_size:
            self.samples.append(value)
        elif self.sample_size:
            j = self.rng.randrange(self.nonempty)
            if j < self.sample_size:
                self.samples[j] = value
        try:
            number = float(value)
            if not math.isfinite(number):
                return
        except ValueError:
            return
        self.numeric_count += 1
        difference = number - self.mean
        self.mean += difference / self.numeric_count
        self.m2 += difference * (number - self.mean)
        self.minimum = number if self.minimum is None else min(self.minimum, number)
        self.maximum = number if self.maximum is None else max(self.maximum, number)

    def report(self):
        frequently_seen = Counter(self.samples).most_common(5)
        numeric_fraction = self.numeric_count / self.nonempty if self.nonempty else 0
        result = {
            'nonempty': self.nonempty,
            'missing': self.missing,
            'missing_rate': round(self.missing / (self.nonempty + self.missing), 4) if self.nonempty + self.missing else 0,
            'numeric_fraction': round(numeric_fraction, 4),
            'sample_distinct_values': len(set(self.samples)),
            'frequent_values_in_random_sample': frequently_seen,
        }
        if self.numeric_count and numeric_fraction >= 0.95:
            result['numeric_stats'] = {
                'min': self.minimum, 'max': self.maximum,
                'mean': round(self.mean, 4),
                'population_stddev': round(math.sqrt(self.m2 / self.numeric_count), 4),
            }
        return result


def profile_csv(path: str | Path, sample_size: int = 256) -> dict:
    if sample_size < 0 or sample_size > 10000:
        raise ValueError('sample_size must be between 0 and 10000')
    path = Path(path)
    with path.open('r', encoding='utf-8-sig', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV must have a header row')
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Duplicate CSV column names are not supported')
        stats = {name: ColumnStats(sample_size, seed=42 + idx) for idx, name in enumerate(reader.fieldnames)}
        rows = 0
        malformed = 0
        for row in reader:
            rows += 1
            if None in row:  # surplus fields beyond header
                malformed += 1
            for name, stat in stats.items():
                stat.observe(row.get(name))
    columns = {key: value.report() for key, value in stats.items()}
    insights = [f'{rows:,} data rows across {len(columns)} columns.']
    if malformed:
        insights.append(f'{malformed:,} rows have more fields than the header.')
    for name, result in columns.items():
        if result['missing_rate'] >= 0.1:
            insights.append(f'{name}: {result["missing_rate"]:.1%} missing values.')
        if 'numeric_stats' in result:
            ns = result['numeric_stats']
            insights.append(f'{name}: mean={ns["mean"]}, min={ns["min"]}, max={ns["max"]}.')
        elif 0 < result['sample_distinct_values'] <= 10 and result['frequent_values_in_random_sample']:
            insights.append(f'{name}: frequent sample values={result["frequent_values_in_random_sample"][:3]}.')
    return {
        'file': path.name,
        'rows': rows,
        'columns': columns,
        'insights': insights,
        'note': 'Frequent values and distinct counts are based on a bounded random sample, not exact full-file counts.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('--sample-size', type=int, default=256)
    parser.add_argument('--output', help='Write full report to a JSON file')
    args = parser.parse_args()
    result = profile_csv(args.csv_path, args.sample_size)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + '\n', encoding='utf-8')
        print(f'Saved {args.output}: {result["rows"]:,} rows, {len(result["columns"])} columns')
    else:
        print(rendered)


if __name__ == '__main__':
    main()
