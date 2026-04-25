from __future__ import annotations

import json
from pathlib import Path


def load_trace_events(trace_jsonl: str | Path) -> list[dict]:
    path = Path(trace_jsonl)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
