# Customer CSV Results

Both datasets were analysed with `scripts/profile_memory.py` using memory-efficient CSV streaming.

| Metric | 100K customers | 2M customers |
| --- | ---: | ---: |
| Rows | 100,000 | 2,000,000 |
| Columns | 12 | 12 |
| Missing values | 0 | 0 |
| Processing time | 1.711 s | 30.959 s |
| Peak process memory (RSS) | 17.531 MiB | 18.938 MiB |
| Distinct countries in 256-row sample | 158 | 163 |

## Key findings

- Both datasets have the same 12 columns and no missing values.
- Processing 20× more rows took longer, while peak memory increased by only 1.407 MiB, consistent with streaming rather than loading the full CSV into memory.

## Reproduce

```bash
python scripts/profile_memory.py customers-100000.csv --output reports/customers_100k.json
python scripts/profile_memory.py customers-2000000.csv --output reports/customers_2m.json
```

*Performance figures are from one run per file. Peak RSS includes Python runtime memory.*