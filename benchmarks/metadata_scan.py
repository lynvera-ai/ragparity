"""Measure a complete synthetic metadata scan in a fresh process; emit JSON to stdout."""

import argparse
import json
import platform
import resource
import sys
from time import process_time

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import CheckPolicy, Record, Status
from lynvera_ragparity.indexes import MemoryIndex
from lynvera_ragparity.sources import MemorySource


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.records < 1:
        parser.error("--records must be positive")

    def records():
        for number in range(args.records):
            yield Record(
                source_id="benchmark",
                document_id=str(number),
                collection="synthetic",
                source_version="1",
                content_hash="sha256:synthetic",
                is_deleted=False,
            )

    cpu_started = process_time()
    report = ConsistencyChecker(CheckPolicy(batch_size=args.batch_size, max_findings=10)).check(
        MemorySource(records()),
        MemoryIndex(records()),
    )
    assert report.status == Status.PASS
    assert report.source_records == report.index_records == report.comparisons == args.records
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    print(
        json.dumps(
            {
                "records_per_layer": args.records,
                "batch_size": args.batch_size,
                "python": platform.python_version(),
                "platform": platform.system(),
                "architecture": platform.machine(),
                "peak_rss_mib": round(rss_bytes / 2**20, 2),
                "cpu_seconds": round(process_time() - cpu_started, 3),
                "elapsed_seconds": round(report.metrics.elapsed_seconds, 3),
                "spool_mib": round(report.metrics.spool_bytes / 2**20, 2),
                "retained_findings": len(report.findings),
                "status": report.status.value,
            }
        )
    )


if __name__ == "__main__":
    main()
