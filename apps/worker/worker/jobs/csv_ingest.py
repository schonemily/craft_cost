from __future__ import annotations
import csv
import io
from typing import Dict, Any

# Minimal CSV ingestion job. Accepts raw bytes of a CSV file and returns counts.
# This is a stub for Week 2 and does not write to the database yet.

def process_csv(data: bytes) -> Dict[str, Any]:
    buf = io.StringIO(data.decode("utf-8", errors="replace"))
    reader = csv.DictReader(buf)
    count = 0
    for _ in reader:
        count += 1
    return {"rows": count}
