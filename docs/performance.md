# Metadata scan measurements

The benchmark is reproducible with `python benchmarks/metadata_scan.py --records N`.
It generates metadata lazily in a fresh process, scans both complete layers, compares
all document identities and retains at most ten detailed findings. No database server,
model API, embeddings or document bodies are involved. These measurements do not
represent PostgreSQL throughput or chunked-index throughput.

## Observed local runs

Measured on October 28, 2026, using CPython 3.12.9 on macOS (Darwin), ARM64, batch size
1,000. Other applications and virtual-machine startup were not controlled. Each row
is one observed run, not a median, a percentile or a guaranteed service level.

| Records in each layer | Elapsed seconds | CPU seconds | Peak process RSS MiB | Main spool MiB | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 100,000 | 11.622 | 8.191 | 72.45 | 171.41 | PASS |
| 1,000,000 | 95.360 | 59.792 | 61.94 | 1,720.97 | PASS |

The million-record run scanned two million physical rows and compared one million
source identities. Both runs retained ten finding details while counting every match.
Peak RSS includes the interpreter, imported libraries, SQLite caches and temporary
Python objects. Differences between fresh processes and allocator behavior can make
a smaller run report a higher peak; these figures do not establish an exact memory curve.

Spool allocation is read from SQLite page count and page size before normal cleanup.
It excludes journals, temporary sort files and filesystem overhead; provision extra
space. The spool was removed after each run. CPU time is measured with `process_time`;
wall time is the checker metric. Values should not be extrapolated to different metadata
sizes, storage, batch sizes, fragmentation or deployment hardware.

## Repeating and extending the measurements

Use a fresh process per size and record the machine, package revision, dependency versions,
background workload and storage type when comparing changes. Repeat runs under controlled
conditions before claiming a performance regression or improvement. Measure PostgreSQL
latency and representative application scopes separately. Include duplicate-heavy and
mismatched inputs when sizing detailed-output limits.

Operational tests cover a bounded main-spool failure, cancellation during staging and
SQLite work, interrupted scans, missing evidence, atomic report failure and cleanup.
Integration tests cover server query timeout and terminating only the test reader's own
backend connection. They verify that failed scans cannot produce a successful audit.
